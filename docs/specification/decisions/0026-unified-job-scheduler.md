# ADR-0026: Unified job scheduler

**Status:** Proposed (2026-05-21). Not yet built.
**Supersedes the implicit design in:** `admz/snapshot/scheduler.py`
(snapshot-only today).

## Context

ADMZ already runs recurring work, but the scheduling is snapshot-shaped.
`admz/snapshot/scheduler.py::SnapshotScheduler` has all the reusable
machinery — human-interval parsing (`parse_interval`), JSON persistence
(`~/.admz/schedules.json`), per-job asyncio loops, `run_now`,
enable/disable, `next_run` tracking — but `_execute_schedule()` is
hardwired to `engine.snapshot_fleet(...)`, and `SnapshotSchedule`
carries only snapshot parameters (`tag_filter`, `device_ids`).

The first concrete pressure is **scheduled configuration audits**: the
operator wants ADMZ to run drift checks on a cadence and report what
changed (US-DM-003, US-SCHED-007). But it doesn't stop there — a
realistic ADMZ runs *many* periodic jobs: certificate-expiry checks,
firmware-availability checks, credential-rotation reminders, snapshot-
repo housekeeping/GC. Each is a `(do X, every N, over scope S)`.

Two signals say "don't keep going one-scheduler-per-feature":

1. The naive path is a parallel `DriftScheduler`, then a
   `CertExpiryScheduler`, then a `GcScheduler` — each re-implementing
   the same loop/persistence/run-now/enable-disable code with a
   different callable in the middle.
2. The requirements docs **already drifted** to describe a state that
   was never built: `scheduling.md` FR-SCH-005 marks "two job types:
   snapshot, drift" as ✅ with `register_drift_schedule(...)` factory
   functions that don't exist, and both `scheduling.md` and
   `drift-detection.md` cite a `/api/v2/...` surface that never
   shipped. That drift is a symptom — the *concept* of "a scheduler
   that runs more than snapshots" is already assumed; the code just
   never generalized.

We also have a separate, deliberately-untouched category: **system
background singletons** — the `HealthMonitor` reachability poller,
temp-credential cleanup, the MCP-pool idle reaper. Those are
fixed-purpose, not operator-defined, not per-job tunable. This ADR is
*not* about folding them in; it's about the operator-defined,
persisted, per-job schedules.

## Decision

Generalize `SnapshotScheduler` into a **`JobScheduler`** built on a
**job-type + handler-registry** pattern — the same pluggable-point
shape used for snapshot facets (ADR-0015), executor families
(ADR-0011), and discovery protocols (ADR-0017).

A **`ScheduledJob`** declares:

- **`job_type`** — `"snapshot"` | `"drift_audit"` | … (open set)
- **`interval_seconds`** — parsed from a human interval as today
- **`scope`** — `tag_filter` / `device_ids` **and** (hierarchy-aware)
  `org_id` / `site_id` / `group_id`, resolved to a device set at run
  time so dynamic Group membership is honored
- **`params`** — job-type-specific options (free dict)
- **`enabled`, `last_run`, `next_run`, `last_result`** — unchanged

A **handler registry** maps `job_type` → an async handler:

```python
@register_job("drift_audit")
async def run_drift_audit(job, components) -> str:
    reports = await components.drift_detector.check_fleet_drift(job.scope)
    # persist results, return a one-line summary for last_result
    ...
```

`_execute_schedule()` dispatches by `job_type` to the registered
handler. Everything else — the loop, persistence, `run_now`,
enable/disable, the management surface — is reused unchanged. The first
two registered handlers are `snapshot` (wrapping the existing
`snapshot_fleet`) and `drift_audit` (wrapping `check_fleet_drift` +
result persistence + the existing `drift_alerts` transition logic).

**Attribution:** a scheduled run executes through ADMZ's own engines —
no LLM, no MCP subprocess — and is attributed in the audit log to a
synthetic **`scheduler`** principal, so the who-did-what trail
distinguishes automated runs from operator and anonymous runs.

**Migration:** existing `schedules.json` entries (all snapshot
schedules today) are read as `job_type="snapshot"` so no operator
action is needed.

## Consequences

**Positive:**
- **New periodic capability = register a handler, no new scheduler.**
  Cert-expiry, firmware-availability, rotation reminders, repo GC all
  become one-handler additions.
- **Makes the docs honest.** The "two job types: snapshot, drift"
  claim becomes real, and the API surface in the docs gets corrected
  to what ships.
- **Scheduled config audits land cheaply** — `drift_audit` reuses
  `check_fleet_drift` + `drift_alerts` rather than a bespoke pipeline.
- **Hierarchy-aware from the start** — `scope` accepting
  `org_id`/`site_id`/`group_id` aligns scheduling with the Org → Site →
  Group work, so "audit the Chicago lobby nightly" is expressible.
- **Consistent with the rest of ADMZ** — same pluggable-registry shape
  operators and contributors already know from facets/executors/
  discovery.

**Negative:**
- **In-process, single-instance — unchanged.** Still no HA/leader
  election; two instances against one `~/.admz/` double-fire (KL-SCH-002).
  No missed-run backfill (KL-SCH-003).
- **The `run_now` ↔ interval-loop race** (flagged in the reliability
  review) becomes more visible with more job types; the generalization
  should land a per-job lock at the same time.
- **A migration touches `schedules.json`** — the new shape adds
  `job_type` + `scope`; the loader must default missing `job_type` to
  `"snapshot"` and tolerate old records.
- **Global registry state** (like the facet registry) populated at
  import time — tests use the production registry rather than
  re-registering.

## References

- User stories: [scheduled-operations](../user-stories/scheduled-operations.md)
  (US-SCHED-001…007), [drift-and-monitoring](../user-stories/drift-and-monitoring.md)
  (US-DM-003 scheduled, US-DM-007 just-in-time)
- Requirements: [scheduling](../requirements/scheduling.md),
  [drift-detection](../requirements/drift-detection.md)
- Same pattern: ADR-0015 (pluggable facets), ADR-0011 (pluggable
  backends), ADR-0017 (two-phase discovery / protocol registry)
- Code: `admz/snapshot/scheduler.py` (to be generalized),
  `admz/snapshot/drift.py`, `admz/snapshot/drift_alerts.py`
