# CPU pinning, steal time, and the live migration that became the workaround

**Symptom:** guests with dedicated CPUs report steal time, which pinning is supposed to make impossible; live-migrating an affected instance makes it disappear, until it returns · **Decision:** stop the migrations, accept a bounded amount of steal, investigate the host instead of relocating the symptom · **Layers:** Nova (flavor, resource tracker, Placement), libvirt/QEMU (`cputune`, emulator thread), host kernel (isolation) · **Commands:** `virsh vcpupin`, `virsh emulatorpin`, `ps -eLo psr` (READ ONLY), `openstack server migrate --live-migration` (POTENTIALLY DISRUPTIVE), `systemctl restart nova-compute` (STATE CHANGING, conditional)

> Composite of real situations from production OpenStack platforms, generalised. No platform, organisation or person is identifiable. The book's *From the field* passage (chapter 15) does not name the final root cause; this page describes the investigation and the usual explanations without inventing a conclusion the record does not contain.

## 1. Context

A production platform with a set of compute hosts dedicated to latency-sensitive workloads: flavors with `hw:cpu_policy=dedicated`, hosts with `[compute] cpu_dedicated_set` configured, PCPU inventory in Placement, huge pages. The workload owners monitor steal time inside their guests because their contract with the platform is "a core is yours".

The symptom appeared weeks after a batch of hosts had been added and a host tuning profile had been "aligned" across the fleet.

## 2. Timeline

| Time | Event | Source |
| --- | --- | --- |
| day 0 | owners report steal time (`st` in `top`, a few percent, in bursts) on three pinned instances on the same host | guest monitoring |
| day 0 | on-call live-migrates one instance to another host; steal disappears; the two others follow | change record |
| day 3 | steal on the same instances, on their new host | guest monitoring |
| day 3–14 | migrations repeated; eleven in two weeks; two cause brief latency spikes the owners notice more than the steal | change records, owners |
| day 14 | decision: no more migrations; bounded steal accepted with the owners; investigation opened on the hosts | platform lead, owners |
| day 15 | on the host: `vcpupin` matches Nova's view; `emulatorpin` covers the instance's own pinned CPUs; host threads observed running on "dedicated" CPUs; the tuning profile does not isolate the dedicated set | host investigation |
| day 16 | one host corrected (isolation profile, emulator thread policy on the flavor), one instance moved onto it, mapping verified, steal gone for a week | verification |
| day 23 | fleet-wide correction host by host; no further migrations as a response | change records |

## 3. Symptoms

Steal time in a guest means the hypervisor did not schedule the vCPU when the guest wanted to run. On a shared-CPU host it is ordinary contention. On a pinned instance each guest vCPU owns one host CPU from `cpu_dedicated_set`, accounted in Placement as `PCPU`, and no other instance's vCPU is placed on it. So steal on a pinned instance means something that is not an instance vCPU is running on that core.

The misleading part was that the fix worked. A live migration that relieves a symptom is not evidence about its cause; it is evidence that the destination host did not have the problem yet. Every migration carried its own risk for the workload (a memory copy, a brief pause, a new NUMA placement), and by the second week the workaround was being applied more often than the symptom was being understood.

## 4. Investigation

### What Nova believes — [`openstack server show`](../series/one-command-one-investigation/01-openstack-server-show.md), `flavor show`, Placement — READ ONLY

```text
openstack server show <server> -c flavor -c OS-EXT-SRV-ATTR:host -c OS-EXT-SRV-ATTR:instance_name    # API 2.47: extra_specs inline
openstack flavor show <flavor> -c properties                     # hw:cpu_policy=dedicated, hw:emulator_threads_policy, hw:mem_page_size
openstack resource provider inventory list <rp-uuid>             # PCPU and VCPU inventories on the host
openstack resource provider usage show <rp-uuid>                 # PCPU used
```

`hw:cpu_policy=dedicated`, no `hw:emulator_threads_policy`, PCPU inventory equal to the size of `cpu_dedicated_set`, usage consistent with the instances on the host. Nova's accounting was right. Nova's accounting is also the limit of what Nova knows: it pins the guest's vCPUs, nothing else.

### What libvirt did — `virsh vcpupin`, `virsh emulatorpin`, `virsh dumpxml` — READ ONLY

```text
virsh vcpupin <instance-name>                 # vCPU → host CPU, as applied
virsh emulatorpin <instance-name>             # where the QEMU emulator thread may run
virsh dumpxml <instance-name> | sed -n '/<cputune>/,/<\/cputune>/p'
```

`vcpupin` matched Nova's view exactly: four vCPUs on four host CPUs from the dedicated set, no overlap with any other domain on the host (checked for every domain). `emulatorpin` showed the emulator thread allowed on the same four CPUs. That is the default: without `hw:emulator_threads_policy`, the emulator thread runs on the instance's own pinned CPUs. Every disk or network I/O the guest does is handled by that thread, on a core the guest believes is its own.

### What the host runs on those CPUs — `ps`, `/proc`, the tuning profile — READ ONLY

```text
ps -eLo psr,pid,tid,comm --sort psr | awk '$1>=8 && $1<=11'    # every thread last seen on the dedicated CPUs 8–11
cat /proc/cmdline                                              # isolcpus=, nohz_full=, rcu_nocbs= — or nothing
tuned-adm active ; cat /etc/tuned/<profile>/tuned.conf          # on Red Hat-family hosts
cat /sys/kernel/mm/ksm/run                                     # 1 = memory deduplication scanning is on
cat /proc/interrupts | awk '{print $1, $10, $11, $12, $13}' | head    # interrupts landing on the dedicated CPUs
```

Kernel worker threads, a monitoring agent, the KSM scanner and a share of the network interrupts were all landing on CPUs 8–11. The command line had no isolation options; the "aligned" tuning profile had replaced a per-host one that had them. Nova cannot see any of this: whether the host keeps its own threads off the dedicated set is arranged on the host, by kernel options or a tuning profile, and the resource tracker reports the CPUs as dedicated whether or not that isolation exists.

### Two usual explanations, both present

The Nova documentation's two facts explain most steal on pinned instances, ahead of overlapping pinning or a Nova/host mismatch: the host's own threads and interrupts are not kept off the dedicated CPUs unless the host is configured for it, and the emulator thread shares the instance's pinned CPUs unless `hw:emulator_threads_policy` moves it (`isolate`: a dedicated extra host CPU per instance; `share`: the `cpu_shared_set` pool). Neither cause lives in the instance; moving the instance only changes which host reproduces the symptom next.

### Where the mapping could have drifted — READ ONLY, then a decision

On hosts that had been through the earlier migrations, one more check: Nova's view of the pinned CPUs in use against the domains actually running. The resource tracker rebuilds the host's NUMA topology usage from the instances on it at startup and on its periodic run; a mismatch between what libvirt pins and what Nova believes shows as PCPU usage that does not match the sum of the running domains' `vcpupin`. On two hosts the numbers differed after the two weeks of moves.

## 5. Cause, in three layers

- **Immediate cause:** host threads, interrupts and the KSM scanner sharing the dedicated CPUs with the guests' vCPUs, plus the QEMU emulator thread on the same CPUs; bursts of guest I/O and host activity produced the steal.
- **Contributing cause:** a fleet-wide tuning profile change that removed the CPU isolation the dedicated hosts had relied on, done as a configuration clean-up with no link to the pinning design; and flavors created without `hw:emulator_threads_policy`, which had been acceptable while the isolation hid the emulator thread's cost.
- **Why it lasted two weeks:** the workaround worked every time, so nobody looked at the host. The migrations were done by whoever was on call, each one reasonable, and no one saw the count until it was written down.

## 6. Decision

**What was done.** On day 14: stop the migrations. Accept, with the owners, a bounded amount of steal on the affected instances for the days the investigation would take, with a threshold that would reopen the discussion. Investigate the host, not the instance.

Then, remediation as a sequence, not a move:

```text
# per host, once its isolation is corrected and verified
openstack compute service set --disable --disable-reason "pinning remediation <change-id>" <host> nova-compute   # STATE CHANGING
openstack server migrate --live-migration --host <corrected-host> --wait <server>                               # POTENTIALLY DISRUPTIVE, one instance
virsh vcpupin <instance-name> ; virsh emulatorpin <instance-name>      # READ ONLY, on the destination: mapping as expected
# guest: steal watched for 24 h before the next instance
```

Empty the host of affected instances this way; correct the host itself (isolation profile with the dedicated set excluded from the host's schedulable CPUs, KSM off on these hosts, interrupt affinity); set `hw:emulator_threads_policy` on the flavors, which applies to new and resized instances (an existing instance keeps its XML until it is moved or rebuilt).

And, on the two hosts whose PCPU usage no longer matched their domains: a restart of `nova-compute` (STATE CHANGING; running instances are unaffected, the host is briefly `down` for the scheduler), so that the resource tracker rebuilds the host's NUMA topology and pinned-CPU usage from the instances actually on it. That step is not a rule for pinning problems. It applied because the drift had been observed; it proves nothing until the mapping and the steal are checked again afterwards.

**Rejected: keep migrating.** It worked, every time, for three days. A workaround is safe only while the risk it introduces stays smaller than the risk it removes, and repetition is the signal that this is no longer true: eleven migrations, two latency incidents, no understanding.

**Rejected: restore the old tuning profile fleet-wide, immediately.** Right in substance, wrong as a first move: it would have changed every dedicated host at once, on a fleet where nobody yet knew whether the profile was the only cause. One host first, one instance on it, a week of evidence.

**Rejected: set `hw:emulator_threads_policy=isolate` on the flavors and resize everything.** Correct for the emulator thread; it costs one extra dedicated host CPU per instance, which the capacity did not have, and it would not have touched the host threads. `share` with a `cpu_shared_set` was the choice, host by host.

## 7. Blast radius and rollback

- **Stop the migrations:** no change; steal accepted at a stated threshold; owners informed. Reversible: a migration remains available if the threshold is crossed.
- **Host correction:** one host at a time, emptied first. The profile change is reversible (the previous profile kept); KSM can be re-enabled; interrupt affinity is a file. Verified on one host for a week before the second.
- **`nova-compute` restart:** the host is unavailable to the scheduler for seconds; instances keep running. Not "reversible", but repeatable, and it was the last step, not the first.
- **Stop condition:** steal reappearing on the corrected host with a verified mapping would have meant a cause not yet found, and the sequence would have stopped there.

## 8. Follow-ups

| Follow-up | Owner | Closed when |
| --- | --- | --- |
| The dedicated hosts' isolation (kernel options or tuning profile, KSM, interrupt affinity) under configuration management, with a check that fails when the dedicated set is not isolated | platform team | check running on every dedicated host |
| `hw:emulator_threads_policy` set on every dedicated flavor; existing instances moved onto it over time | platform team, owners | no dedicated instance without the policy |
| A per-host report of `vcpupin` against Nova's PCPU usage, run weekly | platform team | report exists; the two drifted hosts show no drift |
| Workaround register: any action repeated more than twice on the same symptom is recorded with its count and reviewed | operations lead | register in use |
| Steal time on pinned instances alerted platform-side, not only in the guests | monitoring owner | alert tested |

## 9. What you can reproduce

```text
openstack flavor list --long | grep cpu_policy                 # READ ONLY: which flavors are dedicated, and do they set an emulator thread policy?
virsh emulatorpin <instance-name>                              # READ ONLY, on a dedicated host: does the emulator thread share the guest's CPUs?
ps -eLo psr,comm --sort psr | awk '$1>=<first-dedicated-cpu>'  # READ ONLY: what else runs on your dedicated set right now?
cat /proc/cmdline                                              # READ ONLY: is the isolation you assume actually there?
```

And one question for the change process: when a tuning profile is "aligned across the fleet", who checks it against the hosts that had a reason to differ?

## 10. Sources

- Nova, *CPU topologies* (`hw:cpu_policy=dedicated` and PCPU; `cpu_dedicated_set` and `cpu_shared_set`; `hw:emulator_threads_policy` and the default placement of the emulator thread on the instance's CPUs; live migration of NUMA instances supported from Train): https://docs.openstack.org/nova/latest/admin/cpu-topologies.html
- Nova, configuration reference, `[compute] cpu_dedicated_set`, `cpu_shared_set`: https://docs.openstack.org/nova/latest/configuration/config.html
- libvirt, `virsh vcpupin`, `emulatorpin`, `dumpxml`; domain XML `<cputune>`: https://www.libvirt.org/manpages/virsh.html and https://www.libvirt.org/formatdomain.html#cpu-tuning
- Linux kernel, `isolcpus`, `nohz_full`, `rcu_nocbs` (kernel parameters): https://www.kernel.org/doc/html/latest/admin-guide/kernel-parameters.html
- Linux kernel, KSM (`/sys/kernel/mm/ksm/run`): https://www.kernel.org/doc/html/latest/admin-guide/mm/ksm.html
- python-openstackclient, `server migrate --live-migration --host`, `compute service set`, `flavor show`: https://docs.openstack.org/python-openstackclient/latest/cli/command-objects/server.html
- osc-placement, `resource provider inventory list`, `usage show`: https://docs.openstack.org/osc-placement/latest/cli/index.html
- Related episodes: [#01 `openstack server show`](../series/one-command-one-investigation/01-openstack-server-show.md), [#03 `openstack hypervisor show`](../series/one-command-one-investigation/03-openstack-hypervisor-show.md), [#05 `virsh dumpxml`](../series/one-command-one-investigation/05-virsh-dumpxml-qemu-log.md), [#19 the compute node as a machine](../series/one-command-one-investigation/19-compute-host-as-a-machine.md)
- Guide page: [Compute](../troubleshooting/compute.md#4-cpu-pinning)
- The book, *OpenStack, the Day After Tomorrow*, chapter 15 (when the workaround becomes the risk; pinned CPUs and live migration) and chapter 9 (a symptom is not a diagnosis): https://github.com/soufian-zaouam/openstack-the-day-after-tomorrow

---

*Part of the [incident case studies](README.md) of the [OpenStack Production Guide](../README.md). The reasoning behind the decision is developed in [OpenStack, the Day After Tomorrow](https://github.com/soufian-zaouam/openstack-the-day-after-tomorrow).*
