# Incident record template

The format used by the [incident case studies](../incidents/README.md), ready to copy. Fill it during the incident where you can (timeline, decisions, blast radius), and complete it within days, while the evidence still exists.

The order matters: the timeline before the cause, the evidence before the explanation, the rejected options next to the decision. A record that contains only the fix is a change log, not an incident record.

```markdown
# <Short title: the symptom, then the decision>

**Symptom:** … · **Decision:** … · **Layers:** … · **Commands:** `…` (READ ONLY), `…` (STATE CHANGING), `…` (POTENTIALLY DISRUPTIVE)

Incident ID: … · Severity: … · Start: <first user-visible effect> · Detected: … · Mitigated: … · Resolved: … · Owner of this record: <role>

## 1. Context
What matters for the reasoning: platform shape, backends, versions where they change the behaviour, what was known about the workloads. Nothing that identifies a customer or a person if the record will leave the team.

## 2. Timeline
| Time | Event | Source |
| --- | --- | --- |
| | alert / observation / decision / change / verification | the command, log, alert or person that established it |

Every line has a source. Clocks: state which host or system the time comes from, and whether they were in sync (`chronyc tracking`).

## 3. Symptoms
What was visible, to whom, since when, and what the first hypothesis in the room was. Include the proposals that were made and not taken; they are part of the record.

## 4. Investigation
The checks in the order they were run, each with its safety label and what it established or ruled out. Read-only until the decision. Link to the guide page or series episode for the command instead of re-explaining it.

## 5. Cause, in three layers
- **Immediate cause:** what failed.
- **Contributing cause:** what allowed it to fail that way.
- **Why it reached production:** the gap in monitoring, procedure, review or design that let it become an incident.

## 6. Decision
What was done, as commands with their labels and their order.
**Rejected:** each alternative, with the reason it was rejected. The obvious fix belongs here when it was not taken.

## 7. Blast radius and rollback
Written before the change: what each change affects, whether it is reversible and how, the stop conditions.

## 8. Follow-ups
| Follow-up | Owner (role) | Closed when |
| --- | --- | --- |

A follow-up without an owner or a closing condition is a wish.

## 9. What can be reproduced
The read-only commands another engineer can run to check whether the same conditions exist on another platform, and to verify the findings of this record.

## 10. Sources
Documentation for each factual claim about component behaviour; related guide pages and episodes; the change records referenced.
```

## Notes on filling it

- **Anonymise at the source** if the record may be shared outside the team: placeholders for hosts and projects, documentation IP ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`), no ticket numbers from external systems.
- **Label every command** with `READ ONLY`, `STATE CHANGING` or `POTENTIALLY DISRUPTIVE`. The label is part of the record because the next reader will copy the commands.
- **Actions outside the control plane** (`virsh resume`, a BMC power-off, a database correction) do not appear in OpenStack's event history. Log them by hand, with host, object and time, or they will be invisible to the next investigation.
- **Blameless, not accountable-less**: the record names roles and decisions, not people and faults. See [Root cause analysis](root-cause-analysis.md).

---

*Part of the [OpenStack Production Guide](../README.md). The [decision record template](decision-record-template.md) covers a change or a workaround decided outside an incident.*
