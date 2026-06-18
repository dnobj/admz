# ADMZ Architecture

This document maps the major modules and how they connect.

## Module map

```
admz/
├── __init__.py            — public API: create_device_registry, exceptions
├── __main__.py            — CLI entry: `python -m admz {api,mcp,discover,apikey,maint}`
├── device_registry.py     — DeviceRegistry ABC
├── factory.py             — backend selection (env var → registry instance)
├── components.py          — builds the shared component stack (registry,
│                            catalog, executors, engines, scheduler); single
│                            source used by both the MCP and FastAPI surfaces
├── operations.py          — shared gated-execution core: the one risk-gate +
│                            execution tail MCP, REST, and plans all delegate to
├── recovery.py            — reboot-recovery poller (await_device_recovery, #49)
├── redact.py              — shared sensitive-key rules (chat/audit/fleet-settings)
├── exceptions.py          — ADMZError hierarchy
├── validators.py          — identifier + git-ref input validation
├── ssl_config.py          — TLS-verify default resolution
├── logging_config.py      — global log level/format wiring
├── fleet_settings.py      — SQLite-backed K/V store for fleet-wide settings
│                            (default password, confirmation levels, MCP tool toggles)
│
├── auth.py                — web/REST auth backend selection (none/windows/composite)
├── authz.py               — authorization helpers (authenticated-principal gates)
├── api_keys.py            — API keys for LLM agents (ADR-0022)
├── ldap_groups.py         — LDAP group enrichment for Windows principals (ADR-0023)
├── audit.py               — SQLite audit log (record_event across all surfaces)
├── rate_limit.py          — token-bucket rate limiting for public endpoints
├── migrations/            — one-shot data migrations (e.g. hierarchy_backfill.py)
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
│   # NOTE: the operation catalog, product knowledge, and per-model
│   # capability matrix used to live here (admz/catalog, admz/knowledge,
│   # admz/capabilities). They were extracted to the standalone
│   # **axis-api-atlas** package (ADR-0029) and are now imported as
│   # `axis_api_atlas.{catalog,knowledge,capabilities}`. See the data-layout
│   # note below and docs/AXIS_API_ATLAS_MAINTENANCE.md.
│
├── firmware/              — Axis public FTP firmware fetcher + upgrade-path
│   ├── downloader.py      — fetch .bin from MPQT/PACS, cache locally
│   └── upgrade_path.py    — LTS milestone-aware cross-major upgrade path
│
├── executor/              — API call execution
│   ├── base.py            — BaseExecutor ABC
│   ├── models.py          — ExecutionRequest, StepResult
│   └── vapix.py           — VAPIX executor (legacy-cgi, json-rpc,
│                             config-rest, soap — 4 generations;
│                             none/basic/bearer/digest auth)
│
├── plans/                 — multi-step plan engine
│   ├── models.py          — ExecutionPlan, PlanStep, FailurePolicy
│   └── engine.py          — validation, execution, parallelism, rollback collection
│
├── snapshot/              — config snapshot/restore/drift/schedule
│   ├── models.py          — DeviceSnapshot, DriftReport, FacetResult
│   ├── engine.py          — orchestrates reads via catalog, normalizes
│   ├── git_repo.py        — thin git wrapper
│   ├── restore.py         — git YAML → execution plan
│   ├── drift.py           — live vs git comparison
│   ├── drift_alerts.py    — drift alert tracking/dedup
│   ├── maintenance.py     — snapshot-repo GC / maintenance
│   ├── scheduler.py       — recurring jobs (job_type registry — ADR-0026)
│   └── facets/            — pluggable per-facet adapters
│       ├── base.py        — FacetAdapter ABC + SimpleParamFacet
│       ├── image.py, network.py, time_config.py, stream_profiles.py
│       ├── users.py, events.py
│
├── fleet/                 — fleet-wide background services
│   └── health.py          — background health monitor (get_fleet_health)
│
├── chatbot/               — Gemini web chatbot (ADR-0024/0025)
│   ├── client.py          — manual tool-calling loop over the MCP surface
│   ├── config.py          — model selection + API-key bootstrap
│   ├── mcp_bridge.py      — spawns `python -m admz mcp` as a stdio subprocess
│   ├── mcp_pool.py        — per-principal MCP subprocess pool
│   ├── system_prompt.py   — principal-aware system prompt
│   ├── events.py, sessions.py, usage.py — SSE events, conversation history
│   │                         (named conversations + LLM titles, ADR-0038),
│   │                         token accounting
│
├── survey/                — contributor "survey mode" (ADR-0030)
│   ├── collector.py, runner.py — read-only discovery → contribution bundle
│   ├── validate.py, secrets.py, redact.py — validation + secret-scan gate
│   ├── bundle.py, diff.py, github.py — bundle schema, diffing, fork-and-PR
│
├── mcp/                   — MCP server (the primary entry point)
│   ├── server.py          — 50 tools wiring everything together
│   ├── tools/             — extracted tool-schema modules (firmware, fleet,
│   │                         knowledge, provision, schedules)
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
    │   ├── chat.py        — chatbot SSE route + conversation history REST
    │   ├── survey.py      — survey-mode UI/config
    │   ├── api_keys.py    — API-key management
    │   └── web.py         — browser-facing HTML routes
    └── templates/         — Jinja templates for the UI
                            (includes confirm_form, confirm_settings,
                             fleet_settings, capture_form, …)
```

**Catalog data lives in a sibling package.** The operation catalog
(400+ YAML ops), product knowledge, and per-model capability matrix are
maintained in the standalone **axis-api-atlas** repository and imported as the
`axis_api_atlas` package (ADR-0029). Its on-disk data layout
(`data/vapix/{cgi,rest,ws}/…`, `data/knowledge/`, `data/capabilities/`,
`data/products/`) mirrors what used to live under a root `catalog/` tree.
Edit the catalog *there*, not in ADMZ — see
[AXIS_API_ATLAS_MAINTENANCE.md](AXIS_API_ATLAS_MAINTENANCE.md).

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
6. **MCP server**: routes through `operations.execute_gated_operation` —
   checks risk level, looks up operation, gets credentials from registry,
   calls `VapixExecutor.execute()` which builds the HTTP request, sends it
   (with the device's auth scheme — none/basic/bearer/digest), parses the
   response, returns `StepResult`
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
  picks up via the family namespace (`axis_api_atlas` data dirs
  `vapix/`, and future `acs/`, etc.).
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
| Operation catalog | YAML files in the axis-api-atlas package | `axis_api_atlas` CatalogLoader |
| Product knowledge hints | YAML files in the axis-api-atlas package | `axis_api_atlas` KnowledgeLoader |
| Per-model API capabilities | YAML files in the axis-api-atlas package | `axis_api_atlas` CapabilitiesLoader |
| Fleet settings (default password, confirm levels, MCP toggles) | SQLite | FleetSettings |
| In-flight plans | In-memory dict on PlanEngine (per process). For `url_*`-gated plans the full steps are also serialized into the confirm session so a different process can reconstruct and run them on approval. | PlanEngine + ConfirmStore |
| Capture sessions | SQLite | CaptureStore |
| Confirmation sessions (multi-level, password-protected; single-source for both single ops and plans, cross-process) | SQLite | ConfirmStore |
| Audit log (who did what, when — incl. confirm approvals) | SQLite | AuditLog |
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
