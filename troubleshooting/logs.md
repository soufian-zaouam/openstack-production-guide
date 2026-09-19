# Logs and correlation

Logs are under `/var/log/<service>/`, in journald, or in the deployment tool's log directory for containerised deployments. Knowing which component to open saves more time than any search.

## Where to look

| Component | What to investigate |
| --- | --- |
| **Nova** | `nova-api`: request accepted or rejected · `nova-scheduler`: `No valid host`, filter results · `nova-conductor`: build orchestration, RPC timeouts · `nova-compute`: spawn, VIF plugging, volume attach, resource tracking |
| **Neutron** | `neutron-server`: port binding failures, database and RPC errors · agents (OVS, L3, DHCP, metadata): heartbeats, flow and namespace programming · OVN (`ovn-northd`, `ovn-controller`): database connectivity, translation |
| **Cinder** | `cinder-api` · `cinder-scheduler`: capacity and filter decisions · `cinder-volume`: backend driver errors, attach and detach |
| **Keystone** | Authentication: 401 and 403, token validation, Fernet key mismatches |
| **Glance** | Image upload and download, store backend errors, format and checksum |
| **Placement** | Allocation claims, 409 conflicts, inventory updates from compute hosts |
| **RabbitMQ** | Messaging: partitions, memory and disk alarms, connection churn |
| **MariaDB / Galera** | Database: cluster state changes, flow control, deadlocks, connection limits |
| **libvirt** | VM lifecycle: domain definition and start, device attach, migration |
| **QEMU** | VM execution: `/var/log/libvirt/qemu/<instance_name>.log`, start failures, crashes, device errors |
| **OVS / OVN** | Networking: `ovs-vswitchd` and `ovsdb-server` errors, `ovn-controller` connectivity, chassis registration |

## Correlate, or it is not evidence

A log line becomes evidence when it is tied to a time, a request and a resource.

| Key | How to use it |
| --- | --- |
| **Timestamps** | Compare in UTC, from clocks you trust (NTP on every node). Two minutes of skew reorders the story. |
| **Request IDs** | Every OpenStack log line for an API request carries `req-<uuid>`. `global_request_id` carries the caller's ID into the services it calls. `openstack server event list <vm>` gives you the request ID of each action. |
| **VM UUID** | Nova logs, Placement (as the consumer), libvirt domain XML (`<uuid>`) |
| **Port UUID** | neutron-server, agents, OVN `Port_Binding`, the tap name on the host |
| **Volume UUID** | Cinder logs, os-brick lines in nova-compute, RBD image name `volume-<uuid>` |
| **Recent changes** | Deployment runs, configuration commits, maintenance records |

## Follow one request

```bash
# 1. get the request ID
openstack server event list <vm>

# 2. follow it on a controller (adapt paths to your deployment)
grep -rh "req-<uuid>" /var/log/nova/ /var/log/neutron/ /var/log/cinder/ | sort

# 3. then on the compute host that handled the build
grep -h "req-<uuid>" /var/log/nova/*.log
```

Sorting works because OpenStack log lines start with a timestamp; make sure all nodes log in the same time zone.

## Read logs with a baseline

- An `ERROR` line that appears every day is not your incident. Know what normal noise looks like.
- The first error in time is more informative than the most frequent one.
- A traceback shows where the code failed, not necessarily why. Read the lines before it.
- Absence is a signal: a service that stops logging may have stopped working.

## Increase verbosity carefully

Enabling `debug = True` helps, but it changes configuration, may require a restart, and produces a large volume of logs that can contain sensitive data.

> [!WARNING]
> **Changes state.** Treat debug logging as a change: scope it to one service or one host, limit it in time, and revert it.

## Go deeper

Episodes of [One Command, One Investigation](../series/one-command-one-investigation/README.md) on the commands of this page: [#18 request IDs and log correlation](../series/one-command-one-investigation/18-request-id-log-correlation.md).

Looking for an exact error message? See the [index by error message](../errors.md).

---
Back to: [Troubleshooting index](README.md)
