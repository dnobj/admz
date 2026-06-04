# ADR-0028: Demo / activity tracking as a bounded module on ADMZ's shared substrate

**Status:** Accepted (forward-looking / discussion-captured — not yet a committed implementation plan).
**Date:** 2026-06-04.
**Relates to:** ADR-0027 (ConfigCollector / ACS integration layer), [requirements/multi-target-support.md](../requirements/multi-target-support.md) (FR-MT-013), [personas/experience-center-operator.md](../personas/experience-center-operator.md), [requirements/observability.md](../requirements/observability.md), [requirements/hierarchy.md](../requirements/hierarchy.md)

---

## Context

ADMZ has been asked to track and report what has been *demonstrated* at Axis
Experience Centers (AECs) — a dashboard showing which demos ran, at which site,
and how often. The likeliest mechanism: watch **Axis Camera Station (ACS) audit
and security logs**, optionally monitor device event signals (VAPIX event
streams, MQTT, 2N event subscriptions), and recognize that **certain
combinations of device activity constitute a "demo session."** Example: a call
button pressed on a door station that rings a 2N answering unit = the "door
station + 2N answering unit demo."

At first glance this could be built directly into ADMZ. On closer inspection
it is a different mission:

- **ADMZ's mission:** configuration management — declarative state, snapshots,
  drift, gated mutations.
- **The new capability's mission:** event-stream observability and usage
  analytics — continuous ingest of device events, pattern correlation, demo
  session recognition, and roll-up reporting.

The two missions overlap significantly at the *infrastructure* level but diverge
completely at the *application* level. This ADR captures where the line should
be drawn.

---

## Why building on ADMZ's substrate is the right call

### Inventory and Org → Site → Group hierarchy
"What was demonstrated at each AEC" is inherently a site roll-up. ADMZ is
already the system of record for devices-at-sites. The reporting dashboard
needs that hierarchy; rebuilding it would be duplication.

### The ACS integration layer — the single biggest synergy
ADR-0027 (FR-MT Tier 3) commits ADMZ to building an ACS access layer: the
credential store, connection model (agent / WinRM / SQL), and the machinery to
read ACS internals. Reading ACS **audit and security logs** is the *same
connection, credential, and discovery problem* as reading ACS configuration —
the same `AcsConfigCollector` infrastructure, extended with a log-reading path.
This work gets built once and pays for itself twice: config reads for
snapshot/drift (ADR-0027) and log reads for demo-activity tracking (this ADR).

### Device taxonomy and knowledge
Demo-detection rules are expressed in device *roles* — "door station", "2N
answering unit", "speaker" — which is exactly what the `device_type` taxonomy
and knowledge base (ADR-0027) provides. A rule engine that does not have this
taxonomy would have to invent its own.

### UI shell and a near-identical existing primitive
The Axis Signal audit-log screen is a day-grouped event timeline (actor /
operation / target / site scope). A demo-activity feed is structurally that
screen with correlation and aggregation layered on top. Building the demo
dashboard from scratch would re-implement most of that component. The
[Experience Center operator](../personas/experience-center-operator.md)
persona already exists; the dashboard serves them directly.

### Credential storage and OOB capture
The ACS credential for the log-reader is stored and captured via exactly the
same mechanism ADMZ already provides for ACS config access.

---

## Why it must stay a bounded, separately-deployable module — not fused

### Different paradigm: complex event processing, not declarative config
The core is essentially **CEP (complex event processing)**: events matching a
pattern (device roles + action sequence) within a time window ⇒ a demo
instance. That implies:

- A **continuous ingest pipeline** (poll ACS audit logs; subscribe to VAPIX
  event streams / MQTT / 2N event endpoints).
- A **correlation and rule engine** that matches multi-device event clusters to
  demo definitions.
- An **append-only activity-event store** — a time-series-ish record of what
  happened, not a normalized config snapshot.

None of this is part of the catalog / executor / plans model, nor should it be.

### Purely read-only — ADMZ's mutation-safety machinery does not apply
The tracker never changes a device. Two-gate approval, dangerous-op gating,
and "credentials never enter the AI" (ADR-0005, ADR-0006, ADR-0009, ADR-0020)
are all irrelevant here. Coupling a read-only analytics workload to that
machinery adds complexity without safety benefit.

The inverse is equally important: the ADMZ control plane is
**availability-sensitive** (operators rely on it for safe, gated mutations in
front of customers). An analytics pipeline doing high-volume ACS log polling
should not run inside the same process, sharing the same event loop and error
budget as the control plane.

### Different data model, stakeholders, and cadence
The tracking capability is oriented around:
- **Event records / demo definitions / demo sessions / analytics** — not
  device configs, git diffs, or plan steps.
- **AEC managers and sales-enablement** — reporting consumers, not fleet
  operators applying configuration changes.
- **Continuous ingest at log cadence** vs the control plane's
  operator-driven, approval-gated mutation pace.

---

## Decision

Build a **"Activity / Demo Tracking" module** that:

**Reuses from ADMZ:**
- Device inventory and Org → Site → Group hierarchy (read-only queries).
- Device taxonomy / knowledge (`device_type`, knowledge base) for rule
  expressions.
- The ACS connection and credential layer (the `AcsConfigCollector`
  infrastructure from ADR-0027, extended with a log-reading path).
- Credential storage and OOB capture for the ACS connection.
- The UI chrome and the existing audit-log timeline component.
- Optionally (later): the Console / web chatbot for conversational queries
  ("what got demoed in Chicago last week?") — the MCP tool surface already
  exposes the inventory and hierarchy.

**New and bounded within the module:**
- **Log / event ingestion path** — poll ACS Pro audit and security logs;
  optionally subscribe to VAPIX event streams, MQTT, and 2N event endpoints for
  live device signals.
- **Normalized activity-event store** — append-only; separate from the
  config-snapshot git store.
- **Demo-definition / correlation engine** — maps event clusters (device roles +
  action sequence + time window) to named demo types. Rules are expressed in
  terms of `device_type` values from the shared taxonomy.
- **Reporting dashboard** — demo frequency by site, demo type, time period;
  drill-down to individual sessions and the events that composed them.

**Packaging:** same repository, clearly separable module, deployable independently
if needed. Shared code (inventory, hierarchy, ACS layer, credentials, UI chrome)
is imported; the analytics pipeline does not run inside the control-plane process
or share its reliability envelope. The two parts evolve on different cadences.

---

## Risks / notes

### 1 — The detection rules are the product, and they are the risky part
"Certain combinations of device activity ⇒ a demo" is heuristic and is where
the real product value lives. The rule / event model must be prototyped against
**real ACS log samples** before any shape is committed to. The detection rules
are also a natural place for the LLM to assist: classifying ambiguous event
clusters into demo types, and powering conversational dashboard queries via the
Console.

### 2 — This broadens the ACS discovery spike (FR-MT-013)
The spike must now answer log-access questions in addition to config-access
questions — see [requirements/multi-target-support.md FR-MT-013](../requirements/multi-target-support.md)
for the updated scope. Both the config-read path (ADR-0027) and the demo-tracking
path (this ADR) depend on the same ACS access discovery.

---

## Alternatives considered

**Fuse into the ADMZ control plane.**
Rejected. Couples an availability-sensitive, mutation-gated control system to a
high-volume analytics workload. Mixes read-only observability into a codebase
where every write path carries safety machinery that does not apply. The two
evolve at different speeds and should not share a reliability envelope.

**Fully separate greenfield product.**
Rejected. Would re-implement inventory, Org → Site → Group hierarchy, ACS
access and credentials, device taxonomy, and the UI shell that ADMZ already
owns. The ACS access layer in particular would be built twice — paying the
largest single implementation cost of ADR-0027 a second time for no gain.

---

## Consequences

**Positive:**
- The ACS work (ADR-0027 Tier 3) is amortized across two use-cases: config
  snapshot/drift and demo-activity tracking. The same ACS connection, credential
  model, and discovery spike pays for both.
- The existing audit-log timeline UI and the hierarchy model give the demo
  dashboard a fast path to a working v1 without building from scratch.
- The control plane stays clean — no analytics pipeline inside the
  availability-sensitive mutation path.
- Conversational demo-activity queries via the Console become possible without
  any new infrastructure once the module shares the MCP tool surface.

**Negative / watch-items:**
- A second runtime shape — an event ingest pipeline — to operate, monitor, and
  potentially deploy separately. Operational complexity increases relative to a
  pure control-plane ADMZ.
- The module boundary must be actively enforced. Without it the two missions
  will entangle over time, recreating exactly the coupling this decision rejects.
- CEP rule authoring is new surface area. The rule / event model is where the
  product value and the ambiguity both live; prototyping against real ACS log
  data early is essential.

---

## References

- Shared ACS layer: [ADR-0027](0027-pluggable-control-families-and-config-collectors.md) — ConfigCollector / Actuator split; ACS Tier 3 work
- Spike this broadens: [requirements/multi-target-support.md](../requirements/multi-target-support.md) — FR-MT-013 (ACS discovery spike)
- Primary persona: [personas/experience-center-operator.md](../personas/experience-center-operator.md)
- Observability conventions this module should follow: [requirements/observability.md](../requirements/observability.md)
- Hierarchy this module queries: [requirements/hierarchy.md](../requirements/hierarchy.md)
- Read-only snapshot precedent: [requirements/snapshot-restore.md](../requirements/snapshot-restore.md) (ACS read-path)
- Safety gates this module intentionally does *not* need: ADR-0005, ADR-0006, ADR-0009, ADR-0020
