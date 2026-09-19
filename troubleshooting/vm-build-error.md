# VM stuck in BUILD / ERROR

Do not start with "what failed?". Start with **"where did the request stop?"**. The task state and the host answer that before any log does.

## 1. Read the state

```bash
# control plane, read-only
openstack server show <vm> -c status -c OS-EXT-STS:task_state \
  -c OS-EXT-SRV-ATTR:host -c fault
openstack server event list <vm>
openstack server event show <vm> <request-id>
```

| `task_state` | Host set? | The request stopped in | Look at |
| --- | --- | --- | --- |
| `scheduling` | no | Scheduler, Placement, conductor, RPC | nova-scheduler and nova-conductor logs, allocation candidates, RabbitMQ |
| `networking` | yes | Port creation and binding | neutron-server, the agent or ovn-controller on that host |
| `block_device_mapping` | yes | Volume creation or attachment | Volume status, cinder-scheduler, cinder-volume, backend |
| `spawning` | yes | Image download, libvirt / QEMU start, wait for `network-vif-plugged` | nova-compute on that host, libvirt, QEMU instance log |
| none, status ERROR | either | The build was aborted | `fault` in `server show`, `server event show` |

A VM that stays in the same task state is waiting for something. The task state tells you what.

## 2. Could any host take it?

```bash
# requires the osc-placement client plugin
openstack flavor show <flavor> -c vcpus -c ram -c disk -c properties
openstack allocation candidate list \
  --resource VCPU=<vcpus> --resource MEMORY_MB=<ram> --resource DISK_GB=<disk>
openstack resource provider allocation show <vm-uuid>
# on a controller
nova-manage cell_v2 list_hosts
```

- No allocation candidates: Placement sees no capacity for this request (inventory, reserved values, allocation ratios, traits).
- Candidates exist but the build still fails: the filters, the host itself, or a later step is responsible.
- A compute host that exists but is missing from `list_hosts` is not mapped to a cell.

## 3. What did the request ask for?

```bash
openstack flavor show <flavor> -c properties        # hw:* extra specs, aggregates, PCI aliases
openstack image show <image> -c status -c disk_format -c min_disk -c min_ram -c properties
openstack port list --server <vm>
openstack quota show <project>
openstack limits show --absolute --project <project>
```

Also check recent changes to flavors, image properties, host aggregates and host configuration.

## 4. Follow the request ID

Take the request ID from `server event list` and follow it through `nova-api`, `nova-conductor`, `nova-scheduler`, then `nova-compute` on the selected host. See [Logs](logs.md).

## Faults you will meet

| Message | What it usually means | Next check |
| --- | --- | --- |
| `No valid host was found.` | No host passed Placement and the scheduler filters | Allocation candidates for the flavor, disabled or down compute services, availability zone and aggregate filters, NUMA or PCI requests |
| `Host '<host>' is not mapped to any cell` | The host exists but was never discovered into a cell | `nova-manage cell_v2 list_hosts` |
| `Exceeded maximum number of retries.` | The build failed on several hosts in turn | The cause is on the hosts: read nova-compute on each, not the scheduler |
| `Build of instance <uuid> aborted: Failed to allocate the network(s), not rescheduling.` | Nova did not receive `network-vif-plugged` before `vif_plugging_timeout` | Port binding, the agent or ovn-controller on that host, RabbitMQ between Neutron and its agents |
| `Volume <uuid> did not finish being created even after we waited <n> seconds or <n> attempts.` | Boot from volume waited for Cinder and gave up | cinder-volume logs, backend health, image-to-volume copy time |
| `Quota exceeded for <resource>` | Usually rejected by the API before any VM exists | `openstack quota show`, `openstack limits show --absolute` |

> [!WARNING]
> **Changes state.** `nova-manage cell_v2 discover_hosts --verbose` maps unmapped compute hosts into cells. It is safe in principle, but it modifies the API database: run it knowingly, on a controller, after confirming the host should be in service.

> [!WARNING]
> **Changes state.** `openstack server set --state <active|error> <vm>` rewrites the record, not the reality. It does not free resources, unbind ports or detach volumes. Use it only once you know what the hypervisor, Neutron and Cinder actually hold, and prefer deleting and recreating a VM that never finished building.

## Go deeper

Episodes of [One Command, One Investigation](../series/one-command-one-investigation/README.md) on the commands of this page: [#03 `openstack hypervisor show`](../series/one-command-one-investigation/03-openstack-hypervisor-show.md) · [#15 Placement allocations and `nova-manage placement audit`](../series/one-command-one-investigation/15-placement-allocations.md) · [#07 `openstack port show`](../series/one-command-one-investigation/07-openstack-port-show.md) · [#08 `openstack network agent list`](../series/one-command-one-investigation/08-openstack-network-agent-list.md) · [#18 request IDs and log correlation](../series/one-command-one-investigation/18-request-id-log-correlation.md).

Incident case studies where this page's checks were used under pressure: [RabbitMQ partition: stopping the APIs](../incidents/rabbitmq-partition-api-stop.md).

Looking for an exact error message? See the [index by error message](../errors.md).

---
Next: [Compute](compute.md) · Back to [first commands](vm-first-commands.md)
