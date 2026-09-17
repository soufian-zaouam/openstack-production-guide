# Troubleshooting

Start with the symptom, follow its page in order, and stop where the evidence changes.

| Symptom | Start here |
| --- | --- |
| Something is wrong with a VM, and you do not know where to start | [First commands](vm-first-commands.md) |
| VM is ACTIVE but cannot be reached | [VM unreachable](vm-unreachable.md) |
| VM stays in BUILD, or goes to ERROR | [VM stuck in BUILD / ERROR](vm-build-error.md) |
| VM will not start on its host, or a host misbehaves | [Compute](compute.md) |
| Connectivity, DHCP, routers, floating IPs, OVS / OVN | [Networking](networking.md) |
| Volumes stuck, I/O errors, attach and detach problems | [Storage](storage.md) |
| Many operations fail at the same time | [OpenStack services](control-plane-services.md) |
| RPC timeouts, agents flapping | [RabbitMQ](rabbitmq.md) |
| Database errors, slow or failing APIs | [MariaDB / Galera](mariadb-galera.md) |
| 401, 403, authentication failures | [Keystone](keystone.md) |
| You need to prove what happened | [Logs and correlation](logs.md) |

Before any change, read [Before you act](../methodology/before-you-act.md) and [Changes and rollback](../methodology/changes-and-rollback.md).
