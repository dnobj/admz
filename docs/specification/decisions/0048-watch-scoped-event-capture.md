# ADR-0048 — Watch-scoped event capture + a transient preview feed

**Status:** Accepted (2026-07-18). **Amends ADR-0041** (activity / observability
layer) — specifically its *ingestion* model. Everything else in ADR-0041
(normalized store shape, detections engine, ACS pollers, the activity UI) stands.

## Context — the firehose didn't scale

ADR-0041 shipped ingest as: for **every** device in the (optionally tag-scoped)
roster, open a persistent VAPIX WebSocket subscribed to `//.` (every topic) and
**persist every normalized event**, coarsely filtered only by a category
allow-list. The Activity feed then read that stored table.

Against a real fleet this does not scale, and it bit us in production:

- On an 11-device fleet, a single AXIS Object Analytics camera (P3748-PLVE)
  emitted detections ~1/second continuously. Over ~6 weeks the `events` table
  reached **1.88 million rows / 1.4 GB**.
- The Activity query does substring filters that can't use an index; at that row
  count a single scan took ~5 s and, on the auto-poll, **wedged the whole server**
  (a symptom already commented in `routes/events.py`).

The root design error: **capture was roster-driven, not interest-driven.** The
app streamed and stored everything on the chance an operator might later want to
look at it. Watched events — the operator's actual declared interest — were
purely decorative for ingest (`watched.py`: *"bookmarking never flips ingest on"*).

## Decision

Capture is driven by **what is watched**, and discovery is a **momentary,
non-persisting preview** — never a standing firehose.

### 1. Steady state — watch-scoped capture

- **Device set** = only devices a **watched event** or an **enabled detection**
  targets (explicit `device_id`, or every device carrying a tag-scoped spec's
  tag). Resolved by a new `WatchGate` (`events/subscriptions.py`), version-cached
  off the watched-event + detection stores. No watch ⇒ no stream. Enabling
  capture with zero watched events opens **zero** streams and stores nothing.
  The cache invariant: a store read that fails is **swallowed** (the gate is the
  stream's unguarded `event_filter`, so raising would break the WS read loop) but
  the version cursor is **not** advanced, and a partial read publishes nothing —
  so the next call retries. Advancing past a failed read would be permanent, not
  transient, because the cursor check then short-circuits forever (GH #209).
- **Persistence gate** = a live event is stored only if it **matches** a
  watched-event / detection spec (`WatchGate.matches`, sharing one matcher —
  `events/matching.py::record_matches` — with the detection evaluator so they can
  never diverge). An event matching nothing is dropped outright: it can't fire any
  detection either, so it is never stored and never evaluated. This is what stops
  the firehose. The old category allow-list is removed (the gate subsumes it).
  _Amended 2026-08-09 (GH #172):_ this decision was right but only half-applied
  at the time — the **caller** was removed here, while `store_categories()`, its
  default set, and the `event_store_categories` fleet key were left in place,
  reading as an operator control that silently did nothing. They are now gone,
  and a startup sweep removes the stored row. Wiring them back would be a
  regression, not a completion: a category filter can discard an event the
  operator explicitly watched, which is exactly what the gate exists to prevent.

  **Scope correction, same date.** "An event matching nothing is dropped
  outright" above describes the **device-WebSocket path only** — the gate is
  applied in `events/wsstream.py`, wired from `events/ingest.py`. The three ACS
  writers (`events/acs_ingest.py`, `events/acs_firebird_ingest.py`,
  `modules/acs_pro/routes.py`) call `EventStore.append` unconditionally, so
  "the `events` table holds only watched hits" in the Consequences section is
  true of device events and not of ACS firings, which share the same retention
  budget. That gap is **GH #371**; it is not fixed by a category allow-list
  (ACS firings normalize to `action_rule`, which the old default set also
  excluded, so the allow-list would have dropped all of them).
- **Retention backstop** = even watched-only capture is bounded
  (`EventStore.enforce_retention`: newest-N + age cutoff, fleet-overridable),
  swept each reconcile. A chatty watched topic can never runaway again.

### 2. Discovery — a transient preview feed

To pick a *new* watched event you must see what a device emits now, without
turning the firehose back on. `events/preview.py` opens an **ephemeral** WS stream
to **only the selected device(s)** with `store=None` (nothing persisted) and fans
events to the browser over SSE (`GET /api/events/preview`). It lives exactly as
long as the picker: it tears down when the SSE client disconnects, after an idle
period, or at a hard max-duration cap, and a global cap bounds concurrent preview
device connections. It is independent of the steady-state capture flag — picking
must work with capture off.

The one shared stream class (`DeviceEventStream`) now takes an optional
`event_filter` (the gate) and an optional `store` (None ⇒ preview), so ingest and
preview are the same consumer in two configurations.

### 3. UI

The Activity page's stored feed becomes **"Watched activity"** (only watched hits).
A **"Discover events (live preview)"** panel drives the SSE preview: select a
device → live rows → **Watch this event** bookmarks the pattern → it enters the
watched set → steady-state capture picks it up.

## Consequences

- The `events` table holds only watched hits — small, indexable, fast. The live
  1.88 M-row / 1.4 GB store was truncated + VACUUMed to ~3 MB on adoption.
- Coverage is now honest: you capture what you asked to watch. Nothing is
  captured "just in case," which is the only thing that scales across many
  devices and sites.
- Trade-off: an event that was never watched leaves no history. That is the
  intended behavior — discovery is live (preview), history is watched-only. An
  operator who wants history for a pattern bookmarks it (one click).
- Device-side subscription stays broad (`//.`) per watched device for now; the
  store gate does the narrowing. Narrowing the device-side `topicFilter` to
  watched topics is a future optimization (watched `match.topic` is a substring,
  not a full ONVIF topic path, so it isn't a safe filter as-is).

## Rollout

New branch `feat/events-watched-scoping` (worktree, off the live branch). On
deploy: restart to load the scoped ingest; steady-state capture (`event_ingest_enabled`)
was turned **off** on the live instance during migration to stop the firehose and
reclaim space, and comes back **watch-scoped** once this ships.
