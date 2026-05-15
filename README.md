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
  from a single source of truth (~30 operations, growing)
- **Executes operations** against devices with a two-gate risk check
- **Plans multi-step changes** that are reviewed once and run
  autonomously
- **Snapshots configurations** to a git repo for version control,
  diffing, forking, and restore
- **Detects drift** between live device state and the git baseline
- **Schedules recurring snapshots** for unattended fleet backup

## Installation

```bash
git clone <repo-url>
cd admz
pip install -e .
```

Optional extras:

```bash
pip install -e ".[discovery]"   # network discovery
pip install hvac                # Vault backend (otherwise SQLite is default)
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
python -m admz.mcp.server
```

The server exposes 33 tools across these areas:

| Area | Tools |
|---|---|
| Devices & accounts | `list_devices`, `get_device`, `search_devices`, `register_device`, `update_device`, `delete_device`, `list_accounts`, `add_account`, `delete_account`, `get_credentials` |
| Out-of-band capture | `capture_credentials`, `check_capture_status` |
| Discovery | `discover_network_devices`, `register_discovered_device` |
| Catalog & execution | `query_catalog`, `execute_operation`, `confirm_dangerous_operation` |
| Plans | `create_plan`, `execute_plan`, `get_plan_status` |
| Snapshots | `snapshot_device`, `snapshot_fleet`, `restore_device`, `diff_device`, `check_drift` |
| Schedules | `create_snapshot_schedule`, `list_snapshot_schedules`, `update_snapshot_schedule`, `delete_snapshot_schedule`, `run_snapshot_schedule` |

See [`docs/MCP_TOOLS_REFERENCE.md`](docs/MCP_TOOLS_REFERENCE.md) for the
full parameter reference.

### As a web service

```bash
uvicorn admz.api.main:app --host 0.0.0.0 --port 8000
```

Provides:

- JSON REST API mirroring the MCP surface — devices, accounts, catalog,
  plans, snapshots, drift, discovery, schedules (see `/api/docs` for the
  full OpenAPI reference)
- Browser UI for browsing devices and accounts
- Out-of-band credential capture URLs (`/capture/<token>`)

REST endpoint groups:

| Group | Path prefix |
|---|---|
| Devices & accounts | `/api/devices`, `/api/devices/{id}/accounts/...` |
| Catalog & execution | `/api/catalog/query`, `/api/catalog/execute`, `/api/catalog/confirm` |
| Plans | `/api/plans`, `/api/plans/{id}/execute` |
| Snapshots | `/api/snapshot/device`, `/snapshot/fleet`, `/snapshot/restore`, `/snapshot/diff/{id}`, `/snapshot/drift` |
| Discovery | `/api/discovery/scan`, `/api/discovery/register` |
| Schedules | `/api/schedules`, `/api/schedules/{id}/run` |
| Capture | `/api/capture`, `/capture/{token}` |

## Configuration

ADMZ is configured via environment variables:

| Variable | Default | Description |
|---|---|---|
| `DEVICE_REGISTRY_BACKEND` | `sqlite` | `sqlite` or `vault` |
| `ADMZ_DB_PATH` | `~/.admz/admz.db` | SQLite database path |
| `ADMZ_KEY_PATH` | `~/.admz/admz.key` | Fernet key file path |
| `ADMZ_CATALOG_PATH` | `<repo>/catalog` | Operation catalog directory |
| `ADMZ_CONFIG_REPO_PATH` | `~/.admz/config-repo` | Config git repo path |
| `ADMZ_CONFIG_REPO_REMOTE` | _unset_ | Git remote URL for config repo |
| `VAULT_ADDR` | _unset_ | Vault server URL (vault backend only) |
| `VAULT_TOKEN` | _unset_ | Vault auth token |

## Architecture

```
                          ┌─────────────────────┐
                          │   MCP server (33    │
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

## Design documents

The `docs/` folder contains the design thinking behind major subsystems:

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
pytest tests/ --ignore=tests/test_vault_backend.py --ignore=tests/test_factory.py
```

132 tests across catalog, snapshot, scheduler, and SQLite backend.

## License

See [LICENSE](LICENSE).
