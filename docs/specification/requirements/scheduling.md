# Requirements: scheduling

In-process scheduler for recurring snapshots and drift checks.
Survives restart, supports per-tag and per-device-list filters,
human-readable intervals.

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

### FR-SCH-005 — Two job types: snapshot, drift ✅
A schedule's job type is implicit in the engine reference:
- Schedules calling `snapshot_engine.snapshot_fleet` are snapshot
  schedules
- Schedules calling `drift_detector.check_fleet_drift` are drift
  schedules

The factory functions `register_snapshot_schedule(...)` and
`register_drift_schedule(...)` wire the right callable.

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
- MCP: `list_schedules`, `create_schedule`, `delete_schedule`,
  `set_schedule_enabled`
- REST: `GET/POST /api/v2/schedules`, `DELETE /api/v2/schedules/{id}`

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

## References

- ADRs: [0008](../decisions/0008-mcp-and-rest-surfaces.md), [0012](../decisions/0012-snapshot-on-plans.md)
- Cross-cutting: [reliability.md](reliability.md), [observability.md](observability.md), [performance.md](performance.md)
- Sibling: [snapshot-restore.md](snapshot-restore.md), [drift-detection.md](drift-detection.md)
- Code: `admz/snapshot/scheduler.py`
