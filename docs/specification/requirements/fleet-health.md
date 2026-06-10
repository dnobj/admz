# Requirements: fleet health monitoring

Answer "which devices are online right now?" without operators firing ad-hoc
checks. A background monitor polls every registered device on an interval and
keeps a single current-status row per device in the shared SQLite DB; the MCP
and REST surfaces read that table.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-HLT-001 — Current-state-only health store ✅
`admz/fleet/health.py::DeviceHealthStore` keeps one row per device in the
`device_health` SQLite table: `status`, `last_check`, `last_seen_online`,
`latency_ms`, `consecutive_failures`, `last_error`, and (when an
authenticated probe succeeded) `uptime_seconds` + `bootid`. No history is
kept here — "right now, which devices are reachable?" is a single-row read.
Full history is the audit log's / a future time-series store's job.

### FR-HLT-002 — Coarse reachability status ✅
`DeviceHealthStatus` ∈ `online` | `unreachable` (no TCP connect) |
`auth_failed` (TCP up, VAPIX rejected creds) | `unknown` (never checked).
Status reflects the last successful probe; `last_seen_online` advances on
each `online` result so operators can read "was online 2 minutes ago" for
flapping devices.

### FR-HLT-003 — Two-tier probe ✅
`probe_device` (`admz/fleet/health.py`):
1. **Authenticated tier** — if stored credentials + catalog + executor are
   available, call `systemready.cgi:systemReady`. Success → `online` with
   `uptime_seconds`/`bootid`; `401` → `auth_failed`; connect failure →
   `unreachable`.
2. **TCP tier** — otherwise a bare TCP connect to `host:80`. Connect OK →
   `online` (no uptime info); fail → `unreachable`.
The TCP fallback means a device with no stored creds still yields an
"the IP is up" signal.

### FR-HLT-004 — Single background loop, opt-in ✅
`HealthMonitor` is one async loop per process (shared between the MCP and
REST surfaces like SnapshotScheduler), bounded by an asyncio semaphore
(`ADMZ_HEALTH_*` / fleet-setting tunable; default interval 60 s, timeout 5 s,
concurrency 8). It is **off by default** — operators flip
`health_monitor_enabled=true` (fleet setting) to start it; no server restart
needed (FastAPI lifespan checks at startup, and the web UI can start/stop it).
The loop re-reads its interval each cycle, so changing the interval doesn't
require a restart. `start()` is idempotent (calling twice doesn't spawn two
loops).

### FR-HLT-005 — On-demand sweep ✅
`HealthMonitor.sweep_once()` probes every device once and returns the count;
it is public so operators (and tests) can force a sweep without waiting for
the interval. Surfaced over REST as `POST /api/fleet/health/sweep`.

### FR-HLT-006 — Read surface: MCP + REST ✅
- MCP: `get_device_health(device_id)` and `get_fleet_health()` (the latter
  returns per-device entries + `counts` by status). Both read the cache.
- REST: `GET /api/devices/{device_id}/health`, `GET /api/fleet/health`
  (entries + summary counts), `POST /api/fleet/health/sweep`
  (`admz/api/routes/health.py`).
Devices the monitor hasn't checked report `status="unknown"` with a note
pointing at the fleet flag / the sweep endpoint.

### FR-HLT-007 — Failure-counter continuity across sweeps ✅
Each sweep preserves the prior `last_seen_online` and increments
`consecutive_failures` when a probe fails, so a device down for several
cycles shows a rising failure count rather than resetting each sweep.

## Non-functional requirements

### NFR-HLT-001 — Bounded, non-hostile polling ✅
Concurrency is capped by the shared fleet semaphore so health sweeps don't
fight snapshot sweeps or hammer the network. The interval floors at 5 s
(anything faster is rejected) and the per-device timeout clamps to [1, 60] s.

### NFR-HLT-002 — Probe is read-only ✅
Both probe tiers only read (`systemReady` or a TCP connect that writes
nothing to the socket). A health sweep never changes device state.

## Known limitations

### KL-HLT-001 — Cache lags reboots ⚠️
The table is interval-polled, so immediately after a reboot it can still show
the pre-reboot status until the next sweep. For the "did it come back?"
question right after a restart, use `await_device_recovery`
([device-recovery.md](device-recovery.md)), which live-polls instead.

### KL-HLT-002 — One monitor per process ⚠️
Like the scheduler, the monitor is per-process state. The uvicorn process is
the intended owner; pool-spawned MCP subprocesses should not run their own
(see the scheduler's `ADMZ_MCP_NO_SCHEDULER` pattern — the health monitor is
gated behind its opt-in fleet flag, which subprocesses inherit but typically
leave off).

### KL-HLT-003 — No push alerting ⚠️
Health is pull-based current-state. Transition alerting (online→unreachable
notifications, webhooks) is not built here; drift has a transition log
(`drift_alerts`) but health does not yet.

## References

- User stories: [fleet-monitoring](../user-stories/fleet-monitoring.md)
- Sibling: [device-recovery.md](device-recovery.md), [scheduling.md](scheduling.md),
  [drift-detection.md](drift-detection.md), [mcp-server.md](mcp-server.md)
- Cross-cutting: [reliability.md](reliability.md), [performance.md](performance.md)
- Code: `admz/fleet/health.py`, `admz/api/routes/health.py`
