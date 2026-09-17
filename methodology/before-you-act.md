# Before you act

The first minutes of an incident decide whether you investigate a platform or damage it. Nothing on this page changes production.

## 1. Understand the business impact

**Question:** What is broken, for whom, and how badly?

- Which capability is affected: create, reach, attach, migrate, authenticate?
- Which workloads and which owners? Is there a deadline?
- Is the situation stable, improving, or getting worse?

## 2. Identify the affected scope

**Question:** One VM, one project, one host, or everyone?

```bash
# control plane, read-only
openstack server list --all-projects --host <compute> --long
openstack server list --all-projects --status ERROR
openstack compute service list
openstack network agent list
```

Compare with a known-good VM created the same way.

| Scope observed | Suspect first |
| --- | --- |
| One VM | The guest, its port, its volume, its flavor and image properties |
| One project | Quotas, security groups, project network and router, RBAC / policy |
| One compute host | nova-compute, Neutron agent or ovn-controller, libvirt, host network and storage paths |
| One network, rack or availability zone | Network node or gateway chassis, fabric, storage backend segment |
| Every new request fails | Control plane: APIs, RabbitMQ, MariaDB, Keystone, Placement |
| Running VMs are affected too | Data plane and shared infrastructure: fabric, storage backend, power, hypervisors |

## 3. Isolated or systemic?

**Question:** Does a fresh test VM fail the same way?

One failing VM is a case. Many failing VMs is a platform problem: check the service and agent lists before looking at any individual VM.

## 4. Check recent changes

**Question:** What changed in the last 24 to 72 hours?

Deployments, configuration changes, host maintenance, certificate rotations, firewall and fabric changes, flavor, image, aggregate or quota edits, upstream provider changes. "What changed?" resolves more incidents than any metric.

## 5. Preserve evidence

**Question:** What will I need to explain this tomorrow?

- Save command output with UTC timestamps (`-f json` is useful for later comparison).
- Record request IDs (`openstack server event list <vm>`) and the UUIDs of VMs, ports and volumes.
- Copy the relevant logs before any restart or log rotation.

> [!IMPORTANT]
> A restart clears queues, caches and in-memory state. It is also a deletion of evidence.

## 6. Define the way back before any change

**Question:** If this makes things worse, how do I return to the previous state?

Write down the stop condition and the rollback before running anything. If there is no way back, the decision belongs to someone accountable for the consequence. See [Changes and rollback](changes-and-rollback.md).

## 7. Decide who decides

For disruptive actions (stopping APIs, restarting a shared component, evacuating a host), know who has the authority to decide before you need it.

## Stop sign

If the only way to get the evidence you need is to change production, you have reached a decision point, not a diagnostic step.

---
Next: [VM troubleshooting: first commands](../troubleshooting/vm-first-commands.md) · [Changes and rollback](changes-and-rollback.md)
