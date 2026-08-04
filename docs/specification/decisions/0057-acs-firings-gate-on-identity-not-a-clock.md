# ADR-0057 — ACS firings gate on identity, not on a clock

**Status:** Accepted (2026-08-04). Shipped with #210 (identity firing + `_seeded`,
truncation and skew surfaced). Planned in
[`plans/acs-poller-watermark.md`](../plans/acs-poller-watermark.md); implements GH #210.
**Relates to:** ADR-0041 (the event subsystem and its ACS seam), ADR-0034 (the confirmation gate —
`pre_authorized` bounds the blast radius), GH #209 / #249 (never advance a cursor past data that was
not successfully processed).

## Context

`AcsActionRulePoller` polls ACS's recorded-events log for `"Action Rule"` firings and feeds them into
the same `EventStore` + `DetectionEvaluator` as device events. ACS has no push API, so this is the
only way ADMZ learns that an ACS rule fired.

It **stores** every row it fetches, but only **fires** a detection for rows whose timestamp is strictly
newer than a high-water mark (`acs_ingest.py:219-221`), then advances that mark past the whole page
(`:228`). Two problems follow from that single design choice.

**The two paths disagree about what "new" means.** Storage dedups on a content-hash id; firing compares
a timestamp. Any firing that reaches ADMZ after the watermark has passed its timestamp is stored and
never fired. The operator sees it in the Activity feed, the rule's `fire_count` unchanged,
`last_error: ""`, and `/api/events/status` reporting the poller healthy. Every surface says fine; the
automation did not happen.

**The comparison mixes two clocks.** The mark is seeded from `time.time()` on the **ADMZ host**
(`acs_ingest.py:159`); every timestamp it is compared against comes from the **ACS server**
(`acs_ingest.py:90`). ACS exposes no server-clock operation — we checked the module, the catalog and
the specs — so the skew between them is not merely uncorrected, it is **unmeasurable by construction**.
An ADMZ host running a few minutes ahead of ACS produces a silent dead window after every enablement,
during which firings land in the feed and none of them fire.

A third defect is downstream of the same choice: `_parse_ms` returns `0` for a timestamp it cannot
parse, `0 > mark` is False, so an unparseable firing is stored, never fired, sorted last, and then
reaped by the retention sweep.

**ADMZ already solved this problem correctly once.** `AcsFirebirdPoller` — the *other* ACS firing
source — faces the identical "ignore pre-enablement history, fire everything after" requirement and
seeds its watermark from the data source's own monotonic LOG id (`acs_firebird_ingest.py:66`), pushes
it into the query (`:106`), fires every returned row unconditionally (`:123`), and refuses to start if
the seed read fails (`:67-70`). Two pollers, one subsystem, opposite failure behavior.

## Decision

**An ACS firing earns the right to run an automation by being an identity the event store has never
seen — not by its timestamp beating a mark.**

1. **Fire on `store.append()`'s return value.** `EventStore.append` is `INSERT OR IGNORE` on a
   content-hash id and already returns `True` only for a genuinely new row (`store.py:70-103`). That is
   the dedup, and it is durable across restarts.
2. **Seed with a boolean, not a timestamp.** `_seeded` starts `False`; the first *successful* poll
   after `start()` appends everything and fires nothing, then sets it. This preserves ADR-0041's
   startup contract — historical firings seed the feed but never fire — without reading any clock. It
   is the reason the naive "just use `inserted`" fix was rejected: on first enablement the store is
   empty, so that alone would fire up to `ACS_LOOKBACK_HOURS` of retroactive action rules, including
   pre-authorized service-affecting ones.
3. **No clock comparison remains in the fire path.** Not the local clock, not ACS's, no `>` boundary.
   The skew question is not answered; it is removed from this path.
4. **Unparseable timestamps fire.** The ACS query interval already bounds what is returned, so a parse
   failure is a format problem, not an age problem. Store a poll-time fallback `ts_ms` (so retention
   cannot reap the row), keep the raw string, and mark `data["ts_parsed"] = False`. The id is hashed on
   the raw `start` string, not on `ts_ms` (`acs_ingest.py:91-92`), so the fallback cannot destabilize
   dedup.
5. **Truncation is surfaced, not acted on.** The `more` flag (`modules/acs_pro/events.py:162`) is read
   and exposed in `status()` with a once-per-streak warning. Real paging is deferred — see
   Consequences.
6. **Residual skew is measured, not corrected.** `status()` gains `newest_event_ts_ms` and
   `apparent_skew_ms`.

## Consequences

**The lookback window becomes a self-healing retry buffer.** Every poll re-fetches the whole window, so
a firing whose **append** failed — or that ACS delivered late — is retried on the next poll for up to
`ACS_LOOKBACK_HOURS`. This is the #209 lesson (never advance past unprocessed data) obtained for free:
there is no cursor to advance.

**Amended during implementation (#210).** The Proposed text listed `on_event` raising among the cases
the buffer covers. It does not: the row is appended *before* the callback runs, so a later poll sees
`inserted == False` and that firing is never retried. Fixing it properly means either firing before
appending (which risks a duplicate action if the process dies between the two) or tracking a bounded
re-fire set — a real design choice that deserves its own record rather than an improvised addition, and
that this ADR does not make. It is **not a regression**: the mark this replaced had already advanced
past the firing too. The implementation therefore logs a `on_event` failure at **warning** (once per
streak) naming it as un-retried, instead of the `debug` line that made it invisible at the default
level. Tracked as a follow-up (GH #255) — **superseded on this point by ADR-0058**, which found the
single raise path inside `DetectionEvaluator.evaluate` and fixes it there, closing the gap on all five
event paths without adding any state to this poller.

It also means **a swallowed store error must not be worked around.** `EventStore.append` returns
`False` both for a duplicate and for a swallowed `sqlite3.Error`. Treating that as "already fired"
would skip a firing — but the window retries it 30 seconds later. Adding an in-process seen-set to
disambiguate would *defeat* the retry and reintroduce #209's defect class. We instead count
store-error polls so an outage longer than the window is visible; that is the one genuine loss path and
it must not be silent.

**Skew still affects which rows ACS returns**, because `utc_anchor` builds the query interval from the
local clock (`modules/acs_pro/events.py:20,140`). With ACS behind by δ the effective lookback shrinks
from `L` to `L − δ`, and at `δ ≥ L` the window stops overlapping entirely — the poller returns nothing
at all, in perpetuity, while ACS fires rules. That signature is `last_count: 0` forever, *not* a filling
feed, and `apparent_skew_ms` is what distinguishes it from "ACS is quiet." With ACS ahead by δ, firings
are delayed by δ and then fire correctly — identity firing downgrades that case from loss to latency.
We accept this and document it rather than pretending a local clock can correct a remote one.

**A restart still skips its own window.** A firing arriving during a restart is appended by the seeding
poll and never fired. Current behavior loses the same events, so this is not a regression — but after
this change it is the *only* silent-loss path left, which is why it is recorded here.

**Paging on `more` is deferred**, deliberately: `type_filter` is applied client-side, so paging would
pull 2000-row pages of all recorded-event types to find a handful of Action Rules — an unbounded cost
on exactly the busy install where truncation occurs — and `GetRecordedEvents`' `StartIndex` semantics
are unverified against a live server. The counters make a chronically truncated poll diagnosable, and
the two existing tuning levers (`ACS_POLL_MAX_EVENTS`, `ACS_LOOKBACK_HOURS`) remain the operator's
response.

**The fail-closed knob is one predicate.** If experience shows firing on an unparseable timestamp is
wrong, the change is a single condition at the fire site. Named here so the choice stays revisitable
instead of becoming folklore.

## Alternatives considered

- **Keep the watermark, seed it from `time.time()` as a fixed `_seed_ms`.** Rejected. It fixes the
  dedup conflation but not the skew: a local-clock value still gates remote-clock events.
- **Seed `_seed_ms` from `max(ts_ms)` of the first poll's own data.** Rejected, though close — it is
  skew-immune because it lives in ACS's frame, but it keeps a `>` comparison and therefore the
  equal-millisecond boundary case (`_parse_ms` truncates ACS's 100 ns ticks to ms) and the `ts_ms == 0`
  interaction. The boolean is skew-immune with neither edge.
- **Seed from an ACS-supplied "now."** Unavailable: no such operation exists in the ACS surface ADMZ
  knows.
- **Push a cursor into the ACS query, as the Firebird poller does.** Not possible —
  `GetRecordedEvents` offers only a time interval, no id or cursor. This is the one half of the
  Firebird design we cannot adopt.
- **Drop unparseable timestamps.** Rejected: the realistic failure is wholesale (an ACS version
  changing timestamp format), which would silently disable all ACS automation — the exact
  silent-total-failure class this ADR exists to remove.
