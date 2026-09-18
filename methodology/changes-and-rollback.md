# Changes and rollback in production

Every action on a production platform is a change, including the ones made during an incident to "just try something". This page is the checklist to go through before acting.

## Validation before intervention

Answer each question in writing. The effort should be proportional to the consequence: a routine, reversible action needs a line; a database or cluster intervention needs all of it.

| Question | Why it matters |
| --- | --- |
| **What outcome do we need?** | "Restore VM creation" is an objective. "Restart RabbitMQ" is an action. |
| **What is the current state, with evidence?** | Without a known starting point, you cannot verify the result or return to it. |
| **What exactly will change?** | Components, hosts, number of workloads touched. |
| **What is the blast radius if it goes wrong?** | One VM, one host, one cell, the whole control plane? |
| **What is still unknown?** | State it explicitly, and why the residual uncertainty is acceptable. |
| **What are the stop conditions?** | Defined before starting, not improvised in the middle. |
| **How will we verify success?** | Verification is part of the change, and must be designed before execution. |
| **What is the rollback, and has it been done before?** | "We have rollback" should mean a credible path to a known-good state. |
| **Who decides, and who is informed?** | Technical assessment and acceptance of business risk are different roles. |

## Stop conditions

Agree on them before starting, especially for recurring maintenance:

- an expected dependency behaves differently than planned;
- the blast radius exceeds the approved boundary;
- monitoring does not show what you need to see;
- the rollback is no longer credible;
- workload performance crosses an unacceptable threshold;
- the capacity you counted on is not available;
- the decision owner cannot be reached.

Time already invested creates no obligation to continue. Once stopped, resuming is a new decision.

## Verification is part of the change

A change is not complete when the command returns. If the objective was to restore VM creation, verify that:

1. the affected dependency is healthy (not only its process);
2. the capability works end to end: create a test VM, reach it, attach a volume if relevant, delete it;
3. nothing else broke: services and agents still reporting, no new errors in the logs.

```bash
# control plane, read-only checks after a change
openstack compute service list
openstack network agent list
openstack volume service list
openstack server list --all-projects --status ERROR
```

## Rollback is designed, not assumed

- Keep the previous configuration and know how to redeploy it.
- For data changes, take a backup and know how long a restore takes.
- Some changes have no rollback (schema migrations, a purged queue, a deleted resource). Treat them as one-way doors and escalate the decision accordingly.

## Dangerous shortcuts

> [!WARNING]
> The following commands **change state** and are frequently misused during incidents. They rewrite what OpenStack *records*, not what the infrastructure *does*. Use them only when you know what the hypervisor, Neutron and Cinder actually hold.
>
> - `openstack server set --state <active|error> <vm>` (reset the instance state)
> - `openstack volume set --state <state> <volume>` (reset the volume state)
> - `openstack compute service set --down <host> nova-compute` (force the service down, a prerequisite for evacuation)
> - `nova-manage placement heal_allocations`, `nova-manage db archive_deleted_rows`

Forcing a compute service down tells Nova the host is dead. It does not make it dead. Before evacuating instances from a host, prove that the host is powered off (fencing), or two copies of the same instance may write to the same disk. See [Compute](../troubleshooting/compute.md#host-failure-and-evacuation).

## Record the decision

A minimum change record:

```text
Change / decision:
Date (UTC):
Decision owner:            Technical assessor:
Objective:
Current state and evidence:
What remains unknown:
Options considered, and why rejected:
Selected option and trade-off:
Stop conditions:
Verification:
Rollback:
Follow-up (document, measure, simplify, revisit):
```

The rejected options are as valuable as the selected one: they prevent the next team from reopening the same question without the same information.

## Go deeper

Incident case studies where this page's checks were used under pressure: [Patching with limited capacity](../incidents/patching-campaign-limited-capacity.md) · [CPU pinning, steal time and live migration](../incidents/cpu-pinning-steal-time-live-migration.md) · [Ceph full OSD and CRUSH weights](../incidents/ceph-full-osd-crush-weights.md).

---
Next: [Root cause analysis](root-cause-analysis.md)
