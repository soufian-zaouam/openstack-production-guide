# VM troubleshooting: first commands

Eleven commands cover most first looks at a problematic VM. Each one answers a specific question. All of them run from the control plane and are read-only; several fields require admin credentials.

> [!TIP]
> Use `-c <field>` to keep only what answers your question, and `-f json` when you save evidence.

| Command | Question it answers | Signal to look for |
| --- | --- | --- |
| `openstack server show <vm>` | Where is this VM, in what state, and what failed? | `status`, `OS-EXT-STS:vm_state` / `task_state` / `power_state`, `fault` (only when in ERROR), `OS-EXT-SRV-ATTR:host`, flavor, image, addresses |
| `openstack server list --all-projects --project <project>` | Is it one VM, or a pattern? | Several VMs in BUILD or ERROR with the same host, flavor or image. Also try `--host <compute>` and `--status ERROR`. |
| `openstack server event list <vm>` | What was done to this VM, when, and with what result? | The last action and its **request ID**, your key into the logs |
| `openstack server event show <vm> <request-id>` | What happened inside that action? | Failed events and their traceback (admin) |
| `openstack console log show <vm>` | Did the guest boot, and how far did it get? | Kernel panic, filesystem check or emergency shell, cloud-init without DHCP lease or metadata. An empty log is a signal too. |
| `openstack hypervisor list` | Are the hypervisors up and enabled? | State `down`, status `disabled`, a host missing from the list |
| `openstack hypervisor show <compute>` | What does Nova know about this host? | State, status, host IP. Since compute API microversion 2.88, resource usage is no longer returned here: ask Placement (see [Compute](compute.md)). |
| `openstack compute service list` | Is Nova alive, and are the computes reporting? | `nova-compute` down (stale heartbeat), disabled with a reason, conductor or scheduler down |
| `openstack volume show <volume>` | Is the volume where Nova thinks it is? | `status` (in-use, attaching, error_attaching…), `attachments`, `os-vol-host-attr:host` |
| `openstack port show <port>` | Is the VM's port bound, and up? | `status` ACTIVE or DOWN, `binding_vif_type` = `binding_failed`, `binding_host_id` different from the VM host |
| `openstack network show <network>` | Is the network what the VM expects? | Network type and segment, `mtu`, subnets, `port_security_enabled`, admin state |
| `openstack server show --diagnostics <vm>` | What does the hypervisor report right now? | CPU time, memory, NIC and disk counters (admin). Counters that never move: idle, hung, or disconnected. |

> [!NOTE]
> The diagnostics call is an option of `openstack server show`. The unified client has no separate `server diagnostics` command.

## Find the VM's other identities first

A VM has several identifiers across services. Collect them before going deeper:

```bash
# control plane, read-only
openstack server show <vm> -c id -c OS-EXT-SRV-ATTR:host -c OS-EXT-SRV-ATTR:instance_name
openstack port list --server <vm>          # port UUIDs, MAC and fixed IPs
openstack server volume list <vm>          # attached volume UUIDs
```

- `OS-EXT-SRV-ATTR:host` is the compute host.
- `OS-EXT-SRV-ATTR:instance_name` is the libvirt domain name (for example `instance-0000abcd`), which is what `virsh` expects.
- The tap device on the host is named `tap` followed by the first 11 characters of the port UUID.

## Reading the state fields

| Field | What it tells you |
| --- | --- |
| `status` | The API's summary (ACTIVE, BUILD, ERROR, SHUTOFF, VERIFY_RESIZE, MIGRATING…) |
| `OS-EXT-STS:vm_state` | The stable state Nova recorded |
| `OS-EXT-STS:task_state` | The operation in progress, if any. A task state that does not change is the most useful signal for stuck VMs. |
| `OS-EXT-STS:power_state` | What the hypervisor reported at the last sync: Running, Shutdown, Paused, Crashed… (the API returns a number, the client shows its name) |

When `vm_state` and `power_state` disagree, Nova's record and the hypervisor disagree. Find out which one is right before acting.

---
Next: [VM ACTIVE but unreachable](vm-unreachable.md) · [VM stuck in BUILD / ERROR](vm-build-error.md)
