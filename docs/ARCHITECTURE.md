# ADMZ Architecture

This document maps the major modules and how they connect.

## Module map

```
admz/
├── __init__.py            — public API: create_device_registry, exceptions
├── __main__.py            — CLI entry: `python -m admz {api,mcp,discover}`
├── device_registry.py     — DeviceRegistry ABC
├── factory.py             — backend selection (env var → registry instance)
├── exceptions.py          — ADMZError hierarchy
├── fleet_settings.py      — SQLite-backed K/V store for fleet-wide settings
│                            (default password, confirmation levels, MCP tool toggles)
│
├── backends/              — credential storage backends
│   ├── sqlite_backend.py  — local SQLite + Fernet-encrypted passwords
│   └── vault_backend.py   — HashiCorp Vault backend (optional)
│
├── discovery/             — local network discovery (7 protocols)
│   ├── orchestrator.py    — runs protocols in parallel, merges by MAC
│   ├── mdns_discovery.py  — _axis-video._tcp.local. via zeroconf
│   ├── ssdp_discovery.py  — UPnP M-SEARCH
│   ├── onvif_discovery.py — WS-Discovery for NetworkVideoTransmitter
│   ├── arp_scanner.py     — subnet ARP scan with Axis OUI filter
│   ├── ping_sweep.py      — concurrent ICMP ping
│   ├── http_probe.py      — VAPIX header detection
│   ├── snmp_query.py      — sysDescr + sysName enrichment
│   └── credential_probe.py — active no-auth / legacy / supplied-creds probe
│
├── catalog/               — operation catalog (YAML on disk)
│   ├── models.py          — Operation, CgiMetadata, ParameterGroup, etc.
│   ├── loader.py          — reads YAML from disk, caches
│   └── resolver.py        — (device, intent) → filtered docs for the LLM
│
├── knowledge/             — product-specific hints registry
│   ├── models.py          — Hint, ProductKnowledge
│   ├── loader.py          — loads catalog/knowledge/{product-lines,series,products}/
│   └── resolver.py        — accumulates hints from product → series → product-line
│
├── capabilities/          — per-model API support registry
│   ├── models.py          — FirmwareSnapshot, ModelCapabilities
│   ├── loader.py          — loads catalog/capabilities/models/
│   └── resolver.py        — "does (model, firmware) support api_id?"
│
├── firmware/              — Axis public FTP firmware fetcher + upgrade-path
│   ├── downloader.py      — fetch .bin from MPQT/PACS, cache locally
│   └── upgrade_path.py    — LTS milestone-aware cross-major upgrade path
│
├── executor/              — API call execution
│   ├── base.py            — BaseExecutor ABC
│   ├── models.py          — ExecutionRequest, StepResult
│   └── vapix.py           — VAPIX executor (legacy-cgi, json-rpc,
│                             config-rest, soap — 4 generations)
│
├── plans/                 — multi-step plan engine
│   ├── models.py          — ExecutionPlan, PlanStep, FailurePolicy
│   └── engine.py          — validation, execution, parallelism, rollback
│
├── snapshot/              — config snapshot/restore/drift/schedule
│   ├── models.py          — DeviceSnapshot, DriftReport, FacetResult
│   ├── engine.py          — orchestrates reads via catalog, normalizes
│   ├── git_repo.py        — thin git wrapper
│   ├── restore.py         — git YAML → execution plan
│   ├── drift.py           — live vs git comparison
│   ├── scheduler.py       — recurring snapshots
│   └── facets/            — pluggable per-facet adapters
│       ├── base.py        — FacetAdapter ABC + SimpleParamFacet
│       ├── image.py, network.py, time_config.py, stream_profiles.py
│       ├── users.py, events.py
│
├── mcp/                   — MCP server (the primary entry point)
│   ├── server.py          — 41 tools wiring everything together
│   └── temp_credentials.py — short-lived device user accounts manager
│
└── api/                   — FastAPI web server (mirrors the MCP surface)
    ├── main.py            — app entry point + lifespan
    ├── context.py         — shared AppContext (catalog, executors,
    │                         plan engine, snapshot engine, scheduler)
    ├── capture.py         — out-of-band capture session store (SQLite)
    ├── confirm_store.py   — multi-level confirmation gate store (SQLite)
    ├── models.py          — pydantic request/response models
    ├── routes/
    │   ├── devices.py     — JSON REST CRUD for devices/accounts + fleet settings
    │   ├── catalog.py     — catalog query/execute/confirm
    │   ├── plans.py       — create/execute/status plans
    │   ├── snapshot.py    — snapshot/restore/diff/drift
    │   ├── discovery.py   — network discovery
    │   ├── schedules.py   — recurring snapshot schedules
    │   ├── capture.py     — credential capture endpoints
    │   ├── confirm.py     — out-of-band confirmation endpoints
    │   └── web.py         — browser-facing HTML routes
    └── templates/         — Jinja templates for the UI
                            (includes confirm_form, confirm_settings,
                             fleet_settings, capture_form, …)

catalog/                   — the actual catalog data (YAML, not code)
├── vapix/
│   ├── cgi/<cgi-name>/    — one folder per legacy/json-rpc CGI endpoint
│   │   ├── _api.yaml      — endpoint metadata (renamed from _cgi.yaml)
│   │   └── <ver>/<op>.yaml — one file per operation, versioned
│   ├── rest/<service>/    — config-rest services (cert, snmp, ssh, …)
│   │   ├── _api.yaml
│   │   └── v<N>/<op>.yaml
│   ├── ws/<service>/      — SOAP services (action-service, certificates, …)
│   │   ├── _api.yaml
│   │   └── <Op>.yaml
│   └── index/
│       ├── by-task.yaml   — task slug → file paths
│       └── by-risk.yaml   — risk level → file paths
├── knowledge/             — product hints (product-lines/, series/, products/)
└── capabilities/          — per-model API snapshots (models/<model>.yaml)
```

## Layering

```
                    ┌─────────────────────────────┐
   entry points  →  │  MCP server / FastAPI app   │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────┴──────────────┐
   orchestrators →  │  PlanEngine   SnapshotEngine│
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼─────────────────────┐
              │                    │                     │
  primitives  ▼                    ▼                     ▼
       ┌─────────────┐      ┌──────────────┐      ┌────────────┐
       │ Executor    │      │   Catalog    │      │  GitRepo   │
       │ (per API    │      │  (loader +   │      │            │
       │  family)    │      │   resolver)  │      │            │
       └──────┬──────┘      └──────────────┘      └────────────┘
              │
              ▼
     ┌─────────────────┐
     │ DeviceRegistry  │ (backend: SQLite or Vault)
     └─────────────────┘
```

Things at a lower layer never import from higher layers. The MCP server
is the only place that wires all the pieces together.

## Data flow: typical agent interaction

1. **User**: "Set the resolution on the lobby camera to 1080p."
2. **Agent**: calls `query_catalog(device_id="camera-lobby-01", intent="change resolution")`
3. **MCP server**: looks up device, asks the resolver, returns operations
   + parameter docs for the LLM
4. **LLM**: picks `param.cgi:update` with `root.Image.I0.Resolution=1920x1080`
5. **Agent**: calls `execute_operation(device_id, operation_id, params)`
6. **MCP server**: checks risk level, looks up operation, gets credentials
   from registry, calls `VapixExecutor.execute()` which builds the HTTP
   request, sends it (with digest auth), parses the response, returns
   `StepResult`
7. **Agent**: relays success/failure to user

For a multi-step change ("update resolution and compression"), step 5 is
replaced by `create_plan` → user approves → `execute_plan`.

## Two-gate safety model

Every operation that writes to a device passes through two independent
gates:

1. **Semantic gate (LLM/user)** — the LLM presents the proposed change
   in natural language; the user approves or rejects.
2. **Mechanical gate (catalog)** — the MCP server consults
   `catalog.get_risk_level()`. If the operation is `dangerous`, it's
   blocked even after user approval until `confirm_dangerous_operation`
   is called with a single-use token (TTL: 5 minutes).

Both gates are independent. A reasoning bug in the LLM can't bypass the
mechanical check; a misconfigured catalog can't bypass user review.

## Snapshot/restore on top of plans

The snapshot system is a thin layer on top of the existing plan engine:

- **Snapshot** = a read-only "plan" — runs catalog read ops via the
  executor, but routes results to facet serializers (write YAML) instead
  of returning to the LLM
- **Restore** = a write plan generated from git YAML — built via
  `RestoreBuilder` and handed to the existing `PlanEngine`
- **Drift** = an in-memory snapshot diffed against git HEAD
- **Schedule** = an asyncio background task per schedule calling fleet
  snapshot at intervals

So the snapshot system gets parallelism, dependency tracking, and
two-gate safety for free.

## Pluggable points

- **API families** — add a new executor by implementing `BaseExecutor`
  and registering it in `executors` dict on the MCP server. Catalog
  picks up via the family namespace (`catalog/vapix/`, `catalog/acs/`,
  etc.).
- **Discovery protocols** — add a new module under `discovery/` extending
  `DiscoveryProtocolBase`, then register it in
  `orchestrator.DiscoveryOrchestrator`.
- **Snapshot facets** — add a new facet class under `snapshot/facets/`
  extending `FacetAdapter` (or `SimpleParamFacet` for prefix-based param
  facets) and decorate with `@register_facet`. New device types come
  online by adding facets, not by changing core code.
- **Registry backends** — add a class implementing `DeviceRegistry` and
  register in `factory.create_device_registry`. Existing backends:
  SQLite (default), Vault.

## Where state lives

| State | Storage | Owner |
|---|---|---|
| Device registry (host, model, tags) | SQLite or Vault | DeviceRegistry backend |
| Credentials (encrypted) | SQLite or Vault | DeviceRegistry backend |
| Device configuration history | Git repo | GitRepo |
| Operation catalog | YAML files on disk | CatalogLoader |
| Product knowledge hints | YAML files on disk | KnowledgeLoader |
| Per-model API capabilities | YAML files on disk | CapabilitiesLoader |
| Fleet settings (default password, confirm levels, MCP toggles) | SQLite | FleetSettings |
| In-flight plans | In-memory dict on PlanEngine | PlanEngine |
| Capture sessions | SQLite | CaptureStore |
| Confirmation sessions (multi-level, password-protected) | SQLite | ConfirmStore |
| Legacy in-memory confirm tokens (TTL 5min) — still used by `execute_operation`; migration to ConfirmStore is pending | In-memory dict on MCP server | ADMZMCPServer |
| Snapshot schedules | JSON in `~/.admz/schedules.json` | SnapshotScheduler |
| Temp credentials (live device users with TTL) | In-memory dict on MCP server | TempCredentialManager |
| Cached firmware binaries | `~/.admz/firmware/*.bin` | firmware.downloader |

## Non-goals

ADMZ deliberately does **not**:

- Replace VMS / video recording systems
- Manage ACAP (analytics application) installation lifecycle directly
  (that's planned as a separate concern, hooked in via the catalog when
  it lands)
- Federate multiple Experience Centers (one ADMZ instance per fleet;
  multi-fleet federation is out of scope)
- Run its own scheduler daemon — schedules run as asyncio tasks inside
  the MCP server process
