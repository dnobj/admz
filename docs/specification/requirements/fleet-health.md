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
`reachable_no_api` (host answered, but not with usable VAPIX) |
`auth_failed` (TCP up, VAPIX rejected creds) | `needs_setup` (reachable but
factory-defaulted) | `unknown` (never checked).
Status reflects the last successful probe; `last_seen_online` is the
**reachability** clock — it advances on every result that proved the host
answered (`online`, `auth_failed`, `needs_setup`, `reachable_no_api`), so
operators can read "was online 2 minutes ago" for flapping devices. It says
the host replied; it asserts nothing about what ADMZ verified.

### FR-HLT-003 — Two-tier probe ✅
`probe_device` (`admz/fleet/health.py`):
1. **Authenticated tier** — if stored credentials + catalog + executor are
   available, call `systemready.cgi:systemReady`. Success → `online` with
   `uptime_seconds`/`bootid`; `401` → `auth_failed`; connect failure →
   `unreachable`; any other failure → the reachability confirmation of
   FR-HLT-009.
2. **TCP tier** — otherwise a bare TCP connect to the device's effective
   port (`_probe_port`: an explicit `port`, else 443 when the learned scheme
   is https, else 80). Connect OK → `online` (no uptime info); fail →
   `unreachable`.
The TCP fallback means a device with no stored creds still yields an
"the IP is up" signal.

### FR-HLT-009 — Reachability is never inferred from an API failure ✅
"Is the host up?" and "can ADMZ speak its API?" are separate questions and
never share a verdict (GH #138). When the authenticated tier fails with
anything other than a connect-class error — an unparsable body, an unexpected
content type, an unexpected-but-valid HTTP status — `probe_device` **confirms
reachability with a TCP connect** rather than reading the error string:
connect OK → `reachable_no_api`, connect fail → `unreachable`. So
`unreachable` keeps its documented meaning (the host did not answer), and a
record can never carry a measured `latency_ms` while claiming the device is
unreachable. `reachable_no_api` advances `last_seen_online` and does **not**
accumulate `consecutive_failures` — it is a settled state, not a failing
probe. The UI renders it amber ("Reachable, no API") in the *needs attention*
bucket: up, but ADMZ can't manage it. Real-world case: the AXIS T8516 PoE
switch, which answers HTTP in ~80 ms with an HTML login page and had logged
10,795 consecutive "failures" while never once reading as reachable.

### FR-HLT-008 — Auth-aware: a `systemready` 200 is not proof of valid creds ✅
On some Axis firmware `systemready.cgi:systemReady` answers `200` **without
validating credentials**, so a device with a wrong/stale stored password would
otherwise show a misleading `online`. After a successful systemready, the probe
issues an **auth-required** call (`AUTH_CHECK_OP`,
`basicdeviceinfo.cgi:getAllProperties`, via `_confirm_credentials`). The extra
call fires only for already-reachable devices, and is skippable via the
`health_verify_credentials` fleet setting (default on) for fleets of
intentionally low-privilege accounts. This is the gap that masked the
real-world I8016 case (right IP, stale password — was shown "online").

**A `401` from that one call is not proof of bad credentials** (GH #149). It is
corroborated against a second, independent auth-required op
(`CORROBORATION_OP`, `param.cgi:list`) before the password is condemned, so
`_confirm_credentials` is **tri-state**, not a boolean:

| Both ops refuse | → `auth_failed`, error naming *both* ops |
| The corroborator authenticates (2xx) | → stays **`online`**; a `health_probe` marker records which op works here, so it is preferred next probe |
| The corroborator errors or answers oddly | → **status is not moved at all** |

> **Corrected 2026-08-04 (#214).** This requirement was marked ✅ while
> describing the **pre-#154 rule** — *"a `401`/`403` flips the status to
> `auth_failed`"* — which is the single-401 condemnation that PR #154 replaced,
> and the exact behaviour that parked an AXIS P8815-2 at `auth_failed` with
> 18,004 consecutive failures while it was fully manageable. A reader
> "restoring" the documented rule would reintroduce that bug. `CORROBORATION_OP`,
> `AUTH_CHECK_OP` and the `health_probe` marker appeared **zero** times in
> `docs/` before this correction.
>
> The marker itself selects probe **order only** — it never skips verification.
> A marker meaning "trust this device without an auth check" would make a stale
> password on a marked device invisible, which is #149's own complaint inverted.

**The implementation is the source of truth for the outcome table**
(`admz/fleet/health.py`, `_corroborate_rejection`); when it and this paragraph
disagree, believe the code.

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
Each sweep carries the prior `last_seen_online` forward **when the new probe
didn't establish one** (a fresh reachability stamp is never overwritten by a
stale one) and increments `consecutive_failures` when a probe fails, so a
device down for several cycles shows a rising failure count rather than
resetting each sweep. `online` and `reachable_no_api` reset the counter —
both are settled answers, not failures.

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

### KL-HLT-004 — `reachable_no_api` is only reachable from the authenticated tier ⚠️
The status is produced when the *authenticated* probe gets an unusable answer.
The credential-less TCP tier still reports a bare connect as `online`
(FR-HLT-003 §2) — "no credentials stored yet" is a different situation from
"this device doesn't speak VAPIX", and reclassifying it would relabel every
device awaiting credential capture. Per-device-class probes (a plain `GET /`
for a T85, say) and per-class credential verification are GH #15.

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
