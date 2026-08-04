# ADR-0058 — The detection evaluator degrades to its last good rules, never drops the event

**Status:** Accepted (2026-08-04). Shipped with #255 (`_refresh` degrades; the five
`on_event` sites made loud; `fire_failed_total`). Planned in
[`plans/acs-refire-on-callback-failure.md`](../plans/acs-refire-on-callback-failure.md); implements GH #255.
**Relates to:** ADR-0041 (the event subsystem, layer 3), ADR-0057 (ACS firings gate on identity — this
supersedes its "Amended during implementation" note), GH #209 / #249 (the sibling: `WatchGate._refresh`
must not advance past an unread store), ADR-0034 (`pre_authorized` bounds the blast radius).

## Context

`DetectionEvaluator.evaluate` is the `on_event` callback for **every** event source: the device
WebSocket streams, both ACS pollers, and the ACS webhook. ADR-0057 discovered — during #210's
implementation — that a firing whose `on_event` raises is never retried by the ACS poller, because the
row is appended before the callback runs. #255 was filed to decide what to do about it.

Investigating that question produced a fact that reframes it. **`evaluate` has exactly one way to
raise**: `self._refresh()` (`evaluator.py:65`), which is unguarded, and whose `DetectionStore.list()`
uses `try`/*`finally`* with no `except`. Everything else is already swallowed — the per-rule loop is
wrapped (`:70-81`), so a malformed rule cannot raise; `_fire` is detached via `asyncio.create_task`
(`:79`), so action execution never propagates; `_device_tags` catches its own failures (`:46-51`).

Two consequences follow.

**The failure is transient, never deterministic.** It is a sqlite read error on the rule store, not a
bad rule that would fail identically forever. It is also compound-rare: `_refresh` only touches the DB
when `store.version != _rules_version` (`:37`), so it needs a rule mutation *and* a read error on the
very next event.

**And when it happens, the whole event is lost — every rule, not one.** The raise occurs before any
rule is evaluated, so a single unreadable rule cache silently drops a firing that may have matched
several enabled detections. On four of the five call paths there is no way to get it back: a WS event
is delivered once (`wsstream.py:203-209`, logged at `debug`), the Firebird poller advances its
server-side cursor before firing (`acs_firebird_ingest.py:121-128`, `debug`), and the webhook swallows
with a bare `except: pass` (`modules/acs_pro/routes.py:270-272`). Only the ACS recorded-events poller
has a lookback window to re-poll.

The sibling method already solved this. #249 gave `WatchGate._refresh` the fix: on a failed store read,
keep the previous specs, do not advance the cursor, warn once per streak, retry next call
(`subscriptions.py:72-91`). `DetectionEvaluator._refresh` is the same method in the same subsystem and
was not given the same treatment, because #209 only examined the gate.

## Decision

**When the evaluator cannot re-read its rules, it evaluates against the last good rule list and leaves
its version cursor alone. It never drops the event.**

`_refresh` wraps the store read; on failure it keeps `_rules` and `_rules_version` unchanged, warns
once per failure streak (debug thereafter, one line on recovery), and returns. `evaluate` therefore has
no raise path and becomes total. The success path is unchanged.

Because the raise disappears at its source, all five call sites are fixed at once — including the three
that cannot retry and the two that fail silently. **No poller gains any state**; ADR-0057's thesis that
the ACS poller carries no parallel bookkeeping survives intact.

The call sites keep their `try`/`except` — `on_event` is an *injected* callback and a future source
could supply something that raises for its own reasons — but they stop being quiet: `wsstream.py` and
`acs_firebird_ingest.py` move from `debug` to warn-once-per-streak, the webhook's bare `except: pass`
does the same, and the ACS poller exposes `fire_failed_total` in `status()`. On the current wiring that
counter should be structurally pinned at zero; a non-zero reading means an injected callback is
failing, which is the standing alarm.

## Consequences

**Staleness replaces loss, and that is the whole trade.** Evaluating against a rule list one refresh
cycle old can fire a rule disabled moments earlier. The alternative it replaces is dropping the event
entirely and firing *nothing* — including every rule still enabled. Staleness is bounded to one refresh
cycle, `pre_authorized` still gates every autonomous service-affecting action (`evaluator.py:76-77`),
and `WatchGate` accepted the identical trade for `_specs` in #249, where a just-deleted watched event
keeps capturing for one cycle. This is consistency with a shipped decision, not a new risk appetite. It
is a real behaviour change and carries a test that says so.

**A persistently broken rule store now freezes the rules instead of blanking them.** If every read
fails, detections keep evaluating against their last good state indefinitely rather than silently
matching nothing. The warn-once line names it. Same trade `WatchGate` made.

**#255's three candidate designs are all rejected**, and the reasoning is worth keeping because each
fails differently:

- **Fire before appending.** Its stated cost in #255 — a duplicate action if the process dies between
  firing and appending — is *not real*: ADR-0057's `_seeded` makes the first poll after any start append
  everything and fire nothing, so that row is seeded silently on restart. The real costs are worse. It
  needs an `EventStore.has(id)` existence check before firing (an extra read per event, replacing one
  atomic `INSERT OR IGNORE` with check-then-act), and a fire that succeeds while its **append** fails
  re-fires on the next poll with no crash involved. `append` is a write on every row of every poll
  while `_refresh`'s read happens only after a rule mutation, and in WAL mode writers contend while
  readers do not — so this design moves duplicate risk onto the *more* probable failure to fix the
  *less* probable one, in the dangerous direction for pre-authorized actions.
- **A bounded re-fire set.** Not the seen-set ADR-0057 rejected — the directions are opposite. A
  seen-set makes membership cause a **skip**, so a wrong entry is permanent silent loss (#209's defect
  class); it fails closed. A re-fire set makes membership cause a **fire**, so a wrong entry costs one
  extra fire and a lost entry degrades to the status quo; it fails open. Eviction is also tractable
  (intersect with the ids seen this poll). It is rejected on **scope**, not correctness: it repairs one
  path of five, and specifically the only one that already has a retry buffer.
- **Accept and document.** Kept in part — but as filed it could not be assessed, because there is a
  warn-once latch and no counter, so the rate is invisible to `status()` and to every operator not
  reading logs at WARNING. Accepting an unmeasured failure is a deferral, not a decision. The counter
  is retained here, measuring a much smaller residual.

**The scope of #209's lesson widens.** "Never advance past unprocessed data" and "never drop
unprocessed data" are the same rule seen from two sides. #249 fixed the advancing half in `WatchGate`;
this fixes the dropping half in the evaluator. Any future cache-with-a-version-cursor in this subsystem
should be read against both.
