# Decision record template

For a production decision made outside an incident, or a decision within one that will outlive it: a workaround kept in place, a setting chosen deliberately, a change postponed, a capability disabled, a platform closed. The point of the record is that in six months someone can tell whether the reasons still hold.

A decision record is short. If it needs more than a page, it is probably an incident record or a design document.

```markdown
# <Decision, as a sentence: "Keep cluster_partition_handling at pause_minority", "Stop the APIs during control-plane recovery">

Date: … · Status: proposed / accepted / superseded by <link> / retired · Owner: <role> · Review by: <date or condition>

## Context
The situation that required a decision: what was happening, what was known, what was not, what constraint made the obvious option unavailable.

## Decision
What was decided, in one paragraph, with the commands or settings it implies and their safety labels.

## Options considered
| Option | Cost | Risk | Why not (or why) |
| --- | --- | --- | --- |

The option that was taken is in the table too, with its cost and risk stated as honestly as the others.

## Consequences
What becomes true because of this decision: what is now possible, what is now forbidden, what has to be monitored, what it costs to keep.

## Conditions for revisiting
The facts that would make this decision wrong: a version, a capacity threshold, a repeated symptom, a date. When one is met, the record is reopened, not silently outgrown.

## For a workaround, additionally
Purpose · Owner · Scope (which hosts, instances, versions) · Known side effects · Detection (how you know it is still needed, or no longer working) · Recovery (how to remove it) · Exit condition.
```

## Notes

- **Repetition is evidence.** A workaround applied every week is a decision that has not been taken. Count the applications and put the count in the record.
- **Superseded, not deleted.** When a decision is replaced, the old record stays, marked superseded with a link, so that the history of why the platform looks the way it does survives the people who made it.
- **Decision rights belong in the record.** Who was entitled to take this decision, and was that known before it had to be taken? For disruptive decisions (stopping a platform, refusing a change, fencing a host) the answer should exist before the incident. See [Before you act](before-you-act.md), section 7.

---

*Part of the [OpenStack Production Guide](../README.md). The [incident record template](incident-record-template.md) covers an incident end to end.*
