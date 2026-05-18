# Requirements: configuration

Environment variables, file paths, and runtime knobs that govern ADMZ behavior. The deployment contract.

## Functional requirements

### FR-CFG-001 — Environment-driven backend selection ✅
`DEVICE_REGISTRY_BACKEND` selects the registry backend. Values: `sqlite` (default) or `vault`. Set explicitly via `create_device_registry("vault")` or `python -m admz` env. Unknown values raise `ConfigurationError`. Case-insensitive.

### FR-CFG-002 — Environment-driven paths ✅
All persistent state can be relocated:

| Variable | Default | Owner |
|---|---|---|
| `ADMZ_DB_PATH` | `~/.admz/admz.db` | SQLiteDeviceRegistry, CaptureStore, ConfirmStore, FleetSettings |
| `ADMZ_KEY_PATH` | `~/.admz/admz.key` | SQLiteDeviceRegistry (Fernet) |
| `ADMZ_CATALOG_PATH` | `<package>/catalog` | CatalogLoader, KnowledgeLoader, CapabilitiesLoader |
| `ADMZ_CONFIG_REPO_PATH` | `~/.admz/config-repo` | GitRepo |
| `ADMZ_CONFIG_REPO_REMOTE` | _unset_ | GitRepo push target |

Firmware cache is `~/.admz/firmware/`; not env-overridable as of this release.

### FR-CFG-003 — Vault auth via env ✅
When `DEVICE_REGISTRY_BACKEND=vault`:
- `VAULT_ADDR` — required, the Vault server URL
- `VAULT_TOKEN` — optional, direct token auth
- `VAULT_ROLE_ID` + `VAULT_SECRET_ID` — optional, AppRole auth (recommended for production)

Mount point and path prefix are constructor args (defaults: `secret` and `devices`); env vars for these are documented in `factory.py` but not yet read.

### FR-CFG-004 — Log level via env ✅
`ADMZ_LOG_LEVEL` controls the root logger level. Values: `CRITICAL`, `ERROR`, `WARNING`, `INFO` (default), `DEBUG`. Case-insensitive, whitespace-stripped. Unknown values fall back to `INFO` with a warning.

**Enforced at:** `admz/logging_config.py::resolve_log_level`, called by `mcp/server.py` import time and `__main__.run_api_server`. Tested in `tests/test_logging_config.py`.

### FR-CFG-005 — TLS verification via env ✅
`ADMZ_VERIFY_SSL` controls whether device HTTPS calls verify certificates. Default: `false` (Axis devices typically ship self-signed). Accepts `true`/`false`/`1`/`0`/`yes`/`no`/`on`/`off` — case-insensitive, whitespace-stripped.

**Enforced at:** `admz/ssl_config.py::verify_ssl_default`, consumed by `VapixExecutor` + 4 discovery probes.

### FR-CFG-006 — CORS allowlist via env ✅
`ADMZ_ALLOWED_ORIGINS` — comma-separated list of allowed origins for the REST API. Default: `http://localhost:4242,http://127.0.0.1:4242,http://localhost:8000,http://127.0.0.1:8000`. Wildcard `*` is permitted but forces `allow_credentials=False`.

### FR-CFG-007 — MCP base URL for capture links ✅
`ADMZ_BASE_URL` — the URL the MCP server prepends when generating fleet-password capture URLs. Default: `http://localhost:8000`. Operators running the API on a different port (e.g. 4242) must set this so capture links are not broken.

### FR-CFG-008 — Executor retry count ✅
`ADMZ_VAPIX_RETRIES` — transport-level retry count for the VAPIX executor. Default: `1`. Applied via `httpx.AsyncHTTPTransport(retries=...)` — covers connection failures only, not HTTP-level errors.

### FR-CFG-009 — Single-source version ✅
The version string lives in `admz/__init__.py::__version__`. `setup.py` reads it via regex (no import); the FastAPI app imports it (`from admz import __version__`); the `/health` and `/api/health` responses use it. No other file hard-codes the version.

## Non-functional requirements

### NFR-CFG-001 — Config files have predictable locations ✅
All ADMZ state lives under `~/.admz/` by default:
- `admz.db` — registry, capture sessions, confirm sessions, fleet settings (single SQLite, WAL mode)
- `admz.key` — Fernet encryption key (mode 0o600 on Unix)
- `config-repo/` — git working tree for snapshots
- `schedules.json` — scheduler state
- `firmware/` — cached firmware binaries

The parent directory is chmod'd to 0o700 on Unix on first run.

### NFR-CFG-002 — Sensible defaults — zero config to start ✅
A fresh install with no env vars set produces a working ADMZ instance that uses SQLite locally. Adding a single device requires only `python -m admz api --port 4242` and a browser visit to `/add-device`.

### NFR-CFG-003 — Config changes don't require restart for catalog data ✅
The catalog is YAML on disk. Adding a new operation file is picked up on next `CatalogLoader.get_operation` call (cache miss → disk read). Process restart is required for the env-driven settings (`ADMZ_*`) — those are read once at module init.

### NFR-CFG-004 — Joint backup discipline 📋
`admz.db` + `admz.key` must be backed up together; either alone is useless. Documented in `README.md::Backup`. No automatic backup machinery ships with ADMZ.

## Known gaps

### KG-CFG-001 — Vault mount point / path prefix not in env ⚠️
Documented in `factory.py` docstring but not actually read in `vault_backend.py`. Operators with non-default mount points must pass the args programmatically.

### KG-CFG-002 — Catalog path validation deferred to first use ⚠️
Misset `ADMZ_CATALOG_PATH` produces "no operations found" silently — errors surface only at first `query_catalog` call. Startup-time validation is a Phase 3 deferred item.

### KG-CFG-003 — No `pyproject.toml` ⚠️
`setup.py` is the only packaging source. Modern tooling (poetry, hatch, build, some CI systems) expects `pyproject.toml`. Low priority but worth adding.

## References

- Decisions: [0011 — pluggable backends](../decisions/0011-pluggable-backends.md), [0014 — config in git, creds in DB](../decisions/0014-config-in-git-creds-in-db.md).
- Cross-cutting reqs: [security.md](security.md), [reliability.md](reliability.md).
