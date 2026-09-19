# RabbitMQ partition: stopping the APIs to protect the platform

**Symptom:** users can no longer create VMs; everything already running is fine; RPC calls time out · **Decision:** stop the APIs, restart the bus with its queues purged, restart the database, verify three things, reopen · **Layers:** RabbitMQ, MariaDB Galera, HAProxy, Nova/Neutron/Cinder control plane · **Commands:** `rabbitmqctl cluster_status` (READ ONLY), `SHOW STATUS LIKE 'wsrep_%'` (READ ONLY), HAProxy `disable server` (STATE CHANGING), RabbitMQ restart and queue purge (POTENTIALLY DISRUPTIVE)

> Composite of real situations from production OpenStack platforms, generalised. No platform, organisation or person is identifiable; names, counts and timestamps are illustrative. The decision itself is told in chapter 19 of the book; this page carries the technical file.

## 1. Context

A production platform with a highly available control plane: three controllers, RabbitMQ clustered across them, MariaDB Galera across them, the APIs behind HAProxy with a virtual IP. RabbitMQ of the Mnesia era (before 3.13, or upgraded in place since), with `cluster_partition_handling` left at its default, `ignore`. Nobody knew that last fact until the RCA.

## 2. Timeline

| Time | Event | Source |
| --- | --- | --- |
| 10:02 | tickets: "VM creation stuck", three projects | service desk |
| 10:06 | instances in `BUILD` for more than ten minutes, on every host; running instances unaffected | `openstack server list --status BUILD --all-projects` |
| 10:09 | `nova-conductor` logs: `MessagingTimeout: Timed out waiting for a reply to message ID …` | controller logs |
| 10:12 | `rabbitmqctl cluster_status`: a `partitions` section, two sides, each seeing the other as unreachable | RabbitMQ |
| 10:14 | Galera: one node `wsrep_local_state_comment Donor/Desynced`, flow-control pauses climbing; APIs returning 504 intermittently | MariaDB |
| 10:16 | proposal in the channel: restart the RabbitMQ nodes now, APIs open, "provisioning is already broken anyway" | channel |
| 10:20 | decision by the on-call lead, with the authority written in the escalation policy: stop the APIs first | decision record |
| 10:23 | API backends disabled in HAProxy; consumers told: no create/change/delete until further notice; running workloads untouched | HAProxy, communication |
| 10:25–10:44 | RabbitMQ stopped on all nodes, queues purged, started from one node, others rejoined | RabbitMQ |
| 10:46–11:05 | MariaDB restarted node by node, cluster kept Primary throughout | Galera |
| 11:08 | verification: Galera size 3 Primary; RabbitMQ whole, consumers back; every compute service and network agent `up`/alive; one test VM created, reached, deleted | checks |
| 11:12 | APIs reopened; consumers told | HAProxy, communication |
| 11:40 | clean-up of the requests that had been accepted during the degradation begins | control plane |
| next day | RCA: a network partition inside the RabbitMQ cluster; `cluster_partition_handling = ignore` | RCA |

## 3. Symptoms

One capability lost (provisioning), everything else fine, the APIs still answering. On paper a degradation, not an outage, and the pressure was to repair the bus and the database as fast as possible while the platform stayed "up".

The risk that shaped the decision was invisible. A control plane that keeps accepting requests on a bus that cannot deliver them and a database in flow control does not stay still. Every accepted request writes a record and then waits for RPC messages that may never arrive: an allocation claimed in Placement that never completes, a port created in Neutron and never bound, an instance in `BUILD` that will time out into `ERROR`. Each of those records makes the recovery slower and the platform's state less trustworthy, and none of them raises an alert.

## 4. Investigation

### The bus — [`rabbitmqctl cluster_status`](../series/one-command-one-investigation/16-rabbitmq-cluster-status.md) — READ ONLY

```text
rabbitmqctl cluster_status
rabbitmq-diagnostics check_running
rabbitmqctl list_queues name messages consumers | sort -k2 -n -r | head
```

On a Mnesia-era cluster the output has a `partitions` section; when it is not empty, the cluster has split and each side believes the other is gone. The logs on the affected nodes carry the line `Mnesia(rabbit@<node>): ** ERROR ** mnesia_event got {inconsistent_database, running_partitioned_network, …}`. On a Khepri-based cluster (the default for new clusters in recent 4.x releases) there is no such section: an unreachable node is simply missing from `running_nodes`, and the queue state is read with `rabbitmq-queues quorum_status <queue>`.

`list_queues` showed reply queues with messages and no consumers on one side, and queues with consumers and no messages on the other. The services were talking to a bus whose two halves did not agree on which queues existed.

### The database — [`SHOW STATUS LIKE 'wsrep_%'`](../series/one-command-one-investigation/17-galera-wsrep-status.md) — READ ONLY

```text
mysql -e "SHOW STATUS WHERE Variable_name IN ('wsrep_cluster_status','wsrep_cluster_size','wsrep_local_state_comment','wsrep_flow_control_paused','wsrep_local_recv_queue')"
```

On each node. `wsrep_cluster_status Primary` and `wsrep_cluster_size 3` everywhere: the cluster had not lost quorum. But one node was `Donor/Desynced` after an earlier event and `wsrep_flow_control_paused` was rising, which is the whole cluster slowing down to the pace of its slowest node. That explained the intermittent 504s: HAProxy sends writes to one node, and that node was waiting.

The database was a victim, not a cause: the retries and half-built records generated by the bus failure were the load it was pacing.

### The control plane — [`openstack compute service list`](../series/one-command-one-investigation/02-openstack-compute-service-list.md) and [`network agent list`](../series/one-command-one-investigation/08-openstack-network-agent-list.md) — READ ONLY

Roughly half of the compute services `down` and half of the agents dead, with no pattern by rack or by host generation. A heartbeat that is `up` on one side of a partition and missing on the other is exactly what a split bus produces: each service is connected to one side, and the conductors that write the heartbeats are connected to one side too. The scheduler was refusing hosts that were healthy, which is the `No valid host` two services away from its cause described in the [README](../README.md#from-symptom-to-root-cause).

### What was known, and what was not

Known: the bus was partitioned, the database was under flow control, half the platform's heartbeats were lost, and every request accepted since 10:00 was suspect. Not known: why the partition had happened, which accepted requests had been partially applied, and what the platform's state would look like after twenty more minutes of accepting requests.

## 5. Cause, in three layers

- **Immediate cause:** a network partition inside the RabbitMQ cluster, a few seconds of lost connectivity between two controllers on the cluster interconnect (a switch maintenance nobody had linked to the platform). With `cluster_partition_handling = ignore`, the cluster did not heal when connectivity returned; the two sides kept running independently.
- **Contributing cause:** the partition-handling setting had never been chosen. The deployment tool's default had been accepted, and the runbook for "a RabbitMQ node is down" was the only one that existed. A partition is not a node down: the procedure for a node that has left the cluster (confirm the majority, rejoin or reset the one node) is unsafe on a partitioned cluster, where resetting the wrong side discards the queues the services are using.
- **Why it reached production the way it did:** no alert on partitions; the first signal was users unable to create VMs, ten minutes after the split, by which time the platform had been accepting requests into a broken bus for ten minutes.

## 6. Decision

**What was done: controlled degradation.** Stop accepting requests first; repair on a platform whose state is no longer changing; verify; reopen.

```text
# STATE CHANGING — no new API requests reach the services; running instances are unaffected
echo "disable server nova_api/<controller>" | socat stdio /var/run/haproxy.sock      # for each API backend, each controller
# (the exact backend and server names depend on the deployment; list them first with "show stat")
```

Stopping the APIs does not silence the platform: conductors, schedulers and agents keep their own work going, and every agent on every host reconnects at once when the bus returns, which on a large platform is a load to expect.

```text
# POTENTIALLY DISRUPTIVE — in-flight RPC messages are discarded, not replayed
rabbitmqctl stop_app                      # on every node
rabbitmqctl purge_queue <queue>           # per queue, on the node that will start first; or a reset of the node state, see below
rabbitmqctl start_app                     # on the trusted node first, then the others
rabbitmqctl cluster_status                # READ ONLY: one cluster, no partitions section, all nodes running
```

The queues were purged deliberately: the backlog accumulated during the split was RPC traffic for operations whose state in the database no longer matched, and replaying it against a database that was about to be restarted would have created more inconsistency, not less. The services redeclare their queues when they reconnect, so an empty bus is a valid starting point for oslo.messaging. `purge_queue` is the documented per-queue command; the heavier alternative, returning the node to its initial state with `rabbitmqctl reset` (and `force_reset` on Mnesia clusters, which is deprecated and unsupported with Khepri), removes cluster membership as well and requires rejoining the nodes. Whichever is chosen, the RabbitMQ partition documentation's rule applies: the first node started is from the trusted side.

```text
# STATE CHANGING — one node at a time; the cluster stays Primary
systemctl restart mariadb                                    # node 1; wait for Synced before node 2
mysql -e "SHOW STATUS LIKE 'wsrep_local_state_comment'"      # READ ONLY, on the restarted node: Synced
```

The database restart was rolling because quorum had never been lost. A cluster that has lost quorum is a different operation, the one to rehearse: bootstrap from the most advanced node, identified by `grastate.dat` and `safe_to_bootstrap`, after `--wsrep-recover` when every node reports an unknown sequence number. Bootstrapping the wrong node discards the transactions the others had committed.

**Three verifications before reopening**, written before the stop:

1. `SHOW STATUS LIKE 'wsrep_%'` on all three nodes: `Primary`, size 3, `Synced`; `rabbitmqctl cluster_status`: whole; `list_queues`: consumers reconnected on the service queues.
2. `openstack compute service list` and `openstack network agent list`: every service `up`, every agent alive, none `forced_down`.
3. One test instance: created (`openstack server create --wait`), reached on its network, deleted. A component that is running is not a capability that works.

**Rejected: repair with the APIs open.** The fastest visible path. Its cost was unbounded: every minute of accepted requests added records that disagreed between Nova, Placement and Neutron, on a platform that could not tell which ones. The stop's cost was bounded and explicit: provisioning unavailable for 49 minutes, and a decision nobody could later describe as "the platform stayed up".

**Rejected: restart the RabbitMQ nodes one by one, without purging.** The runbook for a node down. On a partitioned cluster it restarts each node into whichever side it lands on; the messages preserved are the ones whose operations had already timed out on the client side.

**Rejected: wait for the partition to heal itself.** With `ignore`, it does not. With `pause_minority` it would have paused the smaller side, which is the setting the RCA led to.

## 7. Blast radius and rollback

- **API stop:** create, change and delete operations unavailable platform-wide; running instances, their storage and their traffic unaffected, because the control plane and the data plane fail separately. Reversible in seconds (`enable server`).
- **Bus restart with purge:** every in-flight operation lost; every service reconnects; agents resynchronise. Not reversible; accepted with the reasons written down.
- **Rolling database restart:** brief write pauses per node; reversible in the sense that the cluster is never without a Primary component.
- **Stop conditions:** a Galera node failing to reach `Synced`, a RabbitMQ node failing to rejoin, or the test instance failing any of its three steps stops the sequence before the APIs reopen.

## 8. Follow-ups

| Follow-up | Owner | Closed when |
| --- | --- | --- |
| `cluster_partition_handling` set deliberately (`pause_minority` on Mnesia-era clusters); on Khepri-based clusters, confirm the metadata store and the quorum-queue configuration instead | platform team | setting in configuration management, verified on the cluster |
| Alert on RabbitMQ partitions (Mnesia) or on nodes missing from `running_nodes` (Khepri), paging | monitoring owner | alert tested by inducing a partition in the test environment |
| Two runbooks where there was one: "node left the cluster" and "cluster partitioned", the second with a decision point ("stop the APIs?") and an escalation before any reset | runbook owner | both tested by an engineer who did not write them |
| Cluster interconnect and switch maintenance linked to the platform's change calendar | network team, platform team | maintenance notices reach the platform on-call |
| Clean-up of the records created during the degradation: instances in `BUILD`/`ERROR` from that window, orphaned allocations (`nova-manage placement audit`), unbound ports | platform team | `placement audit` clean, no orphaned records from the window |
| Stop authority and the "protection decision" communication template written into the escalation policy | operations lead | policy updated and read by the on-call rotation |

## 9. What you can reproduce

```text
rabbitmqctl cluster_status                                   # READ ONLY: which metadata store? is there a partitions section? what is cluster_partition_handling?
rabbitmqctl environment | grep -A1 cluster_partition_handling  # READ ONLY (Mnesia era)
mysql -e "SHOW STATUS LIKE 'wsrep_flow_control_paused'"      # READ ONLY, on each node: is one node pacing the cluster today?
echo "show stat" | socat stdio /var/run/haproxy.sock | cut -d, -f1,2,18 | head   # READ ONLY: do you know how to close the APIs in one command, and who may decide it?
```

And two questions: who has the authority to stop this platform, and did they know before reading this page?

## 10. Sources

- RabbitMQ, *Clustering and network partitions* (3.13 documentation: `partitions` in `cluster_status`, the `inconsistent_database, running_partitioned_network` log line, `cluster_partition_handling` modes, manual recovery: start from the trusted partition): https://www.rabbitmq.com/docs/3.13/partitions
- RabbitMQ, *Network partitions* (current: partition-handling strategies removed in 4.3.0; Raft-based recovery on Khepri): https://www.rabbitmq.com/docs/partitions
- RabbitMQ, `rabbitmqctl` (`cluster_status`, `list_queues`, `purge_queue`, `stop_app`, `start_app`, `reset`, `force_reset` deprecated and unsupported with Khepri): https://www.rabbitmq.com/docs/man/rabbitmqctl.8
- oslo.messaging, RabbitMQ driver (queues declared by the services on connection; quorum queue options): https://docs.openstack.org/oslo.messaging/latest/admin/rabbit.html
- Galera Cluster, *Quorum*, *Crash recovery* (`grastate.dat`, `safe_to_bootstrap`, `--wsrep-recover`), *Flow control*: https://galeracluster.com/library/documentation/
- HAProxy, runtime API (`disable server`, `enable server`, `show stat`): https://www.haproxy.com/documentation/haproxy-configuration-manual/latest/management/
- OpenStack HA guide, control plane stateful services: https://docs.openstack.org/ha-guide/control-plane-stateful.html
- Related episodes: [#16 `rabbitmqctl cluster_status`](../series/one-command-one-investigation/16-rabbitmq-cluster-status.md), [#17 `SHOW STATUS LIKE 'wsrep_%'`](../series/one-command-one-investigation/17-galera-wsrep-status.md), [#15 Placement allocations](../series/one-command-one-investigation/15-placement-allocations.md) for the clean-up
- Guide pages: [RabbitMQ](../troubleshooting/rabbitmq.md), [MariaDB / Galera](../troubleshooting/mariadb-galera.md), [Controlled degradation](../troubleshooting/control-plane-services.md#controlled-degradation)
- The book, *OpenStack, the Day After Tomorrow*, chapter 19 (when the safe decision is to stop), chapter 10 (the shared components and how they fail), chapter 11 (a runbook for a node down is not a runbook for a partition): https://github.com/soufian-zaouam/openstack-the-day-after-tomorrow

---

*Part of the [incident case studies](README.md) of the [OpenStack Production Guide](../README.md). The reasoning behind the decision is developed in [OpenStack, the Day After Tomorrow](https://github.com/soufian-zaouam/openstack-the-day-after-tomorrow).*
