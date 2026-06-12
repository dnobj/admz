# ADMZ — Axis Device Manager

A device management, credential storage, and configuration-as-code
system for Axis network devices (cameras, access controllers, intercoms,
speakers, AXIS Camera Station). Built for agentic workflows — every
capability is exposed as an MCP tool so an LLM can drive it
conversationally.

## What ADMZ does

- **Discovers** Axis devices on the local network via 7 protocols
  (mDNS, SSDP, ONVIF, ARP, ping, HTTP probe, SNMP)
- **Registers** devices with metadata (model, location, tags, accounts)
- **Stores credentials** locally with at-rest encryption (or in
  HashiCorp Vault for enterprise deployments)
- **Captures credentials out-of-band** so passwords never enter the
  LLM conversation
- **Catalogs VAPIX operations** as YAML so the LLM picks parameters
  from a single source of truth (400+ operations across legacy CGI,
  json-RPC, config-REST, and SOAP — maintained in the
  [axis-api-atlas](https://github.com/mrdnlabs/axis-api-atlas) package
  and growing)
- **Executes operations** against devices with a two-gate risk check
- **Plans multi-step changes** that are reviewed once and run
  autonomously
- **Snapshots configurations** to a git repo for version control,
  diffing, forking, and restore
- **Detects drift** between live device state and the git baseline
- **Schedules recurring snapshots** for unattended fleet backup

## Installation

ADMZ depends on the [axis-api-atlas](https://github.com/mrdnlabs/axis-api-atlas)
package (the executable operation catalog + knowledge + capability matrix —
ADR-0029). It is listed in `requirements.txt`, but is not yet on PyPI, so for
local development install the sibling clone editable alongside ADMZ:

```bash
git clone <admz-repo-url> admz
git clone https://github.com/mrdnlabs/axis-api-atlas.git
cd admz
pip install -e ../axis-api-atlas   # the catalog dependency (required)
pip install -e .                   # ADMZ itself
```

The core install already includes the network-discovery stack (zeroconf,
WSDiscovery, scapy, pysnmp), the Vault client (hvac), the chatbot LLM client
(google-genai), and LDAP support (ldap3) — discovery and the chatbot both
degrade gracefully when their optional runtime config is absent. The only
extra is `dev` (test + lint tooling):

```bash
pip install -e ".[dev]"          # development / test dependencies
```

## Quick start

### As a Python library

```python
from admz import create_device_registry

registry = create_device_registry()  # SQLite by default

registry.add_device("camera-lobby-01", {
    "host": "192.168.1.100",
    "model": "AXIS P3245-V",
    "location": "Lobby",
    "tags": ["indoor"],
})
registry.add_account("camera-lobby-01", "default", {
    "username": "admin",
    "password": "...",
})
```

### As an MCP server

```bash
# Configure your MCP client (Claude Desktop, etc.) to launch:
python -m admz mcp
```

The server exposes 47 tools across these areas:

| Area | Tools |
|---|---|
| Devices & accounts | `list_devices`, `get_device`, `search_devices`, `register_device`, `update_device`, `delete_device`, `list_accounts`, `add_account`, `delete_account` |
| Health & recovery | `get_device_health`, `get_fleet_health`, `await_device_recovery` |
| Out-of-band capture | `capture_credentials`, `check_capture_status` |
| Provisioning & temp creds | `provision_device`, `test_device_credentials`, `create_temp_credentials`, `cleanup_temp_credentials` |
| Discovery | `discover_network_devices`, `register_discovered_device`, `reconcile_device_addresses` |
| Catalog, knowledge, capabilities | `query_catalog`, `query_knowledge`, `check_api_support` |
| Execution | `execute_operation`, `confirm_dangerous_operation` |
| Plans | `create_plan`, `execute_plan`, `get_plan_status` |
| Snapshots | `snapshot_device`, `snapshot_fleet`, `restore_device`, `diff_device`, `check_drift`, `get_drift_alerts` |
| Schedules | `create_snapshot_schedule`, `list_snapshot_schedules`, `update_snapshot_schedule`, `delete_snapshot_schedule`, `run_snapshot_schedule` |
| Fleet settings | `get_fleet_settings`, `set_fleet_setting` |
| Firmware | `download_firmware`, `import_firmware`, `list_cached_firmware` |

See [`docs/MCP_TOOLS_REFERENCE.md`](docs/MCP_TOOLS_REFERENCE.md) for the
full parameter reference.

### As a web service

```bash
python -m admz api --host 127.0.0.1 --port 4242
```

Provides:

- JSON REST API mirroring the MCP surface — devices, accounts, catalog,
  plans, snapshots, drift, discovery, schedules (see `/api/docs` for the
  full OpenAPI reference)
- Browser UI for browsing devices and accounts, managing fleet settings,
  and setting the dangerous-operation confirmation policy
- Out-of-band credential capture URLs (`/capture/<token>`)
- Out-of-band confirmation URLs (`/confirm/<token>`)

REST endpoint groups:

| Group | Path prefix |
|---|---|
| Devices & accounts | `/api/devices`, `/api/devices/{id}/accounts/...` |
| Fleet settings | `/api/fleet/settings`, `/api/fleet/settings/{key}` |
| Catalog & execution | `/api/catalog/query`, `/api/catalog/execute`, `/api/catalog/confirm` |
| Plans | `/api/plans`, `/api/plans/{id}/execute`, `/api/plans/{id}` |
| Snapshots | `/api/snapshot/device`, `/api/snapshot/fleet`, `/api/snapshot/restore`, `/api/snapshot/diff/{id}`, `/api/snapshot/drift` |
| Discovery | `/api/discovery/scan`, `/api/discovery/register` |
| Schedules | `/api/schedules`, `/api/schedules/{id}/run` |
| Capture | `/api/capture`, `/api/capture/{token}/status`, `/capture/{token}` (HTML) |
| Confirm | `/api/confirm/{token}/status`, `/confirm/{token}` (HTML) |

> ⚠️ **Authentication is optional and defaults to off.** Set
> `ADMZ_AUTH_BACKEND` to `windows-local` (sign in with the box's own
> Windows accounts via the `/login` page — ADR-0033 — including
> one-click "continue as the signed-in Windows user" SSO, ADR-0035; the
> recommended posture for single-box / workgroup installs), `windows`
> (Windows IWA via a reverse proxy — ADR-0021), or `composite` to require auth; the
> default `none` leaves the web UI / REST API open. LLM agents can
> authenticate with API keys
> (ADR-0022). Regardless of backend, bind to `127.0.0.1` and front it with
> a reverse proxy for any non-localhost deployment. Default `--host` is
> `127.0.0.1`; pass `--host 0.0.0.0` explicitly to expose on all interfaces.

## Configuration

ADMZ is configured via environment variables:

| Variable | Default | Description |
|---|---|---|
| `DEVICE_REGISTRY_BACKEND` | `sqlite` | `sqlite` or `vault` |
| `ADMZ_DB_PATH` | `~/.admz/admz.db` | SQLite database path |
| `ADMZ_KEY_PATH` | `~/.admz/admz.key` | Fernet key file path |
| `ADMZ_CATALOG_PATH` | _(axis-api-atlas package data dir)_ | Override to point at a local/forked atlas data directory |
| `ADMZ_CONFIG_REPO_PATH` | `~/.admz/config-repo` | Config git repo path |
| `ADMZ_CONFIG_REPO_REMOTE` | _unset_ | Git remote URL for config repo |
| `ADMZ_LOG_LEVEL` | `INFO` | Log level: `CRITICAL`/`ERROR`/`WARNING`/`INFO`/`DEBUG` |
| `ADMZ_LOG_FORMAT` | `text` | `text` (human-readable) or `json` (one JSON object per line for log aggregators) |
| `ADMZ_ALLOWED_ORIGINS` | `http://localhost:4242,http://127.0.0.1:4242` | Comma-separated CORS allowlist for the REST API. Pass `*` (NOT recommended) to allow any origin — credentialed requests will be browser-rejected per the CORS spec. |
| `ADMZ_VAPIX_RETRIES` | `1` | Per-request retry count in the VAPIX executor |
| `ADMZ_SNAPSHOT_FLEET_CONCURRENCY` | `50` | Max devices snapshotted concurrently during `snapshot_fleet`. Bound is per-call (asyncio semaphore). Higher values trade memory + FD pressure for wall-clock; lower values are safer at very large fleet sizes. |
| `ADMZ_VERIFY_SSL` | _unset_ (treated as `false`) | Verify device TLS certificates. Off by default because Axis devices ship with self-signed certs. Set to `true` once you've installed trust anchors on the ADMZ host. Accepts `true`/`false`/`1`/`0`/`yes`/`no`. |
| `ADMZ_BASE_URL` | `http://localhost:4242` | Base URL the MCP server uses when generating fleet-password capture links. Behind a reverse proxy, set this to the public-facing URL. |
| `ADMZ_AUTH_BACKEND` | `none` | Web/REST auth: `none`, `windows-local` (Windows-account login page — ADR-0033), `windows` (IWA via reverse proxy — ADR-0021), `api-key`, or `composite`. |
| `ADMZ_LDAP_ENABLED` | `false` | Enable LDAP group enrichment for Windows principals (ADR-0023). When `true`, reads the `ADMZ_LDAP_*` connection vars. |
| `ADMZ_GEMINI_API_KEY` | _unset_ | Seeds the Gemini API key for the web chatbot (`/chat`). Stored thereafter as a protected fleet setting; the route is disabled when unset. |
| `ADMZ_GEMINI_DEFAULT_MODEL` | `gemini-2.5-flash` | Default chatbot model (operators can also pick per-session from the dropdown). |
| `VAULT_ADDR` | _unset_ | Vault server URL (vault backend only) |
| `VAULT_TOKEN` | _unset_ | Vault auth token |
| `VAULT_ROLE_ID` | _unset_ | AppRole role id (vault backend only) |
| `VAULT_SECRET_ID` | _unset_ | AppRole secret id (vault backend only) |

Additional env vars exist for finer control (auth proxy trust, LDAP
connection details, Gemini retry/thinking budget, git timeouts, fleet-health
intervals, survey mode). They are documented at their point of use in the
code and in the relevant `docs/specification/requirements/` files.

## Architecture

```
                          ┌─────────────────────┐
                          │   MCP server (44    │
                          │      tools)         │
                          └──────────┬──────────┘
                                     │
       ┌─────────────────────────────┼─────────────────────────────┐
       │                             │                             │
       ▼                             ▼                             ▼
┌─────────────┐              ┌──────────────┐             ┌────────────────┐
│  Registry   │              │   Catalog    │             │    Snapshot    │
│  (SQLite /  │              │  (YAML ops,  │             │   (git-backed  │
│   Vault)    │              │   indexes)   │             │    configs)    │
└──────┬──────┘              └──────┬───────┘             └────────┬───────┘
       │                            │                              │
       ▼                            ▼                              ▼
┌─────────────┐              ┌──────────────┐             ┌────────────────┐
│  Discovery  │              │  Executors   │             │    Facets +    │
│  (7 proto-  │              │   (VAPIX +   │             │   restore +    │
│   cols)     │              │   future)    │             │  drift + sched │
└─────────────┘              └──────┬───────┘             └────────────────┘
                                    │
                                    ▼
                            ┌──────────────┐
                            │  Plan engine │
                            │  (multi-step │
                            │  + fleet)    │
                            └──────────────┘
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for a deeper walkthrough.

## Documentation

The `docs/` folder contains:

**Specification** (start here for new contributors):
- **[docs/specification/](docs/specification/)** — the spec-of-record:
  personas, user stories, requirements, decision records, and a
  production-review follow-up tracker. Index at
  [docs/specification/INDEX.md](docs/specification/INDEX.md).

**Design documents** (the thinking behind major subsystems):
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** — module map and data flow
- **[MCP_TOOLS_REFERENCE.md](docs/MCP_TOOLS_REFERENCE.md)** — every tool's
  inputs and outputs
- **[VAPIX_CATALOG_DESIGN.md](docs/VAPIX_CATALOG_DESIGN.md)** — how the
  operation catalog is organized; the catalog-in-the-loop MCP pattern;
  plan-based execution
- **[EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md](docs/EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md)**
  — git-backed configuration management
- **[NETWORK_DISCOVERY_RESEARCH.md](docs/NETWORK_DISCOVERY_RESEARCH.md)**
  — research notes on local device discovery

## Tests

```bash
pytest tests/ --ignore=tests/test_vault_backend.py
```

~1,600 tests across the executor, plans, operations gate, snapshots,
scheduler, discovery, capture, confirm-store, redaction, firmware, auth,
chatbot, survey, API routes, and SQLite backend. (Vault backend tests and a
handful of live-device tests are skipped unless their target is reachable.)

Coverage is measured via `pytest-cov`; an HTML report is written to
`htmlcov/`.

### End-to-end testing of approval-gated flows (dev only)

ADMZ's `url_*` confirmation gates are deliberately human-only, which blocks
*unattended* end-to-end tests of reboot/restore/etc. For development,
`tools/dev_auto_approve.py` is an automated stand-in for the human approver —
it drives the **real** confirmation endpoint (no production bypass), scoped to
`lab`/`test`-tagged devices and guarded by `ADMZ_DEV_AUTO_APPROVE=1`. See
**[docs/DEV_AUTO_APPROVE.md](docs/DEV_AUTO_APPROVE.md)** for the design,
safety model, and a verified live smoke-test recipe. **Never run it against a
production ADMZ.**

## Backup

ADMZ stores two files on first run that must be backed up **together**:

| File | Default location | Override env var |
|---|---|---|
| Encrypted device registry | `~/.admz/admz.db` | `ADMZ_DB_PATH` |
| Fernet encryption key | `~/.admz/admz.key` | `ADMZ_KEY_PATH` |

The DB without the key is useless (passwords cannot be decrypted). The
key without the DB has nothing to decrypt. Treat them as a single
inseparable backup unit. For Vault-backed deployments, both files are
empty and you back up Vault instead.

## License

See [LICENSE](LICENSE).
