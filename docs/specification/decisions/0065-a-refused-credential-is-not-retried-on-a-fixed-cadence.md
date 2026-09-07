# ADR-0065 — A refused credential is not retried on a fixed cadence: the sweep holds, and nothing tries the same pair twice in one pass

**Status:** Accepted — 2026-09-07
**Closes when shipped:** #469 (the sweep's hold) · #475 (the onboarding dedupe)
**Relates to:** [ADR-0061](0061-entry-credentials-and-the-admz-account.md) (asked for the lockout measurement) · [ADR-0064](0064-a-device-admz-cannot-authenticate-to-is-never-online.md) (bounded one onboarding pass; deferred this to "its own issue rather than a paragraph here", decisions-taken-by-default row 8) · [ADR-0063](0063-capability-knowledge-is-local-first.md) (the persisted escalating-TTL shape this reuses) · FR-HLT-009/011, NFR-HLT-001/002, FR-CRED-013 · #138 (five-figure failure counters), #149/#150 (corroborated rejection)

_Plan-first per `process.md`: this document merges before any code. File:line references are against master `5c88fb9`._

## Context

ADMZ reaches a device it does not yet manage by trying credentials, which means deliberately failing to authenticate. How an Axis unit answers repeated failures — lockout, throttle, or nothing — is **unmeasured**. ADR-0061 asked for the measurement against a spare unit; it was never run, and ADR-0064 decision 7 still holds #411 slice F on it.

ADR-0064 slice C bounded the place that was easy to reason about: one onboarding pass now costs at most 8 credentialed operations, once, at registration. It left the larger exposure untouched and said so in as many words.

**A device in `auth_failed` is re-probed with its known-bad credential on every sweep, forever.** `probe_device` (`admz/fleet/health.py:1181-1189`) takes no previous record and has no status-dependent short circuit, so each 60-second sweep spends 2–3 credentialed operations — roughly **4,300 failed authentications a day, per device, unattended**. There are three ways in (`:1331-1341`, `:1606-1620`, `:1484-1493`) and no way out but an operator. The I8307 sat there after its password was rotated; `health.py:84-85` records an 18,004-failure counter from the same family.

The onboarding pass has a smaller version of the same fault. Step 1 corroborates the *stored* credential; if the identical pair is also on the entry list, step 3 tries it again. Two more refusals for a credential the device refused a moment earlier (`admz/onboarding.py:281-282`, `:383`; FR-CRED-013 names it).

Both are the same mistake: **asking a question the device already answered.**

## Decision

### 1. A refused credential is retried on an escalating hold, not on the sweep cadence

After a condemnation the sweep waits before sending credentials to that device again. The wait starts at one sweep interval and doubles per refusal, capped: `min(interval × 2^(streak−1), MAX)`, the shape ADR-0063 already uses for unconfirmed capability leases (`admz/device_capabilities.py:177-192`).

**`MAX` is 30 minutes** — settling to about 120 failed authentications a day instead of 4,300. That number is **chosen, not measured**. It is deliberately far from any plausible lockout threshold in the safe direction, and it is the first thing to revisit when ADR-0064 decision 7's measurement exists. The ceiling is a fleet setting so an installation need not wait for this file to change.

### 2. Holding is not the same as knowing

A held sweep must **carry the previous status forward**, never re-derive one from a cheaper probe. Re-deriving is not a smaller answer, it is a wrong one: a device with a credential that reaches the TCP tier reads `online` (`health.py:1663-1671`), which would fire `on_online` pre-authorised tasks against a device ADMZ cannot authenticate to — precisely what FR-HLT-011 and `event_for_status` exist to prevent.

For the same reason a held sweep still sends the two things that cost no authentication: the TCP connect, and the **unauthenticated** `systemready` read that FR-HLT-011 already uses (`:1679-1720`, auth forced off by construction). That keeps reachability fresh and keeps a factory reset visible, so `on_needs_setup` still fires while the hold is in force. A held sweep observed nothing about the credential, so it does not advance the failure counter either (#138).

### 3. The hold answers to a credential change, not to a clock alone

Every stored credential write clears the hold, so an operator who enters a password sees the device re-probed on the next sweep rather than waiting out the ceiling. The reset is a database row write because the MCP server is a separate process; it is applied at the registry backends, which every writer in the tree funnels through; and it is scoped to the `default` account, because that is the one the sweep authenticates with.

The explicit sweep (`POST /api/fleet/health/sweep`) ignores the hold. An operator asking for a check must get one — without that, a wedged device has no recovery path from the UI.

### 4. One pass never tries the same pair twice

When onboarding's step 1 sees the stored credential **refused**, step 3 skips an entry credential equal to it. Refused only: an unanswered check says nothing about the credential, and treating silence as a rejection would skip a credential that might work. The per-pass maximum is unchanged at 8 operations; what changes is that a device is no longer asked the same question twice in one pass.

## Consequences

- A stuck device costs about 120 failed authentications a day instead of 4,300, and the number has a stated dependency (decision 7) rather than being an unmeasured guess defended as a limit.
- A device fixed **on the camera** rather than in ADMZ can read stale for up to the ceiling. Fixing it in ADMZ, which is the normal path, clears the hold at once; so does the explicit sweep.
- `device_health` gains two columns and two API fields, so an operator can see when the next credential check is due.
- Health rows become the record of a policy decision, not only of an observation. That is new, and it is why the hold is persisted and visible rather than held in memory.

## What this does not do

- **Throttle the drift audit.** `admz/snapshot/engine.py:667-708` runs its own authenticated read against the same condemned credential, and on a 401 passes the real credentials to `read_systemready` (`:698-702`) — 2 operations per audit. Much rarer than 60 seconds, and its own issue. The claim here is that *the sweep* stops burning credentials, not that nothing does.
- **Reset on reboot.** The issue suggested it. A reboot does not fix a wrong password, the case that matters — a factory reset — is already caught by `needsetup` during the hold, and keying off `bootid` would first require fixing its unrelated flap to NULL on exactly these devices (`:1331-1341`, `:1484-1493`, and the carry-forward at `:1944-1959`). Filed separately.
- **Decide the lockout question.** Nothing here measures a device. It reduces exposure under every possible answer, which is why it ships without waiting.

## Verification

`fleet-health.md` FR-HLT-012 carries the requirement. The load-bearing tests are a two-sweep count proving zero credentialed operations on the second sweep with a control proving the first still probes; a held device on a monitor with no executor still reading `auth_failed` and firing no `on_online`; `needsetup` still transitioning during a hold with the exact unauthenticated call list; a credential write clearing the hold read back through a second store instance; and, for decision 4, the onboarding pass showing the refused pair exactly once while the existing stale-credential repair test (same username, different password) keeps passing.
