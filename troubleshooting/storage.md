# Storage problems

A volume exists in three places: the **Cinder record**, the **Nova block device mapping**, and the **hypervisor**. Most storage incidents are these three disagreeing.

```text
Cinder volume → attachment → backend (Ceph RBD, iSCSI, FC, NFS…)
             → host path (os-brick, multipath, or librbd inside QEMU)
             → libvirt disk → guest device
```

## Control plane

```bash
openstack volume show <volume> -c status -c attachments \
  -c os-vol-host-attr:host -c migration_status -c multiattach
openstack server volume list <vm>                       # what Nova believes is attached
openstack volume attachment list --os-volume-api-version 3.27
openstack volume service list                           # cinder-volume per backend: up?
openstack volume backend pool list --long               # backend capacity as seen by the scheduler
```

## Compute node

```bash
virsh domblklist <instance_name>        # what QEMU really has open
lsblk
dmesg -T | grep -iE 'scsi|multipath|blk'
multipath -ll                           # active and failed paths
iscsiadm -m session -P 3                # iSCSI sessions and their state
```

### Ceph RBD

```bash
rbd status <pool>/volume-<volume-uuid>  # watchers: which clients hold the image open
ceph health detail
```

Cinder volumes on RBD are usually named `volume-<uuid>`. Nova ephemeral disks on RBD are usually named `<instance-uuid>_disk`.

## Three views must agree

| Cinder | Nova | Hypervisor | If they disagree |
| --- | --- | --- | --- |
| `volume show`, attachments | `server volume list` | `virsh domblklist` | You have found the problem, or you are about to create one with a state reset. Reconcile before any detach. |

## Symptoms and first questions

| Symptom | First question |
| --- | --- |
| `attaching` or `detaching` for minutes | Did cinder-volume and the backend answer? Check `volume service list` and the backend before touching the state. |
| `error_attaching` | Could the host connect? Look for os-brick lines in nova-compute on that host: iSCSI login, multipath, Ceph keyring and capabilities. |
| Guest I/O hangs, filesystem remounted read-only | Did the host lose paths? `multipath -ll`, `dmesg`, backend health, then the guest. |
| `in-use` in Cinder but absent from `domblklist`, or the reverse | Which view is true? Records and reality diverged, often after a failed detach or migration. |
| Boot from volume slow or timing out | Is the backend copying a large image? Image size, backend load, cinder-volume log. |
| Volume creation fails immediately | Scheduler capacity and filters: `volume backend pool list --long`, cinder-scheduler log. |

> [!CAUTION]
> **Two writers, one disk.** `openstack volume set --state <state> <volume>` and `openstack volume set --detached <volume>` **change state** and rewrite the Cinder record only. Marking a volume `available` while QEMU still holds it invites a second attachment and data corruption. Check `virsh domblklist` on the host (and `rbd status` on Ceph) first.

> [!WARNING]
> **Changes state.** Flushing multipath maps or logging out of iSCSI sessions on a compute node affects every instance using those paths on that host.

---
Next: [OpenStack services](control-plane-services.md) · Back to [Compute](compute.md)
