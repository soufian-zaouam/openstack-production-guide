# Root cause analysis

Recovery and root cause analysis (RCA) are different activities. Mixing them makes both harder.

## The incident sequence

```text
Restore service → Stabilize → Understand root cause → Fix → Prevent recurrence
```

| Stage | Goal | Done when |
| --- | --- | --- |
| **Restore service** | Reduce business impact now | The capability works again, even degraded |
| **Stabilize** | Stop the situation from getting worse | Platform state has stopped changing; guardrails are in place |
| **Understand root cause** | Explain every symptom with evidence | The explanation survives a review by someone else |
| **Fix** | Remove the cause, not the symptom | Verified under the conditions that caused the incident |
| **Prevent recurrence** | Change detection, procedures or design | The change exists and has an owner |

Recovery accepts uncertainty. RCA removes it. Preserve evidence *before* restoring service: a restart erases queue state, process state and sometimes the only log line that mattered.

## Symptom, trigger, root cause, contributing factors

| Term | Question | Example |
| --- | --- | --- |
| **Symptom** | What did users see? | VM creation fails |
| **Trigger** | What started it? | A network event split the RabbitMQ cluster |
| **Root cause** | Why could the trigger produce this impact? | Partition handling and network design allowed a split the services could not tolerate |
| **Contributing factors** | What made it worse or longer? | No alert on queues without consumers; runbook written for a single failed node, not for a partition |

"The service was restarted and it worked" is a recovery, not a root cause. So is "RabbitMQ had a problem": that is a location, not an explanation.

## Build the timeline first

1. Collect timestamps in UTC from every source: alerts, logs, tickets, chat, change records.
2. Place the first user-visible symptom, the first technical signal, and every action taken.
3. Look for the gap between the first technical signal and the first detection: it is often the most useful finding.

## Test the explanation

A root cause is credible when:

- it explains **all** the symptoms, including the ones that looked unrelated;
- it explains the **timing** (why then, not earlier);
- it explains the **scope** (why these hosts or projects, not others);
- removing it would have prevented the incident, or reduced it to something harmless.

If one symptom remains unexplained, the analysis is not finished.

## Ask "why" until you reach something you can change

Stop when the answer is something the organization can act on: a configuration, a design, a missing signal, a procedure, a decision right. Stopping at "human error" is almost always too early: ask why the system allowed the error to have that impact.

## RCA template

```text
Title:
Impact: capability, scope, duration, users affected
Timeline (UTC):
Detection: how, and how long after the first signal
Symptoms:
Trigger:
Root cause:
Contributing factors:
What went well:
What made recovery harder:
Actions: (each with an owner and a due date)
  - detect it earlier
  - prevent it
  - reduce its impact
  - recover faster
Evidence: commands, logs, request IDs, change records
```

## Blameless, not accountable-less

The purpose is to improve the system, not to find a culprit. Decisions made during an incident should be judged against what was known at the time, not against what is known afterwards.

---
Next: [Before you escalate](escalation-checklist.md)
