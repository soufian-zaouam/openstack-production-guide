# MariaDB / Galera

Every OpenStack service keeps its state in its own database, usually on a MariaDB Galera cluster. The databases are the platform's memory: when they degrade, services fail in ways that look unrelated.

## Symptoms that point to the database

- Many API calls fail or are slow at the same time.
- Logs contain `(pymysql.err.OperationalError)` errors such as `Lost connection to MySQL server during query`.
- Logs contain `WSREP has not yet prepared node for application use`: the node is not ready to serve queries.
- Deadlock errors (`Deadlock found when trying to get lock`) increase suddenly.

## 1. Is the cluster whole and in Primary state?

```bash
# on each database node, read-only
mysql -e "SHOW GLOBAL STATUS WHERE Variable_name IN (
  'wsrep_cluster_size','wsrep_cluster_status','wsrep_local_state_comment',
  'wsrep_ready','wsrep_connected','wsrep_cluster_state_uuid',
  'wsrep_flow_control_paused','wsrep_local_recv_queue_avg','wsrep_last_committed');"
```

| Variable | Healthy | If not |
| --- | --- | --- |
| `wsrep_cluster_size` | The expected number of nodes | A node left the cluster |
| `wsrep_cluster_status` | `Primary` | The node lost quorum and refuses queries |
| `wsrep_local_state_comment` | `Synced` | Joining, donor, or desynchronised |
| `wsrep_ready` / `wsrep_connected` | `ON` | The node cannot serve or is not connected |
| `wsrep_cluster_state_uuid` | Identical on all nodes | Nodes belong to different clusters (split) |
| `wsrep_flow_control_paused` | Close to 0 | Replication is throttling writes: a slow node holds the cluster back |
| `wsrep_local_recv_queue_avg` | Low | The node cannot apply writesets fast enough |

## 2. Is the load under control?

```bash
mysql -e "SHOW GLOBAL STATUS LIKE 'Threads_connected';"
mysql -e "SHOW VARIABLES LIKE 'max_connections';"
mysql -e "SHOW FULL PROCESSLIST;"
mysql -e "SHOW ENGINE INNODB STATUS\G"      # latest detected deadlock, lock waits
```

Signals: connections close to `max_connections`, long-running queries, many sessions from one service.

## 3. How do services reach the cluster?

OpenStack deployments usually send writes to a single Galera node through the load balancer, to avoid certification conflicts. Check which node currently receives writes, and whether the load balancer's health checks reflect the real Galera state.

## Recovery: the step to rehearse

After a full cluster outage, the cluster must be bootstrapped from the **most advanced** node.

```bash
# on each node, read-only
cat /var/lib/mysql/grastate.dat      # uuid, seqno, safe_to_bootstrap
```

- After a clean shutdown, the node with the highest `seqno` (and `safe_to_bootstrap: 1`) is the one to start first.
- After an unclean stop, `seqno` is `-1` on every node; the last committed position must be recovered first.

> [!CAUTION]
> **Changes state.** Bootstrapping the wrong node discards transactions the other nodes had committed. Before running `galera_new_cluster`, recovering positions with `mysqld --wsrep-recover` (or `mariadbd --wsrep-recover`), or editing `safe_to_bootstrap`, compare every node, involve the database owner, and follow the documented recovery procedure for your deployment tool. Many deployment tools provide their own recovery playbook: use it.

## Consistency between services

The state of one instance is spread across several databases: Nova (API and cell databases), Placement, Neutron, Cinder, Glance. Restoring them to different points in time produces a platform where services disagree with each other and with the hypervisors.

Read-only checks that reveal drift:

```bash
nova-manage placement audit --verbose          # allocations without instances
openstack server list --all-projects --status ERROR
openstack volume list --all-projects --status error
openstack port list --device-owner compute:<availability-zone> --status DOWN
```

A DOWN port is normal for a stopped instance; one attached to an ACTIVE instance is not.

> [!WARNING]
> **Changes state.** `nova-manage db archive_deleted_rows` moves soft-deleted rows to shadow tables, and `nova-manage db purge` deletes them. Useful for long-lived platforms, but take a backup first and run them in a maintenance window.

---
Next: [Keystone](keystone.md) · Back to [OpenStack services](control-plane-services.md)
