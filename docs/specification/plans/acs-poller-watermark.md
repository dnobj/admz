# Plan: ACS action-rule poller — fire on identity, not on a clock (GH #210)

## Context

`AcsActionRulePoller.poll_once` **stores** every ACS action-rule row it fetches but only **fires** the
detection evaluator for rows whose timestamp is strictly newer than a high-water mark. The two paths
disagree about what "new" means, so a firing can land in the operator's Activity feed while its
detection provably never runs — and no status field, log line, or error moves. The rule shows
`fire_count` unchanged, `last_error: ""`, and the automation silently did not happen.

#210 was filed by an autonomous audit loop and re-scoped after an orientation pass (2026-08-04). That
pass **disproved the issue's primary trigger** (page truncation) and **rejected its suggested fix**
(`if inserted:` alone, which would fire up to 30 minutes of retroactive action rules on first
enablement — including pre-authorized service-affecting ones). This plan carries that diagnosis
forward and settles the three questions it left open.

It also **corrects the orientation pass's own recommendation.** That pass proposed splitting `_hw_ms`
into a fixed `_seed_ms` plus store-identity dedup. The `_seed_ms` half is still wrong: a seed taken
from `time.time()` is a *local*-clock value gating *remote*-clock events, so it does not fix the skew
it was meant to survive. The correct move is to remove the clock comparison from the fire path
altogether — see D1.

## Exploration verified (against `plan/acs-poller-watermark`, cut from master @ 385e835)

- The store/fire split is [acs_ingest.py:219-221](admz/events/acs_ingest.py): `self.store.append(rec)`
  runs unconditionally; `if ts_ms > self._hw_ms and self.on_event is not None` gates the fire. `:228`
  then advances `self._hw_ms = max_ms` past everything in the page, fired or not.
- **The high-water seed mixes clock domains.** [acs_ingest.py:159](admz/events/acs_ingest.py) sets
  `self._hw_ms = int(time.time() * 1000)` from the **ADMZ host** clock; every `ts_ms` it is compared
  against comes from `_parse_ms` over an **ACS server** timestamp
  ([acs_ingest.py:90](admz/events/acs_ingest.py)).
- **ACS exposes no server-clock op.** Grepped the module, the catalog and the specs for
  `GetServerTime` / `ServerTime` / `SystemTime` / `CurrentTime`: the only hit is an Axis *device*
  parameter (`root.Time.ServerTime`, [ignore.py:94](admz/snapshot/ignore.py)), unrelated. So
  "seed from an ACS-supplied now" is **not available** without new ACS API discovery.
- **The query interval is also local-clock.** `search_detections` builds
  `interval: {StartTime: utc_anchor(hours_back), StopTime: utc_anchor(0)}`
  ([events.py:140](admz/modules/acs_pro/events.py)) and `utc_anchor` uses
  `datetime.datetime.now(timezone.utc)` ([events.py:20](admz/modules/acs_pro/events.py)). Skew therefore
  affects *which rows ACS returns at all*, independent of the fire gate — see D1's residual.
- **The store already answers "have I seen this?" exactly.** `EventStore.append` is
  `INSERT OR IGNORE` on a content-hash id and **returns `True` only for a genuinely new row**
  ([store.py:70-103](admz/events/store.py)). It returns `False` for a duplicate *and* for a swallowed
  `sqlite3.Error` — that conflation matters and is handled in D1.
- **The id is hashed on the raw `start` string, not on `ts_ms`**:
  `raw = f"{cam_id}|{ACS_RULE_TOPIC}|{start}|{event_id}"`
  ([acs_ingest.py:91-92](admz/events/acs_ingest.py)). So identity dedup is **immune to timestamp parse
  failure** — which is what makes D3 cheap.
- **The sibling ACS poller already does this correctly** — `AcsFirebirdPoller` solves the identical
  "ignore pre-enablement history, fire everything after" problem
  ([acs_firebird_ingest.py](admz/events/acs_firebird_ingest.py)):
  - seeds from the **data source's own frame**, `self._hw_id = await max_firing_id()` (`:66`) — a
    monotonic LOG id, not a clock;
  - pushes the watermark **into the query**, `read_new_firings(self._hw_id)` (`:106`), so the server
    filters and no client-side comparison exists;
  - **fires every returned row unconditionally** (`:123`) — storage and firing cannot disagree;
  - **refuses to start** if the seed read fails (`:67-70`) rather than starting at 0 and firing
    everything — the fail-safe direction;
  - exposes `"high_water": self._hw_id` in `status()` (`:141`). The recorded-events poller exposes
    **no** watermark at all ([acs_ingest.py:234-243](admz/events/acs_ingest.py)).
  The difference: `GetRecordedEvents` offers no cursor/id to filter on — only a time interval — so we
  can adopt the *seeding* and *fire-everything* halves but not the *push-into-query* half.
- **`more` is computed and never read.** `"more": len(raw) >= int(count)`
  ([events.py:162](admz/modules/acs_pro/events.py)), computed **before** the client-side `"Action Rule"`
  filter at `:151-153`; `poll_once` checks only `res.get("success")` at
  [acs_ingest.py:207](admz/events/acs_ingest.py). It is already covered by
  `test_search_detections_more_flag_at_cap` ([test_acs_detections.py:123](tests/test_acs_detections.py)) —
  the producer is tested, only the consumer ignores it.
- **`search_detections` has three callers**, so producer-side changes are not free:
  [acs_ingest.py:196](admz/events/acs_ingest.py), [routes.py:136](admz/modules/acs_pro/routes.py),
  [tools.py:68](admz/modules/acs_pro/tools.py).
- **Restart semantics already exist**: `POST /api/events/control` does `stop()` → `start()` to
  "reset high-water + restart cleanly" ([events.py:147-148](admz/api/routes/events.py)). `stop()` does
  not touch the watermark; `start()` re-seeds it.
- **Service-affecting autonomous actions are independently gated** by `pre_authorized`
  ([evaluator.py:76-77](admz/events/evaluator.py)) — relevant to D3's safety edge.
- The startup contract is stated in the module docstring
  ([acs_ingest.py:20-21](admz/events/acs_ingest.py)): *"On start it sets a high-water mark to 'now', so
  historical firings seed the store/feed but never fire a detection — only firings observed after
  enablement do."*

## D1 — the clock-domain question

**Decision: delete the clock comparison from the fire path. Gate firing on store identity, and seed
with a `_seeded` boolean — the first *successful* poll after start appends everything and fires
nothing.**

The question as posed was "what should `_seed_ms` be seeded from." The honest answer is that the
question dissolves: `_seed_ms` only exists to express *"was this firing already there when I started?"*,
and the store answers that directly and durably. Once firing is identity-based there is no timestamp
comparison in the fire path at all — no local clock, no ACS clock, no `>` boundary.

Options weighed:

| Option | Verdict |
|---|---|
| Seed `_seed_ms` from `time.time()` (the orientation pass's proposal) | **Rejected.** A local-clock value still gates remote-clock events. Fixes the dedup conflation, not the skew. |
| Seed from an ACS-supplied "now" | **Unavailable.** No such op exists (verified above). |
| Seed `_seed_ms` from `max(ts_ms)` of the first poll's own data | **Rejected, though close.** Skew-immune (ACS's own frame), but keeps a `>` comparison — so it retains the equal-millisecond boundary case (`_parse_ms` truncates ACS's 100 ns ticks to ms) and still interacts with `ts_ms == 0`. The boolean is skew-immune *and* has neither edge. |
| `_seeded` boolean + `store.append()` identity | **Adopted.** Matches the Firebird sibling's shape, removes two edge cases, and needs no new state beyond one flag. |

Why this preserves the startup contract — the constraint that killed the naive fix. On first ever
enablement the store holds no ACS rows, so `inserted` alone would fire 30 minutes of history. The
`_seeded` flag is exactly the guard: poll 1 appends and fires nothing, and every poll after fires on
`inserted`. Set `_seeded = False` in `start()` (alongside where `_hw_ms` is seeded today) so the
existing `stop()`→`start()` control path at [events.py:147](admz/api/routes/events.py) keeps its current
meaning.

Two properties fall out that are worth naming, because they are the reason to prefer this over a
patched watermark:

1. **The lookback window becomes a self-healing retry buffer.** Every poll re-fetches the whole
   `ACS_LOOKBACK_HOURS` window. If a firing fails to fire on one poll — store hiccup, `on_event`
   raised, ACS delivered it late — the next poll retries it, for up to 30 minutes. The watermark
   design skips it permanently. This is the #209 lesson applied: never advance past data that was not
   successfully processed. Here there is no cursor to advance, so "don't advance" is free.
2. **A restart is safe by construction.** After a restart the window's rows are already in the store,
   so they dedup out and nothing re-fires — without consulting any clock.

**The `append` conflation must be handled.** `EventStore.append` returns `False` both for a duplicate
and for a swallowed `sqlite3.Error` ([store.py:101-103](admz/events/store.py)). Treating a DB error as
"already seen" would silently skip a fire — the same defect class as #209 reappearing in the new
design. Property 1 contains it: a store error means we simply do not fire *this* poll, and the next
poll (30 s later, same window) retries. **Do not** add a separate in-process seen-set to work around
it — that would defeat the retry. Do count store-error polls in `status()` so an outage longer than
the window is visible; that is the only case where an event is genuinely lost, and it should not be
silent.

**Residual skew — this is where "make it observable" is the right answer.** The fix removes skew from
the *fire* path but not from the *query* path, because `utc_anchor` builds the interval from the local
clock. With ACS behind ADMZ by δ, the effective lookback shrinks from `L` to `L − δ` (and at `δ ≥ L`
the window stops overlapping entirely — the poller returns nothing, forever, while ACS fires rules).
With ACS ahead by δ, firings are delayed by δ and then fire correctly — identity firing degrades that
case from *loss* to *latency*, which the watermark did not.

We cannot know ACS's clock, so make it measurable: add `newest_event_ts_ms` and `apparent_skew_ms`
(local now − newest event ts) to `status()`. That turns "the poller looks healthy and nothing fires"
into a number an operator can read. Document the assumption in the ADR rather than pretending to fix
it.

*Correction to the record:* the orientation pass claimed ACS lagging by more than the lookback means
"no ACS detection ever fires, ever, while the feed fills normally." The second half is wrong — at
`δ ≥ L` the query window does not overlap, so **nothing is returned at all** and the feed stays empty
too. The symptom is `last_count: 0` in perpetuity, not a filling feed. Same severity, different
signature, and `apparent_skew_ms` is what distinguishes it from "ACS is quiet."

## D2 — what `more` should do

**Decision: read it, surface it, do not page on it in this slice.**

Under identity firing, truncation-induced *late arrival* is already handled for free — an event that
appears in any later page fires when first inserted, whatever its timestamp. What `more` still signals
is different and worse: because paging is newest-first from `StartIndex: 0` and the window slides
forward every 30 s, a row pushed off a truncated page is **never returned again** — lost from the feed
*and* the fire path. `more` cannot fix that; only real paging could.

Paging is deferred deliberately, not overlooked:

- `type_filter` is applied **client-side** ([events.py:151-153](admz/modules/acs_pro/events.py)), so
  paging would pull 2000-row pages of *all* recorded-event types to find a handful of Action Rules —
  an unbounded cost on exactly the busy install where truncation happens.
- `GetRecordedEvents` `StartIndex` semantics are unverified against the live server, and ACS's native
  ordering is the assumption the orientation pass could not test. Building paging on it now would
  stack an unverified behavior on an unverified behavior.
- `search_detections` has three callers; paging is a producer-side change that would alter the REST
  route and the MCP tool too.

So: consume `more` in `poll_once`, expose `last_truncated: bool` and `truncated_polls: int` in
`status()`, and log at **warning once per truncation streak** (the latch shape #249 introduced for
`WatchGate`, for the same reason — `poll_once` runs every 30 s and an unconditional warning is a log
flood). That gives the operator the two levers that already exist — raise `ACS_POLL_MAX_EVENTS`, lower
`ACS_LOOKBACK_HOURS` ([config.py:50-52](admz/events/config.py)) — and makes a chronically truncated
poll diagnosable instead of invisible. Paging is recorded as a follow-up issue.

## D3 — what `ts_ms == 0` means

**Decision: fire it, store it with a poll-time fallback timestamp, and make it loud.**

Under identity firing the *suppression* half of this bug disappears for free: `ts_ms` no longer gates
firing, so an unparseable timestamp can no longer silently skip a detection. What remains is the
**retention** half, which is real and independent — a `ts_ms == 0` row sorts last under
`ORDER BY ts_ms DESC` ([store.py:151](admz/events/store.py)) and is deleted by the first retention
sweep, `DELETE FROM events WHERE ts_ms < ?` ([store.py:196](admz/events/store.py)), which runs each
reconcile ([ingest.py:139](admz/events/ingest.py)).

So in `normalize_acs_action_rule`: when `_parse_ms` returns 0 on a **non-empty** `start` string, fall
back to poll time for the stored `ts_ms`, keep the raw string in `ts` untouched, and mark
`data["ts_parsed"] = False`. This is safe because **the id is hashed on the raw `start` string, not on
`ts_ms`** — so the fallback cannot destabilize dedup across polls, and `INSERT OR IGNORE` means the
first insert's value sticks.

On the safety edge — firing on an event whose time we could not bound. Firing is the right default
here, for three reasons:

1. The ACS **query interval already bounds it**. Anything returned is, per ACS's own filter, inside
   the lookback window. Our parse failure is a *format* problem, not an authenticity or age problem.
2. The realistic failure is **wholesale, not sporadic**: an ACS version changing its timestamp format
   makes *every* row unparseable. Fail-closed would then silently disable all ACS automation — exactly
   the class of silent-total-failure this issue exists to remove. Fire-anyway degrades to "works,
   loudly complaining."
3. Autonomous service-affecting actions are **already gated** by `pre_authorized`
   ([evaluator.py:76-77](admz/events/evaluator.py)), so the blast radius is bounded by a decision the
   operator already made explicitly.

Make it loud: warn once per streak with the raw offending string (truncated), and expose
`unparsed_ts: int` in `status()`. If the operator prefers fail-closed, it is one predicate at the fire
site — call that out in the ADR as the knob, so the choice is revisitable rather than buried.

## Design — what changes

`admz/events/acs_ingest.py`:
- `__init__`: drop `_hw_ms`; add `_seeded = False`, `last_truncated = False`, `truncated_polls = 0`,
  `unparsed_ts = 0`, `store_error_polls = 0`, `newest_event_ts_ms = 0`, and two log-once latches
  (`_warned_truncated`, `_warned_unparsed`).
- `start()`: replace the `time.time()` seed with `self._seeded = False`. No clock read remains.
- `poll_once()`: read `more` → truncation counters + latched warning; for each row (keep the existing
  oldest-first `sorted`, which still gives deterministic in-poll ordering) `inserted = self.store.append(rec)`;
  fire when `inserted and self._seeded and self.on_event is not None`; at the tail set
  `self._seeded = True` on any successful poll.
- `normalize_acs_action_rule(detection, *, now_ms=None)`: poll-time fallback + `data["ts_parsed"]`.
- `status()`: add `seeded`, `newest_event_ts_ms`, `apparent_skew_ms`, `last_truncated`,
  `truncated_polls`, `unparsed_ts`, `store_error_polls`.

`admz/api/routes/events.py:147` — the `# reset high-water + restart cleanly` comment becomes
`# re-seed (next poll fires nothing) + restart cleanly`. Behavior of the route is unchanged.

Module docstring `:20-21` — restate the startup contract in the new terms ("the first successful poll
after start seeds the feed and fires nothing"), since the sentence currently describes the mechanism
being removed.

Not touched: `EventStore.append`'s signature (three device-ingest callers depend on it),
`search_detections` (three callers), `_parse_ms`'s own contract.

## Tests — `tests/test_acs_event_ingest.py`

All deterministic: fake stores and a page-per-call `search_detections`. **No sleeps, no threads, no
wall-clock reads** — the Windows leg is authoritative and anything timing-dependent flakes there. The
existing `_Store` fake already returns `True`/`False` from `append` like the real store
([test_acs_event_ingest.py:49-53](tests/test_acs_event_ingest.py)), so the identity path is directly
testable today.

- **Late arrival fires (the headline).** `fake_search` returns page 1 = `[newer]`, page 2 =
  `[newer, older]`. With `_seeded` pre-set, assert `fired == 2` and that the *older* event fired.
  Fails against current code (`older.ts_ms > hw` is False), passes after.
- **Startup contract.** Fresh poller, `start()`-equivalent state, first poll returns 3 historical rows
  → `fired == 0`, `len(store.rows) == 3`. Second poll adds one new row → `fired == 1`. This is the
  test that would have caught the rejected `if inserted:` fix.
- **Restart does not re-fire.** Same store instance, new poller, `_seeded` reset → first poll fires 0
  even though rows are "new" to the poller.
- **Clock skew, both directions.** Events timestamped far behind *and* far ahead of any local clock
  still fire exactly once. Constructed by fixing timestamps in the fake, never by reading the clock.
- **Equal-millisecond boundary.** Two rows with identical `ts_ms` split across polls both fire —
  the case the `>` comparison drops.
- **`ts_ms == 0`.** A row with an unparseable `ts` fires, is stored with a non-zero fallback `ts_ms`,
  carries `data["ts_parsed"] is False`, keeps its raw `ts`, has a **stable id across two polls** (so
  it dedups), and bumps `unparsed_ts`.
- **Truncation surfaces.** `fake_search` returns `more: True` → `last_truncated`, `truncated_polls`
  increment, and one warning per streak (assert via `caplog`), not one per poll.
- **Store error does not consume the fire.** A fake `append` that returns `False` on poll 1 (simulating
  the swallowed `sqlite3.Error`) and `True` on poll 2 → the event fires on poll 2. Pins the retry
  buffer, and pins that we did not paper over the conflation with a seen-set.
- **`status()` shape** — extend the existing key-presence test with the new fields.

Mutation-check every new test by reverting `acs_ingest.py` before believing them, and say so in the
PR — the #209 PR did this and it is now the house expectation.

Regression watch: `tests/test_acs_detections.py` covers the producer and should be untouched;
`test_poll_fires_only_events_newer_than_high_water`
([test_acs_event_ingest.py:70](tests/test_acs_event_ingest.py)) **encodes the behavior being removed**
and must be rewritten, not deleted — it becomes the late-arrival test above.

## ADR — yes, needed, drafted alongside this plan

This changes a subsystem's contract, not just its implementation: *how an ACS firing earns the right to
run an automation* moves from "its timestamp beat a clock" to "the store had never seen it." Per
`CLAUDE.md` ("read the relevant ADR before changing a subsystem, and write a new one when a decision
changes") and `process.md` step 1 (ADRs are drafted at planning time), this PR carries
**`docs/specification/decisions/0057-acs-firings-gate-on-identity-not-a-clock.md`** — next free number
(highest on master is 0056). It records: the two-clock problem and that ACS exposes no server-time op;
the identity + `_seeded` decision and why the local-clock seed was rejected; the Firebird precedent;
the residual query-window skew and the decision to measure rather than correct it; and D3's fire-anyway
default with the fail-closed knob named.

## Risks

- **`_seeded` skips one window on every restart.** A firing that arrives *during* a restart is appended
  but never fired. Current behavior loses the same events (the `time.time()` seed also skips them), so
  this is not a regression — but it is now the *only* silent-loss path left, and it should be stated in
  the ADR rather than discovered later.
- **ACS ordering remains unverified.** D2 rests on newest-first paging. If ACS actually returns
  oldest-first, truncation means the poller falls permanently behind instead of dropping old rows —
  a different failure that the `more` counters would also surface. Worth one live check on staging
  during implementation; the counters make it observable either way.
- **Retention could reap a row still inside the lookback window** if an operator sets
  `event_store_retention_days` very low, re-arming a re-fire. Bounded by the 30-minute window versus a
  day-granularity setting; noted, not defended against.
- **`apparent_skew_ms` is only meaningful when events exist.** On a quiet install it reads stale. Label
  it as "since last event," not "current skew."

## Out of scope (follow-up issues)

Real `StartIndex` paging on `more` (D2). Pushing a cursor into the ACS query the way Firebird does —
blocked on ACS exposing one. Correlating ACS camera ids to ADMZ devices (deferred at
[acs_ingest.py:102](admz/events/acs_ingest.py)). GH #125 (`read_new_firings` missing a `RULE_ID<>0`
filter) — the Firebird path's own defect, unrelated to this watermark.

## Critical files

Edit: `admz/events/acs_ingest.py` (the whole change), `admz/api/routes/events.py` (one comment),
`tests/test_acs_event_ingest.py`.
New: `docs/specification/decisions/0057-acs-firings-gate-on-identity-not-a-clock.md`.
Reuse, don't reimplement: `EventStore.append`'s `INSERT OR IGNORE` + boolean return, the content-hash
id in `normalize_acs_action_rule`, the log-once-per-streak latch from #249, `AcsFirebirdPoller`'s
seed-from-the-source shape.
Read before touching: ADR-0041 (the ACS event seam), and `AcsFirebirdPoller` — it is the worked example.
