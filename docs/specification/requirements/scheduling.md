# Requirements: scheduling

In-process scheduler for recurring jobs. **Today it runs snapshots
only.** The design (ADR-0026) generalizes it into a job-type +
handler-registry scheduler whose first new job type is the scheduled
**configuration audit** (`drift_audit`). Survives restart, supports
per-tag and per-device-list filters (and, planned, per-Org/Site/Group),
human-readable intervals.

> **Accuracy note (2026-05-21):** earlier revisions of this file marked
> drift scheduling and a `/api/v2/...` surface as ✅. Neither shipped —
> `_execute_schedule()` hardcodes `snapshot_fleet()`, there are no
> `register_drift_schedule` / `set_schedule_enabled` symbols, and the
> REST surface is `/api/schedules`, not `/api/v2/...`. The statuses
> below have been corrected against the code, and the planned
> generalization is captured as ADR-0026.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-SCH-001 — SnapshotSchedule model ✅
`admz/snapshot/scheduler.py::SnapshotSchedule`:
- `id`, `description`, `interval_seconds`
- `tag_filter` (optional) — only schedule devices carrying this tag
- `device_ids` (optional) — explicit allowlist
- `enabled`, `last_run`, `next_run`, `last_result`

A schedule with neither filter targets the whole fleet.

### FR-SCH-002 — Human-readable interval parsing ✅
`parse_interval(text)` accepts `30s`, `15m`, `4h`, `1d`. Numeric
prefix can be a float (`1.5h`). Suffix is case-insensitive and has
a known set of aliases (`s`/`sec`/`seconds`, `m`/`min`/`minutes`,
etc.).

### FR-SCH-003 — In-memory scheduler with persistence ✅
`Scheduler` keeps schedules in `~/.admz/schedules.json`. On startup
it loads the file, on every change it rewrites it. Schedules
survive restart; `last_run` / `next_run` persist so the scheduler
doesn't re-fire missed runs after a long downtime.

### FR-SCH-004 — Async loop runs every minute ✅
The scheduler runs a single asyncio task that ticks once a minute.
Each tick checks every enabled schedule's `next_run` and fires
ready jobs. One scheduler instance per process — enforced by the
components builder (FR-CORE-006).

### FR-SCH-005 — Snapshot is the only job type today 🚧
`_execute_schedule()` calls `engine.snapshot_fleet(...)` directly;
`SnapshotSchedule` carries only snapshot params. There is **no** drift
job type and **no** `register_drift_schedule` / `register_snapshot_schedule`
factory in the code. Generalizing to multiple job types — starting with
`drift_audit` — is planned via the unified job scheduler (FR-SCH-010,
ADR-0026).

### FR-SCH-006 — Bounded concurrency via shared semaphore ✅
Both snapshot and drift jobs go through `snapshot_engine` which
holds the fleet semaphore (FR-SNP-004). A schedule that fires
across 500 devices doesn't blast 500 concurrent connections.

### FR-SCH-007 — Last-result captured for visibility ✅
Each run writes a short summary into `last_result` — e.g.
`"snapshot 420/425 devices, 5 failed"`, or `"drift: 12 devices
drifted across 17 fields"`. Visible in MCP `list_schedules` and
the web UI.

### FR-SCH-008 — Per-schedule enable / disable ✅
`enabled=False` skips a schedule without deleting it. Useful for
maintenance windows. Toggling re-computes `next_run` from now +
interval.

### FR-SCH-009 — Schedules exposed via MCP and REST ✅
Actual surface (corrected):
- MCP: `list_snapshot_schedules`, `create_snapshot_schedule`,
  `update_snapshot_schedule`, `delete_snapshot_schedule`,
  `run_snapshot_schedule`
- REST: `GET/POST /api/schedules`, `PATCH/DELETE /api/schedules/{id}`,
  `POST /api/schedules/{id}/run`. Writes follow the post-CR-3 pattern
  (`require_authenticated_principal` + audited).

## Unified job scheduler (planned — ADR-0026)

### FR-SCH-010 — Job type + handler registry ✅
`SnapshotScheduler` now dispatches via a `(job_type → async handler)`
registry. `ScheduledJob` (alias of `SnapshotSchedule` for back-compat)
carries `job_type` (`"snapshot"` | `"drift_audit"` | …) plus
job-specific `params`. Handlers receive a `JobContext` bundle of
deps. Registered at module import via `@register_job_handler(...)`
on `admz/snapshot/scheduler.py`. Existing `schedules.json` rows
without a `job_type` field load as `"snapshot"` so no operator
action is required (migration per ADR-0026). The loop, persistence,
`run_now`, and enable/disable machinery (FR-SCH-002…008) are reused
unchanged.

### FR-SCH-011 — `drift_audit` is the first new job type ✅
A `drift_audit` job runs `DriftDetector.check_fleet_drift(scope)` on
its interval and feeds each report through
`DriftAlertStore.process_report` so only *transitions* (appeared /
changed / cleared) emit alert rows — standing drift is suppressed
(KL-DRF-004). `last_result` summarises checked count, drifted vs
clean, and the transition tally. The history is queryable via
the FR-DRF-010 surface that landed earlier.

### FR-SCH-012 — Hierarchy-aware scope 📋
A job's `scope` accepts `org_id` / `site_id` / `group_id` alongside
`tag_filter` / `device_ids`, resolved to a device set at run time so
dynamic Group membership is honored. A scheduled snapshot for a Site
commits into that Site's Org repo (per the per-Org-repo hierarchy).

### FR-SCH-013 — Scheduled runs attributed to a `scheduler` principal ✅
Every scheduled-job execution writes one audit row with
`requester="scheduler"`, `auth_source="scheduler"`, action
`scheduler.run.<job_type>`, resource `schedule:<id>`. Failures are
audited too (`success=false` + `error_message`). Operator-driven
`run_now` invocations through the REST/MCP surface continue to be
attributed to the calling principal — only the in-process loop is
the scheduler principal.

### FR-SCH-014 — Generalized management surface 📋
`list` / `create` / `update` / `delete` / `run-now` / enable-disable
work uniformly across all job types (the snapshot-specific MCP/REST
names generalize). A web-UI schedules dashboard (cadence, last outcome,
drill-in) is the operator-facing view — currently there is none.

## Non-functional requirements

### NFR-SCH-001 — Scheduler is process-local ✅
There is no distributed scheduler. Running two ADMZ instances
against the same `~/.admz/` would double-fire every schedule.
Multi-instance deployment is not currently supported — see
KL-SCH-002.

### NFR-SCH-002 — Schedule store is small ✅
`schedules.json` is a flat list, expected to stay under 100 KB
even with hundreds of schedules. No DB schema needed.

## Known limitations

### KL-SCH-001 — Minute-granularity tick ⚠️
Schedules with `interval < 60s` will be re-evaluated on the next
minute tick, not at exact interval. Fine for the intended use case
(snapshots every hour, drift sweeps every 15 minutes); not
suitable for second-level scheduling.

### KL-SCH-002 — Single-process only ⚠️
No leader election or distributed lock. Running two ADMZ instances
double-fires schedules. Production HA deployments would need either
external scheduling (cron + `admz` CLI) or a small leader-election
layer.

### KL-SCH-003 — Missed runs are not caught up ⚠️
If the process is down for 4 hours and an hourly snapshot was
scheduled, only one snapshot fires on restart, not four. By design
— back-to-back snapshots after downtime are usually not what an
operator wants.

### KL-SCH-004 — No cron expression syntax ⚠️
Schedules are interval-based ("every 4h"), not cron-based ("every
day at 02:00 UTC"). "At a specific wall-clock time" requires
external scheduling or a planned `cron_expression` field.

### KL-SCH-005 — `run_now` can race the interval loop ✅ (resolved)
Resolved as part of the unified-scheduler work (#22 Slice A).
`_execute_schedule` now acquires a per-job `asyncio.Lock` before
dispatching to the handler, so `run_now` and the interval loop
serialize for the same `schedule_id`. Different schedules continue
to run in parallel (the lock is per-job, not global).

## References

- ADRs: [0008](../decisions/0008-mcp-and-rest-surfaces.md), [0012](../decisions/0012-snapshot-on-plans.md), [0026](../decisions/0026-unified-job-scheduler.md)
- User stories: [scheduled-operations](../user-stories/scheduled-operations.md), [drift-and-monitoring](../user-stories/drift-and-monitoring.md)
- Cross-cutting: [reliability.md](reliability.md), [observability.md](observability.md), [performance.md](performance.md)
- Sibling: [snapshot-restore.md](snapshot-restore.md), [drift-detection.md](drift-detection.md)
- Code: `admz/snapshot/scheduler.py`
