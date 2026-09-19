# Index by error message

The exact string you are looking at, the page that explains what it means and what it does *not* mean, and the first read-only check. Messages are quoted as they appear in API responses, service logs, `virsh`, QEMU, Ceph, RabbitMQ and MariaDB; `<…>` stands for a value.

The index is deliberately short on interpretation. An error message tells you where a failure became visible, not where it started; the page it points to is where the investigation is.

## Nova and Placement

| Message | Where it appears | What it usually means | Read this | First check |
| --- | --- | --- | --- | --- |
| `No valid host was found. There are not enough hosts available.` | server `fault`, nova-scheduler log | No host passed Placement and the filters; the reason is on the hosts or in Placement, not in the scheduler | [VM stuck in BUILD / ERROR](troubleshooting/vm-build-error.md), [#03 `hypervisor show`](series/one-command-one-investigation/03-openstack-hypervisor-show.md), [#15 Placement allocations](series/one-command-one-investigation/15-placement-allocations.md) | `openstack allocation candidate list` for the flavor's resources |
| `Exceeded maximum number of retries.` | server `fault` | The build failed on several hosts in turn; the cause is on the hosts | [VM stuck in BUILD / ERROR](troubleshooting/vm-build-error.md) | nova-compute log on each host that tried |
| `Build of instance <uuid> aborted: Failed to allocate the network(s), not rescheduling.` | server `fault`, nova-compute log | Nova did not receive `network-vif-plugged` before `vif_plugging_timeout` | [VM stuck in BUILD / ERROR](troubleshooting/vm-build-error.md), [#07 `port show`](series/one-command-one-investigation/07-openstack-port-show.md), [#08 `network agent list`](series/one-command-one-investigation/08-openstack-network-agent-list.md) | `openstack port show <port>` → `binding:vif_type`, `status` |
| `Host '<host>' is not mapped to any cell` | nova-api, `openstack server create` | The compute host exists but was never discovered into a cell | [VM stuck in BUILD / ERROR](troubleshooting/vm-build-error.md) | `nova-manage cell_v2 list_hosts` |
| `Volume <uuid> did not finish being created even after we waited <n> seconds or <n> attempts.` | server `fault` | Boot from volume waited for Cinder and gave up | [VM stuck in BUILD / ERROR](troubleshooting/vm-build-error.md), [Storage](troubleshooting/storage.md) | cinder-volume log, backend health |
| `Quota exceeded for <resource>` | API response (HTTP 403) | Rejected before any instance exists | [VM stuck in BUILD / ERROR](troubleshooting/vm-build-error.md) | `openstack quota show`, `openstack limits show --absolute` |
| `host_status UNKNOWN` | `openstack server show` (API ≥ 2.16) | The compute service on the instance's host is not reporting; the instance may or may not be running | [#02 `compute service list`](series/one-command-one-investigation/02-openstack-compute-service-list.md), [#01 `server show`](series/one-command-one-investigation/01-openstack-server-show.md) | `openstack compute service list --host <host>` |
| `Cannot 'unpause' instance <uuid> while it is in vm_state active` (HTTP 409) | `openstack server unpause` | The domain is paused by QEMU (I/O error) and Nova never recorded it; resume happens outside Nova | [#04 `virsh domstate --reason`](series/one-command-one-investigation/04-virsh-list-domstate.md), [Ceph full OSD](incidents/ceph-full-osd-crush-weights.md) | `virsh domstate --reason <instance>` on the host |
| `Compute service of <host> is still in use.` (HTTP 400) | `openstack server evacuate` | The compute service is not reported down; evacuation is refused. Forcing it down does not make the host safe to evacuate | [Evacuation and fencing](incidents/evacuation-fencing-shared-storage.md) | BMC power state, `rbd status` watchers |
| `power_state` `SHUTDOWN` / `CRASHED` / `NOSTATE` with `status ACTIVE` | `openstack server show` | Nova's periodic sync found the domain in that state; `SHUTDOWN` and `CRASHED` get the instance stopped, `NOSTATE` and `PAUSED` are left alone | [#01 `server show`](series/one-command-one-investigation/01-openstack-server-show.md), [#04 `virsh domstate`](series/one-command-one-investigation/04-virsh-list-domstate.md) | `virsh list --all` on the host |
| `Cannot 'get_diagnostics' instance <uuid> while it is in power state <state>` (HTTP 409) | `openstack server show --diagnostics` (API ≥ 2.48) | Diagnostics need a running domain; the 409 is information about the domain, not about the guest | [#01 `server show`](series/one-command-one-investigation/01-openstack-server-show.md) | `virsh domstate --reason` |
| Consumer with two allocations, or an allocation on a host with no instance | `openstack resource provider allocation show`, `nova-manage placement audit` | Leftover of a failed migration or evacuation; capacity counted twice | [#15 Placement allocations](series/one-command-one-investigation/15-placement-allocations.md) | `nova-manage placement audit --verbose` (read-only without `--delete`) |

## Neutron, OVS and OVN

| Message | Where it appears | What it usually means | Read this | First check |
| --- | --- | --- | --- | --- |
| `binding:vif_type binding_failed` | `openstack port show` | No mechanism driver could bind the port on the requested host: agent dead, wrong `binding:host_id`, segment not available on that host | [#07 `port show`](series/one-command-one-investigation/07-openstack-port-show.md), [#08 `network agent list`](series/one-command-one-investigation/08-openstack-network-agent-list.md) | `openstack network agent list --host <host>` |
| `binding:vif_type unbound` | `openstack port show` | The port has no host yet; a VM port in this state after boot means Nova never asked, or asked for the wrong host | [#07 `port show`](series/one-command-one-investigation/07-openstack-port-show.md) | `binding:host_id` against `OS-EXT-SRV-ATTR:host` |
| Port `status DOWN` with `vif_type ovs` | `openstack port show` | The agent (or OVN) has not reported the port up: not plugged, not wired, or the agent's RPC is not reaching the server | [#08 `network agent list`](series/one-command-one-investigation/08-openstack-network-agent-list.md), [#09 `ovs-vsctl`, `ovs-ofctl`](series/one-command-one-investigation/09-ovs-vsctl-ofctl.md) | `ovs-vsctl --columns=name,tag,external_ids find Port` on the host |
| VLAN `tag 4095` on a port | `ovs-vsctl show`, `ovs-vsctl list Port` | The OVS agent put the port on the dead VLAN: it could not map it to a network (unknown network, segmentation missing, agent starting up) | [#09 `ovs-vsctl`, `ovs-ofctl`](series/one-command-one-investigation/09-ovs-vsctl-ofctl.md) | agent log on the host, `ovs-vsctl get Port <tap> external_ids` |
| `Port_Binding` with empty `chassis` | `ovn-sbctl find Port_Binding` | No chassis claimed the port: `requested_chassis` wrong, ovn-controller not running there, or `ovn-bridge-mappings` missing the segment | [#10 `ovn-nbctl`, `ovn-sbctl`](series/one-command-one-investigation/10-ovn-nbctl-sbctl.md) | `ovn-sbctl show`, `ovs-vsctl get Open_vSwitch . external_ids` on the host |
| `url_helper.py[WARNING]: Calling 'http://169.254.169.254/...' failed` | guest console log (cloud-init) | Metadata unreachable from the guest: no route to 169.254.169.254, DHCP namespace or metadata proxy not answering, haproxy not listening | [#11 `ip netns`](series/one-command-one-investigation/11-ip-netns.md), [#06 `console log show`](series/one-command-one-investigation/06-openstack-console-log-show.md) | `ip netns exec <ns> ss -lntp` on the node hosting the namespace |
| Ping works, SSH hangs after the banner | user report | MTU: overlay overhead not subtracted, large packets dropped | [Networking](troubleshooting/networking.md) | `ping -M do -s 1472` from the guest |

## Cinder, os-brick and block devices

| Message | Where it appears | What it usually means | Read this | First check |
| --- | --- | --- | --- | --- |
| Volume `attaching` or `detaching` for minutes | `openstack volume show` | Cinder or the backend has not answered; the state is a record, not a fact about the disk | [#12 `volume show`](series/one-command-one-investigation/12-openstack-volume-show.md), [Storage](troubleshooting/storage.md) | `openstack volume service list`, `openstack volume attachment list --volume <id>` (API ≥ 3.27) |
| Volume `error_attaching` | `openstack volume show` | The compute host could not connect: iSCSI login, multipath, Ceph keyring or capabilities | [Storage](troubleshooting/storage.md), [#13 block devices](series/one-command-one-investigation/13-os-brick-block-devices.md) | os-brick lines in nova-compute on that host |
| Volume `error_deleting` | `openstack volume list --status error_deleting` | The backend refused or timed out on the delete; the record and the backend object may both still exist | [Ceph full OSD](incidents/ceph-full-osd-crush-weights.md), [Storage](troubleshooting/storage.md) | `rbd ls -l <pool>` / backend inventory, cinder-volume log |
| HTTP 409 on `volume attachment delete` | Cinder API (≥ 3.27) | A Nova instance still uses the attachment; detach from Nova's side, not Cinder's | [#12 `volume show`](series/one-command-one-investigation/12-openstack-volume-show.md) | `openstack server volume list <server>` |
| `failed faulty` on a path | `multipath -ll` | A path to the LUN is down on this host; every instance using the map is affected | [#13 block devices](series/one-command-one-investigation/13-os-brick-block-devices.md) | `iscsiadm -m session -P 3`, `dmesg -T` |
| `session recovery timed out` | `dmesg`, kernel log | An iSCSI session could not be recovered within `node.session.timeo.replacement_timeout`; I/O errors follow | [#13 block devices](series/one-command-one-investigation/13-os-brick-block-devices.md), [#19 the host](series/one-command-one-investigation/19-compute-host-as-a-machine.md) | `iscsiadm -m session`, storage network |
| `Input/output error` on a guest disk, guest filesystem read-only | guest console log, QEMU log | The host lost the path or the backend refused the write; the guest saw it because `rerror=report` | [#13 block devices](series/one-command-one-investigation/13-os-brick-block-devices.md), [#05 QEMU log](series/one-command-one-investigation/05-virsh-dumpxml-qemu-log.md) | `virsh domblkerror <instance>` on the host |

## libvirt and QEMU

| Message | Where it appears | What it usually means | Read this | First check |
| --- | --- | --- | --- | --- |
| `paused (I/O error)` | `virsh domstate --reason` | QEMU paused the guest on a failed write (`werror=enospc` default); the storage path is the cause, the guest is intact | [#04 `virsh domstate --reason`](series/one-command-one-investigation/04-virsh-list-domstate.md), [Ceph full OSD](incidents/ceph-full-osd-crush-weights.md) | `virsh domblkerror <instance>`, then `ceph -s` or the backend |
| `paused (migrating)` | `virsh domstate --reason` | A live migration is in its final phase; not a fault unless it stays | [#04 `virsh domstate --reason`](series/one-command-one-investigation/04-virsh-list-domstate.md) | `virsh domjobinfo <instance>`, `openstack server migration list` |
| `shut off (destroyed)` | `virsh domstate --reason` | The domain was stopped by libvirt on request: Nova's stop, a sync decision, or an operator | [#04 `virsh domstate --reason`](series/one-command-one-investigation/04-virsh-list-domstate.md), [#05 QEMU log](series/one-command-one-investigation/05-virsh-dumpxml-qemu-log.md) | `openstack server event list <server>`; libvirt log `shutting down, reason=` |
| `shut off (crashed)` | `virsh domstate --reason` | QEMU died: a signal, an abort, an OOM kill on the host | [#05 QEMU log](series/one-command-one-investigation/05-virsh-dumpxml-qemu-log.md), [#19 the host](series/one-command-one-investigation/19-compute-host-as-a-machine.md) | QEMU log tail, `dmesg -T \| grep -i 'killed process'` |
| `terminating on signal 15 from pid <pid> (/usr/sbin/libvirtd)` | QEMU log | A clean stop requested through libvirt; not a crash | [#05 QEMU log](series/one-command-one-investigation/05-virsh-dumpxml-qemu-log.md) | who asked libvirt: Nova events, libvirt log |
| `rbd: … No space left on device` | QEMU log | The Ceph cluster or pool refused the write (`OSD_FULL` / `POOL_FULL`) | [#14 `ceph -s`](series/one-command-one-investigation/14-ceph-status.md), [Ceph full OSD](incidents/ceph-full-osd-crush-weights.md) | `ceph -s`, `ceph osd df tree` |
| Console `409 Conflict` | `openstack console url show`, `console log show` | The instance is not in a state where a console can be attached; information about the domain, not the guest | [#06 `console log show`](series/one-command-one-investigation/06-openstack-console-log-show.md) | `virsh domstate --reason` |

## Ceph

| Message | Where it appears | What it usually means | Read this | First check |
| --- | --- | --- | --- | --- |
| `OSD_NEARFULL` / `OSD_BACKFILLFULL` / `OSD_FULL` | `ceph -s`, `ceph health detail` | One OSD crossed `nearfull_ratio` (0.85), `backfillfull_ratio` (0.90) or `full_ratio` (0.95); a cluster is full when its fullest OSD is | [#14 `ceph -s`](series/one-command-one-investigation/14-ceph-status.md), [Ceph full OSD](incidents/ceph-full-osd-crush-weights.md) | `ceph osd df tree` |
| `POOL_FULL` / `pool '<pool>' is full (no space)` | `ceph health detail` | Writes to the pool refused; QEMU guests on it pause | [#14 `ceph -s`](series/one-command-one-investigation/14-ceph-status.md) | `ceph df`, `ceph osd df tree` |
| `OSD_DOWN` | `ceph -s` | OSDs down; after `mon_osd_down_out_interval` (600 s) they are marked out and recovery starts | [#14 `ceph -s`](series/one-command-one-investigation/14-ceph-status.md) | `ceph osd tree`, the host (`#19`) |
| `PG_AVAILABILITY` / `pgs inactive` | `ceph -s` | Some PGs cannot serve I/O; guests on them hang rather than error | [#14 `ceph -s`](series/one-command-one-investigation/14-ceph-status.md) | `ceph pg dump_stuck` |
| `SLOW_OPS` | `ceph -s` | Requests older than the threshold on some OSDs; latency in the guests before any error | [#14 `ceph -s`](series/one-command-one-investigation/14-ceph-status.md) | `ceph health detail`, the named OSDs' hosts |
| Watcher from a host that is "down" | `rbd status <pool>/<image>` | A client on that host still has the image open: the host is not dead | [Evacuation and fencing](incidents/evacuation-fencing-shared-storage.md), [#13 block devices](series/one-command-one-investigation/13-os-brick-block-devices.md) | BMC power state |

## RabbitMQ and oslo.messaging

| Message | Where it appears | What it usually means | Read this | First check |
| --- | --- | --- | --- | --- |
| `MessagingTimeout: Timed out waiting for a reply to message ID <id>` | any service log | An RPC call got no reply within `rpc_response_timeout` (60 s): the callee is down, disconnected, or on the other side of a partition | [RabbitMQ](troubleshooting/rabbitmq.md), [#16 `rabbitmqctl cluster_status`](series/one-command-one-investigation/16-rabbitmq-cluster-status.md), [RabbitMQ partition](incidents/rabbitmq-partition-api-stop.md) | `rabbitmqctl cluster_status` |
| `AMQP server on <host>:<port> is unreachable` | any service log | The service cannot connect to that node; it will try the next one in `transport_url` | [RabbitMQ](troubleshooting/rabbitmq.md) | `rabbitmq-diagnostics check_running`, `check_port_connectivity` |
| `Mnesia(rabbit@<node>): ** ERROR ** mnesia_event got {inconsistent_database, running_partitioned_network, …}` | RabbitMQ log (Mnesia era) | The cluster has partitioned; with `cluster_partition_handling = ignore` it will not heal by itself | [RabbitMQ partition](incidents/rabbitmq-partition-api-stop.md), [#16](series/one-command-one-investigation/16-rabbitmq-cluster-status.md) | `rabbitmqctl cluster_status` → `partitions` |
| `node rabbit@<node> down: net_tick_timeout` | RabbitMQ log | A peer stopped answering the Erlang distribution ticks: network, or a node too busy to answer | [#16 `rabbitmqctl cluster_status`](series/one-command-one-investigation/16-rabbitmq-cluster-status.md) | `rabbitmq-diagnostics check_running` on the peer, the network between nodes |
| Queues with messages and no consumers | `rabbitmqctl list_queues name messages consumers` | Whoever should consume is gone or connected to another partition | [RabbitMQ](troubleshooting/rabbitmq.md), [#16](series/one-command-one-investigation/16-rabbitmq-cluster-status.md) | which service owns the queue; its `compute service list` / `agent list` state |

## MariaDB and Galera

| Message | Where it appears | What it usually means | Read this | First check |
| --- | --- | --- | --- | --- |
| `WSREP has not yet prepared node for application use` | API 500, service log | The node is not `Synced` (joining, donor, or non-Primary) and refuses queries; the load balancer sent traffic to it | [MariaDB / Galera](troubleshooting/mariadb-galera.md), [#17 `wsrep_%`](series/one-command-one-investigation/17-galera-wsrep-status.md) | `SHOW STATUS LIKE 'wsrep_local_state_comment'` on every node |
| `wsrep_cluster_status non-Primary` | `SHOW STATUS` | The node lost quorum; it refuses writes until it rejoins a Primary component | [#17 `wsrep_%`](series/one-command-one-investigation/17-galera-wsrep-status.md) | `wsrep_cluster_size` and `wsrep_cluster_state_uuid` on every node |
| `Deadlock found when trying to get lock; try restarting transaction` (error 1213) | service log | Certification conflict: the same rows written on several nodes, or a write sent to a non-Primary node; not a classic deadlock | [#17 `wsrep_%`](series/one-command-one-investigation/17-galera-wsrep-status.md) | `wsrep_local_cert_failures`, `wsrep_local_bf_aborts`, the load balancer's write target |
| `(pymysql.err.OperationalError) … Lost connection to MySQL server during query` | service log | The connection was cut mid-query: node restart, flow-control pause, load-balancer timeout | [MariaDB / Galera](troubleshooting/mariadb-galera.md) | `wsrep_flow_control_paused`, HAProxy backend status |
| `safe_to_bootstrap: 0` on every node after an outage | `grastate.dat` | No node is known to be the most advanced; bootstrapping without `--wsrep-recover` risks discarding transactions | [MariaDB / Galera](troubleshooting/mariadb-galera.md), [RabbitMQ partition](incidents/rabbitmq-partition-api-stop.md) | `mariadbd --wsrep-recover` on each node (read-only), compare sequence numbers |

## Keystone

| Message | Where it appears | What it usually means | Read this | First check |
| --- | --- | --- | --- | --- |
| `The request you have made requires authentication. (HTTP 401)` | any client, service-to-service | Token invalid or not validatable: Fernet keys out of sync, clock skew, memcached | [Keystone](troubleshooting/keystone.md) | `openstack token issue`, Fernet key checksums per node, `chronyc tracking` |
| `Policy doesn't allow <rule> to be performed. (HTTP 403)` | any client | The token is valid; the policy rejects the action, often after an upgrade | [Keystone](troubleshooting/keystone.md) | the service's `policy.yaml` and the release notes for the policy defaults |

## The host

| Message | Where it appears | What it usually means | Read this | First check |
| --- | --- | --- | --- | --- |
| `Out of memory: Killed process <pid> (qemu-kvm)` | `dmesg -T`, kernel log | The host OOM killer stopped a guest; overcommit or a host process leak | [#19 the host](series/one-command-one-investigation/19-compute-host-as-a-machine.md), [Compute](troubleshooting/compute.md) | `free -m`, `openstack hypervisor show`, the instance's `virsh domstate --reason` (`crashed`) |
| `rx_missed_errors` / `rx_crc_errors` increasing | `ethtool -S <iface>` | The NIC drops frames (ring full) or the link is bad; intermittent loss for every instance on the host | [#19 the host](series/one-command-one-investigation/19-compute-host-as-a-machine.md), [Networking](troubleshooting/networking.md) | `ip -s link`, `ethtool <iface>` |
| Units in `failed` state | `systemctl --failed` | A host service did not start or died; if it is `nova-compute`, `neutron-*`, `openvswitch` or `libvirtd`, the OpenStack symptom follows | [#19 the host](series/one-command-one-investigation/19-compute-host-as-a-machine.md) | `journalctl -u <unit> -b` |
| Steal time (`st`) on a pinned instance | guest `top`, `/proc/stat` | Something that is not the guest's vCPU runs on its dedicated CPU: host threads, interrupts, the emulator thread | [CPU pinning and steal time](incidents/cpu-pinning-steal-time-live-migration.md), [Compute](troubleshooting/compute.md#4-cpu-pinning) | `virsh emulatorpin`, `ps -eLo psr,comm` on the host |

## Adding a message

One row per exact message, quoted as it appears, with the page that explains it. A message without a page is a reason to write the page, not to add the row. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

*Part of the [OpenStack Production Guide](README.md).*
