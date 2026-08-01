# Requirements: MCP server

What the MCP server (`admz/mcp/server.py`) must expose and how it
behaves. Co-equal entry point with the REST API
([ADR-0008](../decisions/0008-mcp-and-rest-surfaces.md)).

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-MCP-001 — Stdio transport per the MCP spec ✅
The server runs as `python -m admz mcp`, communicating with the
client over stdin/stdout. No protocol-level auth needed — the trust
boundary is "the user that launched the process."

### FR-MCP-002 — Catalog-in-the-loop tool surface ✅
The primary workflow tools:
- `query_catalog(device_id, intent)` — filtered operations + parameter docs
- `query_knowledge(device_id, topic?)` — product-specific hints
- `check_api_support(device_id, api_id?)` — capability lookup
- `execute_operation(device_id, operation_id, params)` — single op,
  two-gate safety applies
- `confirm_dangerous_operation(confirm_token)` — single-use token
  consumption (Phase 2E unified with REST via ConfirmStore)

### FR-MCP-003 — Multi-step plan tools ✅
- `create_plan(description, steps, on_failure)` — validate + stage
- `execute_plan(plan_id, confirm_dangerous?)` — run; plans containing
  dangerous steps require explicit consent (Phase 2D)
- `get_plan_status(plan_id)` — progress query

### FR-MCP-004 — Device + account CRUD tools ✅
`list_devices`, `get_device`, `search_devices`, `register_device`,
`update_device`, `delete_device`, `list_accounts`, `add_account`,
`delete_account`, `get_credentials` (last one gated by fleet flag).

### FR-MCP-005 — Discovery tools ✅
`discover_network_devices` (read-only network scan),
`register_discovered_device` (operator-explicit add to registry).
**Discovery never auto-registers.**

### FR-MCP-006 — Snapshot / restore / drift tools ✅
`snapshot_device`, `snapshot_fleet`, `restore_device`, `diff_device`,
`check_drift`. Restore builds a plan; doesn't auto-execute.

### FR-MCP-007 — Scheduling tools ✅
`create_snapshot_schedule`, `list_snapshot_schedules`,
`update_snapshot_schedule`, `delete_snapshot_schedule`,
`run_snapshot_schedule`. Persisted to `~/.admz/schedules.json`.

### FR-MCP-008 — Out-of-band credential capture tools ✅
`capture_credentials` returns a URL the user clicks in a browser;
`check_capture_status` polls. **The password never enters the LLM's
context.** Same pattern for `set_fleet_setting` with a password key —
returns a capture URL.

### FR-MCP-009 — Provisioning + temp creds ✅
`provision_device` (probe + auto-create admin user),
`test_device_credentials` (passwords never in response),
`create_temp_credentials` (short-lived `at_<hex>` device users —
plaintext returned because that's the point),
`cleanup_temp_credentials`.

### FR-MCP-010 — Fleet settings tools ✅
`get_fleet_settings` (password values masked),
`set_fleet_setting` (protected keys refused — see
[ADR-0020](../decisions/0020-protected-fleet-settings.md)).

### FR-MCP-011 — Firmware tools ✅
`download_firmware`, `import_firmware`, `list_cached_firmware`.

### FR-MCP-012 — Two-gate safety applies at every write entry ✅
`execute_operation` returns `{blocked: true, confirm_token, ...}` for
dangerous-risk operations. `execute_plan` returns the analog for
plans containing any dangerous step. The MCP server cannot bypass
the catalog risk classification — that's by design (ADR-0005).

### FR-MCP-013 — Tool descriptions document the safety semantics ✅
Each tool's `description` (visible to the LLM) explains gating
behavior, expected inputs, and the "blocked → confirm round trip"
pattern. The LLM doesn't need to discover the safety model
empirically.

### FR-MCP-014 — Get_credentials is opt-in via fleet flag ✅
Filtered out of `list_tools()` when
`tool_get_credentials_enabled != "true"`. The flag is a protected
fleet-setting key; only the web UI can toggle it.

### FR-MCP-015 — Advanced capabilities are readable, never writable ✅
`get_advanced_capabilities` returns the advanced-capability registry
(`admz/capabilities.py`) — every declared switch, its danger class, and
whether it is active and from where — in the same shape `GET /api/capabilities`
serves, so an agent diagnosing an install sees exactly what an operator does.
Read-only, no arguments.

There is deliberately **no** enable/disable tool, and adding one would be a
defect rather than a feature: these switches decide who may satisfy a
confirmation gate and who the calling principal is, so a write tool would let
the model grant itself those powers. Enforced twice — no such tool exists, and
every capability `setting_key` is a protected fleet-setting key, so
`set_fleet_setting` refuses it too ([ADR-0020](../decisions/0020-protected-fleet-settings.md)).
See [ADR-0052](../decisions/0052-advanced-capability-switches.md).

## Non-functional requirements

### NFR-MCP-001 — Tool results are structured JSON, not free text ✅
Every tool returns a dict; success cases have `success: true`,
failures have `success: false, error: "..."`, blocked cases have
`blocked: true, ...`. The LLM can branch on shape, not parse English.

### NFR-MCP-002 — Tool surface is documented in code AND in MCP_TOOLS_REFERENCE.md ✅
Updated each time tools are added or schemas change.

### NFR-MCP-003 — Server logs respect the global log level + format ✅
Uses `admz.logging_config.configure_logging()` like the FastAPI app.
Same `ADMZ_LOG_LEVEL` + `ADMZ_LOG_FORMAT` env vars.

## Known limitations

### KL-MCP-001 — Tool surface lives in one 3,400-line file ⚠️
`admz/mcp/server.py` registers all 52 tools in a single class. The
list_tools dispatcher is a giant if/elif chain. Refactor into a
`tools/` package (one module per tool group) is deferred to the
chatbot work, which will need the same extraction for its
in-process tool dispatch.

### KL-MCP-002 — No per-tool rate limiting ⚠️
A misbehaving LLM agent can spam any tool. Phase 4 added rate limits
on the public-facing browser endpoints (`/capture`, `/confirm`); the
MCP surface is intentionally unmetered because the trust model
trusts the user who launched the process.

### KL-MCP-003 — ADMZ_BASE_URL must match the reverse-proxy URL ⚠️
The MCP server generates `/capture/fleet/{token}` URLs from
`ADMZ_BASE_URL`. When ADMZ runs behind IIS, operators must set this
to the IIS-facing URL or capture links break. Phase 4F added a
startup warning when this is misconfigured.

## References

- ADRs: [0005](../decisions/0005-two-gate-plan-approval.md), [0008](../decisions/0008-mcp-and-rest-surfaces.md), [0009](../decisions/0009-oob-credential-capture.md), [0020](../decisions/0020-protected-fleet-settings.md)
- Cross-cutting reqs: [security.md](security.md), [authentication.md](authentication.md), [reliability.md](reliability.md)
- Tool reference: [docs/MCP_TOOLS_REFERENCE.md](../../MCP_TOOLS_REFERENCE.md)
- Code: `admz/mcp/server.py`
