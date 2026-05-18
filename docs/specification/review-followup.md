# Production Review Follow-up Tracking

**Review date:** 2026-05-17 (four-agent code review)
**Tracking started:** 2026-05-18
**Status legend:** ✅ done · 🔄 in progress · 📝 deferred · ⏭ skipped (with reason)

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
| 1.14 | README tool count 33 → 40 | `README.md:71, 131` | 📝 |
| 1.15 | README "~30 operations" → actual count (200+) | `README.md:19` | 📝 |
| 1.16 | README REST endpoint groups — add `/api/confirm/...`, fix snapshot path prefixes | `README.md:100` | 📝 |
| 1.17 | ARCHITECTURE.md tool count 33 → 40 | `docs/ARCHITECTURE.md:55` | 📝 |
| 1.18 | ARCHITECTURE.md module map — add `capabilities/`, `knowledge/`, `firmware/`, `fleet_settings.py`, `mcp/temp_credentials.py`, `api/confirm_store.py`, `api/context.py` | `docs/ARCHITECTURE.md:7-82` | 📝 |
| 1.19 | ARCHITECTURE.md — update `_cgi.yaml` → `_api.yaml` references | `docs/ARCHITECTURE.md:76` | 📝 |
| 1.20 | ARCHITECTURE.md "Where state lives" table — capture/confirm/fleet are now SQLite-backed | `docs/ARCHITECTURE.md:180-189` | 📝 |
| 1.21 | MCP_TOOLS_REFERENCE.md — fix "33 tools" claim and add 10 missing tool entries (query_knowledge, test_device_credentials, get/set_fleet_settings, provision_device, download/import/list_cached_firmware, create/cleanup_temp_credentials) | `docs/MCP_TOOLS_REFERENCE.md` | 📝 |
| 1.22 | MCP_INTEGRATION.md — full rewrite (last touched ~3 months ago, ends at tool #10, still says "AxisSecrets") | `docs/MCP_INTEGRATION.md` | 📝 |
| 1.23 | VAULT_SETUP.md — "Axis Secrets" → "ADMZ", `cameras/` → `devices/`, fix imports and URL | `docs/VAULT_SETUP.md:3, 47, 208, 226, 390` | 📝 |
| 1.24 | MIGRATION.md — fix v2-side examples that still use `axis_secrets` | `docs/MIGRATION.md:265, 293-297` | 📝 |

### Operational hygiene

| # | Item | Status |
|---|---|---|
| 1.25 | Make `/health` actually exercise the registry | 📝 |
| 1.26 | Add `ADMZ_LOG_LEVEL` env var (currently `logging.basicConfig(level=INFO)` hardcoded twice) | 📝 |
| 1.27 | Document the joint `admz.db` + `admz.key` backup requirement | 📝 |

---

## Phase 2: Security & gating

| # | Item | Severity | Status |
|---|---|---|---|
| 2.1 | Mask password values in `GET /api/fleet/settings` (MCP already masks) | 🔴 | 📝 |
| 2.2 | Gate `/api/devices/{id}/credentials` behind `tool_get_credentials_enabled` flag | 🔴 | 📝 |
| 2.3 | Default `uvicorn --host 127.0.0.1`; require explicit `--host 0.0.0.0` | 🔴 | 📝 |
| 2.4 | Tighten CORS — env-driven origin list, no wildcard | 🔴 | 📝 |
| 2.5 | Add `ADMZ_VERIFY_SSL` env var for executor + discovery probes | 🔴 | 📝 |
| 2.6 | Wire `dangerous` risk gate into `PlanEngine._execute_step` | 🟠 | 📝 |
| 2.7 | Replace both in-memory `_confirm_tokens` dicts with the SQLite `ConfirmStore` | 🟠 | 📝 |

---

## Phase 3: Architecture & ops

| # | Item | Status |
|---|---|---|
| 3.1 | Extract `build_components(registry, ...)` factory; share between `AppContext` and MCP server (currently duplicated, creates two scheduler instances) | 📝 |
| 3.2 | Switch `SQLiteDeviceRegistry` to per-call short-lived connections (like capture/confirm/fleet_settings) | 📝 |
| 3.3 | Add `close()` method to `SQLiteDeviceRegistry`; call from FastAPI lifespan shutdown | 📝 |
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
| 4.1 | Add authentication to FastAPI app (API token via env, header-based at minimum) | 🔴 | 📝 |
| 4.2 | Add audit log of credential access and operation execution | 🟠 | 📝 |
| 4.3 | Add structured logging (JSON formatter option) | 🟡 | 📝 |
| 4.4 | Implement `requester` parameter (currently documented but ignored in `sqlite_backend.py:172-195`) | 🟡 | 📝 |
| 4.5 | Enforce `0o700` permissions on `~/.admz/` directory | 🟡 | 📝 |
| 4.6 | Add rate limiting on `/capture/{token}` and `/confirm/{token}` POSTs | 🟡 | 📝 |
| 4.7 | Add password attempt lockout for `url_and_password` confirms | 🟡 | 📝 |
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
