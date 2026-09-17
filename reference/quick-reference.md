# Quick reference by question

Read-only commands, grouped by the question they answer. `[cp]` runs from the control plane with the `openstack` client; `[ctl]` runs on a controller node; `[node]` runs on a compute or network node. Shared-component commands run on the nodes of that component. Details and signals are in the linked pages.

## Scope

| Question | Command |
| --- | --- |
| What else runs on this host? | `[cp] openstack server list --all-projects --host <compute>` |
| How many VMs are in ERROR? | `[cp] openstack server list --all-projects --status ERROR` |
| Are computes and agents reporting? | `[cp] openstack compute service list` · `openstack network agent list` · `openstack volume service list` |

## One VM ([details](../troubleshooting/vm-first-commands.md))

| Question | Command |
| --- | --- |
| State, host, fault? | `[cp] openstack server show <vm>` |
| What was done to it, and its request IDs? | `[cp] openstack server event list <vm>` |
| Did the guest boot? | `[cp] openstack console log show <vm>` |
| Its ports and volumes? | `[cp] openstack port list --server <vm>` · `openstack server volume list <vm>` |
| Its libvirt domain name? | `[cp] openstack server show <vm> -c OS-EXT-SRV-ATTR:instance_name` |
| Does the hypervisor agree? | `[node] virsh domstate <instance_name>` · `virsh domblklist <instance_name>` |
| Live counters? | `[cp] openstack server show --diagnostics <vm>` |

## Scheduling and capacity ([details](../troubleshooting/vm-build-error.md))

| Question | Command |
| --- | --- |
| Could any host take this flavor? | `[cp] openstack allocation candidate list --resource VCPU=<n> --resource MEMORY_MB=<n> --resource DISK_GB=<n>` |
| What does Placement think is used on this host? | `[cp] openstack resource provider usage show <rp-uuid>` |
| Are there orphaned allocations? | `[ctl] nova-manage placement audit --verbose` |
| Is this host mapped to a cell? | `[ctl] nova-manage cell_v2 list_hosts` |

## Network ([details](../troubleshooting/networking.md))

| Question | Command |
| --- | --- |
| Is the port bound, and where? | `[cp] openstack port show <port>` |
| Which router hosts this network's gateway? | `[cp] openstack network agent list --router <router> --long` (ML2/OVS) · `ovn-sbctl show` (ML2/OVN) |
| Does traffic leave the VM? | `[node] tcpdump -eni tap<first-11-chars-of-port-id>` |
| Are flows matching? | `[node] ovs-ofctl dump-flows br-int` (twice) |
| Is ovn-controller connected? | `[node] ovn-appctl -t ovn-controller connection-status` |

## Storage ([details](../troubleshooting/storage.md))

| Question | Command |
| --- | --- |
| Where is the volume, and to what is it attached? | `[cp] openstack volume show <volume>` |
| Is the backend service up? | `[cp] openstack volume service list` |
| What does QEMU really have open? | `[node] virsh domblklist <instance_name>` |
| Are all paths healthy? | `[node] multipath -ll` |
| Who holds this RBD image open? | `[node] rbd status <pool>/volume-<uuid>` |

## Shared components

| Question | Command |
| --- | --- |
| Is RabbitMQ whole, without partitions or alarms? | `rabbitmq-diagnostics cluster_status` · `rabbitmq-diagnostics check_local_alarms` |
| Are messages consumed? | `rabbitmqctl list_queues -p <vhost> name messages consumers` |
| Is Galera Primary and in sync? | `mysql -e "SHOW GLOBAL STATUS LIKE 'wsrep_%';"` |
| Can I get a token? | `openstack token issue` |
| Are Fernet keys identical on all Keystone nodes? | `sha256sum /etc/keystone/fernet-keys/*` (compare, never display) |
| Is time synchronised? | `chronyc tracking` |

## Commands that change state

Never run these as a diagnostic. Each one needs a reason, an owner and a way back.

| Command | Effect |
| --- | --- |
| `openstack server set --state <state> <vm>` | Rewrites the instance record |
| `openstack volume set --state <state> <volume>` | Rewrites the volume record |
| `openstack compute service set --down <host> nova-compute` | Declares a host dead (prerequisite for evacuation: fence first) |
| `openstack server evacuate` / `nova evacuate` | Rebuilds instances elsewhere: fence the source host first |
| `nova-manage cell_v2 discover_hosts` | Maps new hosts into cells |
| `nova-manage placement heal_allocations` / `audit --delete` | Creates or deletes allocations |
| `nova-manage db archive_deleted_rows` / `db purge` | Moves or deletes database rows |
| `rabbitmqctl purge_queue` / `reset` / `forget_cluster_node` | Discards messages or cluster membership |
| `galera_new_cluster`, editing `grastate.dat` | Bootstraps a cluster from one node |
| `keystone-manage fernet_rotate` | Rotates token keys |
