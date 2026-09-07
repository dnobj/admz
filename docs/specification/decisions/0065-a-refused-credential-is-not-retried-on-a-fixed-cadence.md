# ADR-0065 — A refused credential is not retried on a fixed cadence: the sweep holds, and nothing puts the same pair to a device twice in one pass

**Status:** Accepted — 2026-09-07
**Closes when shipped:** #469 (the sweep's hold) · #475 (the onboarding dedupe)
**Relates to:** [ADR-0061](0061-entry-credentials-and-the-admz-account.md) (asked for the lockout measurement) · [ADR-0064](0064-a-device-admz-cannot-authenticate-to-is-never-online.md) (bounded the onboarding loop; deferred this to "its own issue rather than a paragraph here", decisions-taken-by-default row 8) · [ADR-0063](0063-capability-knowledge-is-local-first.md) (the persisted escalating-TTL shape this reuses) · FR-HLT-006/007/009/011, NFR-HLT-001/002, FR-CRED-013 · #138 (five-figure failure counters), #149/#150 (corroborated rejection), #458 (the capability-record skip)

_Plan-first per `process.md`: this document merges before any code. File:line references are against master `5c88fb9`._

## Context

ADMZ reaches a device it does not yet manage by trying credentials, which means deliberately failing to authenticate. How an Axis unit answers repeated failures — lockout, throttle, or nothing — is **unmeasured**. ADR-0061 asked for the measurement against a spare unit; it was never run, and ADR-0064 decision 7 still holds #411 slice F on it.

ADR-0064 slice C bounded the part that was easy to reason about: the entry loop now tries at most three credentials, 6 credentialed operations, and a whole onboarding pass is at most 8. It left the larger exposure untouched and said so in as many words.

**A device in `auth_failed` is re-probed with its known-bad credential on every sweep, forever.** `probe_device` (`admz/fleet/health.py:1181-1189`) takes no previous record and has no status-dependent short circuit, so each 60-second sweep spends 2–3 credentialed operations depending on which of the three condemnation paths it takes (`:1331-1341`, `:1606-1620`, `:1484-1493`). At three a minute that is **4,320 failed authentications a day, per device, unattended**. The I8307 sat there after its password was rotated. The unattended-counter class is old news here: `health.py:84-85` records an 18,004-failure counter on a P8815-2 — a different cause (#149's false condemnation) but the same shape, a loop nobody was watching.

There are exits today, and they are all somebody noticing: an operator entering a password, a camera-side change that the next sweep happens to catch, or a factory reset filing `needs_setup`. None of them bounds what the sweep spends in the meantime.

The onboarding pass has a smaller version of the same fault. Step 1 corroborates the *stored* credential; if the identical pair is also on the entry list, step 3 puts it to the device again (`admz/onboarding.py:281-282`, `:383`). FR-CRED-013 names it.

Both are the same mistake: **asking a question the device already answered.**

## Decision

### 1. A refused credential is retried on an escalating hold

After a condemnation the sweep waits before sending credentials to that device again. The wait starts at one sweep interval and doubles per refusal, capped: `min(interval × 2**max(streak−1, 0), MAX)` — the shape and the clamp of ADR-0063's unconfirmed capability lease (`admz/device_capabilities.py:177-188`).

**`MAX` is 30 minutes.** The reduction is exactly `MAX ÷ interval`, so at the default 60-second cadence a condemned device settles at **30× fewer** credentialed operations: 48 probes a day instead of 1,440, about **144 credentialed operations a day instead of 4,320**. The first day costs a little more (52 probes, ~156 operations) because the escalation has to climb.

That ceiling is **chosen, not measured**. It is deliberately far from any plausible lockout threshold in the safe direction, and it is the first thing to revisit when ADR-0064 decision 7's measurement exists. It is a fleet setting so an installation need not wait for this file to change. Note the first hold equals one ordinary interval, so the first retry lands on the normal cadence and only then does the wait start doubling — the escalation is not a lockout of ADMZ's own making.

**Two persisted columns** carry it, mirroring `device_capabilities`' `fail_streak` + `expires_at`: a **streak** and an absolute **deadline**. The streak advances only on a refusal the hold did not suppress; a held sweep leaves it alone, because a held sweep asked nothing. `consecutive_failures` is not reused: it also counts `unreachable`, so it would saturate the curve out of sweeps that made no request.

### 2. Holding is not knowing

A held sweep **re-derives a status only from credential-free evidence**, and never from the credentialed tiers it is skipping:

| What the free evidence says | The verdict |
|---|---|
| TCP connect fails | `unreachable` |
| unauthenticated `systemready` says `needsetup=yes` | `needs_setup` |
| otherwise | the **last credential verdict** — `auth_failed` — carried forward |

"Carry the last credential verdict" is the load-bearing phrase, not "carry the previous status": a device that flapped to `unreachable` last sweep and answers TCP this sweep is still a device whose credential was refused, and freezing the *status* would leave a reachable device reading unreachable for up to the ceiling.

What a held sweep must **not** do is fall through to the TCP tier and let it decide. A device in a hold has a credential by definition, so that tier files `online` (`health.py:1663-1671`) and fires `on_online` pre-authorised tasks at a device ADMZ cannot authenticate to — the failure FR-HLT-011 exists to prevent.

The two requests a held sweep still makes cost no authentication: the TCP connect, and an **unauthenticated** `systemready` read. The auth-forcing shape already exists at `health.py:1679-1720`, but it sits inside the credential-less branch and is **unreachable for a device that has a credential** — so the held path needs its own call site, and the request is best extracted into one helper rather than copied. Two conditions travel with it: it needs a catalog and an executor, and ADR-0063's `skip_read` (#458) suppresses it on a device whose `systemready` capability row says absent. So a factory reset is *usually* still seen during a hold, not always — which is one more reason the hold stays time-bounded.

A held sweep observed nothing about the credential, so it does not advance the failure counter of FR-HLT-007 either (#138). It does advance `last_check` and stamps the reachability clock, because the host did answer; it reports the TCP round-trip as latency; and it **suffixes** the hold onto the condemnation text rather than replacing it, because that text is what routes an operator to capture. Suffixing must be idempotent, or the note grows one sweep at a time. `_dc_replace(prev, …)` at `health.py:1899-1906` is the in-file precedent for carrying a row forward.

### 3. The hold answers to a credential change, not to a clock alone

Every stored credential write clears the hold, so an operator who enters a password sees the device re-probed on the next sweep rather than waiting out the ceiling.

- It is a **database row write**, because the MCP server is a separate process and an in-memory signal would not reach the sweep.
- It is applied at the **registry backends**. There are two concrete ones and every credential writer in the tree funnels through their `add_account` / `update_account` / `remove_account`; no raw SQL against `accounts` exists elsewhere.
- It is scoped to the **`default` account**, which is what the sweep authenticates with (`health.py:1879`, and FR-HLT-011's "only the `default` account counts"). Stashing a `recovery` password answers nothing about the credential in use.
- It is an **UPDATE, never an upsert**: #428 purges health rows inside the device-delete transaction, and a device that has never been swept has no row that should be conjured. A miss is success.
- It must **win the race with the sweep's own write**. `_check` ends by upserting the whole row, so a clear that lands while a probe is in flight would be silently resurrected. The sweep re-reads the deadline before writing and lets the clear stand.

The explicit sweep (`POST /api/fleet/health/sweep`) ignores the hold. An operator asking for a check must get one, and this is the recovery path if a device is ever wedged. The interval loop never forces.

### 4. One pass never puts the same pair to a device twice

When onboarding's step 1 sees the stored credential **refused**, step 3 skips an entry credential equal to it. Refused only: an unanswered check says nothing about the credential, and treating silence as a rejection would skip a credential that might work. The per-pass maximum is unchanged at 8 operations; what changes is that no pair is put to a device to authenticate twice in one pass.

## Consequences

- A condemned device costs about 144 credentialed operations a day instead of 4,320, and the number has a stated dependency (decision 7) rather than being an unmeasured guess defended as a limit.
- A device fixed **on the camera** rather than in ADMZ can read stale for up to the ceiling. Fixing it in ADMZ, the normal path, clears the hold at once; so does the explicit sweep.
- `device_health` gains two columns and two API fields, so an operator can see the streak and when the next credential check is due. Devices already sitting in `auth_failed` when the columns arrive have neither, which reads as "no hold" — they are probed once and then held, which is the right start.
- Health rows become the record of a policy decision, not only of an observation. That is new, and it is why the hold is persisted and visible rather than held in memory.
- The deadline is wall-clock, so a backwards clock step could park it. It is clamped: a deadline more than one whole ceiling away is treated as due. ADR-0063 carries the same exposure without the clamp.
- FR-HLT-007 gains a third case (a frozen counter) and KL-HLT-001's "cache lags reboots until the next sweep" becomes "up to the ceiling" for a held device.

## What this does not do

- **Throttle the drift audit.** `admz/snapshot/engine.py:667-708` runs its own authenticated read against the same condemned credential, and on a 401 passes the **real** credentials to `read_systemready` (`:701-703`) — 2 operations per audit, in pointed contrast to the health sweep, which forces auth off. Much rarer than 60 seconds, and its own issue. The claim here is that *the sweep* stops burning credentials, not that nothing does.
- **Throttle `await_device_recovery`.** `admz/recovery.py:50`'s `AUTH_FAILFAST_CONSECUTIVE = 2` is the tree's existing in-call version of this idea; reconciling the two is not attempted here.
- **Reset on reboot.** The issue suggested it. A reboot does not fix a wrong password, the case that matters — a factory reset — is already caught by `needsetup` during the hold, and keying off `bootid` would first require fixing its unrelated flap to NULL on exactly these devices (`:1331-1341` and `:1484-1493` construct their records with no `bootid`, and the carry-forward at `:1944-1959` does not preserve it). Filed separately.
- **Decide the lockout question.** Nothing here measures a device. It reduces exposure under every possible answer, which is why it ships without waiting.

## Verification

FR-HLT-012 in `fleet-health.md` carries decision 1–3; FR-CRED-013 in `credential-storage.md` carries decision 4. The load-bearing tests:

- a two-sweep count proving the second sweep spends **zero** credentialed operations, with a control proving the first still probes, and a separate check that the first hold equals one ordinary interval;
- a held device on a monitor built with **no catalog or executor** still reading `auth_failed` and firing no `on_online` — the shape that would otherwise fall through to the TCP tier;
- `needsetup` still transitioning during a hold, asserted on the exact call list so the read is proved credential-free;
- the hold surviving an intervening `unreachable`, and being forgotten by a working credential;
- a credential write clearing the hold, read back through a second store instance on the same file, with `recovery` proved not to clear it, and a write landing mid-probe proved to survive the sweep's own upsert;
- the ceiling bounding an arbitrarily long streak, and a parked deadline treated as due;
- an old database migrating, and a migration failure that is not a duplicate column refusing to be mistaken for a completed one;
- for decision 4, the refused pair asked exactly once, an unanswered one still asked twice, and the same password under a different username still tried.
