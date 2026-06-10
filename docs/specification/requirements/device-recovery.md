# Requirements: device recovery

Wait for a device to come back after a reboot/restart-class operation and
report — concretely — whether it actually completed a boot cycle. The
operator-facing answer to "is it back up yet?" after an approved reboot.
Implements the v1 path of [GH #49](https://github.com/dnobj/admz/issues/49).

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-REC-001 — Live-poll `systemready`, don't trust the cache ✅
`admz/recovery.py::await_device_recovery` polls the device's
`systemready.cgi:systemReady` operation directly through a dedicated probe
executor (5 s timeout, no retries — a short cadence the shared 15 s+retries
executor would wreck). It does **not** read the health-monitor cache, which
lags reboots (FR-HLT-*). The MCP tool description says as much so the LLM
picks the right tool.

### FR-REC-002 — Recovery requires evidence of a real boot cycle ✅
A first healthy `systemready=yes` response is **not** recovery on its own — a
device polled before it has gone down answers healthy with its pre-reboot
`bootid` and high uptime. Recovery is declared only when a healthy response
coincides with at least one boot-cycle signal:
`offline_observed` ∨ `not_ready_observed` ∨ `bootid != baseline` ∨ uptime
decreased vs the previous probe ∨ uptime < `FRESH_BOOT_UPTIME_S` (180 s).

### FR-REC-003 — Built for repeated calls under the chat watchdog ✅
The chat SSE stream aborts a turn if no event arrives for ~120 s, and no
events flow while an MCP tool runs. So the tool defaults to `timeout_s=90`
and, when it hasn't yet observed recovery, returns `status="still_waiting"`
with the observed `baseline_bootid`. The caller re-invokes passing that
`baseline_bootid` to continue detection across calls. `timeout_s` is clamped
to [5, 600]; `poll_interval_s` to [1, 30]; garbage coerces to defaults.

### FR-REC-004 — Fail fast on bad credentials ✅
A device that is *up* but rejecting credentials shouldn't burn the whole
timeout. After two consecutive `401`/`403` probes the tool returns
`status="auth_failed"`. A single transient `401` (the web server can answer
before the auth subsystem is fully up mid-boot) does not abort — the counter
resets on any other outcome.

### FR-REC-005 — Structured, self-describing result envelope ✅
Every status returns the same shape:
`{success, recovered, status, device_id, waited_s, polls, offline_observed,
not_ready_observed, bootid, uptime_s, needsetup, baseline_bootid, timeout_s,
poll_interval_s, message}` (plus `error` on `auth_failed`). `status` is one of
`recovered` | `still_waiting` | `auth_failed`. `still_waiting` carries
`success=True` and a message telling the caller to re-call with the
`baseline_bootid`.

### FR-REC-006 — Surface factory-default recovery ✅
If the recovered device reports `needsetup=yes` it came back
factory-defaulted (a reset, not just a reboot) and needs provisioning. The
recovered message calls this out so the operator/LLM doesn't assume the
device returned with its prior config.

### FR-REC-007 — Exposed as a read-only MCP tool ✅
`await_device_recovery(device_id, timeout_s=90, poll_interval_s=3,
baseline_bootid="")` (`admz/mcp/server.py`). It is read-only (not in the
destructive-tool set), dispatcher-audited like every tool, and delegates to
the leaf `admz.recovery` core. The chatbot system prompt instructs the model
to call it after an approved reboot or when the user asks "is it back?", and
to re-call on `still_waiting`.

## Non-functional requirements

### NFR-REC-001 — Leaf module, reusable by v2 ✅
`admz/recovery.py` takes `catalog`/`registry` as parameters and never imports
the MCP server, API context, or route modules — so the planned v2 REST
endpoint / job-store path (#49) can reuse the same core. Test seams
(`probe_executor`, `sleep`, `monotonic`) let the 17 unit tests in
`tests/test_recovery.py` run with a fake clock and scripted probe sequence,
no real sleeping or network.

## Known limitations

### KL-REC-001 — Synchronous, no job store (v1 scope) ⚠️
v1 is a synchronous tool only — no background job, no REST endpoint, no UI
card. A long reboot needs the caller to re-invoke with `baseline_bootid`
(up to ~2 more times before concluding the device needs attention). The
job-store + live-card design remains open in #49 as v2.

### KL-REC-002 — `systemready` must exist in the catalog ⚠️
If the atlas catalog lacks `systemready.cgi:systemReady` for the family the
tool raises `OperationNotFoundError`. All current Axis OS devices expose it;
this would only bite a hypothetical non-VAPIX family.

## References

- Issue: [#49](https://github.com/dnobj/admz/issues/49)
- User stories: [device-recovery](../user-stories/device-recovery.md)
- Sibling: [fleet-health.md](fleet-health.md) (cached health — the lagging
  signal this tool deliberately bypasses), [mcp-server.md](mcp-server.md)
- Code: `admz/recovery.py`, `tests/test_recovery.py`
