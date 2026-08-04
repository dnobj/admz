# Plan: a detection lost to an unreadable rule cache — fix the evaluator, not the poller (GH #255)

## Context

ADR-0057 replaced the ACS poller's clock watermark with store identity, and its Proposed text claimed
the lookback window retries a firing whose `on_event` callback raised. It does not: the row is appended
*before* the callback runs, so a later poll sees `inserted == False` and that firing is never retried.
#253 amended the record and filed this follow-up rather than improvising a fix.

#255 offers three designs: fire-before-append, a bounded re-fire set, or accept-and-document.

**This plan recommends a fourth, and rejects all three as scoped.** The decisive fact is not a
trade-off to argue — it is checkable, and it says the defect is not in the poller at all. `on_event`
is `DetectionEvaluator.evaluate`, and `evaluate` has exactly **one** way to raise. Fixing that one way
closes the gap on **five** call paths at once, adds no state to any poller, and preserves ADR-0057's
thesis. A re-fire set would fix one path — and specifically the only one that already has a natural
retry buffer.

## Exploration verified (against `plan/acs-refire-on-callback-failure`, cut from master @ ce8d048)

**`evaluate` has a single raise path.** [evaluator.py:64-81](admz/events/evaluator.py):

- `self._refresh()` at `:65` is **unguarded** — `DetectionStore.list()` uses `try`/*`finally`* with no
  `except` ([detections.py:180-192](admz/events/detections.py)), so a sqlite error propagates out of
  `evaluate` to whoever called it.
- Everything else is swallowed. The per-rule body is wrapped at `:70-81`, so a malformed rule, a
  matcher error, a bad cooldown or a failed pre-auth check **cannot** raise.
- `_fire` is **detached** — `asyncio.create_task(...)` at `:79` — so action execution never propagates
  to `evaluate` at all; `_fire` has its own try/except, `record_fire` and audit at `:101-121`.
- `_device_tags` catches its own failures at `:46-51`.

**And that path is compound-rare.** `_refresh` only touches the DB when
`self.store.version != self._rules_version` ([evaluator.py:37](admz/events/evaluator.py)). In steady
state that is an integer comparison which cannot raise. So an `on_event` failure needs *both* a
detection-rule mutation *and* a sqlite read error on the very next event.

**This answers #255's own question — "what does `on_event` do, and how can it fail?"** The realistic
failure is a **transient store read error**, never a deterministic one. A malformed rule cannot cause
it. A failing action cannot cause it. So a retry would be meaningful and would **not** loop. But the
same fact relocates the fix: if the only failure is "the evaluator could not re-read its rules," the
place to handle it is the evaluator.

**Five call paths share the identical shape** — append (or advance), then `on_event` inside a swallow —
and only one of them can retry:

| Path | Site | Log level today | Retry available? |
|---|---|---|---|
| Device WS stream | [wsstream.py:203-209](admz/events/wsstream.py) | `debug` | **None** — a WS event is delivered once |
| ACS recorded-events poll | [acs_ingest.py](admz/events/acs_ingest.py) | `warning`, once/streak (#253) | the `ACS_LOOKBACK_HOURS` window |
| ACS Firebird poll | [acs_firebird_ingest.py:116-128](admz/events/acs_firebird_ingest.py) | `debug` | **None** — `_hw_id` advances at `:121-122` *before* the fire, and the cursor is pushed server-side |
| ACS webhook | [routes.py:270-272](admz/modules/acs_pro/routes.py) | **`except: pass`** — fully silent | **None** |
| Direct/test callers | [test_event_detections.py:130](tests/test_event_detections.py) | — | — |

**There is no fire-failure counter.** #253 added a `_warned_fire_failed` latch but no metric, and
`status()` exposes none ([acs_ingest.py](admz/events/acs_ingest.py)). So "the gap is loud" is true of
the log and false of every machine-readable surface — which matters for option 3.

**The sibling already made this exact fix.** #249 gave `WatchGate._refresh` the shape being proposed
here: on a failed store read, keep the previous specs, do not advance the version cursor, warn once per
streak, return ([subscriptions.py:51-91](admz/events/subscriptions.py)). `DetectionEvaluator._refresh`
is the same method in the same subsystem and did not get the same treatment.

## D1 — fire before appending: **reject**

**#255's stated cost for this option is wrong, and its real cost is worse.**

The issue says a crash between firing and appending runs the action twice. It cannot: ADR-0057's
`_seeded` makes the first poll after *any* start append everything and fire nothing, so a row that
fired-but-did-not-append before a crash is silently seeded on restart. The crash window is already
closed — by the mechanism #253 shipped.

The real costs are two, and both are worse than the one that was named:

1. **It needs a new read API and an extra round-trip per event.** Firing first requires knowing the row
   is new *before* appending, but `append`'s return value is exactly what tells us that. So the poller
   would need an `EventStore.has(id)` existence check on every event of every poll — a check-then-act
   pair replacing one atomic `INSERT OR IGNORE`.
2. **It puts the duplicate risk on the most likely failure, to fix the least likely one.** Under
   fire-before-append, a fire that succeeds while its **append** fails re-fires on the very next poll —
   no crash needed. In WAL mode readers do not block but writers contend, and `append` is a *write* on
   every row of every poll while `_refresh`'s read happens only after a rule mutation. So append
   failure is the more probable event by a wide margin, and this design converts it from "no fire" into
   "duplicate fire" — the dangerous direction, since ACS detections can drive pre-authorized
   service-affecting actions.

Trading a rare missed action for a more-likely duplicated one is the wrong way round.

## D2 — a bounded re-fire set: **defensible, but reject as scoped**

**First, the honest answer to "is this the rejected seen-set wearing a new hat?" — no, it is the
opposite, and the difference is the failure direction.**

- The seen-set ADR-0057 rejected makes membership cause you to **skip**. A wrong entry is a permanent
  silent loss; that is #209's defect class exactly. It fails **closed**.
- A re-fire set makes membership cause you to **fire**. A wrong entry costs one extra fire; a *lost*
  entry degrades to today's behaviour. It fails **open**, toward the status quo we already accept.

Eviction is also not the problem it looks like: intersect the set with the ids seen in the current poll
at the end of each poll and it is bounded by the window's contents, self-evicting, in-process, and
empty after a restart. No TTL, no size cap.

So it is not the same mistake. It is still the wrong fix, for a different reason: **it repairs one path
out of five, and it repairs the only one that already has a retry buffer.** The device WS stream, the
Firebird poller and the webhook have no window to re-poll — an event arrives once and is gone. A
re-fire set in `acs_ingest.py` would leave the highest-volume path (device events) and the two
silent-failure paths untouched while adding state to the one place that could already recover.

## D3 — accept and document: **half-right, and it cannot be assessed today**

It is the cheapest option, it is already true, and #253 already made it loud in the log. But #255 asks
what would have to be observed before it stops being defensible, and **today nothing can be observed**:
there is a warn-once latch and no counter, so the failure rate is invisible to `status()`, to
`/api/events/status`, and to any operator who is not reading logs at WARNING.

Accepting an unmeasured failure is not a decision, it is a deferral. Adding the counter is the part of
this option worth keeping, and this plan keeps it — under D4, where the residual it measures is much
smaller.

## D4 — make the evaluator degrade instead of drop: **recommended**

**Give `DetectionEvaluator._refresh` the shape `WatchGate._refresh` already has (#249): on a failed
store read, keep the last good rule list, do not advance `_rules_version`, warn once per streak, and
return.** `evaluate` then has no raise path and becomes total.

Why this is the right level:

- **It fixes all five paths at once**, including the three that have no retry buffer and the two that
  fail silently today.
- **It adds no state to any poller.** ADR-0057's thesis — the poller carries no parallel bookkeeping —
  survives intact. The state it does add (a bool latch) lives in the evaluator, next to the cache it
  guards, exactly as in `WatchGate`.
- **It is a shipped, tested shape, not an invention.** #249 made this precise change to the sibling
  method three PRs ago.
- **It is symmetric with #209.** WatchGate's bug was *advancing a cursor past* unprocessed data; the
  evaluator's is *dropping* the data outright. Both are answered by "keep the last good snapshot and
  retry" — and the evaluator half was missed because #209 only looked at the gate.

**The trade-off, stated plainly.** Evaluating against a rule list one refresh cycle stale can fire a
rule that was disabled moments earlier. Today's alternative is to drop the event entirely and fire
*nothing at all* — including every rule that is still enabled. Staleness is bounded to one refresh
cycle and `pre_authorized` still gates every service-affecting action
([evaluator.py:76-77](admz/events/evaluator.py)). `WatchGate` accepted the identical trade for
`_specs` in #249 (a just-deleted watched event keeps capturing for one cycle), so this is consistency
rather than a new risk appetite.

**Residual, and why the pollers stay defensive.** `on_event` is an *injected* callback — tests and any
future event source can supply something else — so every call site keeps its try/except. What changes
is that failures stop being invisible:

- raise `wsstream.py:207-209` and `acs_firebird_ingest.py:127-128` from `debug` to warn-once-per-streak;
- replace the webhook's bare `except: pass` at `routes.py:271-272` with the same;
- add `fire_failed_total` to the ACS poller's `status()` (D3's keeper).

After D4, a non-zero `fire_failed_total` on the current wiring should be structurally impossible — which
is what makes it a useful alarm rather than noise, and is the concrete answer to #255's "what would
have to be observed."

## Design — what changes

`admz/events/evaluator.py`:
- `__init__`: add `self._refresh_failing = False`.
- `_refresh()`: wrap the `store.list()` call; on exception keep `self._rules` and `self._rules_version`
  unchanged, warn once per streak (debug thereafter), and return. Log recovery once, mirroring
  [subscriptions.py:86-88](admz/events/subscriptions.py).
- No change to `evaluate`, `_fire`, or the matcher.

Log-level only (no behaviour change): `admz/events/wsstream.py`,
`admz/events/acs_firebird_ingest.py`, `admz/modules/acs_pro/routes.py` — each gains the same
warn-once-per-streak latch, replacing `debug` / `except: pass`.

`admz/events/acs_ingest.py`: `fire_failed_total` counter incremented at the existing failure site and
exposed in `status()`. No other change — the poller's firing logic is untouched by this plan.

Not touched: `EventStore` (no `has()` is needed — D1 is rejected), the ACS poller's `_seeded` /
identity gate, `DetectionStore.list`'s contract.

## Tests

Deterministic throughout — fake stores, no sleeps, no threads, no wall-clock reads. Windows is the
authoritative leg.

`tests/test_event_detections.py` (mirroring the `TestWatchGateRefreshFailure` block #249 added to
[test_events_watched_scoping.py](tests/test_events_watched_scoping.py)):

- **`evaluate` does not raise when the rule store does.** A store whose `list()` raises once →
  `evaluate` returns normally. Fails now (the exception propagates), passes after.
- **It fires against the last good rule list during the outage.** A rule loaded on call 1; call 2's
  refresh raises (bump the version so a refresh is attempted) → the rule still fires.
- **The version cursor does not advance**, so call 3 re-reads and recovers. Asserted behaviourally
  first, then on `_rules_version`, so a regression fails on the behaviour and not on a private
  attribute — the #207 lesson.
- **First-ever refresh failure fires nothing and still does not raise** (there is no previous list),
  then recovers on the next call.
- **Warn once per streak**, plus one recovery line, via `caplog`.
- **Accepted staleness is pinned deliberately**: a rule disabled *during* an outage still fires once.
  It is a decision, so it gets a test that says so rather than being discovered later as a bug.
- **Poller residual**: an `on_event` that raises still does not stop the poll, and increments
  `fire_failed_total`.

Mutation-check every new test — revert the source, confirm each goes red *for the reason claimed*, and
report what was seen. Two of #253's tests initially went red for the wrong reason and had to be
rewritten; assume the same until shown otherwise.

Regression watch: `tests/test_event_detections.py` currently constructs evaluators with fake stores
whose `list()` always succeeds, so no existing test should move.

## ADR — a new one (0058), not an amendment to 0057

**New**, because the decision is not about the ACS poller. ADR-0057 answers *how an ACS firing earns
the right to run an automation*; this answers *what the detection evaluator does when it cannot read
its rules*, which governs every event source — device WS, both ACS pollers, and the webhook. Filing it
as an amendment to 0057 would bury a cross-cutting decision under one source, where a reader following
the device path would never find it. ADR-0057 is also ✅ shipped; amending a shipped record to carry a
*new* decision muddies the trail that `process.md` depends on.

**`docs/specification/decisions/0058-the-detection-evaluator-degrades-never-drops.md`** (0057 is the
highest on master). It records: the single raise path and why it is compound-rare; the five call sites
and which can retry; why fire-before-append inverts the risk onto the more probable failure; why a
re-fire set is *not* the rejected seen-set but is still the wrong scope; the staleness-versus-loss
trade and its bound; and the `fire_failed_total` alarm as the standing check. ADR-0057's "Amended
during implementation" block gains a one-line pointer to it.

## Risks

- **Wider blast radius than the issue implies.** Touching `evaluate` affects every event path, not just
  ACS. Mitigated by it being the shape #249 already shipped and tested on the sibling, and by the
  change being confined to the failure branch — the success path is byte-identical.
- **Stale-rule firing is now deliberate.** Bounded to one refresh cycle, `pre_authorized` still gates,
  and a test pins it — but it is a real behaviour change and should be read as one.
- **The counter could read zero forever** and be mistaken for "not implemented." The ADR states that
  zero is the expected value for the current wiring and that non-zero means an injected callback is
  failing.
- **`_refresh` swallowing could mask a genuinely broken detection store** (every read failing, rules
  frozen at their last good state indefinitely). The warn-once-per-streak line names it, and unlike the
  current behaviour the events still evaluate. Same trade `WatchGate` accepted.

## Out of scope

Any change to the ACS poller's identity gate or `_seeded` (ADR-0057 stands). `EventStore.has()` — only
D1 needed it. Retrying a *detached* `_fire` action failure ([evaluator.py:79](admz/events/evaluator.py))
— that path already records `record_fire` + an audit row and is a separate concern. GH #125.

## Critical files

New: `docs/specification/decisions/0058-the-detection-evaluator-degrades-never-drops.md`.
Edit: `admz/events/evaluator.py` (the change), `admz/events/wsstream.py`,
`admz/events/acs_firebird_ingest.py`, `admz/modules/acs_pro/routes.py`, `admz/events/acs_ingest.py`
(log levels + counter), `tests/test_event_detections.py`, ADR-0057 (one-line pointer), `INDEX.md`.
Reuse, don't reimplement: `WatchGate._refresh`'s failure branch
([subscriptions.py:72-91](admz/events/subscriptions.py)) — this is that code, in the sibling method.
Read before touching: ADR-0057 and #249's diff.
