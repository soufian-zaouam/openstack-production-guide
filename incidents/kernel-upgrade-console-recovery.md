# Kernel upgrade: a critical VM no longer boots

**Symptom:** a VM does not come back after a guest kernel upgrade; its owners cannot rebuild it in the time the business can afford · **Decision:** recover what exists through the console and the previous kernel, then investigate · **Layers:** guest OS, instance console, bootloader · **Commands:** `openstack console log show` (READ ONLY), `openstack console url show` (READ ONLY), `openstack server reboot --hard` (STATE CHANGING), GRUB menu selection (guest-side, this boot only)

> Composite of real situations from production OpenStack platforms, generalised. No platform, organisation or person is identifiable; names, versions and timestamps are illustrative.

## 1. Context

A production platform hosting a VM that carries a business process: data, configuration and integrations accumulated over years, none of it reproducible from an image and a playbook in less than days. The VM's owners applied a routine operating-system update inside the guest, which installed a new kernel, and rebooted. The platform team was called forty minutes later.

Nothing about the platform is unusual. The VM has a boot volume on the storage backend, a noVNC console exposed by the compute host, and a guest image that keeps the previous kernel installed after an upgrade, which is the default behaviour of the common distributions.

## 2. Timeline

| Time | Event | Source |
| --- | --- | --- |
| 22:05 | guest OS update and reboot, by the VM's owners | change record, afterwards |
| 22:09 | service unreachable; owners retry a reboot from the dashboard, twice | Nova instance actions |
| 22:47 | platform on-call engaged: "the VM is broken, can you recreate it?" | ticket |
| 22:50 | `openstack server show`: `ACTIVE`, `power_state Running`, host healthy | Nova |
| 22:52 | console log: kernel panic during early boot of the new kernel; the previous kernel is still listed by the bootloader lines above it | `openstack console log show` |
| 22:55 | decision: recover on the previous kernel before anything else; owners agree | on-call, owners |
| 22:57 | console URL generated; hard reboot; GRUB menu interrupted; previous kernel selected | console, `server reboot --hard` |
| 22:59 | guest boots; service reachable; owners confirm | verification |
| 23:10 | previous kernel set as default in the guest, so that the next reboot does not repeat the incident | owners, in the guest |
| next day | RCA: the new kernel and an out-of-tree module in the guest; permanent fix planned by the owners | RCA |

## 3. Symptoms

From Nova's side there was no incident: the instance was `ACTIVE` and `Running`, the host was fine, the volume attached. From the users' side the service was down and the request that reached the platform team was "recreate it". That request contained a hypothesis (the VM is lost) and a solution (rebuild) that nobody had checked.

The first question in production is not always "how do we rebuild this?". Sometimes it is "what do we still have?".

## 4. Investigation

### Where the guest stopped — [`openstack console log show`](../series/one-command-one-investigation/06-openstack-console-log-show.md) — READ ONLY

```text
openstack console log show --lines 300 <server>
```

The log showed the bootloader listing two kernels, the boot of the new one, and a panic a few seconds in, before the root filesystem was mounted. Two facts, both decisive: the fault is in the guest and it is in the new kernel; and the previous kernel is still installed. The platform is not involved, and the way back is inside the VM.

The console log is the only view of a guest that cannot answer on the network. It is read from a file the compute host keeps for the domain; it survives the owners' two reboots because the panic repeats identically, but it would not survive a rebuild. The rebuild that was requested would have destroyed the evidence along with the VM.

### Is the platform side healthy — [`openstack server show`](../series/one-command-one-investigation/01-openstack-server-show.md) — READ ONLY

`OS-EXT-STS:vm_state active`, `task_state None`, `power_state Running`, `host_status UP`, the boot volume `in-use`. Nothing to fix here, and nothing to touch: every platform-side action (rebuild, resize, migrate) was excluded because the cause was already located.

### What the recovery depends on

Before choosing the path, the on-call listed what had to be true for it to work, and checked each point:

- the previous kernel is still installed in the guest (console log: yes);
- the bootloader is reachable from the console: GRUB shows its menu, or can be made to (console type: noVNC, so keyboard input works; on a serial console the menu must be enabled on that terminal);
- the platform exposes a console for this instance (`openstack console url show` returns a URL);
- the VM can be rebooted (owners' agreement; it is already down for its users);
- the cause is the new kernel, not the disk, the network or the hypervisor (console log: the panic is inside the kernel, before storage or network initialisation).

Any of these failing sends the recovery elsewhere: a rescue boot (`openstack server rescue`, STATE CHANGING, boots the instance from a rescue image with its disk attached), or a restore from the owners' backups.

## 5. Cause, in three layers

- **Immediate cause:** the new guest kernel panicked during early boot. The RCA the next day traced it to an out-of-tree kernel module the owners depended on, rebuilt against the new kernel by the package manager's hook but incompatible with it.
- **Contributing cause:** the update was applied and the VM rebooted with no snapshot beforehand and no plan for a failed boot. The owners' change was routine for them; it was not routine for a VM nobody could rebuild.
- **Why it reached the platform team as "recreate it":** the owners did not know that the console existed, nor that the previous kernel was still there. The platform's documentation for tenants described how to create instances, not how to recover one.

## 6. Decision

**What was done.** Recover first, on the known-good kernel; investigate afterwards, on a service that is up.

```text
# READ ONLY — open the console before rebooting: the GRUB menu is visible for seconds
openstack console url show --novnc <server>

# STATE CHANGING — the guest is already down for its users; --hard because a guest
# stuck in a panic will not answer the ACPI signal a --soft reboot relies on
openstack server reboot --hard --wait <server>
```

In the console, immediately after the reboot: interrupt the bootloader (Esc or Shift, depending on the image; cloud images often ship with `GRUB_TIMEOUT=0` and show no menu unless a key is held), select the previous kernel, boot. The selection applies to this boot only.

Once the service was reachable, the owners made the previous kernel the default in the guest (`GRUB_DEFAULT` and `update-grub` on Debian-family images, `grubby --set-default` on Red Hat-family images) so that the next reboot, planned or not, would not restart the incident. Then the RCA, with the new kernel installed but not selected, and the panic message from the console log as its first line of evidence.

**Rejected: rebuild the VM.** The request that arrived. It would have cost days, lost the evidence, and solved a problem that did not exist: the disk, the data and the configuration were intact.

**Rejected: `openstack server rescue`.** Valid, and the second option if the bootloader had been unreachable. It boots from a rescue image with the original disk attached, so an engineer can fix the guest from outside. Heavier than a menu selection, and it puts the platform team inside the tenant's filesystem, which is a decision in itself.

**Rejected: snapshot the boot volume before rebooting.** Considered, and worth doing when time allows: `openstack volume snapshot create --force --volume <volume> <name>` (STATE CHANGING on Cinder, harmless to the guest) preserves the disk as it was, for the RCA or for a restore. Here the reboot changed nothing on the disk that the two previous reboots had not already changed, and the owners chose speed. The choice was written down.

## 7. Blast radius and rollback

- **Hard reboot:** one instance, already unavailable. No effect on any other tenant or on the host.
- **Bootloader selection:** guest-side, this boot only; nothing on the platform changes. Reversible by the next reboot, which is precisely the risk the default-kernel change in step 6 closes.
- **Stop condition:** a panic on the previous kernel too would have meant the cause was not the kernel; the recovery would have stopped there and moved to rescue mode.

## 8. Follow-ups

| Follow-up | Owner | Closed when |
| --- | --- | --- |
| Tenant documentation: how to open the console, read the console log, and boot a previous kernel; what `server rescue` is for | platform documentation owner | page published and reviewed by a tenant team |
| A "snapshot before guest upgrade" recommendation in the same page, with the command and its cost | platform documentation owner | same page |
| The VM's owners hold a tested rebuild or restore path with a known duration | service owner | a restore has been exercised once |
| Instance-level criticality recorded (metadata or shared table), so that "cannot be rebuilt quickly" is known before the next incident | service owner, platform team | criticality recorded for this VM and its peers |
| RCA of the kernel and module incompatibility; permanent fix (module rebuilt or replaced) | service owner | new kernel boots in a test VM |

## 9. What you can reproduce

```text
openstack console log show --lines 100 <server>        # READ ONLY: does your image write a console log at all? (serial console configured in the image)
openstack console url show --novnc <server>              # READ ONLY: is a console available for every instance, or only some hosts?
```

In a test VM: apply a kernel update, reboot, and check whether you can reach the GRUB menu from the console before you need to. The images that hide the menu are the ones you will meet at 22:50.

## 10. Sources

- python-openstackclient, `console log show [--lines <num-lines>] <server>`: https://docs.openstack.org/python-openstackclient/latest/cli/command-objects/console-log.html
- python-openstackclient, `console url show [--novnc | --xvpvnc | --spice | --spice-direct | --rdp | --serial | --mks] <server>`: https://docs.openstack.org/python-openstackclient/latest/cli/command-objects/console-url.html
- python-openstackclient, `server reboot [--hard | --soft] [--wait] <server>`, `server rescue`: https://docs.openstack.org/python-openstackclient/latest/cli/command-objects/server.html
- python-openstackclient, `volume snapshot create [--volume <volume>] [--force] <snapshot-name>`: https://docs.openstack.org/python-openstackclient/latest/cli/command-objects/volume-snapshot.html
- Nova, *Rescue an instance*: https://docs.openstack.org/nova/latest/user/rescue.html
- GNU GRUB manual, `GRUB_TIMEOUT`, `GRUB_DEFAULT`, `GRUB_TERMINAL`: https://www.gnu.org/software/grub/manual/grub/grub.html
- Related episodes: [#01 `openstack server show`](../series/one-command-one-investigation/01-openstack-server-show.md), [#06 `openstack console log show`](../series/one-command-one-investigation/06-openstack-console-log-show.md)
- The book, *OpenStack, the Day After Tomorrow*, chapter 10 (recovery is a feature: recover what exists before rebuilding): https://github.com/soufian-zaouam/openstack-the-day-after-tomorrow

---

*Part of the [incident case studies](README.md) of the [OpenStack Production Guide](../README.md). The reasoning behind the decision is developed in [OpenStack, the Day After Tomorrow](https://github.com/soufian-zaouam/openstack-the-day-after-tomorrow).*
