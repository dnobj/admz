# Requirements: observability

Logs, audit records, health probes, and visibility into ADMZ at
runtime. What an operator (or their monitoring stack) can see.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-OBS-001 — Configurable log level ✅
`ADMZ_LOG_LEVEL` env var selects `CRITICAL` / `ERROR` / `WARNING` /
`INFO` (default) / `DEBUG`. Case-insensitive, whitespace-stripped.
Unknown values fall back to `INFO` with a warning.

### FR-OBS-002 — Configurable log format ✅ (Phase 4 stretch)
`ADMZ_LOG_FORMAT` env var: `text` (default, human-readable) or `json`
(one JSON object per line for aggregators — Splunk, Loki, ELK,
Datadog, CloudWatch). The JSON formatter merges any `extra={...}` data
from `logger.info("msg", extra={"k": v})` calls into the emitted
object verbatim.

### FR-OBS-003 — Audit log of credential access and key events ✅ (Phase 4D)
The `audit_log` SQLite table records:
- `get_credentials` (with success/failure, requester, resource)
- `api_key.create` / `api_key.revoke`
- (Extensible) any handler that calls `record_event(principal, …)`

Each entry has timestamp, requester, auth_source, action, resource,
details_json, success, error_message. See
[security.md](security.md) FR-AUTH-011.

### FR-OBS-004 — Audit log read endpoint ✅
`GET /api/audit?limit=&action=&requester=&since=` returns recent
entries newest-first with filters. Authenticated like every other
`/api/*` route.

### FR-OBS-005 — Liveness vs readiness probes ✅ (Phase 1F)
- `/health` — cheap liveness, returns 200 if the process is up.
  Designed for fast/cheap polling by reverse proxies and load
  balancers.
- `/api/health` — readiness, actively calls `registry.list_devices()`
  and returns 503 + diagnostic detail on failure. Designed for
  Kubernetes-style readiness gating.

### FR-OBS-006 — Health probes bypass auth ✅
Both health endpoints are in the auth-exempt list so the reverse
proxy can probe without forwarding credentials.

### FR-OBS-007 — Snapshot history is the configuration audit trail ✅
Every configuration change tracked via the snapshot/restore system
produces a git commit with timestamp, author (when the git repo is
configured with a user), and the diff. `git log fleet/<device>/`
shows the history; `git blame` reveals who touched a specific value
last.

## Non-functional requirements

### NFR-OBS-001 — Logs include enough context to root-cause ✅
Critical paths (registry operations, plan steps, executor requests,
auth attempts) emit logs with the device_id, operation_id, and
outcome. The JSON formatter (FR-OBS-002) makes the context structured
for aggregator queries.

### NFR-OBS-002 — Audit log is best-effort (never breaks operations) ✅
See [reliability.md](reliability.md) NFR-REL-001. Audit-write
failures log a warning but never deny the underlying operation.

### NFR-OBS-003 — Logs never contain plaintext credentials ✅
Convention: never log password values, API keys (other than display
names), or Fernet bytes. The masking helpers in
`admz/fleet_settings.py` are used everywhere fleet settings get
written to logs.

## Known limitations

### KL-OBS-001 — No metrics endpoint ⚠️
No Prometheus `/metrics`, no StatsD client, no OpenTelemetry traces.
Operators monitor via log aggregation (JSON format helps) and the
audit log query. A future enhancement could add a `/api/metrics`
exposition in Prometheus text format.

### KL-OBS-002 — No request-log middleware ⚠️
HTTP access logs come from uvicorn's default; they don't include the
authenticated principal. The audit log carries the principal for
gated actions, but routine reads (`GET /api/devices`) don't appear
in any persistent log unless uvicorn's access log is captured.

### KL-OBS-003 — No alerting integration ⚠️
ADMZ doesn't post to Slack, send email, page on-call, or write to
syslog. Operators integrate via their log-aggregator's alerting (the
JSON logs make this practical).

### KL-OBS-004 — Drift history is point-in-time, not persistent ⚠️
Each `check_drift` call is independent. Drift events aren't recorded
to the audit log or to a separate drift-history table. Trend analysis
("when did the lobby cameras start drifting?") requires external
log/event capture today.

## References

- ADRs: [0024](../decisions/0024-bundled-web-chatbot.md) (the chatbot will use this log infrastructure too)
- Cross-cutting reqs: [security.md](security.md), [reliability.md](reliability.md), [configuration.md](configuration.md)
- Code: `admz/logging_config.py`, `admz/audit.py`, `admz/api/main.py` (health endpoints)
