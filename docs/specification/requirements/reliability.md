# Requirements: reliability

How ADMZ behaves when devices misbehave, networks flake, partial work
happens, and concurrent callers race. The cross-cutting story for
error handling, retries, timeouts, rollback, and recovery.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-REL-001 — Operations return structured outcomes, never raise to MCP ✅
Every MCP tool returns `{success: bool, ...}` or
`{blocked: true, ...}`. Exceptions inside tool handlers are caught
and converted to `{success: false, error: "..."}` so the LLM gets
parseable failures instead of stack traces.

### FR-REL-002 — Device-side failures don't crash plans ✅
`asyncio.gather(..., return_exceptions=True)` is used in fleet
operations. One device throwing doesn't poison the gather. Per-device
exceptions become synthetic FAIL `StepResult` entries.

### FR-REL-003 — Reboot-style operations recognize timeout as success ✅
Operations with `response.expect_timeout: true` in their YAML (restart,
factory-reset, firmware-upgrade) treat the executor's
`httpx.TimeoutException` as a success-with-warning. See
[ADR-0018](../decisions/0018-expect-timeout-semantics.md).

### FR-REL-004 — Failure policies are explicit per plan ✅ (Phase 3C)
`create_plan(on_failure="stop"|"skip_dependents"|"continue")` selects:
- **stop** — abort on first failure
- **skip_dependents** — continue, skip steps whose deps failed
- **continue** — run every step regardless

Phase 3C fixed `continue` so it actually runs dependents (was
observationally identical to `skip_dependents` before).

### FR-REL-005 — Retries at the transport layer ✅
`VapixExecutor` uses `httpx.AsyncHTTPTransport(retries=N)`. Default
1 (configurable via `ADMZ_VAPIX_RETRIES`). Covers connection failures
only; HTTP-level errors are not retried.

### FR-REL-006 — Configurable per-operation timeouts ✅
Catalog operations can override the default 15s timeout via
`request.timeout` (in their YAML). Firmware upload sets a multi-minute
timeout; the executor honors it.

### FR-REL-007 — Rollback pre-reads where possible 🚧
For `param.cgi:update` steps, the engine pre-reads the current value
of the affected parameters before executing the write. Rollback
operations are then computed and stored as
`plan.rollback_steps`. **Only `param.cgi:update` is supported today;
other write operations (REST POSTs, SOAP writes, multipart uploads)
do not have pre-read rollback.** Generating but not auto-executing
the rollback steps was a v1 deliberate choice — the operator decides
whether to run them.

### FR-REL-008 — Graceful shutdown ✅ (Phase 3A)
FastAPI lifespan stops the scheduler, closes the registry (no-op for
short-lived-connection registries). MCP server cancels the temp-
credential cleanup loop and attempts a final cleanup of all active
temp users on shutdown.

### FR-REL-009 — Health probes that exercise real components ✅ (Phase 1F)
`GET /api/health` invokes `registry.list_devices()` and returns 503
with diagnostic detail when it fails. `GET /health` is a cheap
liveness probe (returns 200 if the process is up).

### FR-REL-010 — Confirmation tokens survive single-process restart ✅ (Phase 2E)
Confirm sessions live in the SQLite `ConfirmStore`, not in-memory.
Process restarts don't invalidate active tokens. Single-use is
enforced atomically via `UPDATE … WHERE status='pending'`.

## Non-functional requirements

### NFR-REL-001 — Audit-write failures never break operations ✅
`AuditLog.record` wraps the SQLite write in try/except + warning log.
A locked DB, full disk, or schema mismatch surfaces as a missing
audit row, not a denied operation. See
[security.md](security.md) NFR-AUTH-003.

### NFR-REL-002 — LDAP failures never break auth ✅
`LdapGroupResolver.resolve_groups` returns `[]` with a logged warning
on any LDAP exception. Authentication still succeeds via the local
`REMOTE_USER` header; just `Principal.groups` ends up empty.

### NFR-REL-003 — Per-device failures don't poison fleet operations ✅
Fleet snapshot, fleet drift, fleet plan execution all use
`return_exceptions=True` gather patterns + explicit error reporting
per device.

## Known limitations

### KL-REL-001 — Rollback covers only param.cgi:update ⚠️
Other write operations (`pwdgrp.cgi:add-user`, REST POSTs, SOAP
state-change operations, multipart firmware uploads) do not capture
pre-read state. A failed restore mid-flight may leave the device in
an intermediate state with no automated revert path.

### KL-REL-002 — Rollback steps generated but not auto-executed ⚠️
`plan.rollback_steps` is populated and `rollback_available: bool` is
surfaced in the plan response, but no MCP tool actually runs the
rollback plan. Operators do it manually via a new `create_plan +
execute_plan` round trip using the rollback step list. A
`rollback_plan(plan_id)` tool would close this.

### KL-REL-003 — No per-device concurrency lock ⚠️
Two plans on the same device can race. The executor doesn't serialize
calls to the same `device_id`. In practice this is rare (the LLM
agent isn't pipelining), but contention with the device's own web
UI is possible.

### KL-REL-004 — No retry policy for HTTP-level errors ⚠️
The transport-level retry covers TCP/TLS failures but not 5xx HTTP
responses. A device returning intermittent 500s during configuration
push will fail the operation; no automatic retry.

### KL-REL-005 — No circuit breaker per device ⚠️
A device flooding ADMZ with timeouts gets the same per-operation
timeout treatment forever. A circuit breaker that marks the device
"unhealthy for the next N minutes" would speed up fleet operations
when a single device is misbehaving.

## References

- ADRs: [0005](../decisions/0005-two-gate-plan-approval.md), [0012](../decisions/0012-snapshot-on-plans.md), [0018](../decisions/0018-expect-timeout-semantics.md)
- Cross-cutting reqs: [security.md](security.md), [performance.md](performance.md)
- Code: `admz/plans/engine.py`, `admz/executor/vapix.py`, `admz/audit.py`
