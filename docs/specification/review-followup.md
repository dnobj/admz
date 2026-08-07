# Production Review Follow-up Tracking

**Review date:** 2026-05-17 (four-agent code review)
**Tracking started:** 2026-05-18
**Status legend:** ✅ done · 🔄 in progress · 📝 deferred · ⏭ skipped (with reason)

> **Note (2026-08-04, #214).** Tied to a dated review, but this is a **live
> tracker, not a dated record**: its Status column asserts present state, so it
> goes stale like any current-state doc. Rows 4.6 and 4.7 sat at 📝 *deferred*
> after both shipped. Keep it current or retire it; a stale tracker is read as
> a work queue.

This document tracks the per-issue follow-up for the production-quality review of ADMZ. Each row is one finding from the review with a concrete fix, a status, and pointers to the commit / file changes that addressed it.

---

## Phase 0: WIP commit + test baseline

| # | Item | Status | Notes |
|---|---|---|---|
| 0.1 | Install `pytest-asyncio` so async tests actually run | ✅ | Added to `requirements-dev.txt`; was silently missing. 42 tests had been silently passing-as-skipped. |
| 0.2 | Fix `VAPXExecutor` typo in `tests/test_catalog.py` (lines 417, 451) | ✅ | Two missed occurrences from the earlier rebase sed pass — SOAP tests imported the misnamed class. |
| 0.3 | Fix test pollution: schedules persist to real `~/.admz/schedules.json` on Windows | ✅ | `test_api_routes.py` now sets both `HOME` and `USERPROFILE` (Windows uses the latter for `expanduser`). |
| 0.4 | Skip Unix-style chmod assertion on Windows | ✅ | `test_sqlite_backend.py::test_key_file_created_with_secure_permissions` now skipped on `sys.platform == "win32"`. |
| 0.5 | Commit WIP (SOAP, capabilities, confirm-store, temp-creds, fleet-settings, catalog rename) | 🔄 | All in working tree from prior session's stash pop. |
| 0.6 | Commit specification docs (this directory) | 🔄 | New files under `docs/specification/` from the spec-writing work. |

---

## Phase 1: Low-risk cleanup

### Vestigial / dead code

| # | Item | File:line | Status |
|---|---|---|---|
| 1.1 | Delete `async-upnp-client` from `requirements.txt` (never imported) | `requirements.txt` | ✅ |
| 1.2 | Delete `_FTP_BASE` alias (no external consumer) | `admz/firmware/downloader.py:45` | ✅ |
| 1.3 | Delete `AxisSecretsError = ADMZError` v1 compat alias | `admz/exceptions.py:12`, `admz/__init__.py:9` | ✅ |
| 1.4 | Delete unused `run_discovery` import (re-imported as `run_network_discovery` on line 79) | `admz/mcp/server.py:47` | ✅ |
| 1.5 | Delete unused `CaptureStatus` import | `admz/mcp/server.py:45` | ✅ |
| 1.6 | Wire `admz/capabilities/` in via new `check_api_support` MCP tool (decided: wire rather than delete; data has real value for pre-checking plan steps) | `admz/mcp/server.py`, `tests/test_capabilities.py` | ✅ |
| 1.7 | Fix `tests/test_factory.py` — rewrote with correct patch targets at the actual import sites; also fixed an incorrect assertion (test claimed Vault was the default; SQLite is) | `tests/test_factory.py` | ✅ |

### Stale config files

| # | Item | File:line | Status |
|---|---|---|---|
| 1.8 | Fix `pytest.ini` coverage target — `--cov=axis_secrets` → `--cov=admz` | `pytest.ini:10` | ✅ |
| 1.9 | Rewrite `setup.py` `install_requires` from `requirements.txt` (currently lists Flask) | `setup.py:33` | ✅ |
| 1.10 | Fix `setup.py` author/email/URL placeholders | `setup.py:9-14` | ✅ |
| 1.11 | Update `setup.py` `Development Status :: 4 - Beta` (currently 3-Alpha) | `setup.py:17` | ✅ |
| 1.12 | Single-source the version string — `api/main.py` now imports `__version__` from `admz` | both files | ✅ |
| 1.13 | Consider adding `pyproject.toml` (modern packaging) | new file | 📝 |

### Documentation drift

| # | Item | File:line | Status |
|---|---|---|---|
| 1.14 | README tool count 33 → 41 | `README.md:71, 131` | ✅ |
| 1.15 | README "~30 operations" → actual count (~250+) | `README.md:19` | ✅ |
| 1.16 | README REST endpoint groups — added `/api/confirm/...`, `/api/fleet/...`, fixed snapshot path prefixes | `README.md:100` | ✅ |
| 1.17 | ARCHITECTURE.md tool count 33 → 41 | `docs/ARCHITECTURE.md:55` | ✅ |
| 1.18 | ARCHITECTURE.md module map — added `capabilities/`, `knowledge/`, `firmware/`, `fleet_settings.py`, `mcp/temp_credentials.py`, `api/confirm_store.py`, `__main__.py`, `discovery/credential_probe.py` | `docs/ARCHITECTURE.md:7-82` | ✅ |
| 1.19 | ARCHITECTURE.md — updated `_cgi.yaml` → `_api.yaml` references and the catalog layout to show cgi/ + rest/ + ws/ | `docs/ARCHITECTURE.md:76` | ✅ |
| 1.20 | ARCHITECTURE.md "Where state lives" table — capture/confirm/fleet are now SQLite-backed; added knowledge/capabilities/firmware/temp-creds rows | `docs/ARCHITECTURE.md:180-189` | ✅ |
| 1.21 | MCP_TOOLS_REFERENCE.md — fixed "33 tools" claim and added 11 missing tool entries (provision_device, test_device_credentials, query_knowledge, check_api_support, create_temp_credentials, cleanup_temp_credentials, get_fleet_settings, set_fleet_setting, download_firmware, import_firmware, list_cached_firmware) | `docs/MCP_TOOLS_REFERENCE.md` | ✅ |
| 1.22 | MCP_INTEGRATION.md — fixed all `AxisSecrets` / path placeholders, added pointer to MCP_TOOLS_REFERENCE for the full 41-tool list (full rewrite deferred — existing 10-tool section retained as quick-start examples) | `docs/MCP_INTEGRATION.md` | ✅ |
| 1.23 | VAULT_SETUP.md — "Axis Secrets" → "ADMZ", `cameras/` → `devices/`, fixed imports and support URL | `docs/VAULT_SETUP.md:3, 47, 208, 226, 390` | ✅ |
| 1.24 | MIGRATION.md — fixed v2-side examples that still used `axis_secrets` and `secret/cameras` | `docs/MIGRATION.md:265, 293-297` | ✅ |

### Operational hygiene

| # | Item | Status |
|---|---|---|
| 1.25 | Make `/health` actually exercise the registry. `/health` remains a cheap liveness probe; `/api/health` now calls `registry.list_devices()` and returns 503 + error detail on failure. 3 new tests in `tests/test_api_routes.py::TestHealth`. | ✅ |
| 1.26 | Add `ADMZ_LOG_LEVEL` env var via new `admz/logging_config.py` (`configure_logging()` called from `__main__.run_api_server` and `mcp/server.py`). 12 new tests in `tests/test_logging_config.py`. | ✅ |
| 1.27 | Document the joint `admz.db` + `admz.key` backup requirement — added "Backup" section to `README.md`. | ✅ |

---

## Phase 2: Security & gating

| # | Item | Severity | Status |
|---|---|---|---|
| 2.1 | Mask password values in `GET /api/fleet/settings`. Extracted `is_sensitive_setting_key`, `mask_setting_value`, `mask_settings_for_display` into `admz/fleet_settings.py`; both MCP and REST surfaces now use the same helper. 11 new tests in `tests/test_fleet_settings.py` + 3 REST tests in `TestFleetSettingsMasking`. | 🔴 | ✅ |
| 2.2 | Gate `/api/devices/{id}/credentials` behind `tool_get_credentials_enabled` flag — returns 403 with a `/confirm-settings` hint when disabled. 3 new tests in `TestCredentialsEndpointGated`. *(Superseded: the endpoint was later removed entirely, and the flag deleted in #151 — see security.md FR-SEC-006 for the current surface.)* | 🔴 | ✅ |
| 2.3 | Default `--host 127.0.0.1` in `__main__.py`; explicit `--host 0.0.0.0` required. Help text documents the no-auth caveat. | 🔴 | ✅ |
| 2.4 | CORS now driven by `ADMZ_ALLOWED_ORIGINS` env var (comma-separated). Default is the 4 localhost variants; `*` is opt-in and downgrades `allow_credentials` to False. | 🔴 | ✅ |
| 2.5 | `ADMZ_VERIFY_SSL` env var via new `admz/ssl_config.py::verify_ssl_default()`. Wired into `VapixExecutor`, `http_probe`, `ssdp_discovery`, `credential_probe` (all 4 hard-coded `verify=False` call sites). Backward-compatible default still False. 13 new tests in `tests/test_ssl_config.py`. | 🔴 | ✅ |
| 2.6 | Wire dangerous-step gate into `PlanEngine.execute_plan`. Plans containing any `risk_level: dangerous` step now require explicit `confirm_dangerous=True`; otherwise raises `PermissionError` listing the offending steps. MCP `execute_plan` tool exposes the parameter and returns a `{blocked: true, reason: "plan_contains_dangerous_steps", retry_with: {confirm_dangerous: true}}` envelope mirroring the `execute_operation` flow. 4 new tests in `tests/test_plan_engine.py::TestDangerousPlanGate`. | 🟠 | ✅ |
| 2.7 | Replace both in-memory `_confirm_tokens` dicts (MCP + REST) with the shared SQLite `ConfirmStore`. Tokens issued via one surface are now consumable via the other; single-use is enforced via `UPDATE … WHERE status='pending'` (the loser of a race gets 409). 3 new tests in `tests/test_api_routes.py::TestConfirmTokenUnification`. | 🟠 | ✅ |

---

## Phase 3: Architecture & ops

| # | Item | Status |
|---|---|---|
| 3.1 | Extracted `build_components(registry, ...)` factory into new `admz/components.py`. Returns a `Components` dataclass holding catalog, resolver, executors, plan_engine, git_repo, snapshot_engine, restore_builder, drift_detector, scheduler. Both `AppContext` and `ADMZMCPServer.__init__` now delegate to it — fixes the two-scheduler-instances-corrupt-schedules.json bug when MCP and FastAPI run in the same process. `AppContext` is now a thin wrapper with property forwarding so existing route code (`ctx.registry`, `ctx.catalog`, etc.) is unchanged. 7 new tests in `tests/test_components.py`. | ✅ |
| 3.2 | Switched `SQLiteDeviceRegistry` to per-call short-lived connections via new `_connect()` helper. All 14 call sites updated to `with self._connect() as conn: ...`. Fixes cross-thread `ProgrammingError` risk under FastAPI's sync handler thread pool. Also tightened `~/.admz/` directory perms to 0o700 (Unix; no-op on Windows). | ✅ |
| 3.3 | Added `close()` no-op method to `SQLiteDeviceRegistry`; FastAPI lifespan calls it on shutdown. Safe to call repeatedly. 3 new tests in `tests/test_sqlite_backend.py::TestShortLivedConnections` (idempotent close, post-close usage, concurrent threads). | ✅ |
| 3.4 | Add database migration runner (Alembic) OR document blow-away-on-major-version policy | 📝 |
| 3.5 | Implement `FailurePolicy.SKIP_DEPENDENTS` and `CONTINUE` (or remove from enum + MCP schema) | 📝 |
| 3.6 | Broaden rollback pre-read to any operation with a `rollback:` spec | 📝 |
| 3.7 | Add MCP tool to actually execute rollback steps | 📝 |
| 3.8 | Add bounded concurrency (semaphore) to `_execute_fleet_parallel` | 📝 |
| 3.9 | Add nickname index to SQLite schema (currently O(N) scan) | 📝 |
| 3.10 | Catalog validation at startup (fail fast on misset `ADMZ_CATALOG_PATH`) | 📝 |
| 3.11 | Add per-device lock to prevent concurrent plans on same device racing | 📝 |
| 3.12 | Add `os.makedirs(..., exist_ok=True)` to `~/.admz/` in capture/confirm/fleet stores | 📝 |
| 3.13 | Add end-to-end integration test (register → query_catalog → execute) using `respx` | 📝 |

### Code quality (deferrable but listed)

| # | Item | Status |
|---|---|---|
| 3.14 | Unify error-handling convention (registries raise; MCP layer converts to JSON) | 📝 |
| 3.15 | Extract shared SQLite helpers (`_default_db_path` + `_connect` duplicated 3 times) | 📝 |
| 3.16 | Extract shared `get_registry()` Depends helper (duplicated 3 times in routes) | 📝 |
| 3.17 | Single-source `CONFIRM_TOKEN_TTL_SECONDS` (defined three times) | 📝 |
| 3.18 | Named constant for `"default"` account_id (literal in 5+ places) | 📝 |
| 3.19 | Single fleet-default-username constant (literal in 5+ places) | 📝 |
| 3.20 | Reconcile `host` vs `ip_address` field redundancy | 📝 |
| 3.21 | Split `admz/mcp/server.py` (3392 lines) by tool group | 📝 |
| 3.22 | Refactor `call_tool` dispatcher to `_TOOL_HANDLERS` dict | 📝 |
| 3.23 | Refactor `_provision_device` (225 lines) into state-machine helpers | 📝 |
| 3.24 | Fix `_execute_on_host` return type annotation (`tuple` → `Tuple[bool, Optional[str]]`) | 📝 |

---

## Phase 4: Auth + audit log + structured logging

| # | Item | Severity | Status |
|---|---|---|---|
| 4.1 | Add authentication to FastAPI app. **Done as four backends** (none/windows/api-key/composite), Windows IWA via reverse proxy + API keys with optional LDAP group enrichment. Closes KG-SEC-001. See ADR-0021/0022/0023, `requirements/authentication.md`, `docs/DEPLOYMENT_WINDOWS.md`. | 🔴 | ✅ |
| 4.2 | Add audit log of credential access and operation execution. New `audit_log` SQLite table, `admz/audit.py` store, `record_event` helper wired into get_credentials/api-key mint/revoke. `GET /api/audit` endpoint with filters. Closes KG-SEC-003. | 🟠 | ✅ |
| 4.3 | Add structured logging (JSON formatter option) | 🟡 | 📝 |
| 4.4 | Implement `requester` parameter — now carries the authenticated principal's identity through to the registry's `get_credentials` call, recorded in the audit log. | 🟡 | ✅ |
| 4.5 | Enforce `0o700` permissions on `~/.admz/` directory — landed in Phase 3A (`SQLiteDeviceRegistry.__init__` chmods the parent dir). | 🟡 | ✅ |
| 4.6 | Add rate limiting on `/capture/{token}` and `/confirm/{token}` POSTs — shipped: `rate_limiter.check` at `admz/api/routes/confirm.py:200`, `:687` and `admz/api/routes/capture.py:200`. | 🟡 | ✅ |
| 4.7 | Add password attempt lockout for `url_and_password` confirms — shipped: `_PW_LOCKOUT_SECONDS = 300.0` with `_record_password_failure` / `_is_locked` (`admz/api/routes/confirm.py:41-57`). | 🟡 | ✅ |
| 4.8 | Document network egress (Axis FTP, Vault) for air-gapped deployments | 🟢 | 📝 |

---

## Phase 5: Spec doc updates (interleaved with above)

| # | Item | Status |
|---|---|---|
| 5.1 | Write remaining 8 user stories (paused mid-spec for the review) | 📝 |
| 5.2 | Write remaining 19 requirements docs | 📝 |
| 5.3 | Write remaining 20 decision records | 📝 |
| 5.4 | Update personas as functional changes land (especially security-conscious-operator) | 📝 |
| 5.5 | Add NFR sections to requirements docs reflecting the fixes that landed | 📝 |

---

## Items intentionally deferred (and why)

- **Secret zeroization** (Python `str` is immutable, lives in arena until GC) — would require switching to bytearrays everywhere; out of proportion to the threat model for this scale of deployment.
- **OIDC / RBAC inside ADMZ** — out of scope; API token auth (4.1) is sufficient for the target persona. Multi-tenant deployments need a different architecture.
- **Real-time monitoring / webhook drift detection** — out of scope per `00-overview.md` non-goals.

---

## Lessons learned (folded back into the spec)

- **Test infrastructure is itself a feature.** Missing `pytest-asyncio` made 42 async tests silently no-op. Track infra deps in `requirements-dev.txt` and add a smoke test that verifies async test recognition.
- **Platform assumptions in tests** (chmod on Windows) — call them out explicitly with `@pytest.mark.skipif`, don't paper over them.
- **`expanduser("~")` differs across platforms** — use `HOME` and `USERPROFILE` together in test fixtures, or refactor to env-driven paths.
