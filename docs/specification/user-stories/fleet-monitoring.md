# User stories: fleet health monitoring

"Which of my devices are online right now?" — answered from a maintained
current-status table rather than ad-hoc checks. A background monitor polls
every device on an interval; the MCP and REST surfaces read the cache.

## US-FH-001 — See which devices are reachable, at a glance

**As an** operator of a fleet, **I want to** ask "which devices are online?"
and get an immediate per-device status plus a summary, **so that** I can spot
trouble without checking each device by hand.

**Acceptance criteria:**
1. `get_fleet_health()` (MCP) / `GET /api/fleet/health` (REST) return a
   per-device list plus `counts` by status (`online`, `unreachable`,
   `reachable_no_api`, `auth_failed`, `needs_setup`, `unknown`).
2. Each entry carries `status`, `last_check`, `last_seen_online`,
   `latency_ms`, and `consecutive_failures`; authenticated probes also
   include `uptime_seconds` and `bootid`.
3. A device the monitor hasn't checked yet shows `status="unknown"` with a
   note explaining how to enable the monitor or run a sweep.

**Related requirements:** [fleet-health](../requirements/fleet-health.md), [mcp-server](../requirements/mcp-server.md).

## US-FH-004 — Tell "it's down" apart from "I can't manage it"

**As an** operator with mixed hardware, **I want** a device that ADMZ can't
talk VAPIX to but that is demonstrably up to read as *up*, **so that** a red
"unreachable" always means a real outage and I keep trusting the health page.

**Acceptance criteria:**
1. A device that answers but whose reply isn't usable VAPIX (unparsable body,
   wrong content type, unexpected status) reads `reachable_no_api`, not
   `unreachable` — confirmed by a TCP connect, not inferred from the error.
2. `unreachable` is reserved for a genuine connect failure (timeout, refused,
   no route). A record can never show a measured `latency_ms` **and**
   `unreachable`.
3. The UI shows it amber ("Reachable, no API") in the *needs attention*
   bucket — distinct from both the green of `online` and the red of an
   outage.
4. It doesn't accumulate `consecutive_failures` (it's a stable state, not a
   failing probe), and it advances `last_seen_online` — the host answered.

**Related requirements:** [fleet-health](../requirements/fleet-health.md).

## US-FH-002 — Turn monitoring on without a restart

**As an** operator, **I want to** enable background health polling from
config, **so that** the status table stays fresh without me running checks or
restarting the server.

**Acceptance criteria:**
1. The monitor is off until `health_monitor_enabled=true` (fleet setting);
   flipping it starts the loop without a server restart.
2. The poll interval, timeout, and concurrency are tunable via fleet settings
   / `ADMZ_HEALTH_*` env vars (default 60 s / 5 s / 8), and an interval change
   takes effect on the next cycle without a restart.
3. Polling is bounded (shared fleet semaphore) so it doesn't hammer the
   network or fight snapshot sweeps.

**Related requirements:** [fleet-health](../requirements/fleet-health.md), [configuration](../requirements/configuration.md).

## US-FH-003 — Force a check now

**As an** operator who just changed something, **I want to** trigger an
immediate health sweep, **so that** I don't have to wait for the next interval
to see the result.

**Acceptance criteria:**
1. `POST /api/fleet/health/sweep` probes every device once and returns the
   count checked.
2. A single device's health is readable via `get_device_health(device_id)` /
   `GET /api/devices/{device_id}/health`.
3. The probe is read-only — a sweep never changes device state.

**Related requirements:** [fleet-health](../requirements/fleet-health.md).

## Known limitations

- ⚠️ **Cache lags reboots.** Right after a restart the table can still show
  the old status until the next sweep. For "did it come back?" immediately
  after a reboot, use device recovery
  ([device-recovery](device-recovery.md)), which live-polls.
- ⚠️ **Current-state only, no history or push alerts.** The table holds one
  row per device; there's no transition log or webhook notifier for health
  (unlike drift, which has `drift_alerts`).
