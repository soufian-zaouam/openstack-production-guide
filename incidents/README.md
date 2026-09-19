# Incident case studies

Anonymised production situations, written as root cause analyses: what was seen, what was checked, what was decided, what it cost, and what changed afterwards.

Each case is a composite of real patterns from production OpenStack platforms, generalised so that no platform, organisation, customer or person can be recognised. Names, timestamps, counts and versions are illustrative. What is not invented is the shape of the reasoning, the decision, and the reasons the alternatives were rejected.

| Case | Symptom | Decision | Layers |
| --- | --- | --- | --- |
| [Evacuation and fencing on shared storage](evacuation-fencing-shared-storage.md) | compute host stops reporting, instances unreachable, evacuation "ready" | fence through out-of-band management before `server evacuate` | Nova, Ceph RBD, QEMU |
| [Kernel upgrade: a critical VM no longer boots](kernel-upgrade-console-recovery.md) | VM does not come back after a guest kernel upgrade, no quick rebuild possible | recover through the console and the previous kernel, then investigate | guest, console, GRUB |
| [RabbitMQ partition: stopping the APIs](rabbitmq-partition-api-stop.md) | provisioning lost, running instances fine, RPC timeouts | stop the APIs before repairing the bus and the database | RabbitMQ, Galera, HAProxy |
| [Patching with limited capacity](patching-campaign-limited-capacity.md) | mandatory host patching, not enough room to live-migrate everything | differentiated strategy from a criticality table filled in by the consuming teams | Nova, live and cold migration, capacity |
| [CPU pinning, steal time and live migration](cpu-pinning-steal-time-live-migration.md) | steal time on dedicated-CPU instances, migration "fixes" it every time | stop the migrations, accept bounded steal, investigate the host | Nova, libvirt/QEMU, host kernel |
| [Ceph full OSD and CRUSH weights](ceph-full-osd-crush-weights.md) | VMs paused on several hosts within the same minute | reclaim confirmed space and reweight; leave `full_ratio` alone | Ceph, QEMU, Nova |

## The format

Every case follows the same structure, so that they can be compared and so that the reader can reproduce the investigation on their own platform:

1. **Context** — the platform, generalised: what matters for the reasoning, nothing that identifies it.
2. **Timeline** — the events with their source (alert, command output, log line, decision), in order.
3. **Symptoms** — what was visible, to whom, and what the first hypothesis in the room was.
4. **Investigation** — the read-only checks, in the order they were run, with what each one established and ruled out. Commands are labelled `READ ONLY`, `STATE CHANGING` or `POTENTIALLY DISRUPTIVE`. Where a check is covered by an episode of [One Command, One Investigation](../series/one-command-one-investigation/README.md), the case points to it rather than repeating it.
5. **Cause, in three layers** — the immediate cause, the contributing cause, and the reason it reached production.
6. **Decision** — what was done, the options that were rejected, and why.
7. **Blast radius and rollback** — written before the change, as they should be.
8. **Follow-ups** — each with an owner (a role, never a name) and a condition for closing it.
9. **What you can reproduce** — the read-only commands a reader can run on their own platform to check whether the same conditions exist.
10. **Sources** — the documentation each factual claim rests on.

The format is also available as a template: [incident record template](../methodology/incident-record-template.md).

## What these cases are not

They are not runbooks. A runbook says what to do; a case shows how a decision was reached under uncertainty, with the information available at the time. Several of the decisions here were not "technically clean"; they were the ones that kept the blast radius bounded and the way back open. The reasoning is meant to be reused, not the sequence.

The cases are also not the book's stories retold. Several of them appear in [OpenStack, the Day After Tomorrow](https://github.com/soufian-zaouam/openstack-the-day-after-tomorrow) as short *From the field* passages, where they serve an argument about how platforms are operated. Here they carry the technical file: the commands, the evidence, the alternatives, and the follow-ups.

---

*Part of the [OpenStack Production Guide](../README.md). Same licence as the rest of the repository.*
