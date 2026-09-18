# One Command, One Investigation #18 — One request, six services, one ID

**Command:** `openstack server event list`, `openstack server event show`, `journalctl`, `grep req-<id>` · **Safety:** READ ONLY · **Layer:** instance actions, request IDs, service logs across the platform · **Level:** intermediate

> Command → Evidence → Hypothesis → Investigation → Correlation → Decision
>
> The question of every episode: *what can this command actually tell us during a production incident, and what does it NOT tell us?*

---

## 1. Production situation

Seventeen episodes have produced findings that all end the same way: "and the event list at that timestamp says who asked". A `shutting down, reason=destroyed` at 08:12 (#05). An allocation held by a migration that ended (#15). A port bound on the wrong host (#07). A volume `detaching` since 06:40 (#12). A conductor that stopped acknowledging at 03:12 (#16).

Each of those is one operation that crossed several services and stopped somewhere. Reconstructing it is not a matter of reading more logs. It is a matter of reading the right lines, in six services, on three or four hosts, in order. OpenStack gives every request an identifier that survives that journey, and Nova keeps a record of every action taken on an instance. This episode is about using both before concluding anything.

## 2. The command

```bash
openstack server event list <server-id>
openstack server event show <server-id> <request-id>
```

Then, with the request ID and the timestamps in hand, on each host involved:

```bash
journalctl -u nova-compute --since "<start>" --until "<finish>" | grep "req-<id>"
grep -h "req-<id>" /var/log/nova/*.log /var/log/neutron/*.log /var/log/cinder/*.log
```

**READ ONLY.** The event API is owner or admin (traceback and host fields admin by default); the logs need root or the log group on each host.

```text
client ──X-Openstack-Request-Id: req-<uuid>──▶ nova-api        [req-<uuid> user project]
                                                 │ RPC (the context travels with the message)
                                                 ▼
                                               nova-conductor   [req-<uuid> ...]
                                                 ▼
                                               nova-scheduler   [req-<uuid> ...]  → Placement (its own req id, plus the global one)
                                                 ▼
                                               nova-compute     [req-<uuid> ...]  → libvirt, os-vif, os-brick
                                                 ├─▶ neutron-server  [<global req> <neutron req> ...]
                                                 └─▶ cinder-api      [<global req> <cinder req> ...]

instance action  = one API request on one instance: action, request_id, start_time, user, project, message
action events    = the steps compute ran for it: compute_<step>, start_time, finish_time, result, host, traceback
```

Every service logs with oslo.log's context format: `[<global_request_id> <request_id> <user> <project> ...]`. Within Nova the request ID is the same from API to compute because the RPC context carries it. Across services (Nova calling Neutron or Cinder), each service issues its own request ID, and since Compute API 2.46 a global request ID can be passed in `X-Openstack-Request-Id` (format `req-` + UUID) and is logged by every service that receives it. Without the global ID, the join between services is made by timestamp and by the object (port ID, volume ID, instance ID) in the log line.

## 3. What the command tells us

### The instance's action history

```bash
openstack server event list <server-id>
```

```text
Request ID                                  Server ID   Action        Start Time                  Message
req-3f2a9c1e-...                            ...         live-migration  2026-09-18T03:11:52.000000  None
req-8b7d...                                 ...         stop          2026-09-18T08:12:40.000000  Error
req-c01e...                                 ...         create        2026-09-01T10:04:11.000000  None
```

Every API operation on the instance, most recent first, with its request ID and start time; `Message` is `Error` when the action failed. This list answers the question the previous episodes kept asking: what was done to this VM, when, and by which request. It survives the instance's deletion (microversion 2.21 and later), which is how the orphaned allocations of #15 get their story.

### The action's events

```bash
openstack server event show <server-id> <request-id>
```

```text
action          live-migration
request_id      req-3f2a9c1e-...
user_id / project_id
start_time      2026-09-18T03:11:52
updated_at      2026-09-18T03:14:03
message         Error
events
  - event        compute_check_can_live_migrate_destination
    start_time   03:11:53   finish_time  03:11:55   result  Success   host  compute-23
  - event        compute_pre_live_migration
    start_time   03:11:56   finish_time  03:12:03   result  Success   host  compute-23
  - event        compute_live_migration
    start_time   03:12:03   finish_time  03:14:03   result  Error     host  compute-17
    traceback    ... MigrationError: Live migration failed: operation aborted: migration out job: canceled by client ...
    details      (2.84+) the error message without the traceback
```

Each event is a step nova-compute ran, on which host, with its outcome. The sequence is the timeline of the operation, the `host` column (2.62+, admin) says where each step ran, and the `traceback` (admin) is the exception at the point of failure. Three things come out of it for free: the exact window to open the logs on (03:12:03 to 03:14:03), the two hosts involved, and the request ID to grep.

`updated_at` on the action, compared with the last event's `finish_time`, tells whether the action is still running or has simply been abandoned: an action with `Error` and no finished event is the stuck `task_state` from #01.

### The logs, joined by the request ID

With `req-3f2a9c1e` and the window:

```text
compute-17  nova-compute   03:12:03  [req-3f2a...] Starting live migration to compute-23
compute-17  nova-compute   03:13:58  [req-3f2a...] Migration operation was cancelled
compute-17  nova-compute   03:14:03  [req-3f2a...] Live migration failed ... MigrationError
ctl1        nova-conductor 03:14:03  [req-3f2a...] Exception during message handling: MigrationError
compute-23  nova-compute   03:14:04  [req-3f2a...] Rolling back pre live migration on destination
ctl1        neutron-server 03:14:04  [req-91aa... req-3f2a...] PUT /v2.0/ports/<port>  binding:host_id=compute-17   ← the rollback of the binding
```

Read in time order across hosts, the request tells its own story: the migration was cancelled on the source at 03:13:58 (the log line before it names the reason, often the `completion_timeout` or a libvirt error), rolled back on the destination, and Neutron was asked to put the port binding back. If the last line is missing, the port is bound on the wrong host (#07); if the conductor's rollback of allocations is missing, #15 has its orphan.

What makes this possible is the format every service shares, `logging_context_format_string`: `%(asctime)s ... %(levelname)s %(name)s [%(global_request_id)s %(request_id)s %(user_identity)s] %(instance)s%(message)s`. The `%(instance)s` field prefixes every line concerning an instance with its UUID, which is the second join key when the request ID is not available.

### The global request ID

```bash
curl -s -H "X-Auth-Token: $TOKEN" -H "X-Openstack-Request-Id: req-$(uuidgen)" \
     -H "OpenStack-API-Version: compute 2.46" "$NOVA_URL/servers/<server-id>"
```

A read-only call, with a global request ID chosen by the caller. Any client can send `X-Openstack-Request-Id: req-<uuid4>` with a request, and every service that receives the call, directly or through another service, logs it as `global_request_id`. On platforms where operators set it from their tooling, the join across Nova, Neutron, Cinder and Placement is a single grep. Where they do not, the object IDs and the timestamps do the joining.

## 4. What the command does NOT tell us

The event list records what went through the Nova API. A domain destroyed by hand with `virsh destroy` (#04), an OVS port removed by an agent restart (#08), a volume detached by a Cinder-side operation, a libvirt or QEMU crash: none of them is an instance action. An event list with nothing at 08:12 and a QEMU log with `shutting down, reason=destroyed` at 08:12 is precisely the finding: something outside Nova did it, and the host's logs (#19) and shell history are next.

The request ID is per request. A retry from the client is a new request ID; a periodic task in nova-compute (`_sync_power_states`, `update_available_resource`) logs with no request context at all, or with a service-generated one. The stop that Nova issued in #01 because the domain was found `SHUTDOWN` appears in the event list as a `stop` action whose user is the service user, not a human, and that is how a "nobody stopped it" mystery ends.

Timestamps are only as good as the clocks. Controllers and computes that drift by seconds turn a clean sequence into an argument; `chronyc tracking` on each host is part of the correlation, and the difference between the API's `start_time` and the compute's first log line is the drift estimate.

`traceback` shows where the exception was raised, not why the condition existed. `MigrationError: canceled by client` names the mechanism; the reason libvirt cancelled is in libvirt's own log and in the source host's QEMU log for that domain (#05).

Logs rotate and are truncated. An investigation two weeks after the fact reads what survived; the event list survives longer, which is why it comes first.

And a request ID does not cross into the guest, the switch, the SAN or the Ceph cluster. The join with #14 and #19 is by time alone.

## 5. What it lets us hypothesise

```text
event list: nothing at T; QEMU/libvirt log: something at T     → done outside Nova: hand, agent, crash              → host logs, shell history (#19)
action with Error, last event unfinished                        → operation abandoned mid-way; task_state stuck      → #01, its rollback never ran
compute_live_migration Error on source, no rollback on dest     → destination half-prepared; port and allocations    → #07, #15
stop action by the service user at T                            → Nova's own sync reacted to a dead domain           → why the domain died (#05)
same request id, minutes between two log lines on one host      → the host was blocked in between: libvirt, storage → #04, #13, #19
request id present in nova, absent in neutron/cinder            → the call never reached them: RPC, TLS, timeout    → #16, endpoints
many requests failing at the same step on many hosts            → a shared dependency: bus, database, Placement     → #16, #17, #15
clocks disagreeing by seconds across hosts                      → NTP; every timeline built so far is suspect       → chronyc on each host
```

## 6. Next investigation

Read-only, to complete the timeline:

```bash
journalctl -u nova-conductor -u nova-scheduler --since "<start>" --until "<finish>" | grep -E "req-<id>|<instance-id>"
grep -h "<port-id>\|<volume-id>" /var/log/neutron/server.log /var/log/cinder/*.log | sort
journalctl -u libvirtd --since "<start>" --until "<finish>"
chronyc tracking
```

And, when the event list is silent at the time that matters, the host as a machine, which is episode #19.

What we do not do at this stage:

- Retrying the failed action "to see if it works now" — STATE CHANGING. It creates a second request ID, a second set of events, and, if the first one left half a state behind (a port binding, a migration allocation, a reserved volume), a second half-state on top of it. The retry comes after the reconciliation, not instead of it.
- `openstack server set --state`, `nova-manage` or SQL to "clear" the stuck action — STATE CHANGING; #01 and #12 covered why editing a state is not resolving it.
- Turning on `debug = True` on a production service during the incident — STATE CHANGING, and the restart it usually requires is a bigger event than the log lines it will add. Debug logging is a decision taken for a reproduction, on one service, for a bounded time.
- Deleting or rotating logs to make room, on a host where the incident is being read — the evidence goes with them; copy first (`journalctl -u nova-compute --since ... > /root/incident-<id>/nova-compute.log`), then decide.

## 7. Investigation chain

```text
"Something happened to this VM at T"
        ↓
openstack server event list             which requests touched it, when, with what outcome
        ↓
openstack server event show <req>       the steps, the hosts, the failing step, the traceback, the window
        ↓
grep req-<id> on each host in the window  the same request, in time order, across services
        ↓
join with object ids (port, volume) in Neutron and Cinder logs; global request id when present
        ↓
  a step failed ────────────→ the component of that step (#04–#14)
  a step never ran ─────────→ the call did not arrive: bus, database (#16, #17)
  nothing in the event list ─→ done outside Nova: the host (#19)
        ↓
chronyc tracking                        before trusting any of the above
        ↓
Timeline written down: what happened, in order, with evidence — the input of the RCA (#20)
```

## 8. Production lesson

Nobody debugs a distributed system by reading more logs. They debug it by following one request through the services that touched it, in order, and writing down where it stopped. The request ID is that thread; the event list is where it begins; the timeline is the deliverable, and everything in #20 is built on it.

---

## Memo

![Investigation memo #18](memo/18-memo.png)

## Version notes

- Instance actions: `GET /servers/{id}/os-instance-actions` and `/{request_id}`; actions of deleted instances are returned from microversion 2.21; `events.host` and `events.hostId` from 2.62 (`host` admin by default); `events.details` from 2.84; `traceback` admin by default (`os_compute_api:os-instance-actions:events`); pagination with `--changes-since` (2.58) and `--changes-before` (2.66).
- Global request IDs: header `X-Openstack-Request-Id`, format `req-<uuid4>`, accepted from Compute API microversion 2.46 and propagated by oslo.context/oslo.middleware; each service also returns its own `X-Compute-Request-Id` / `X-Openstack-Request-Id` in responses.
- oslo.log defaults: `logging_context_format_string = %(asctime)s.%(msecs)03d %(process)d %(levelname)s %(name)s [%(global_request_id)s %(request_id)s %(user_identity)s] %(instance)s%(message)s`; `logging_default_format_string` (no context) prints `[-]`. Deployments that ship logs to a central store (Loki, OpenSearch) keep the same fields, and the request ID is the query.
- File locations differ by deployment: `/var/log/nova/*.log` (packages), `/var/log/kolla/nova/*.log` (Kolla Ansible), journald (`journalctl -u <unit>`) on systemd-managed services, `docker logs <container>` for container stdout.
- `openstack server event list` needs the instance UUID (names are resolved); `--long` adds user and project; `server event show` takes the request ID as printed.

## Sources

- Nova API reference, *Servers actions (servers, os-instance-actions)* (microversions 2.21, 2.51, 2.58, 2.62, 2.66, 2.84; `events.host`, `events.hostId`, `events.traceback`, `events.details`): https://docs.openstack.org/api-ref/compute/#servers-actions-servers-os-instance-actions
- Nova API reference source, `api-ref/source/os-instance-actions.inc` and `parameters.yaml` (`event_host`, `event_hostId`, `event_traceback`, `event_details`): https://opendev.org/openstack/nova/src/branch/master/api-ref/source
- Nova API guide, *Faults* (request IDs, global request ID in `X-Openstack-Request-Id` from microversion 2.46): https://docs.openstack.org/api-guide/compute/faults.html
- oslo.log configuration (`logging_context_format_string`, `logging_default_format_string`, `%(global_request_id)s`, `%(instance)s`): https://docs.openstack.org/oslo.log/latest/configuration/index.html
- oslo.context, request and global request IDs: https://docs.openstack.org/oslo.context/latest/
- oslo.middleware, middleware reference (`RequestId`): https://docs.openstack.org/oslo.middleware/latest/reference/index.html
- python-openstackclient, `server event list --changes-since/--changes-before/--long`, `server event show`: https://docs.openstack.org/python-openstackclient/latest/cli/command-objects/server.html
- systemd, `journalctl` manual (`-u`, `--since`, `--until`, `-k`): https://man7.org/linux/man-pages/man1/journalctl.1.html
- oslo.log, usage (context formatter, instance-prefixed lines): https://docs.openstack.org/oslo.log/latest/user/usage.html

---

*Part of the series [One Command, One Investigation](README.md), a technical companion to the book [OpenStack, the Day After Tomorrow](https://github.com/soufian-zaouam/openstack-the-day-after-tomorrow).*

Previous: [**#17 — Galera**](17-galera-wsrep-status.md). Next: [**#19 — `dmesg -T`, `journalctl -k`, `top`, `df`, `ss -s`**](19-compute-host-as-a-machine.md): the compute node as a machine.
