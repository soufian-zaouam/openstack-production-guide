# Evacuation and fencing on shared storage

**Symptom:** a compute host stops reporting; its instances are unreachable; the tools to rebuild them elsewhere are ready · **Decision:** prove the host is off before `openstack server evacuate` · **Layers:** Nova, Ceph RBD, QEMU · **Commands:** `openstack compute service list` (READ ONLY), `rbd status` (READ ONLY), `ipmitool chassis power` (STATE CHANGING), `openstack server evacuate` (POTENTIALLY DISRUPTIVE)

> Composite of real situations from production OpenStack platforms, generalised. No platform, organisation or person is identifiable; names, counts and timestamps are illustrative.

## 1. Context

A production platform with Ceph as the storage backend for instance disks: boot volumes on RBD, no local instance storage that matters. Compute hosts have an out-of-band management interface (BMC), reachable from the operations network and not from the platform's own management network. There is no automatic fencing: nothing powers a host off when it stops reporting, and no host-evacuation automation is in place.

That combination is common, and it is the whole case. Shared storage is what makes evacuation possible: the rebuilt instance opens the same RBD images and boots from them. It is also what makes evacuation dangerous when the original host is not dead.

## 2. Timeline

| Time | Event | Source |
| --- | --- | --- |
| 02:12 | monitoring: compute host `cmp-17` unreachable on the management network; its instances stop answering | alerting |
| 02:13 | `nova-compute` on `cmp-17` reported `down` | `openstack compute service list` |
| 02:15 | on-call proposes evacuating the host: "the service is down, evacuate is allowed" | channel |
| 02:16 | decision: no evacuation until the host's real state is known | on-call lead |
| 02:19 | BMC reachable; power state `on`; system event log shows no power event | `ipmitool` |
| 02:21 | `rbd status` on two of the host's images: one watcher each, from `cmp-17`'s storage address | Ceph |
| 02:24 | host powered off through the BMC; power state `off` confirmed | `ipmitool` |
| 02:26 | `rbd status` on the same images: no watchers | Ceph |
| 02:27 | evacuation of the host's 11 instances, one at a time, to hosts chosen by the scheduler | `openstack server evacuate` |
| 02:41 | last instance `ACTIVE`, reached from inside its network; owners informed | verification |
| 09:30 | host examined: management NIC firmware fault; the host had been running its instances the whole time | RCA |

## 3. Symptoms

From the control plane, the picture was clean and complete: one host down, its instances unreachable, every other service up. The Nova API would accept an evacuation as soon as the compute service was reported down, which happened within `service_down_time` (60 s by default) of the last heartbeat.

The first hypothesis in the room was "the host is dead". The evidence for it was the absence of a heartbeat. The absence of a heartbeat is also what a host looks like when it is alive and cut off from the control plane.

## 4. Investigation

### What Nova knows — [`openstack compute service list`](../series/one-command-one-investigation/02-openstack-compute-service-list.md) — READ ONLY

```text
openstack compute service list --service nova-compute --host cmp-17 --long
```

`State down`, `Status enabled`, `forced_down False`, `Updated At` two minutes old. That is everything Nova can say. The heartbeat travels from `nova-compute` to `nova-conductor` over the message bus and into the database; a host whose management NIC has failed, whose RabbitMQ connection has dropped, or whose `nova-compute` process has hung all look identical here. Nova's evacuation documentation says it in one sentence: the procedure "should not be used if the instance is still up and running". Nova cannot check that condition for you. The operator can even force the state (`openstack compute service set --down`, microversion 2.11), which is the reason `forced_down` exists and the reason it proves nothing about the hardware.

### What the hypervisor knows — nothing reachable

`ssh cmp-17` timed out on the management address. The storage network is separate; a host can be alive on it and dead on management. There was no serial console on this platform; the BMC is the only independent path.

### What the BMC knows — `ipmitool` — READ ONLY at this step

```text
ipmitool -I lanplus -H <bmc-address> -U <user> -E chassis power status
ipmitool -I lanplus -H <bmc-address> -U <user> -E sel list | tail -20
```

`Chassis Power is on`. The system event log had no power, thermal or watchdog event in the last hours. A powered-on host with an empty event log is, until proven otherwise, a host running its instances.

### What Ceph knows — [`rbd status`](../series/one-command-one-investigation/13-os-brick-block-devices.md) — READ ONLY

```text
rbd status vms/<instance-uuid>_disk
rbd status volumes/volume-<uuid>
```

Each image listed one watcher, from the address `cmp-17` uses on the storage network. A watcher is a client with the image open; a QEMU process is such a client. The host was not only powered on: it had the images open.

This check is a strong signal, not a proof in either direction. A watcher can persist for a short time after a client disappears, until its watch times out on the OSD side, and a client that has crashed hard leaves no watcher even though the host is powered on. It is the combination that decides: power state from the BMC, watchers from Ceph, and the absence of any event that would explain a crash.

### Why nothing in the stack refuses a double start

Nova checks that the compute service is reported down, and nothing else. Ceph does not arbitrate either: the RBD `exclusive-lock` feature is cooperative. Its documentation states that it "does not prevent two or more concurrently running clients from opening the same RBD image and writing to it in turns"; the lock is handed from one client to the other on request, and a client is blocklisted only when it stops responding to the cluster. Two QEMU processes for the same instance, on two hosts that can both reach the cluster, will both write. Two guest kernels, two page caches, two journals, one block device: the filesystem does not survive it, and the damage is silent until something reads what the other side wrote.

## 5. Cause, in three layers

- **Immediate cause of the outage:** the host's management NIC failed (firmware fault, confirmed the next morning). The host lost the control plane and the tenant traffic that transits the same interface, and kept running every instance.
- **Contributing cause:** no fencing mechanism existed, manual or automatic, so a lost heartbeat and a dead host were indistinguishable from the control plane, and the evacuation procedure did not contain the step that distinguishes them.
- **Why it could have reached production:** the runbook for host failure started at `openstack server evacuate`. It had been written from the Nova documentation's command examples, which describe the mechanics of evacuation, not the precondition. Nobody had rehearsed the case where the host is alive.

## 6. Decision

**What was done.** No evacuation on the strength of the missing heartbeat. The host's real state was established through the BMC, then confirmed through Ceph; the host was powered off through the BMC (STATE CHANGING: it stops every instance on the host, which were already unreachable to their users); the absence of watchers was confirmed; only then were the instances evacuated, one at a time, checking each one before the next:

```text
# STATE CHANGING — stops the host and every instance on it
ipmitool -I lanplus -H <bmc-address> -U <user> -E chassis power off
ipmitool -I lanplus -H <bmc-address> -U <user> -E chassis power status      # READ ONLY: confirm "off"

# READ ONLY — no client must still hold the images
rbd status vms/<instance-uuid>_disk

# POTENTIALLY DISRUPTIVE — rebuilds the instance elsewhere; requires the compute service to be down
openstack server evacuate --wait <server>
openstack server show <server> -c status -c OS-EXT-SRV-ATTR:host -c OS-EXT-STS:power_state
```

`openstack server evacuate` takes an optional `--host`; it was left to the scheduler, so that Placement and the filters chose a destination with capacity rather than a human under pressure. From compute API 2.14 the shared-storage detection is automatic and `--shared-storage` is not needed.

**Rejected: evacuate immediately.** Fastest path to "instances back". Its failure mode was a corrupted filesystem discovered hours later, on workloads whose owners had just been told they were safe, with a restore from backup as the only way out. Unbounded, invisible, and the kind of damage no rollback undoes.

**Rejected: wait for the host to come back.** It might have; the NIC fault was intermittent at first. But the instances were down for their users either way, and waiting had no bound. The cost of fencing was minutes of an outage already under way and the loss of a chance the host would recover on its own. That cost was bounded and visible.

**Rejected: `compute service set --down` to "speed things up".** Not relevant here because the service was already reported down, but it was said aloud in the channel and deserves an answer: forcing the state changes what Nova believes, not what the host does, and makes the evacuation acceptable to the API without making it safe.

## 7. Blast radius and rollback

Written before the power-off:

- **Power-off:** affects the 11 instances on `cmp-17`, all already unreachable. No effect on any other host, on Ceph, or on the control plane. Reversible: the host can be powered on again through the BMC, and would rejoin the platform with its instances if the fault had cleared; it must not be powered on again after the evacuation starts, because the evacuated instances' records now point elsewhere and the original domains would start against the same images. The host stayed off and disabled (`openstack compute service set --disable --disable-reason "fenced <ticket>"`) until it was examined.
- **Evacuation:** one instance at a time; each rebuild claims capacity on a destination and rewrites the instance's host in Nova. Not reversible as such: an evacuated instance is a new domain on a new host. The way back is the same operation in the other direction, which is why the original host must stay fenced.
- **Stop condition:** any evacuated instance that failed to boot, or any watcher reappearing on an image, stops the sequence.

## 8. Follow-ups

| Follow-up | Owner | Closed when |
| --- | --- | --- |
| Fencing written into the host-failure runbook as a precondition: power state from the BMC, watchers on Ceph, power-off confirmed, then evacuation | platform team lead | the runbook is tested by an engineer who did not write it |
| BMC reachability and credentials checked from the operations network, for every host, as a scheduled check | operations | the check exists and alerts on failure |
| Any future automation that evacuates on a lost heartbeat must fence first, or not exist; evaluated with that requirement, not after | architecture | decision recorded |
| Management NIC firmware audited across the fleet | operations | audit complete, affected hosts updated in a maintenance window |
| Instance owners' assumption corrected: "unreachable" was never "lost"; a status note explains what fencing protects | service owner | communication sent |

## 9. What you can reproduce

On your own platform, read-only, in a quiet moment:

```text
openstack compute service list --service nova-compute --long          # is forced_down ever True? who set it, and why?
rbd status <pool>/<image>                                              # do you know which address each host uses on the storage network?
ipmitool -I lanplus -H <bmc-address> -U <user> -E chassis power status  # can you reach every BMC from where you would be during an incident?
```

And one question for the runbook: between "the compute service is down" and "`openstack server evacuate`", what step proves the host is off?

## 10. Sources

- Nova, *Evacuate instances* (the procedure "should not be used if the instance is still up and running"; `--on-shared-storage` no longer needed from API 2.14): https://docs.openstack.org/nova/latest/admin/evacuate.html
- python-openstackclient, `server evacuate [--wait] [--host <host>] [--password <password> | --shared-storage] <server>`: https://docs.openstack.org/python-openstackclient/latest/cli/command-objects/server.html
- python-openstackclient, `compute service set [--enable | --disable] [--disable-reason <reason>] [--up | --down] <host> <service>` (`--down` requires API 2.11): https://docs.openstack.org/python-openstackclient/latest/cli/command-objects/compute-service.html
- Nova, compute service heartbeat and `service_down_time`: https://docs.openstack.org/nova/latest/configuration/config.html
- Ceph, *RBD exclusive locks* (cooperative lock; blocklisting only for unresponsive clients): https://docs.ceph.com/en/latest/rbd/rbd-exclusive-locks/
- Ceph, `rbd status` (watchers): https://docs.ceph.com/en/latest/man/8/rbd/
- ipmitool, `chassis power status | off`, `sel list`: https://manpages.debian.org/testing/ipmitool/ipmitool.1.en.html
- Related episodes: [#02 `openstack compute service list`](../series/one-command-one-investigation/02-openstack-compute-service-list.md), [#13 block devices and `rbd status`](../series/one-command-one-investigation/13-os-brick-block-devices.md), [#19 the compute node as a machine](../series/one-command-one-investigation/19-compute-host-as-a-machine.md)
- The book, *OpenStack, the Day After Tomorrow*, chapter 10 (unplanned host failure; evacuation and fencing) and figure 20.1: https://github.com/soufian-zaouam/openstack-the-day-after-tomorrow

---

*Part of the [incident case studies](README.md) of the [OpenStack Production Guide](../README.md). The reasoning behind the decision is developed in [OpenStack, the Day After Tomorrow](https://github.com/soufian-zaouam/openstack-the-day-after-tomorrow).*
