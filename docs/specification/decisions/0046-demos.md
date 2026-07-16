# ADR-0046 — Demos (the experience-center unit of work)

**Status:** Accepted (2026-07-16).
**Relates to:** ADR-0028 (demo / activity tracking — the shared substrate this
finally operationalizes), ADR-0041 (event layers 1–3; this is **Layer 4, phase 1**),
ADR-0044 (scenarios — the config layer a demo composes), ADR-0039 (nav model),
ADR-0034 (widget-gated pushes).

## Context

ADMZ is organized around the **inventory**: devices, their config, their events.
But in an experience center the operator's unit of work isn't a device — it's a
**demo**: the thing you show a customer. A demo is a named bundle of specific
**devices** (each playing a role) + **the config that makes it work** + **the
events that prove it's running** + **a narrative** (what you actually say).

Every real question an operator asks is a mental join across those:

* "Is the loitering demo ready?" → join devices × config × health.
* "Why isn't the speaker firing?" → join roles × events.
* "Put it back" → scenario return, but *which* devices?

The architecture already assumed this keystone. ADR-0028 is literally titled
"Demo / activity tracking". ADR-0041 says *"'Demo tracking' is a configured preset
on this layer — not a separate plugin"* and defines its **Layer 4** as *"a named
correlation rule expressed in device roles + a sequence + a window"*. Layers 1–3
shipped; Layer 4 never did. ADR-0044 names demo/test mode as its motivating
example. The concept was load-bearing in three ADRs and modelled in none.

## Decision

**Ship the demo as a first-class object that composes existing primitives, and
make its one job answering "is this ready?"** — the green light.

| Layer | Primitive | Status |
|---|---|---|
| unit / grouping | Device, Tag | exists (ADR-0032) |
| **config** | **Scenario** — named alternate config; activate / snap-back | exists (ADR-0044) |
| **signal** | **Detection / watched event** — one event, in isolation | exists (ADR-0041 L3) |
| **experience** | **Demo** | ← this ADR |

```
Demo = { name, narrative,
         devices: tag | explicit list, each with a ROLE ("detector", "responder"),
         config_source: "baseline" (default) | "scenario:<name>",
         signals: [ {role|device, category/topic} ],
         computed: readiness }
```

### 1. `config_source` — the baseline IS the demo config

The load-bearing decision. For everyday demos the device's **normal config already
runs them**, so no scenario is involved and "Prepare" is a *check*, not a push. A
**scenario** is the exception: a **sidelined** demo you load when needed and snap
back from.

Two consequences fall straight out:

* **Baseline demos on the same device coexist.** All ready at once, no conflict —
  a camera can take part in five demos its normal config supports.
* **Only a sidelined demo takes exclusive control** (`active_scenario` is
  one-per-device by construction). Ending it hands the device back. So conflict is
  temporary and *directional*, and `in_scenario: <other>` is precisely the
  **"on loan"** signal — with no new state to track.

A baseline demo is therefore **fully drift-verified** (normal drift *is* its
correctness check). A sidelined demo's loaded config is asserted, not verified —
see Deferred.

### 2. Readiness = a pure rollup over caches we already keep

`demos/readiness.py` is pure: (what the demo needs) × (what the device is) → a
verdict. It reads the last-known drift signature (`drift_status_for`) and the
last-known health record — **never a live probe**, the same contract as
`snapshot/drift_status.py`, so the Demos page and the Devices page can never
disagree about a device.

| demo `config_source` | device drift state | verdict |
|---|---|---|
| baseline | `in_sync` | ✓ ready |
| baseline | `drifted` | ✗ config changed — review / revert |
| baseline | `in_scenario: Y` | ✗ **on loan** to sidelined demo Y — end it to reclaim |
| baseline | `none` / `unchecked` | ⚠ no baseline / not checked yet |
| scenario:X | `in_scenario: X` | ✓ ready (loaded) |
| scenario:X | `in_sync` / `drifted` | ○ not loaded — hit Prepare |
| scenario:X | `in_scenario: Y` | ✗ conflict — Y is loaded |

The demo's verdict is the **worst device row** (plus offline devices), with the
reasons listed as blockers. `not_loaded` is amber, not red: it's the expected
resting state of a sidelined demo and the fix is one button.

### 3. Prepare / End delegate to a shared scenario core

Prepare **is** activate; End **is** return-to-baseline. Rather than let a second
surface reimplement "build one plan across N devices, mark the marker, gate it",
that logic moved out of the REST route into `snapshot/scenarios.py`, and both the
`/api/snapshot/scenario/*` routes and the demo endpoints call it. **A demo
introduces no new way to touch a device — only a new reason to**, so it inherits
the ADR-0034 approval widget for free.

Guards: Prepare/End on a *baseline* demo refuse (nothing to load or end). Prepare
**refuses (409) to steal a device another scenario holds** — exclusivity is the
point of a scenario; report the conflict and name the demo that has it.

### 4. Naming: `Demo`

ADR-0028/0041 already use the word, and the codebase is a naming minefield already
("action rule" = an on-device VAPIX rule *and* an ACS rule; "detection" =
`event_detections`, `TRIGGER_DETECTION` tasks, *and* ACS `search_detections`).
Adding "integration" or "experience" as a fourth near-synonym would cost more than
it buys. **Scenario stays the config layer**; a Demo *contains* (optionally) one.

### 5. Demos is a **core** nav item, above Devices

The job view leads; the inventory view supports it. It must be core rather than a
module: module `NavSection` items get `badge`/`accent` stripped in the
NavSection→dict flattening (`templating.py`), and this needs a badge.

## Consequences

* One SQLite `demos` table in the control-plane DB (like `tasks`). `roles` and
  `signals` are JSON so Layer 4 can grow an ordered sequence + window without a
  migration; `config_source` is a string so a demo can later point at something
  other than baseline/scenario.
* Demo CRUD is inert metadata → authenticated principal only (same bar as
  detections). The only device-touching path is Prepare/End, already gated.
* Readiness costs no device round-trips, so the list page is cache-cheap.
* Deleting a demo touches no device and no config.

## Deferred (named, not hidden)

* **Liveness / true Layer 4** — the ordered sequence + window across roles that
  would prove the demo *ran*, not merely that it's configured. Detections match
  one event in isolation (`events/evaluator.py`); `active_window` is a reserved
  unused column and `match_json` was shaped to grow into a tree. Phase 1 shows
  per-signal "last seen" only.
* **Action-rule restore** — `ActionRulesFacet` is snapshot-only (`write_ops = []`),
  firmware-gated to AXIS OS ≥ 12; only `root.Event.*` (`EventsFacet`) restores. So
  a **sidelined** demo's Prepare may not recreate v2beta rules. Baseline demos are
  unaffected (the rules are simply already there). ADMZ *can* create rules
  (ADR-0043) → restore is buildable by replaying them. Highest-value follow-on.
* **Drift vs the active scenario** — drift is measured against `baseline_sha` only,
  so a loaded sidelined demo's config is asserted, not verified.
* **ACS corroboration** — ACS has no firing API; the polled firing is anonymous (no
  rule name), only Firebird names it (alarm-raising only), and ACS events aren't
  joined to ADMZ devices — though `acs_find_camera_for_device` already MAC-correlates.
* **Process isolation** — ADR-0041/0028 say the matcher must not run in the control
  plane; `DetectionEvaluator` does today. Relevant when Layer 4 lands.
