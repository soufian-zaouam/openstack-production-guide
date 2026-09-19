# Ceph full OSD and CRUSH weights: six VMs paused in the same minute

**Symptom:** VMs of several projects unreachable on several compute hosts within one minute; Nova reports them `ACTIVE` · **Decision:** reclaim confirmed space and reweight the small OSDs; leave `full_ratio` alone · **Layers:** Ceph (OSD, CRUSH), QEMU (I/O error pause), Nova (power-state sync) · **Commands:** `virsh domstate --reason`, `ceph -s`, `ceph osd df tree` (READ ONLY), `rbd snap rm`, `ceph osd crush reweight` (STATE CHANGING), `virsh resume` (STATE CHANGING, outside Nova)

> Composite of real situations from production Ceph-backed OpenStack platforms, generalised. No platform, organisation or person is identifiable; names, counts, percentages and timestamps are illustrative. The investigation is run command by command in [episode #20 of One Command, One Investigation](../series/one-command-one-investigation/20-complete-investigation.md); this page is the incident record.

## 1. Context

A production platform with Ceph as the storage backend for boot volumes (Cinder on RBD) and ephemeral disks. Forty-eight OSDs over several hosts; a `vms` pool for Nova and a `volumes` pool for Cinder. Three weeks before the incident, a host with disks half the size of the others had been added, and its OSDs had been given a CRUSH weight set by hand to match the larger disks. The OpenStack dashboards were green; the Ceph health page was not on any dashboard the platform team looked at.

## 2. Timeline

| Time | Event | Source |
| --- | --- | --- |
| day −6 | `OSD_NEARFULL` appears in `ceph -s` for one OSD; nobody sees it | Ceph health, afterwards |
| 07:38:12 | first `No space left on device` from QEMU on RBD, on two hosts within the same second | QEMU logs |
| 07:41 | four VMs of one project unreachable; two more from two other projects within three minutes; five hosts | monitoring |
| 07:42 | first message in the channel: "should we just reboot them?" | channel |
| 07:44 | `server show` on two VMs: `ACTIVE`, `Running`, `host_status UP`, different hosts | Nova |
| 07:46 | every compute service up, every agent alive | Nova, Neutron |
| 07:49 | `virsh domstate --reason`: `paused (I/O error)`, on both hosts checked | libvirt |
| 07:52 | QEMU log: `rbd: … No space left on device`, 07:38, same minute on every host | QEMU |
| 07:56 | `ceph -s`: `HEALTH_ERR`, 1 full OSD, 3 nearfull, pool `vms` full; all 48 OSDs up and in | Ceph |
| 08:03 | `ceph osd df tree`: the four OSDs on the host added three weeks earlier, weights equal to the larger disks; imbalance growing for three weeks | Ceph, CRUSH tree |
| 08:10 | decision: reclaim space from what can be deleted with certainty; reweight; `full_ratio` untouched | decision record |
| 08:12–08:31 | deletions confirmed with owners, executed one at a time, OSD 31 watched; below 95 % at 08:31 | Ceph |
| 08:31–08:40 | `virsh resume` per domain, one host at a time, logged by hand; console log read per VM | libvirt, Nova |
| 08:45 | the four OSDs reweighted to their real capacity; backfill starts | Ceph |
| 15:10 | backfill complete; `HEALTH_OK` | Ceph |

## 3. Symptoms

Unreachable VMs, spread over five hosts and three projects, with a control plane that reported nothing wrong: `ACTIVE`, `Running`, services up. The spread ruled out a host and the healthy control plane ruled out the bus; the common factor had to be below both. The first proposal, a hard reboot of the six VMs, would have destroyed the paused guests' state, overwritten the QEMU logs that carried the cause, and brought the VMs back to a cluster that still refused writes.

## 4. Investigation

Read-only, in this order, each command chosen by the previous answer; the details are in the episodes.

1. [`openstack server show`](../series/one-command-one-investigation/01-openstack-server-show.md) on two VMs: not a host, not Nova. Nova's power-state sync logs a domain found `PAUSED` and does nothing; `ACTIVE` here is not a lie, it is a limit.
2. [`openstack compute service list`](../series/one-command-one-investigation/02-openstack-compute-service-list.md), [`network agent list`](../series/one-command-one-investigation/08-openstack-network-agent-list.md): not the bus, not the control plane.
3. [`virsh list --all`, `virsh domstate --reason`](../series/one-command-one-investigation/04-virsh-list-domstate.md): `paused (I/O error)`. QEMU's default error policy for a disk write that fails with `ENOSPC` is to pause the guest (`werror=enospc`); Nova sets no other policy. The guests were not crashed; they were stopped on the first failed write, with their filesystems intact.
4. [QEMU log](../series/one-command-one-investigation/05-virsh-dumpxml-qemu-log.md): `No space left on device` on `rbd`, 07:38, every host. The domain XML: every affected VM has its root disk on the `vms` pool.
5. [`openstack volume show`](../series/one-command-one-investigation/12-openstack-volume-show.md): Nova, Cinder and the host agree; nothing to reconcile. The databases were right; the storage was not.
6. [`ceph -s`, `ceph health detail`, `ceph df`, `ceph osd df tree`](../series/one-command-one-investigation/14-ceph-status.md): `HEALTH_ERR`, `OSD_FULL` on OSD 31 at 95.1 % with `full_ratio 0.95`, three OSDs `OSD_NEARFULL`, cluster average 71 %. A cluster is full when its fullest OSD is; the pool's PGs on that OSD refused writes; the six VMs happened to write to those PGs first.
7. `ceph osd df tree` read against the CRUSH tree: the four OSDs on one host, half-size disks, CRUSH weight equal to the large ones. Data had been placed as if they were as large as the rest for three weeks.

Twenty-two minutes from the first alert to the root cause; nothing changed.

## 5. Cause, in three layers

- **Immediate cause:** OSD 31 crossed `full_ratio`; the cluster refused writes to every PG it holds; QEMU paused the guests on the first write that failed.
- **Contributing cause:** four OSDs added with a CRUSH weight set by hand to the wrong value, so that CRUSH placed data on half-size disks as if they were full-size.
- **Why it reached production:** `OSD_NEARFULL` had been in `ceph -s` for six days. The platform's dashboards showed OpenStack health, and Ceph's health was not on them.

## 6. Decision

**Rejected first: raise `full_ratio` to 0.97.** One command, immediate effect, every VM resumable within minutes. And a cluster with an OSD at 97 % that has lost its safety margin: the next OSD failure on that host triggers recovery onto disks that cannot take it, and the outage becomes data at risk instead of VMs paused. The change that buys minutes and costs the margin.

**Rejected as a first step: reweight only.** Correct and slow: hours of backfill before the full OSD drops below the ratio, VMs paused the whole time.

**What was done.**

```text
# READ ONLY — what can be reclaimed with certainty
rbd du -p vms | sort -k2 -h | tail                      # slow and read-heavy on a large pool: one pool, once
rbd snap ls vms/<image>                                 # snapshots left by a backup job that had failed to clean up for two weeks
openstack volume list --all-projects --status error_deleting    # volumes abandoned a month ago, owners had given up

# STATE CHANGING — irreversible; each item listed, sized, confirmed with its owner in the channel, deleted one at a time
rbd snap rm vms/<image>@<snapshot>
openstack volume delete <volume>                         # after the owner's confirmation; force only when Cinder cannot
ceph osd df tree | grep -E 'osd\.31\b'                   # READ ONLY, after each deletion: watch the fullest OSD

# STATE CHANGING — reversible (reweight back); starts a backfill that raises latency for hours; consumers told
ceph osd crush reweight osd.31 <real-weight>             # then the three others
ceph -s                                                  # READ ONLY: backfill progress; osd_max_backfills left at its default
```

At 08:31 OSD 31 dropped below 95 % and the cluster accepted writes again. The reweight was applied after the VMs were back, so that the backfill did not compete with the guests' first writes.

**Resuming the VMs, outside Nova.** Nova had never moved the instances to `PAUSED` (its sync ignores that state), so `openstack server unpause` is refused with a 409: the API requires `vm_state PAUSED`. The domains were resumed with `virsh resume <instance-name>` on each host, one at a time (STATE CHANGING; the guest continues from the failed write, which QEMU retries), and libvirt's lifecycle event let `nova-compute` bring `power_state` back to `Running` within seconds. Because the resumes did not go through Nova they do not appear in `openstack server event list`; they were logged by hand in the incident record with host, domain and time. Each VM's console log was then read: paused, not crashed; filesystems clean.

## 7. Blast radius and rollback

- **Deletions:** touched no running VM; irreversible, which is why they were the items confirmed with owners.
- **Reweight:** reversible with `ceph osd crush reweight` back to the previous value; the backfill raises cluster latency for hours and was announced.
- **`full_ratio`:** untouched, and the reason written down, because it is the change the next on-call will reach for first.
- **`virsh resume`:** per domain; a guest that does not come back cleanly is stopped there and its console log kept.
- **Stop conditions:** OSD 31 not dropping after the confirmed deletions (the next step would have been a temporary `nearfull_ratio`/`full_ratio` discussion with the margin written out, not a reflex); any resumed guest showing filesystem errors in its console log.

## 8. Follow-ups

| Follow-up | Owner | Closed when |
| --- | --- | --- |
| Ceph health on the platform dashboard; `OSD_NEARFULL` a paging alert | monitoring owner | alert tested by lowering `nearfull_ratio` in the test cluster |
| CRUSH weight checked against disk size in the procedure for adding OSDs, with `ceph osd df tree` as the verification | storage team | procedure updated; next OSD addition reviewed against it |
| Backup job's snapshot clean-up fixed; orphaned snapshots reported weekly | backup owner | report empty two weeks running |
| `error_deleting` volumes cleaned up as a routine, not during incidents | platform team | routine exists; count at zero |
| Runbook note: `paused (I/O error)` on several hosts at once means storage; the first command is `ceph -s`, not a reboot; resume is `virsh resume`, logged by hand | runbook owner | note published |

## 9. What you can reproduce

```text
ceph osd df tree                                         # READ ONLY: does any OSD's weight disagree with its size? which OSD is fullest, and how far from the average?
ceph osd dump | grep -E 'full_ratio|nearfull_ratio'      # READ ONLY: the margins you are running with
rbd snap ls <pool>/<image>                               # READ ONLY, on a few images: snapshots nobody owns?
openstack volume list --all-projects --status error_deleting   # READ ONLY: how many, how old?
```

And one question for the dashboard: is `ceph -s` on it?

## 10. Sources

- Ceph, *Health checks* (`OSD_FULL`, `OSD_NEARFULL`, `POOL_FULL`; ratios as safety thresholds): https://docs.ceph.com/en/latest/rados/operations/health-checks/
- Ceph, *CRUSH maps* (`ceph osd crush reweight`; weight and device size): https://docs.ceph.com/en/latest/rados/operations/crush-map/
- Ceph, `rbd du`, `rbd snap ls`, `rbd snap rm`: https://docs.ceph.com/en/latest/man/8/rbd/
- Ceph, OSD configuration (`osd_max_backfills`, recovery throttling): https://docs.ceph.com/en/latest/rados/configuration/osd-config-ref/
- QEMU, `werror`/`rerror` defaults (`enospc` pauses the guest): https://www.qemu.org/docs/master/system/invocation.html
- libvirt, `virsh domstate --reason`, `virsh resume`: https://www.libvirt.org/manpages/virsh.html
- Nova, server states and the `unpause` action's state requirement (`nova/compute/api.py`): https://docs.openstack.org/api-guide/compute/server_concepts.html and https://opendev.org/openstack/nova/src/branch/master/nova/compute/api.py
- Related episodes: [#04 `virsh domstate --reason`](../series/one-command-one-investigation/04-virsh-list-domstate.md), [#14 `ceph -s`](../series/one-command-one-investigation/14-ceph-status.md), [#20 the complete investigation](../series/one-command-one-investigation/20-complete-investigation.md)
- Guide page: [Storage](../troubleshooting/storage.md)
- The book, *OpenStack, the Day After Tomorrow* (blast radius and rollback; the RCA structure): https://github.com/soufian-zaouam/openstack-the-day-after-tomorrow

---

*Part of the [incident case studies](README.md) of the [OpenStack Production Guide](../README.md). The reasoning behind the decision is developed in [OpenStack, the Day After Tomorrow](https://github.com/soufian-zaouam/openstack-the-day-after-tomorrow).*
