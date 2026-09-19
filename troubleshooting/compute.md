# Compute problems

Once the scheduler has chosen a host, the question changes from "is there capacity?" to "can this host honour what the flavor asks for?"

## Map the VM to its host and its domain

```bash
# control plane
openstack server show <vm> -c OS-EXT-SRV-ATTR:host -c OS-EXT-SRV-ATTR:instance_name
# on that compute node
virsh domstate <instance_name>      # instance-XXXXXXXX, not the VM name
```

> [!NOTE]
> In containerised deployments, run `virsh` inside the libvirt container, and read logs from the deployment tool's log directory. The questions are the same.

## An order that saves time

```text
Service enabled → Placement capacity → Flavor fits host → libvirt domain → QEMU process
```

Each step is cheaper than the next and rules out a whole layer. Jumping to the QEMU log first often explains the last error, not the first one.

## 1. Compute service

**Can this host receive work at all?**

```bash
openstack compute service list --service nova-compute --long
```

A host that is up but disabled receives no new instances. The `Disabled Reason` column often says why, and who disabled it.

## 2. Capacity: Placement is the source of truth

**What does the scheduler believe is free on this host?**

```bash
# requires the osc-placement client plugin
openstack resource provider list --name <compute>
openstack resource provider inventory list <resource-provider-uuid>   # total, reserved, allocation_ratio
openstack resource provider usage show <resource-provider-uuid>
openstack resource provider allocation show <vm-uuid>
# on a controller, read-only
nova-manage placement audit --verbose
```

- Allocations that belong to no instance (orphans) make a host look full.
- `reserved` and `allocation_ratio` explain why a host that looks empty to a human is full for the scheduler, or the opposite.
- Since compute API microversion 2.88, `openstack hypervisor show` no longer reports usage figures.

> [!WARNING]
> **Changes state.** `nova-manage placement audit --delete` removes orphaned allocations, and `nova-manage placement heal_allocations` creates missing ones. Run the audit without `--delete` first, review the output, and keep it as evidence.

## 3. CPU, RAM and NUMA

**Does the guest topology fit on one host NUMA node?**

```bash
# control plane
openstack flavor show <flavor> -c properties    # hw:numa_nodes, hw:mem_page_size, hw:cpu_policy
# compute node
lscpu
numactl --hardware
```

The CPUs and memory of a guest NUMA node must come from the same host NUMA node. A host with enough free memory in total can still fail a request that needs it on one node.

## 4. CPU pinning

**Are dedicated CPUs available, and really dedicated?**

- `hw:cpu_policy=dedicated` consumes the `PCPU` resource class, provided by the host's `[compute] cpu_dedicated_set`. Shared CPUs come from `cpu_shared_set` (`VCPU`).
- Nova pins the guest vCPUs. It does not keep host kernel threads, interrupts or other processes off those cores: host isolation has to be configured on the host.
- By default, the QEMU emulator threads run on the instance's pinned CPUs, unless `hw:emulator_threads_policy` moves them.

```bash
# compute node
virsh vcpupin <instance_name>
virsh emulatorpin <instance_name>
```

Steal time on a pinned instance usually comes from the host (isolation, emulator threads), not from the instance. Live-migrating the instance moves the symptom; it does not fix the host.

## 5. Huge pages

**Are there enough free pages on the right NUMA node?**

```bash
grep -i huge /proc/meminfo
cat /sys/devices/system/node/node*/hugepages/hugepages-*/free_hugepages
```

Huge pages are counted per NUMA node. A large free total can still fail a guest bound to one node.

## 6. PCI passthrough and SR-IOV

**Is the device exposed, free, and matched?**

- Port: `binding:vnic_type` is `direct` (SR-IOV VF) or another non-`normal` value.
- Nova configuration: `[pci] device_spec` (named `passthrough_whitelist` before the Zed release) and `[pci] alias`.
- Host: `lspci -nn`, `ip link show <physical-function>` to list VFs.

Instances with passthrough devices often cannot be live-migrated, which matters for maintenance planning.

## 7. libvirt

**Did libvirt define and start the domain?**

```bash
virsh list --all
virsh dominfo <instance_name>
virsh dumpxml <instance_name>      # CPU tuning, NUMA, disks, interfaces
journalctl -u libvirtd             # or virtqemud with modular libvirt daemons
```

## 8. QEMU and instance logs

**Why did the process refuse to start, or die?**

- `/var/log/libvirt/qemu/<instance_name>.log`: missing device, unsupported CPU model, permission denied, SELinux or AppArmor denials.
- Then `nova-compute` on the same host, filtered by the request ID.
- The guest side: `openstack console log show <vm>`.

## Host failure and evacuation

When a compute host fails, `nova evacuate` (`openstack server evacuate` in recent clients) rebuilds its instances on other hosts, reusing their volumes or shared disks.

Nova requires the compute service to be reported down. What Nova cannot know is whether the host is really off or only unreachable from the control plane.

> [!CAUTION]
> **Never evacuate a host that may still be running its instances.** With shared storage (for example Ceph RBD), two QEMU processes would write to the same disk, and the guest filesystem will be corrupted silently.
>
> Before evacuating:
> 1. **Fence the host**: confirm its state and power it off through out-of-band management, or isolate it at the switch.
> 2. **Verify on the storage side**: with Ceph RBD, `rbd status <pool>/<image>` lists the clients still watching an image. A watcher from the "dead" host means the host is not dead.
> 3. Only then force the service down (`openstack compute service set --down <host> nova-compute`) if needed, and evacuate.
>
> Any automation that evacuates on a lost heartbeat must fence first.

## Go deeper

Episodes of [One Command, One Investigation](../series/one-command-one-investigation/README.md) on the commands of this page: [#02 `openstack compute service list`](../series/one-command-one-investigation/02-openstack-compute-service-list.md) · [#03 `openstack hypervisor show`](../series/one-command-one-investigation/03-openstack-hypervisor-show.md) · [#04 `virsh list --all`, `virsh domstate --reason`](../series/one-command-one-investigation/04-virsh-list-domstate.md) · [#05 `virsh dumpxml` and the QEMU log](../series/one-command-one-investigation/05-virsh-dumpxml-qemu-log.md) · [#19 the compute node as a machine](../series/one-command-one-investigation/19-compute-host-as-a-machine.md).

Incident case studies where this page's checks were used under pressure: [Evacuation and fencing on shared storage](../incidents/evacuation-fencing-shared-storage.md) · [CPU pinning, steal time and live migration](../incidents/cpu-pinning-steal-time-live-migration.md).

Looking for an exact error message? See the [index by error message](../errors.md).

---
Next: [Networking](networking.md) · [Storage](storage.md)
