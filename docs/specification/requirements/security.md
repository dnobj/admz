# Requirements: security (cross-cutting)

Security posture for ADMZ. Spans every subsystem because most attacks are systemic. Each requirement is tagged with status (✅ implemented, 🚧 partial, ⚠️ known gap, 📋 planned) and a short note on enforcement.

## Functional requirements

### FR-SEC-001 — Two-gate write safety ✅
Every write operation against a device passes through two independent gates:
1. **Semantic gate** — the LLM (or REST caller) presents the proposed change to a human in natural language; the human approves or rejects.
2. **Mechanical gate** — the catalog's per-operation `risk_level` field. `dangerous`-risk operations are blocked at execute time and return a `confirm_token`. A reasoning bug in the LLM cannot bypass the mechanical check; a misconfigured catalog cannot bypass the user review.

**Enforced at:** `mcp/server.py::_execute_operation`, `api/routes/catalog.py::execute_operation`, and `plans/engine.py::execute_plan`. See [0005](../decisions/0005-two-gate-plan-approval.md).

### FR-SEC-002 — Dangerous-step plans require explicit confirmation ✅
`PlanEngine.execute_plan(plan_id, confirm_dangerous=True)` must be set for any plan containing a step with `risk_level: dangerous`. Otherwise `PermissionError` is raised listing the offending steps. The MCP `execute_plan` tool surfaces this as a structured `{blocked: true, reason: "plan_contains_dangerous_steps", retry_with: {confirm_dangerous: true}}` envelope.

**Enforced at:** `plans/engine.py::execute_plan` (Phase 2D). Tested in `tests/test_plan_engine.py::TestDangerousPlanGate`.

### FR-SEC-003 — Confirmation tokens are single-use, time-limited, cross-surface ✅
`confirm_token`s issued by either MCP `execute_operation` or REST `POST /api/catalog/execute` are stored in a shared SQLite `ConfirmStore`:
- 32-byte URL-safe random (≈256 bits entropy)
- 5-minute TTL (`CONFIRM_TOKEN_TTL_SECONDS = 300`)
- Single-use via `UPDATE … WHERE status='pending'` (atomic — a concurrent second consumer gets HTTP 409)
- Tokens issued by MCP can be consumed via REST and vice versa

**Enforced at:** `api/confirm_store.py` (Phase 2E). Tested in `tests/test_api_routes.py::TestConfirmTokenUnification`.

### FR-SEC-004 — Out-of-band credential capture ✅
Tools that need a device password (`capture_credentials`, `set_fleet_setting` for password keys) return a one-time URL (`/capture/{token}`, `/capture/fleet/{token}`) that opens a browser form. The password is submitted directly to the registry; it never enters the LLM context or the chat transcript.

**Enforced at:** `api/capture.py` + `api/routes/capture.py`. See [0009](../decisions/0009-oob-credential-capture.md).

### FR-SEC-005 — At-rest credential encryption ✅
The SQLite backend encrypts the `password` field of each account with Fernet (AES-128-CBC + HMAC-SHA256). The key lives in `~/.admz/admz.key` (overridable with `ADMZ_KEY_PATH`), chmod'd to `0o600` on Unix. The `~/.admz/` parent directory is chmod'd to `0o700`.

**Enforced at:** `backends/sqlite_backend.py::_store_account_data` and `_encrypt`/`_decrypt`. Tested in `tests/test_sqlite_backend.py::TestEncryption`.

### FR-SEC-006 — `get_credentials` is opt-in ✅
The MCP `get_credentials` tool and the REST `GET /api/devices/{id}/credentials` endpoint return plaintext passwords. Both are gated by the `tool_get_credentials_enabled` fleet flag (default: disabled). The flag is in `PROTECTED_SETTING_KEYS` — MCP cannot write it; only the `/confirm-settings` web UI can.

**Enforced at:** `mcp/server.py::_register_handlers` (filters tool out of `list_tools()`), `api/routes/devices.py::get_device_credentials` (returns 403). See [0020](../decisions/0020-protected-fleet-settings.md).

### FR-SEC-007 — Password values masked when listing fleet settings ✅
`get_fleet_settings` (MCP) and `GET /api/fleet/settings` (REST) both mask any setting whose key contains "password" — displayed as `****** (N chars)` — never plaintext. Shared helper `mask_settings_for_display` in `admz/fleet_settings.py` enforces a single rule across both surfaces.

**Enforced at:** `admz/fleet_settings.py::mask_settings_for_display`. Tested in `tests/test_fleet_settings.py` and `tests/test_api_routes.py::TestFleetSettingsMasking`.

### FR-SEC-008 — Per-protocol device authentication ✅
ADMZ probes each device's `WWW-Authenticate` header on HTTP and HTTPS, persists the detected scheme per-protocol in `device_info["auth"]`, and uses the scheme-appropriate auth handler at request time. Supported schemes: `digest`, `basic`, `bearer`, `none`.

**Enforced at:** `discovery/credential_probe.py::_detect_auth_schemes`, `executor/vapix.py::_resolve_auth`. See [0007](../decisions/0007-per-protocol-auth.md).

### FR-SEC-009 — TLS verification is operator-selectable ✅
The `ADMZ_VERIFY_SSL` env var controls TLS verification across the VAPIX executor and all four discovery probes (`http_probe`, `ssdp_discovery`, `credential_probe` ×2). Default is `false` (backward-compatible — most Axis devices ship with self-signed certs). Accepts `true`/`false`/`1`/`0`/`yes`/`no` (case-insensitive). Unknown values fall back to `false` with a warning.

**Enforced at:** `admz/ssl_config.py::verify_ssl_default`. Tested in `tests/test_ssl_config.py`.

### FR-SEC-010 — Default bind to localhost ✅
`python -m admz api` defaults to `--host 127.0.0.1`. Binding to `0.0.0.0` requires the operator to pass it explicitly. The help text and README both call out the no-auth caveat (FR-SEC-013).

**Enforced at:** `admz/__main__.py::api_parser`.

### FR-SEC-011 — CORS allowlist, not wildcard ✅
The FastAPI app's CORS policy is driven by `ADMZ_ALLOWED_ORIGINS` (comma-separated). Default is the 4 localhost variants (ports 4242 and 8000 × `localhost`/`127.0.0.1`). Wildcard `*` is opt-in and forces `allow_credentials=False` per CORS spec.

**Enforced at:** `api/main.py` (CORS middleware config).

### FR-SEC-012 — Protected fleet-setting keys ✅
The following keys cannot be written via the MCP `set_fleet_setting` tool — only via the `/confirm-settings` web UI:
- `confirm_level_dangerous`, `confirm_level_service-affecting`, `confirm_level_normal`, `confirm_level_read-only`
- `confirm_password_hash`
- `tool_get_credentials_enabled`

The rationale: an LLM that can change its own guardrails has no guardrails.

**Enforced at:** `api/confirm_store.py::PROTECTED_SETTING_KEYS`, `mcp/server.py::_set_fleet_setting`. See [0020](../decisions/0020-protected-fleet-settings.md).

## Non-functional requirements

### NFR-SEC-001 — Confirmation password is PBKDF2-hashed ✅
The `confirm_password_hash` fleet setting stores a PBKDF2-SHA256 hash with 600,000 iterations and a 16-byte salt. Stored format: `salt_hex:hash_hex`.

**Enforced at:** `api/confirm_store.py::hash_confirm_password` / `verify_confirm_password`.

### NFR-SEC-002 — No plaintext in logs ⚠️
The standard logger never emits passwords. `StepResult.error` messages may contain HTTP response bodies that *could* include sensitive data (e.g. a misformatted SOAP response echoing credentials) — this is a non-mitigated risk and is called out for review. Audit log (NFR-OBS-001 in `observability.md`) is a known gap.

### NFR-SEC-003 — Confirm tokens are not predictable ✅
All confirmation tokens use `secrets.token_urlsafe(32)` → 256 bits of entropy. Brute force is computationally infeasible. Single-use enforcement (FR-SEC-003) prevents replay.

## Known gaps (Phase 4 work, tracked in [review-followup.md](../review-followup.md))

### KG-SEC-001 — No authentication on ADMZ itself ⚠️
The FastAPI app mounts every router without any `Depends(auth)` middleware. Endpoints that return passwords (when enabled), execute operations, capture credentials, or change settings are accessible to anyone who can reach the bind address. Mitigations in place:
- Default `--host 127.0.0.1` (FR-SEC-010)
- CORS allowlist not wildcard (FR-SEC-011)
- `get_credentials` opt-in (FR-SEC-006)

But for non-localhost deployment, network-level controls (private subnet, VPN, reverse proxy with its own auth) are mandatory. Adding API-token auth (header-based, env-configured) is the highest-priority Phase 4 item.

### KG-SEC-002 — No CSRF protection on capture / confirm forms ⚠️
Tokens are 256-bit single-use, but a CSRF defense (token in form, validated server-side) would still be appropriate.

### KG-SEC-003 — No audit log ⚠️
The registry ABC documents a `requester` parameter for audit purposes, but the SQLite backend ignores it. Git history of the snapshot repo is the closest equivalent for configuration changes — but credential access, dangerous-operation execution, and authentication events are not recorded.

### KG-SEC-004 — Fernet key has no rotation path ⚠️
Losing `~/.admz/admz.key` means losing all encrypted credentials. There is no master-key wrap or envelope encryption. Joint backup of `admz.db` + `admz.key` is documented in `README.md::Backup`.

### KG-SEC-005 — No rate limiting on `/capture` and `/confirm` POSTs ⚠️
A determined attacker with the token URL can hit the POST handler repeatedly. Tokens are single-use so they're effectively neutralized after the first attempt, but pre-attempt brute-force is unbounded. (Tokens are 256-bit, so brute-force is theoretical, but lockout on the `url_and_password` confirm level is a reasonable hardening.)

### KG-SEC-006 — No secret zeroization in memory ⚠️
Python `str` is immutable and lives in the arena until GC. Memory dumps would expose credentials. Acceptable for the target threat model; switching to `bytearray` everywhere is out of proportion.

## Conventions for new code

- **Don't add MCP tools that return credentials.** The OOB capture pattern is the right answer. Exception: `create_temp_credentials` returns plaintext intentionally because the whole point is the LLM uses the short-lived cred directly.
- **Don't add MCP tools that change confirmation policy.** Protected keys (FR-SEC-012) are the right surface for that.
- **Don't add executor families that hard-code `verify=False`.** Use `verify_ssl_default()` from `admz/ssl_config.py`.
- **Don't add REST endpoints that return passwords without the same fleet-flag gating** as the MCP equivalents (FR-SEC-006).
- **Always mask password-shaped fleet settings** in any list/get response (FR-SEC-007).

## References

- Decisions: [0005](../decisions/0005-two-gate-plan-approval.md), [0006](../decisions/0006-multi-level-confirmation.md), [0007](../decisions/0007-per-protocol-auth.md), [0009](../decisions/0009-oob-credential-capture.md), [0010](../decisions/0010-fernet-encryption.md), [0020](../decisions/0020-protected-fleet-settings.md).
- Cross-cutting reqs: [reliability.md](reliability.md), [observability.md](observability.md), [configuration.md](configuration.md).
- Personas: [security-conscious-operator.md](../personas/security-conscious-operator.md), [llm-agent.md](../personas/llm-agent.md).
