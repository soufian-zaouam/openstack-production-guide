# Patching with limited capacity: the campaign and the arbitration

**Symptom:** a mandatory operating-system patch on every compute host, each requiring a reboot; not enough spare capacity to live-migrate every instance away from every host · **Decision:** a differentiated strategy built on a criticality table filled in by the consuming teams · **Layers:** Nova (service disable, live and cold migration), Placement, the business · **Commands:** `openstack compute service set --disable` (STATE CHANGING), `openstack server migrate --live-migration` (POTENTIALLY DISRUPTIVE), `openstack server migrate` (POTENTIALLY DISRUPTIVE), `openstack resource provider usage show` (READ ONLY)

> Composite of real situations from production OpenStack platforms, generalised. No platform, organisation or person is identifiable; counts and durations are illustrative. The decision is told in chapter 20 of the book; this page carries the campaign's technical file.

## 1. Context

A production platform of a few hundred compute hosts, in several racks that form the failure domains, running workloads whose business criticality the platform team does not know: Nova sees instances, not business processes. A security requirement imposes an operating-system patch on every host, with a deadline. The patch requires a reboot. Rebooting a host without disrupting the instances it runs means moving them first.

Spare capacity: about the equivalent of two hosts per rack, some of it fragmented across hosts in a way that no single large instance could use. Live migration was configured and worked; it had never been run at the scale of a fleet-wide campaign.

## 2. Timeline

| Time | Event | Source |
| --- | --- | --- |
| week 0 | patch mandated; deadline in six weeks | security |
| week 0 | capacity assessment: migrating every instance off every host, one host at a time, needs more free memory per rack than exists once the larger instances are counted | Placement usage, flavor list |
| week 0 | first proposal: "reboot everything in a maintenance window"; second: "delay until capacity is added" | channel |
| week 1 | decision: ask the consuming teams what the platform cannot infer; build the campaign on their answers | platform lead, security, service owners |
| week 1–2 | criticality table filled in per team: instance or project, criticality, tolerated downtime, preferred window, contact | shared table |
| week 2 | migration-compatibility inventory: pinned/NUMA instances, SR-IOV and PCI passthrough, large memory footprints, CPU model per host generation | Nova, Placement, host inventory |
| week 3–5 | campaign: per rack, per host; critical workloads live-migrated inside the available capacity; the rest restarted in agreed windows | change records |
| week 5 | last host patched; every instance running on a patched host | verification |
| week 6 | review: the table kept as platform metadata; capacity planning updated with a maintenance scenario | RCA |

## 3. Symptoms

Not an incident: a constraint. The security objective was not negotiable and the capacity was what it was. What made it a decision rather than a task was the uncertainty in the middle: which workloads could tolerate a restart, and which could not. The infrastructure had no way of knowing, and every uniform strategy failed on that uncertainty: migrate everything (impossible), restart everything (unknown business impact), delay (extended exposure).

## 4. Investigation

### How much room there is — [`openstack resource provider usage show`](../series/one-command-one-investigation/15-placement-allocations.md) and [`hypervisor show`](../series/one-command-one-investigation/03-openstack-hypervisor-show.md) — READ ONLY

```text
openstack resource provider list
openstack resource provider usage show <rp-uuid>            # per host: VCPU, MEMORY_MB, DISK_GB used
openstack resource provider inventory list <rp-uuid>        # total, reserved, allocation_ratio
openstack server list --host <host> --all-projects --long   # what is on it, with flavor
```

Per rack, the sum of free memory after `reserved` and `allocation_ratio` against the largest instances on each host. Headroom in aggregate is not headroom for a given instance: a 128 GB instance needs one destination with 128 GB free, not four with 32. The capacity assessment was done per host, per rack, against the actual instances, and it showed that a one-host-at-a-time rolling migration worked for most racks and failed in three, where the largest instances had nowhere to go.

### What can move at all — READ ONLY

```text
openstack server show <server> -c flavor -c properties          # API 2.47: extra_specs inline (hw:cpu_policy, pci_passthrough:alias, hw:mem_page_size)
openstack port list --server <server> -c ID -f value | xargs -n1 openstack port show -c binding_vnic_type -f value   # direct = SR-IOV
openstack resource provider trait list <rp-uuid> | grep HW_CPU_   # CPU feature traits per host (cpu_info left hypervisor show in API 2.88)
virsh capabilities | grep -A3 '<cpu>'                           # on the host, the model from libvirt
```

Live migration has constraints a campaign runs into directly. The destination's CPU model must be compatible with the source's; migration from a newer libvirt/QEMU to an older one is not supported, so once some hosts are patched instances can move onto them but not back, and the order of patching decides where instances can go. Instances with PCI passthrough or SR-IOV direct ports cannot be live-migrated; instances with a NUMA topology (pinned CPUs, huge pages) can since Train. Memory-intensive workloads whose pages change faster than they copy do not converge unless auto-converge or post-copy is enabled. For all of those, a restart is a technical necessity, not a business choice, and the table had to say so before the owners were asked.

### What the platform cannot know

Which of the remaining instances carry a process that tolerates five minutes of downtime, and which carry one that does not. There is no command for that. It was collected from the consuming teams in a shared table: instance or project, criticality (three levels), tolerated downtime, preferred window, a contact reachable during the window, and a note when the team itself preferred a restart (some did: a clean restart on a patched host was simpler for them than a migration during business hours).

## 5. Cause, in three layers

There was no failure, so the three layers describe the constraint:

- **Immediate constraint:** insufficient spare capacity, per failure domain, to migrate every instance away from every host.
- **Contributing cause:** capacity planning had been done for growth, not for maintenance. The question "how many hosts can be out at once, per rack, with every instance still running?" had never been asked, so the answer was found in week 0 of a six-week deadline.
- **Why it became a platform-team problem:** instance criticality lived in the consuming teams' heads. The platform could not differentiate because nobody had ever recorded, on the platform, which workloads mattered how much.

## 6. Decision

**What was done: a differentiated campaign, rack by rack, host by host.**

For each host, in an order that respected the libvirt/QEMU version constraint (patched hosts become destinations; unpatched hosts stop being destinations for anything that came from a patched one):

```text
# STATE CHANGING — the scheduler stops placing new instances on the host; running instances unaffected
openstack compute service set --disable --disable-reason "patch <change-id>" <host> nova-compute

# READ ONLY — the list to work through
openstack server list --host <host> --all-projects --long

# POTENTIALLY DISRUPTIVE — critical instances, within the rack's capacity, destination chosen by the scheduler
openstack server migrate --live-migration --wait <server>
openstack server migration list --server <server>        # READ ONLY: status, source, destination
openstack server show <server> -c OS-EXT-SRV-ATTR:host -c status -c OS-EXT-STS:task_state

# POTENTIALLY DISRUPTIVE — instances whose owners accepted a stop, in their window
openstack server migrate --wait <server>                 # cold migration: the instance is stopped, moved, restarted; requires confirm
openstack server resize confirm <server>
# or, when the owner preferred it and the host would be back within the window:
openstack server stop <server> ; (patch and reboot the host) ; openstack server start <server>

# after the reboot
openstack compute service list --host <host>              # READ ONLY: up
openstack compute service set --enable <host> nova-compute   # STATE CHANGING: the host is a destination again
```

Live migrations were run a few at a time, not in parallel across the rack, with `virsh domjobinfo <domain>` on the source to watch memory copy progress and a stop condition on any migration that did not converge. Instances that had to restart were restarted in windows their owners had chosen, with the contact on the line.

**The order was the campaign.** Three racks lacked room for their largest instances. Those instances were moved first, into the spare capacity of racks already patched, which freed their source hosts; then their racks were patched; then, if their owners wanted, they were moved back. The libvirt/QEMU direction constraint made "patched first, then destinations" the only order that worked, and it was drawn on a whiteboard before the first command.

**What a patched host proves.** A hypervisor or QEMU patch protects only the instances that have been migrated or restarted since. An instance that keeps running on the old binary is not patched. The campaign's completion criterion was not "every host rebooted" but "every instance running on a patched host, started after the patch", checked from `openstack server list --all-projects --long` against the hosts' reboot times.

**Rejected: reboot everything in one window.** Achievable in a night; unknown business impact; the option everyone would have regretted by morning.

**Rejected: delay until capacity is added.** Weeks of extended exposure, and the capacity was not funded; "delay" was "do not patch" with a nicer name.

**Rejected: evacuate hosts instead of migrating.** Evacuation is for a host that has already failed; it must never be used on a host still running its instances (see [evacuation and fencing](evacuation-fencing-shared-storage.md)). It was proposed once because it is faster; it was not discussed twice.

## 7. Blast radius and rollback

- **Service disable:** one host at a time; no effect on running instances; reversible in one command.
- **Live migration:** one instance at a time; the instance keeps running; a migration that fails leaves it on the source. Network and storage load during the copy is the visible cost; the stop condition was a migration not converging or a second consecutive failure on a host.
- **Restart in an agreed window:** the instance is down for the duration of the host's patch and reboot, or moved cold; the owner is on the line; rollback is "start it again on the same host", which is why the host's patch itself had a tested rollback (previous kernel kept, boot verified on the first host of the campaign before the second).
- **Fleet-wide:** never more than one host per rack out at once, which is the failure-domain rule capacity planning should have contained from the start.

## 8. Follow-ups

| Follow-up | Owner | Closed when |
| --- | --- | --- |
| Criticality table kept as platform metadata (instance or project properties) and reviewed with the owners twice a year | service owners, platform team | metadata present for every project; review scheduled |
| Capacity planning includes a maintenance scenario: hosts out per failure domain, instances in flight, spare capacity for safe patching | capacity owner | scenario documented and the spare capacity budgeted |
| Migration-compatibility inventory (pinned, SR-IOV, PCI, large memory, CPU model per generation) maintained, not rebuilt per campaign | platform team | inventory generated from Nova and Placement by a script, run monthly |
| The patching order rule (patched hosts first as destinations; direction constraint) written into the campaign runbook | runbook owner | runbook tested on the next campaign |
| Recurring difficulty patching or migrating raised as a lifecycle item on the platform roadmap, not solved per campaign | platform lead | roadmap item with a decision |

## 9. What you can reproduce

```text
openstack resource provider usage show <rp-uuid>                    # READ ONLY, per host: how much room, really, after reserved and ratios?
openstack server list --all-projects --long | awk '{print $NF}' | sort | uniq -c   # READ ONLY: how many instances per host; which host would be hardest to empty?
openstack resource provider trait list <rp-uuid> | grep HW_CPU_       # READ ONLY: how many CPU generations do you run? compare a host per rack
```

And one question for capacity planning: if one host per rack is down tonight, does every instance still run?

## 10. Sources

- Nova, *Configure live migrations* and *Live-migrate instances* (constraints, `libvirt`/QEMU version direction, auto-converge and post-copy): https://docs.openstack.org/nova/latest/admin/configuring-migrations.html and https://docs.openstack.org/nova/latest/admin/live-migration-usage.html
- Nova, *Migrate instances* (cold migration, confirm): https://docs.openstack.org/nova/latest/admin/migration.html
- Nova, *CPU topologies* (live migration of NUMA instances supported from Train): https://docs.openstack.org/nova/latest/admin/cpu-topologies.html
- python-openstackclient, `server migrate [--live-migration] [--host <hostname>] [--shared-migration | --block-migration] [--wait] <server>`, `server migration list`, `server resize confirm`, `server stop`, `server start`: https://docs.openstack.org/python-openstackclient/latest/cli/command-objects/server.html
- python-openstackclient, `compute service set [--enable | --disable] [--disable-reason <reason>] <host> <service>`: https://docs.openstack.org/python-openstackclient/latest/cli/command-objects/compute-service.html
- osc-placement, `resource provider usage show`, `resource provider inventory list`: https://docs.openstack.org/osc-placement/latest/cli/index.html
- libvirt, `virsh domjobinfo`: https://www.libvirt.org/manpages/virsh.html
- Related episodes: [#03 `openstack hypervisor show`](../series/one-command-one-investigation/03-openstack-hypervisor-show.md), [#15 Placement allocations](../series/one-command-one-investigation/15-placement-allocations.md), [#02 `openstack compute service list`](../series/one-command-one-investigation/02-openstack-compute-service-list.md)
- Guide page: [Changes and rollback](../methodology/changes-and-rollback.md)
- The book, *OpenStack, the Day After Tomorrow*, chapter 20 (security, capacity and business criticality; figure 20.1 on which operation applies) and chapter 10 (evacuation): https://github.com/soufian-zaouam/openstack-the-day-after-tomorrow

---

*Part of the [incident case studies](README.md) of the [OpenStack Production Guide](../README.md). The reasoning behind the decision is developed in [OpenStack, the Day After Tomorrow](https://github.com/soufian-zaouam/openstack-the-day-after-tomorrow).*
