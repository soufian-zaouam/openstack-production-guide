# RabbitMQ

OpenStack services use RabbitMQ (through oslo.messaging) for RPC between their own components (for example nova-api, nova-conductor, nova-scheduler, nova-compute) and, with ML2/OVS, between neutron-server and its agents. When the bus degrades, the symptoms appear everywhere except in RabbitMQ.

## Symptoms that point to the bus

- Many operations stall or time out across several services.
- Compute services or network agents flap between up and down.
- Logs contain `MessagingTimeout: Timed out waiting for a reply to message ID <id>`.
- Logs contain `AMQP server on <host>:<port> is unreachable`.
- VMs stuck in `networking` or `scheduling` task states.

## 1. Is the cluster whole?

```bash
# on a RabbitMQ node
rabbitmq-diagnostics cluster_status
rabbitmq-diagnostics check_running
rabbitmq-diagnostics check_local_alarms
```

Signals: fewer running nodes than cluster members (an unreachable node is missing from the running nodes), a reported network partition on Mnesia-based clusters, memory or disk alarms. A node under a memory or disk alarm blocks publishers.

## 2. Are messages being consumed?

```bash
rabbitmqctl list_queues -p <vhost> name messages messages_ready messages_unacknowledged consumers
# queues holding messages with nobody consuming them
rabbitmqctl list_queues -p <vhost> --no-table-headers name messages consumers \
  | awk '$2 > 0 && $3 == 0'
```

A queue whose messages accumulate while its consumers disappear is a service that has stopped processing, whatever its process list says.

## 3. Who is connected?

```bash
rabbitmqctl list_connections name user state
rabbitmqctl list_consumers -p <vhost>
rabbitmq-diagnostics memory_breakdown --unit MB
```

Signals: connection churn (services reconnecting in a loop), a large number of connections from one host, memory consumed by queues or connections.

## 4. Quorum queues

Recent oslo.messaging releases recommend quorum queues (`rabbit_quorum_queue`). A quorum queue stays available while a majority of its members is up.

```bash
rabbitmq-queues quorum_status <queue> --vhost <vhost>
rabbitmq-diagnostics check_if_node_is_quorum_critical   # before stopping a node for maintenance
```

## Partitions

A network partition is the most dangerous RabbitMQ failure for OpenStack: services on different sides may talk to different halves of the bus.

- On clusters that use the **Mnesia** metadata store (older releases), behaviour during a partition is governed by `cluster_partition_handling`; `pause_minority` is the usual choice for OpenStack.
- On clusters that use the Raft-based **Khepri** metadata store (the only one from RabbitMQ 4.3.0), partition handling strategies no longer exist: `cluster_partition_handling` is accepted but has no effect.

Check which RabbitMQ version and metadata store your cluster uses before following any partition runbook.

> [!IMPORTANT]
> A runbook for **one node that left the cluster** is not a runbook for **a partitioned cluster**. For a single failed node: confirm the others still form a majority, then rejoin or reset that node. For a partition: do not touch the nodes yet, establish which side the services are using, decide whether to stop the APIs first, and escalate before resetting anything.

> [!CAUTION]
> **Changes state.** The following commands can discard messages or cluster membership:
>
> - `rabbitmqctl purge_queue <queue>` deletes all messages in a queue.
> - `rabbitmqctl stop_app` / `reset` / `forget_cluster_node` change cluster membership; `reset` erases the node's data.
> - Restarting the whole cluster makes every service and agent reconnect at once, which is a load to expect on a large platform.
>
> Purging queues during recovery means accepting that in-flight operations are lost rather than replayed. That is sometimes the right decision, and always a decision.

---
Next: [MariaDB / Galera](mariadb-galera.md) · Back to [OpenStack services](control-plane-services.md)
