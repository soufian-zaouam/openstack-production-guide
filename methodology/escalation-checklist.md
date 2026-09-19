# Before you escalate

Escalating to a platform team, a vendor or an upstream community is faster when the first message contains the evidence. This checklist is what an experienced engineer expects to receive.

## The minimum escalation package

```text
1. Symptom      What fails, observed by whom, since when (UTC)
2. Impact       Capability, scope (VMs / projects / hosts), business criticality
3. Scope        One VM, one host, one project, or systemic? Is it getting worse?
4. Identifiers  VM / port / volume UUIDs, request IDs, hostnames (as used internally)
5. State        Output of the commands below, with timestamps
6. Changes      What changed recently, and when
7. Actions      Everything already tried, in order, with the result
8. Hypotheses   What you think, and what evidence supports or contradicts it
9. Versions     OpenStack release, distribution, deployment tool, backend (OVS/OVN, storage)
```

## Commands to attach

```bash
# control plane, read-only
openstack server show <vm> -f json
openstack server event list <vm>
openstack server event show <vm> <request-id> -f json
openstack port list --server <vm> -f json
openstack server volume list <vm>
openstack compute service list
openstack network agent list
openstack volume service list
```

For a compute host:

```bash
# compute node, read-only
virsh list --all
virsh dumpxml <instance_name>
journalctl -u <nova-compute unit> --since "<start time>"   # unit name and log location vary by distribution
```

## Before sending

> [!CAUTION]
> Remove secrets before sharing any output: passwords, tokens, Fernet keys, `transport_url` values, database connection strings, and certificates. `openstack --debug` output can contain sensitive headers. When escalating outside your organization, also replace internal hostnames and addresses.

## What escalation is not

- A way to transfer the decision without the evidence.
- A reason to stop collecting information: keep the timeline running while you wait.

## Go deeper

Episodes of [One Command, One Investigation](../series/one-command-one-investigation/README.md) on the commands of this page: [#18 request IDs and log correlation](../series/one-command-one-investigation/18-request-id-log-correlation.md).

---
Back to: [Production troubleshooting principles](production-troubleshooting.md)
