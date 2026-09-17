# OpenStack services

When many operations fail at once, stop looking at individual VMs. Check the control plane as a whole: the APIs, the services behind them, and the shared components they depend on.

## 1. Can I authenticate at all?

```bash
openstack token issue
```

If this fails, every other check will fail too. Go to [Keystone](keystone.md).

## 2. Are the services reporting?

```bash
openstack compute service list
openstack network agent list
openstack volume service list
```

| Signal | Meaning |
| --- | --- |
| One compute or agent down | A host problem: start with that host |
| All computes or agents down at the same time | Rarely a host problem: suspect RabbitMQ, the database, or the conductor |
| `nova-conductor` or `nova-scheduler` down | Builds and many operations will stall |
| `cinder-volume` down for one backend | Only volumes on that backend are affected |

A service marked **up** only proves that its heartbeat is recent. It does not prove the service is processing requests.

## 3. Do the APIs answer?

```bash
openstack endpoint list --interface public
curl -s -o /dev/null -w '%{http_code} %{time_total}s\n' <endpoint-url>/
```

Any HTTP answer (200, 300, 401) proves that the load balancer and an API process responded. A timeout, a 502 or a 503 does not. Compare the answer time with your usual baseline.

At the load balancer, check how many backends are up for each API: one healthy backend out of three is not an outage yet, but it is a capacity and resilience problem.

## 4. Are the processes or containers healthy?

The exact commands depend on the deployment tool. Typical checks:

```bash
systemctl --failed
systemctl status <service-unit>
# containerised deployments
docker ps --filter health=unhealthy      # or: podman ps --filter health=unhealthy
```

## 5. Are the shared components healthy?

Every OpenStack service depends on the same few components. When several services fail together, look here first.

| Component | First check | Page |
| --- | --- | --- |
| RabbitMQ | Cluster status, partitions, alarms, queues without consumers | [RabbitMQ](rabbitmq.md) |
| MariaDB / Galera | Cluster size, Primary state, flow control | [MariaDB / Galera](mariadb-galera.md) |
| Keystone | Token issuance, Fernet keys, time | [Keystone](keystone.md) |
| Memcached | Reachable from API nodes; its loss makes token validation slow or failing | — |
| Load balancer and VIP | Backends up, VIP where expected | — |
| Time | NTP synchronised on every node (`chronyc tracking`) | — |
| Certificates | Expiry dates on API, RabbitMQ and database endpoints | — |

## 6. Upgrade readiness checks

These commands are read-only and also useful outside upgrades to detect inconsistencies:

```bash
nova-status upgrade check
neutron-status upgrade check
cinder-status upgrade check
placement-status upgrade check
```

## Controlled degradation

When the control plane is unstable, running instances usually keep running: the control plane (APIs, schedulers, conductors, message bus, databases) and the data plane (hypervisors, their disks and network paths) fail separately. What is lost is the ability to create, modify, migrate or delete resources, and the propagation of new network state.

This makes "stop accepting new requests, protect what is running" a credible option when an unstable control plane keeps accepting requests that leave inconsistent state behind (half-built instances, orphaned allocations, unbound ports).

> [!WARNING]
> **Changes state.** Stopping the APIs, withdrawing them from the load balancer, or restarting shared components are disruptive decisions. They need an owner, a communication to users, and explicit conditions for reopening. Stopping the control plane should mean the APIs, the message bus and the databases, not the agents running on compute nodes. Verify how your networking backend behaves before relying on this in an incident.

---
Next: [RabbitMQ](rabbitmq.md) · [MariaDB / Galera](mariadb-galera.md) · [Keystone](keystone.md)
