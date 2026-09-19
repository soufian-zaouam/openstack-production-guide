# One Command, One Investigation

A technical series for engineers who operate OpenStack in production: administrators, SREs, platform and cloud engineers.

Each episode starts from a production symptom and a single command, and follows the reasoning of an investigation:

```text
Command → Evidence → Hypothesis → Investigation → Correlation → Decision
```

The command is never the content. The investigation is the content. Every episode answers two questions:

- What can this command actually tell us during a production incident?
- What does it **not** tell us?

The series is part of the [OpenStack Production Guide](../../README.md) and a technical extension of the book [OpenStack, the Day After Tomorrow](https://github.com/soufian-zaouam/openstack-the-day-after-tomorrow). It follows the principles of the guide: observability before action, investigate first and change second, control the blast radius, keep rollback capability, do not confuse activity with resolution, document what was found.

## Structure of an episode

1. **Production situation** — a realistic symptom, not a story.
2. **The command** — with its safety label (READ ONLY / STATE CHANGING / POTENTIALLY DISRUPTIVE) and the path it takes through the components.
3. **What the command tells us** — the fields that matter, and why.
4. **What the command does NOT tell us** — the limits, and the assumptions it invites.
5. **What it lets us hypothesise** — the branch each observation sends you to.
6. **Next investigation** — the next command or component, still read-only whenever possible.
7. **Investigation chain** — the reasoning, drawn.
8. **Production lesson** — one idea, short.

## What ships with every episode

- **The episode** (`NN-<command>.md`) — the technical source of truth: context, investigation, commands, hypotheses, verifications, version notes, sources, precautions and the lesson. Written to be used on its own during an incident.
- **The investigation memo** (`memo/NN-memo.png`) — a one-page card, generated from `memo/NN-memo.json` with `memo/render_memo.py` so that every command on the card is exact. The JSON is the source; edit it and re-render rather than editing the image.


Commands that change state are never presented as troubleshooting steps. When one appears, it comes with its impact, blast radius, prerequisites, rollback, and the conditions under which it must not be run.

## How the series fits the rest of the guide

- The [troubleshooting pages](../../troubleshooting/README.md) are organised by symptom; each one points to the episodes that go deeper on its commands.
- The [incident case studies](../../incidents/README.md) show the same commands used under pressure, with the decision and its alternatives. Episode #20 runs one incident end to end; its record is [Ceph full OSD and CRUSH weights](../../incidents/ceph-full-osd-crush-weights.md).
- [errors.md](../../errors.md) maps exact error messages to the episode or page that explains them.

## Roadmap

The series follows one VM end to end: Nova's view, the hypervisor, the guest, then the network path, the storage path, and finally the control plane that made all of it possible or impossible. Levels: **F** foundation, **I** intermediate, **A** advanced.

### Part I — The instance, from Nova to the guest

| # | Command | Symptom | Layer | Level | Status |
|---|---|---|---|---|---|
| 01 | [`openstack server show`](01-openstack-server-show.md) | VM reported unreachable, restart requested | Nova API / database | F | published |
| 02 | [`openstack compute service list`](02-openstack-compute-service-list.md) | `host_status UNKNOWN`, several VMs on one host unreachable | nova-compute heartbeat | F | published |
| 03 | [`openstack hypervisor show`](03-openstack-hypervisor-show.md) | `No valid host` while capacity exists | resource tracker / Placement | I | published |
| 04 | [`virsh list --all`, `virsh domstate --reason`](04-virsh-list-domstate.md) | Nova says ACTIVE, the VM does not answer | libvirt | I | published |
| 05 | [`virsh dumpxml`, QEMU log, `ps`](05-virsh-dumpxml-qemu-log.md) | domain "running", VM frozen or QEMU gone | QEMU/KVM | A | published |
| 06 | [`openstack console log show`](06-openstack-console-log-show.md) | domain healthy, VM unreachable | platform / guest boundary | F | published |

### Part II — The network path

| # | Command | Symptom | Layer | Level | Status |
|---|---|---|---|---|---|
| 07 | [`openstack port show`](07-openstack-port-show.md) | IP known, no traffic | Neutron port binding | I | published |
| 08 | [`openstack network agent list`](08-openstack-network-agent-list.md) | ports DOWN on one host, slow DHCP | Neutron agents / ovn-controller | I | published |
| 09 | [`ovs-vsctl`, `ovs-ofctl`, `ofproto/trace`](09-ovs-vsctl-ofctl.md) | port ACTIVE, tap present, nothing passes | OVS (ML2/OVS) | A | published |
| 10 | [`ovn-nbctl`, `ovn-sbctl`, `ovn-trace`](10-ovn-nbctl-sbctl.md) | same symptom, OVN backend | OVN NB/SB, chassis | A | published |
| 11 | [`ip netns`, `ip -n <ns> addr`, `ss`](11-ip-netns.md) | no IP in the VM, metadata unreachable | DHCP / L3 / metadata namespaces | I | published |

### Part III — The storage path

| # | Command | Symptom | Layer | Level | Status |
|---|---|---|---|---|---|
| 12 | [`openstack volume show`, `volume attachment list`](12-openstack-volume-show.md) | volume `in-use`, disk invisible; volume stuck `attaching` | Cinder attachments, Nova BDM | I | published |
| 13 | [`virsh domblklist`, `multipath -ll`, `iscsiadm`, `rbd status`](13-os-brick-block-devices.md) | I/O frozen, guest disk errors | os-brick, Linux block device | A | published |
| 14 | [`ceph -s`, `ceph health detail`, `ceph df`](14-ceph-status.md) | VMs frozen in waves | Ceph | A | published |

### Part IV — The control plane, and correlation

| # | Command | Symptom | Layer | Level | Status |
|---|---|---|---|---|---|
| 15 | [`openstack resource provider allocation show`, `placement audit`](15-placement-allocations.md) | `No valid host`, host "full" after failed migrations | Placement | A | published |
| 16 | [`rabbitmqctl cluster_status`, `list_queues`, `rabbitmq-diagnostics`](16-rabbitmq-cluster-status.md) | `MessagingTimeout`, task states stuck everywhere | RabbitMQ | A | published |
| 17 | [`SHOW STATUS LIKE 'wsrep_%'`, `SHOW PROCESSLIST`](17-galera-wsrep-status.md) | intermittent API 500/504 | MariaDB Galera | A | published |
| 18 | [`server event list/show`, `journalctl`, request-id correlation](18-request-id-log-correlation.md) | an operation failed "somewhere" | logs across services | I | published |
| 19 | [`dmesg -T`, `systemctl`, `top`, `df`, `ss -s`](19-compute-host-as-a-machine.md) | OpenStack symptoms, host cause | the compute node as a machine | I | published |
| 20 | [Complete investigation](20-complete-investigation.md) | from the alert to the root cause | the whole chain | A | published |


## Rules

- Every command is verified against official documentation or source code before publication; sources are listed at the end of each episode.
- Version differences (API microversions, client versions, Nova releases) are stated when they change what a command shows.
- Nothing is presented as a fact when it is a hypothesis.
- All situations are generic and anonymised: no customer, employer, project, hostname or internal data.
- Read-only commands are the default. State-changing commands are labelled and framed as decisions.

## Licence

Same licence as the rest of this repository: [CC BY-SA 4.0](../../LICENSE).
