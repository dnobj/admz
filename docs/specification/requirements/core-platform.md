# Requirements: core platform

The foundation modules every other capability rests on: device
registry ABC, exception hierarchy, the factory that picks backends,
fleet-settings store, and the components builder.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-CORE-001 — DeviceRegistry ABC ✅
`admz/device_registry.py::DeviceRegistry` declares the contract every
backend must satisfy:

**Read methods (required):**
- `get_credentials(device_id, account_id, requester)` → dict
- `get_device_info(device_id)` → dict
- `get_device_by_nickname(nickname)` → dict | None
- `list_devices()` → list[dict]
- `list_accounts(device_id)` → list[dict]
- `device_exists(device_id)` → bool
- `account_exists(device_id, account_id)` → bool

**Write methods (optional, raise NotImplementedError by default):**
- `add_device`, `update_device`, `update_device_info`, `remove_device`
- `add_account`, `remove_account`

**Lifecycle:**
- `close()` — optional. The FastAPI lifespan calls it on shutdown
  via `getattr(registry, "close", None)`.

### FR-CORE-002 — Factory selects backend by env ✅
`admz/factory.py::create_device_registry(backend=None, **kwargs)`:
- `backend` arg or `DEVICE_REGISTRY_BACKEND` env var picks the impl
- Default: `sqlite` (zero-config)
- Currently supports `sqlite`, `vault`
- Lazy imports the concrete class so installing without `hvac`
  doesn't break SQLite installs
- Raises `ConfigurationError` for unknown backend names

### FR-CORE-003 — Exception hierarchy rooted at ADMZError ✅
`admz/exceptions.py`:
- `ADMZError` (root)
  - `DeviceNotFoundError`
  - `AccountNotFoundError`
  - `PermissionDeniedError`
  - `AuthenticationError`
  - `ConfigurationError`
  - `BackendError`

Backends raise these; MCP / REST handlers catch the family and convert
to structured errors. Non-ADMZ exceptions bubble up — they're either
bugs (programming errors) or framework-level (HTTPException from
FastAPI, which has its own handling).

### FR-CORE-004 — Fleet settings store ✅
`admz/fleet_settings.py::FleetSettings` — SQLite-backed K/V store for
settings that apply across all devices:
- `default_password` / `default_username` for `provision_device`
- `confirm_level_<risk>` per-risk confirmation policy
- `confirm_password_hash` PBKDF2 hash

Module-level singleton `fleet_settings`. Per-call connections, WAL mode.

### FR-CORE-005 — Sensitive-value masking helpers ✅
`is_sensitive_setting_key(key)` and `mask_setting_value(value)` in
`admz/fleet_settings.py`, applied uniformly by the MCP tool and the REST
endpoint. **The rule itself lives in `admz/redact.py::is_sensitive_key`** —
named rather than restated here, because restating it is what made this
paragraph wrong.

> **Corrected 2026-08-04 (#214).** This said the rule was
> `"password" in key.lower()`. It has since widened to cover `secret`, `token`,
> `api_key`, compound `*key*` and a discrete `pat`. A reader auditing "are our
> API keys masked?" against the documented rule would have concluded that
> `gemini_api_key`, `acs_webhook_token` and `survey_github_pat` are returned in
> plaintext. They are masked — the docs understated the protection.

### FR-CORE-006 — Components builder ✅ (Phase 3B)
`admz/components.py::build_components(registry, ...)` returns a
`Components` dataclass with the shared orchestration stack: catalog,
resolver, executors, plan_engine, git_repo, snapshot_engine,
restore_builder, drift_detector, scheduler. Both `AppContext`
(FastAPI) and `ADMZMCPServer` (MCP) use this factory. Ensures one
scheduler instance even when both surfaces run in one process.

### FR-CORE-007 — CLI entry point ✅
`admz/__main__.py` exposes:
- `admz api` — start FastAPI server
- `admz mcp` — start MCP server (stdio)
- `admz discover` — one-shot network discovery
- `admz api-key {create,list,revoke}` — API key management

## Non-functional requirements

### NFR-CORE-001 — Zero-config first run ✅
A fresh install with no env vars set works. `~/.admz/admz.db` and
`~/.admz/admz.key` are created on first contact. Directory is chmodded
to 0o700 on Unix (Phase 3A).

### NFR-CORE-002 — Backends are independently installable ✅
Vault support requires `hvac`; the factory lazy-imports. SQLite is
the default and uses only stdlib + `cryptography`.

### NFR-CORE-003 — Single-source version string ✅
`admz/__init__.py::__version__` is the only place the version lives.
`setup.py` reads it via regex; the FastAPI app imports it; health
endpoints use it.

## Known limitations

### KL-CORE-001 — No audit-log of read operations ⚠️
Read operations (list_devices, get_device_info) don't currently
audit-log who looked at what. Write operations + credential
retrieval do. Tradeoff: audit-volume vs completeness. Phase 4D
deliberately scoped to the gated paths; broader audit coverage is
a follow-up.

### KL-CORE-002 — `requester` parameter is opportunistic ⚠️
The ABC accepts `requester` on `get_credentials`. Pre-Phase 4 it was
ignored entirely. Now it's recorded but caller-supplied — the REST
handler combines the route's authenticated principal with any
caller-passed `requester` query parameter. Not all call sites pass
it (MCP tool just passes the principal's name).

## References

- ADRs: [0011](../decisions/0011-pluggable-backends.md), [0020](../decisions/0020-protected-fleet-settings.md)
- Cross-cutting: [security.md](security.md), [extensibility.md](extensibility.md)
- Code: `admz/device_registry.py`, `admz/factory.py`, `admz/exceptions.py`, `admz/fleet_settings.py`, `admz/components.py`, `admz/__main__.py`
