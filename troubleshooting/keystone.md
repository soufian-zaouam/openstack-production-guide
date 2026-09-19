# Keystone

Every OpenStack API call is authenticated. When Keystone, its keys or its cache misbehave, the whole platform fails at once, with errors that often look like permission problems.

## Symptoms

- `The request you have made requires authentication. (HTTP 401)` for users who were working a minute ago.
- Services logging authentication failures when talking to each other.
- Every API call is slow: token validation is slow (often memcached).
- `Policy doesn't allow <rule> to be performed. (HTTP 403)` after an upgrade or a policy change.

## 1. Can a token be issued and used?

```bash
openstack token issue
openstack catalog list
openstack endpoint list --service identity
```

> [!CAUTION]
> `openstack --debug <command>` shows the full HTTP exchange and is very useful, but its output can contain sensitive headers and service catalog details. Never paste it publicly without redacting it.

## 2. 401 or 403?

| Code | Meaning | Look at |
| --- | --- | --- |
| **401** | Authentication failed: credentials, token, or token validation | Keystone logs, Fernet keys, time, memcached, service user passwords |
| **403** | Authenticated, but not allowed | Role assignments, project scope, the service's policy |

```bash
openstack role assignment list --user <user> --project <project> --names
openstack project show <project>
```

## 3. Fernet keys

Keystone Fernet tokens are encrypted with keys that must be identical on every Keystone node. A rotation that removes a key still needed, or nodes with different key sets, breaks authentication for tokens issued by the other nodes.

```bash
# on each Keystone node: compare checksums, never display the keys
sha256sum /etc/keystone/fernet-keys/*
```

The checksums and file names must match across nodes.

> [!CAUTION]
> Fernet keys are secrets. Do not print, copy to tickets, or share their content. **Changes state:** `keystone-manage fernet_rotate` rotates keys; run it only through your deployment's rotation and distribution procedure.

## 4. Time

Token expiry depends on time. A node whose clock drifts rejects valid tokens or accepts expired ones.

```bash
chronyc tracking        # on every control plane node
```

## 5. Token validation path

Services validate tokens through keystonemiddleware, which caches results in memcached. If memcached is unreachable, every API call pays the full validation cost against Keystone, and Keystone becomes the bottleneck.

Check that API nodes can reach the memcached servers configured in their `[keystone_authtoken]` section, and look at Keystone's request rate and latency.

## 6. Policy and RBAC after upgrades

Recent releases moved to new default RBAC policies (project reader, member and manager personas, a service role, scoped admin), controlled by the `[oslo_policy] enforce_new_defaults` and `enforce_scope` options. An upgrade can therefore change what users, automation accounts and integrations are allowed to do.

- Test policy changes against real automation accounts before production.
- Treat local policy overrides as carried divergence: document them and review them at each upgrade.

## 7. Certificates

An expired certificate on the identity endpoint breaks every client and every service at once. Keep expiry dates visible and rotation rehearsed.

## Go deeper

Keystone is a reserve subject for season 2 of [One Command, One Investigation](../series/one-command-one-investigation/README.md) (`openstack token issue`, `openstack endpoint list`: the 401s and 503s that are not what they look like). For the exact messages, see the [index by error message](../errors.md#keystone).

---
Next: [Logs](logs.md) · Back to [OpenStack services](control-plane-services.md)
