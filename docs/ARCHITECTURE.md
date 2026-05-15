# ADMZ Architecture

This document maps the major modules and how they connect.

## Module map

```
admz/
├── __init__.py            — public API: create_device_registry, exceptions
├── device_registry.py     — DeviceRegistry ABC
├── factory.py             — backend selection (env var → registry instance)
├── exceptions.py          — ADMZError hierarchy
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
│   └── snmp_query.py      — sysDescr + sysName enrichment
│
├── catalog/               — operation catalog (YAML on disk)
│   ├── models.py          — Operation, CgiMetadata, ParameterGroup, etc.
│   ├── loader.py          — reads YAML from disk, caches
│   └── resolver.py        — (device, intent) → filtered docs for the LLM
│
├── executor/              — API call execution
│   ├── base.py            — BaseExecutor ABC
│   ├── models.py          — ExecutionRequest, StepResult
│   └── vapix.py           — VAPIX executor (legacy-cgi, json-rpc, config-rest)
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
│   └── server.py          — 33 tools wiring everything together
│
└── api/                   — FastAPI web server
    ├── main.py            — app entry point
    ├── capture.py         — out-of-band capture session store
    ├── models.py          — pydantic request/response models
    ├── routes/
    │   ├── devices.py     — JSON REST CRUD for devices/accounts
    │   ├── capture.py     — credential capture endpoints
    │   └── web.py         — browser-facing HTML routes
    └── templates/         — Jinja templates for the UI

catalog/                   — the actual catalog data (YAML, not code)
└── vapix/
    ├── cgi/<cgi-name>/    — one folder per CGI endpoint
    │   ├── _cgi.yaml      — endpoint metadata
    │   └── <op>.yaml      — one file per operation
    └── index/
        ├── by-task.yaml   — task slug → file paths
        └── by-risk.yaml   — risk level → file paths
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
| In-flight plans | In-memory dict on PlanEngine | PlanEngine |
| Capture sessions | In-memory dict | CaptureStore |
| Confirm tokens (TTL 5min) | In-memory dict on MCP server | ADMZMCPServer |
| Snapshot schedules | JSON in `~/.admz/schedules.json` | SnapshotScheduler |

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
