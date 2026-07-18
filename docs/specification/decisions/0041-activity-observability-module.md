# ADR-0041 — Activity / observability layer: log search, a cross-source event timeline, and event-pattern detections

**Status:** Accepted (2026-06-19). **Ingestion model amended by
[ADR-0048](0048-watch-scoped-event-capture.md)** (2026-07-18): capture is now
watch-scoped (only devices/events an operator watches) with a transient preview
feed for discovery — the original "subscribe every device to every topic, store
all" firehose did not scale. The rest of this ADR stands.
Operationalizes the planning half of
**ADR-0028** ("Demo / activity tracking as a bounded module"), which was
"discussion-captured, not a committed plan." This ADR commits the architecture
now that the substrate ADR-0028 assumed actually exists.
**Builds on:** ADR-0039 (platform + modules), ADR-0040 (ACS Pro module),
ADR-0037 (unified tasks / detections).

## Context — what changed since ADR-0028

ADR-0028 concluded that "what was demonstrated at each AEC" is **event-stream
observability + usage analytics** (a different mission from ADMZ's config
management), and that it should be a **bounded module on the shared substrate**:
reuse inventory / Org→Site hierarchy / device taxonomy / the ACS connection
layer / the audit-log timeline UI; keep new and bounded the log ingest, a
normalized append-only event store, a correlation engine, and a dashboard.

Three of those "to be built" pieces now exist:
- **The module platform** (ADR-0039) — a module is a first-class, gated unit.
- **The ACS connection layer** (ADR-0040) — a working Negotiate executor + the
  atlas's `acs-pro` log/event facades.
- **A detections engine** (ADR-0037) — `detection` tasks (event-based, one-shot)
  in one store, fired by a sweep evaluator.

So this is no longer greenfield; it's **assembling existing parts**.

### Grounding in real data (ADR-0028's #1 risk: prototype against real logs)

Probed against a live ACS Pro 6.16 server:
- `EventLogFacade:GetEventLogList` takes `{range:{StartIndex,NumberOfElements},
  time:"YYYY-MM-DD hh:mm:ss"}` — `time` is the UTC window-start anchor; events
  return newest-first, paged by `range`.
- Real events are `{Timestamp, EventLogType, Data:{...}}`, e.g.
  `RecordingStarted` / `RecordingStopped` with `{Name, CameraId}`.
- `RecordedEventFacade:GetRecordedEventTypes` is the activity vocabulary:
  Failover, Action Rule, Motion, Manual, Object detection, …

`RecordingStarted/Stopped` per camera + that taxonomy **are** the demo-activity
primitives — a demo session is a cluster of these on demo-tagged cameras within
a time window.

## Decision

Build an **`activity` module** (read-only observability) in four layers, each
independently useful. **"Demo tracking" is a configured preset on this layer —
not a separate plugin.**

### Layer 1 — ACS log read + search (ship first; lowest risk)
ACS-module tools over `EventLogFacade:GetEventLogList` /
`RecordedEventFacade:GetRecordedEvents` / `LogFacade:GetLogs`, an
`acs_search_events` MCP tool (time window + type/device filters), and a
searchable `/acs` logs view. **Live passthrough — no storage.** This ships value
immediately and is where the real request/parse shape gets locked (already
resolved above). It lives in the ACS Pro module (ADR-0040).

### Layer 2 — a normalized cross-source event store (the ADR-0028 substrate)
An append-only timeline ingesting **both** ACS events and device (VAPIX) events,
normalized to `{ts, site, device_id, role, source, type, severity, summary,
raw}`. This is the reusable core — it makes logs searchable beyond ACS's
retention, correlatable across sources, and fast for the agent. SQLite + FTS,
**separate from the git config-snapshot store**. Reuses inventory / hierarchy /
the device-taxonomy (roles).

### Layer 3 — detections as event-pattern rules (generalize ADR-0037)
Generalize the detection trigger from `on_needs_setup` to an **event-pattern
match**: `match {source/type/role/site/window} → action {annotate | notify |
open a "session" | spawn a task}`. The matcher runs in the **activity module's
ingest pipeline, NOT the control-plane process** (ADR-0028: an analytics
pipeline must not share the control plane's event loop / error budget). Same
"one store of definitions, separate evaluators" shape ADR-0037 already uses.

### Layer 4 — dashboards as config-driven views (presets, not plugins)
Widgets/queries over the event store + detections. **"Demo activity"** and
**"Lab status (what's up / down)"** are *presets*, not separate modules — a
`Failover` event is literally "a demo is down." A demo type is a named
correlation rule expressed in device roles + a sequence + a window.

## Why generalize (the "AEC Demo Dashboard is too specific" question)

One ingest + detection + dashboard engine powers demo reporting, lab health, and
arbitrary custom detections — instead of a one-off demo dashboard. The
demo-specific logic lives in **data** (rules + a preset), not code. Naming:
module = `activity`; dashboards = `demo` / `lab` presets.

## Non-goals / boundaries (carried from ADR-0028)

- **Read-only.** The tracker never mutates a device; the two-gate / dangerous-op
  machinery does not apply (reads still route through the gate for uniform
  audit).
- **Process isolation.** The high-volume ingest/CEP does not run inside the
  availability-sensitive control plane.
- **Separable.** Same repo, clearly separable module, deployable independently.

## Sequence

1. **Layer 1** — ACS log read/search slice (this PR series). De-risks the schema.
2. **Layer 2** — normalized event store + device-event ingestion.
3. **Layer 3** — generalized event-pattern detections.
4. **Layer 4** — the `activity` dashboards (lab + demo presets).

Each layer ships on its own; nothing downstream is committed until its inputs
are proven against real data.

## Open questions to settle before Layer 2

- Retention/volume policy for the event store (ACS recording churn is high).
- Device-event source for Layer 2 (VAPIX event stream vs MQTT vs poll) — pick
  per device capability.
- The rule expression language for Layer 3 (declarative match spec vs small DSL).
