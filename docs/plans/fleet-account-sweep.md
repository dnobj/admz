# Read-only fleet account sweep — finding temp accounts that predate #315

**Status:** planned, not executed. **Authorized** by the owner on 2026-08-07
(`q_70025d93`, answered "yes"). Closes out the unknown left by
[#314](https://github.com/dnobj/admz/issues/314).

This is a procedure against **live cameras**, so it is written down before it is
run. Writing it first already changed it twice — see [Prerequisite](#prerequisite-no-verified-read-operation-covering-the-fleet)
and [Do it in the same window as #165](#do-it-in-the-same-window-as-165).

---

## Why a sweep is needed at all

Until #315 shipped, `TempCredentialManager` kept its records **in memory**. Three
failure modes each let a temp device account outlive ADMZ's only record of it:

- no persistence across restarts;
- after `_MAX_CLEANUP_ATTEMPTS` (5) the record was **deleted** while the account
  stayed on the device;
- the shutdown sweep was graceful-only.

The sharpest case: the MCP subprocess is reaped after `ADMZ_MCP_POOL_IDLE_SECONDS`
(default 300s) while the temp TTL was clamped to 3600s — **a one-hour credential
outliving its own tracker by 55 minutes, in the default configuration.**

#315 fixed all of that going forward, and `TempCredentialManager.list_orphaned()`
now reports accounts ADMZ created and could not remove. **It cannot report the
past**: it only knows about records written after it shipped. Anything already on
a camera predates the mechanism that would know about it.

So the question "are there orphaned admin accounts on the fleet right now?" is
not answerable from ADMZ's own data. It has to be asked of the devices.

## What we are looking for

Temp accounts have a **distinctive, machine-checkable name**. From
`admz/mcp/temp_credentials.py`:

```python
_USERNAME_PREFIX = "at_"
_USERNAME_HEX_LEN = 8          # secrets.token_hex(4) → 8 hex chars
```

So every account ADMZ ever created as a temp credential matches
**`^at_[0-9a-f]{8}$`** — 11 characters, inside the 14-character Axis limit.

That matters more than it sounds. The sweep does **not** have to decide what
counts as an "unrecognised" account, which would mean knowing every account the
operator ever created by hand and would produce a pile of false positives to
adjudicate. It looks for one regex.

**Classification, once the account list is in hand:**

| Account | Meaning |
|---|---|
| matches `at_[0-9a-f]{8}` **and** in `temp_credentials` as `active` | live, tracked — leave it, it has a TTL |
| matches **and** in `temp_credentials` as `orphaned` | already known (#315 found it) — nothing new |
| matches **and** absent from `temp_credentials` | **a pre-#315 orphan. This is the finding.** |
| does not match | operator's own account, or `root` — out of scope, do not report |

The last row is the one that keeps this sweep cheap and honest: we are not
auditing the operator's account hygiene, only ADMZ's own litter.

## Prerequisite: no *verified* read operation covering the fleet

`q_70025d93` says the sweep would "enumerate accounts per device **via the
existing catalog read path**". There isn't one that can be relied on across this
fleet. What the catalog actually has:

| Operation | What it is | Usable here? |
|---|---|---|
| `pwdgrp.cgi:add-user` / `remove-user` / `update-user` | the three `pwdgrp.cgi` ops | **No — all writes.** There is no `pwdgrp.cgi` read. |
| `user-management:getConfig` | REST `v2beta`, `risk_level: read-only`, `auth_level: viewer` | **Maybe.** Its own note says *"BETA, auto-drafted from OpenAPI — verify request/response shape + risk before relying on it."* Unverified, and `v2beta` will not exist on older firmware. |
| `ssh:listUsers` | REST `ssh/v2` | **No — different account space.** SSH users, not VAPIX device accounts. |

> An earlier revision of this plan said flatly that *no* read operation existed.
> That was wrong: I had grepped only `data/vapix/cgi/` and generalised from it.
> `user-management:getConfig` and `ssh:listUsers` both live under `data/vapix/rest/`.
> The corrected claim is narrower and is the one that matters — nothing verified
> covers the whole fleet.

VAPIX does support the universal read
(`docs/vapix-docs/vapix-network-video-system-settings.md:193`):

```
GET /axis-cgi/pwdgrp.cgi?action=get

admin="root,joe"
operator="root,joe,ellen"
viewer="root,joe,ellen,frank"
ptz="root,joe,ellen"
digusers="root,joe,ellen,frank"
```

**So step 0 is a catalog change in `axis-api-atlas`**, and it has two parts,
in this order:

1. **Try `user-management:getConfig` against one device first.** If it returns
   the account roster on this fleet's firmware, that is the modern path and
   costs nothing to confirm — but it must be *verified*, not assumed, because
   the operation says so itself. Promote it out of "auto-drafted" if it works.
2. **Add `pwdgrp.cgi:get` regardless.** This fleet spans four executor
   generations; `v2beta` will not be everywhere, and a sweep that silently skips
   older devices is worse than no sweep, because it reports a clean total that
   excludes exactly the units most likely to be stale.

That is a separate repo with its own version stream, so it is a PR there and an
atlas bump here.

Two things to get right in the new operation:

- **It discloses account names.** `risk_level: read-only` is correct for the
  confirmation gate — nothing is modified — but the response is not something to
  log verbatim at info level. Treat the username list like device metadata, not
  like a secret, and keep it out of chat context by default.
- **Not every device will answer either call.** Speaker and intercom firmwares
  vary. The sweep must treat a non-200 as *unknown*, never as *no orphans*.

### Why not use the snapshot `users` facet instead

`admz/snapshot/facets/users.py` already reads accounts — but it reads
`root.Properties.API.HTTP.AdminAccess*` **parameters**, which describe admin-access
properties, not the account roster. It cannot answer this question, and
stretching it to try would conflate two different things. Add the read operation.

## Do it in the same window as #165

**[#165](https://github.com/dnobj/admz/issues/165) already requires a production
atlas reinstall + service restart** — its catalog fix (`pwdgrp.cgi:add-user`
risk level `normal` → `service-affecting`) is on atlas `main` but production runs
an older non-editable copy, so the gate is still downgraded on the live fleet.

This sweep needs an atlas addition deployed to production too. **They are the
same maintenance action.** Doing them separately means two restarts of a service
that manages a live fleet, for no reason. Sequence:

1. Add `pwdgrp.cgi:get` to atlas, merge there.
2. One production window: reinstall the atlas copy (picks up **both** the #165
   risk-level fix and the new read op), restart `admz`, verify the #165 gate now
   resolves to `service-affecting`.
3. Run the sweep.

Step 2 is the owner-authorized part of #165 and is still outstanding.

## Execution

**Read-only. No writes, no deletions, under any outcome.** If the sweep finds
orphans, removing them is a **separate decision** and a separate procedure — the
authorization covers looking, not cleaning.

1. **Scope:** every device in the registry with stored credentials. Devices with
   no working credentials cannot be read and are reported as `unknown`, not
   `clean`.
2. **Serially, not in parallel.** The fleet is small enough that a sequential
   pass costs minutes, and a burst of authenticated requests across every camera
   is exactly the kind of load that is hard to distinguish from an incident if
   someone is watching the logs. One device at a time, with the executor's normal
   timeouts.
3. **Per device, record:** device id, host, HTTP status, the parsed username set,
   and the classification above. Nothing else — in particular **no passwords, and
   no response bodies**.
4. **Abort conditions.** Stop and report rather than pressing on if: more than
   three consecutive devices return 401 (something is wrong with stored
   credentials, not with the devices), or any device becomes unreachable
   *during* the sweep having been reachable at its start.
5. **Output:** a written summary — devices swept, devices unknown and why, and
   the list of pre-#315 orphans with the device each is on. Attach it to #314.

## What a clean result means, and what it does not

If the sweep finds nothing, that is genuine evidence: the `at_` signature is
exact, so a clean pass means no ADMZ-created temp account survives on any device
that answered. It says **nothing** about devices that did not answer, which is
why they are reported separately rather than folded into a total.

If it finds orphans, the exposure is bounded and worth stating plainly: an
unrecognised admin account on a camera on the operator's own LAN, created by
ADMZ, with a password ADMZ no longer holds. That is a real finding but not an
emergency — and the mechanism that created it is already fixed.

## Explicitly out of scope

- **Removing anything.** Separate decision, separate authorization.
- **Auditing operator-created accounts.** Only `at_[0-9a-f]{8}` is ours.
- **Any device that is not in the registry.** This is not a network scan.
