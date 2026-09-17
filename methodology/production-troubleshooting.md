# Production troubleshooting principles

Troubleshooting a production OpenStack platform is not the same activity as debugging a lab. The platform carries workloads that matter, its state has history, and every action you take is itself a change. This page describes the reasoning the rest of the guide relies on.

## Symptom, hypothesis, cause

Keep three things separate, and write them down separately during an incident:

| Term | Meaning | Example |
| --- | --- | --- |
| **Symptom** | What someone observed | "VM creation fails with `No valid host was found`" |
| **Hypothesis** | A candidate explanation, not yet proven | "The scheduler has no capacity for this flavor" |
| **Evidence** | An observation that supports or rejects a hypothesis | "`openstack allocation candidate list` returns candidates for the flavor's resources" → capacity is not the cause |
| **Root cause** | The explanation that accounts for *all* the evidence | "Compute services are reported down because heartbeats no longer reach the conductor" |

A good investigation tries to **disprove** hypotheses as well as confirm them. OpenStack produces plausible explanations in abundance: a scheduling failure looks like a Nova problem, a network timeout looks like a Neutron problem, a slow operation looks like a capacity problem. The architecture makes each of them plausible without making any of them true.

## Where a symptom appears is not where it starts

Services depend on each other and on shared infrastructure:

```text
Keystone ── authenticates every call
Nova API ── Conductor ── Scheduler ── Placement
   │            │
   │       RabbitMQ (RPC inside Nova, and to Neutron agents)
   │            │
MariaDB / Galera (one database per service)
   │
Compute host ── libvirt / QEMU ── Neutron (port binding) ── Cinder / Glance
```

A failure anywhere in this graph can surface as "VM cannot be created". Investigate along the dependency path, not along the service named in the error.

## Evidence proportional to consequence

- A read-only command needs little justification.
- Restarting a service needs evidence and a reason.
- A database intervention, a queue purge, or a cluster bootstrap needs strong evidence, an owner, and a way back.

The burden of proof rises with blast radius and irreversibility. When uncertainty is high and waiting is cheap, collecting more evidence is the safer action.

## Reduce the experimental surface

The best test is often smaller than the platform:

- one VM compared with a known-good VM;
- one compute host isolated from the scheduler (disabled, not stopped);
- one request followed by its request ID;
- one dependency observed without changing anything else.

## Do not stack uncertainty

Never change several things at once during an incident. If the operating system, the network configuration and a service configuration all change together, the next unexpected behaviour cannot be attributed to any of them.

## Recovery is not root cause analysis

Restoring service and understanding the failure are different activities, often done at different speeds and by different people. Recovery accepts uncertainty to reduce impact now. Root cause analysis removes uncertainty, and cannot be rushed without being wrong. See [Root cause analysis](root-cause-analysis.md).

## Golden rules

1. Understand before changing.
2. Stability comes before new features.
3. Protect what is working.
4. Never change production without a rollback strategy.
5. A command is not a diagnosis.
6. Logs without context are not evidence.
7. Correlate symptoms across layers.
8. Document production decisions.
9. Automate repetitive read-only diagnostics first.
10. Do not confuse recovery with root cause analysis.

## The Production Question

> **What do I know, what do I not know, and what evidence do I need before touching production?**

- **What do I know?** Facts observed directly, with a timestamp and a source. Not what a dashboard implies, not what worked last time.
- **What do I not know?** Hypotheses and assumptions, stated as such. Uncertainty is a risk signal, not a weakness to hide.
- **What evidence do I need?** The smallest safe observation that would change the decision. If it can only be obtained by changing production, you have reached a decision point, not a diagnostic step.

---
Next: [Before you act](before-you-act.md)
