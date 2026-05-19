# Requirements: extensibility

The four documented pluggable extension points and the contract each
one expects from contributors. Most "new device family" / "new
integration" work happens via one of these — no core code changes.

## The four extension points

ADMZ has four explicit places where you can add functionality without
touching the engine:

1. **Catalog operations** — YAML files; data, not code (ADR-0003).
2. **API families (executors)** — implement `BaseExecutor`, register
   in `executors` dict.
3. **Discovery protocols** — implement `DiscoveryProtocolBase`,
   register in `DiscoveryOrchestrator`.
4. **Registry backends** — subclass `DeviceRegistry`, wire into the
   factory.
5. **Snapshot facets** — implement `FacetAdapter`, decorate with
   `@register_facet`.

Each is a contract; this doc records what the contract is.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-EXT-001 — Catalog operations are YAML-only ✅
Adding a new VAPIX operation requires:
1. A YAML file under `catalog/vapix/{cgi,rest,ws}/<api>/<version>/<action>.yaml`
2. At least one entry in `catalog/vapix/index/by-task.yaml` (so the
   operation is discoverable via intent search)
3. An entry in `catalog/vapix/index/by-risk.yaml`

No Python changes. CI validates against `schema/operation.schema.yaml`
(the schema lives in the catalog itself). See
[ADR-0001](../decisions/0001-organize-catalog-by-cgi.md),
[ADR-0002](../decisions/0002-one-yaml-per-operation.md),
[ADR-0003](../decisions/0003-yaml-not-generated-code.md),
[ADR-0019](../decisions/0019-inverted-index-files.md).

### FR-EXT-002 — New API families via BaseExecutor ✅
`admz/executor/base.py::BaseExecutor` declares:

```python
class BaseExecutor(ABC):
    @property
    @abstractmethod
    def family(self) -> str: ...
    @abstractmethod
    async def execute(self, operation, device, credentials, params) -> StepResult: ...
```

Concrete implementations live in `admz/executor/`. `VapixExecutor` is
the only family today; adding (e.g.) `AcsExecutor` for AXIS Camera
Station is a new file + dictionary entry in MCP server / AppContext
construction. Catalog files under `catalog/<family>/` are picked up
automatically by `CatalogLoader`.

### FR-EXT-003 — New discovery protocols via DiscoveryProtocolBase ✅
Subclass `DiscoveryProtocolBase`, implement `discover(timeout)`,
register in `DiscoveryOrchestrator.__init__`. The
`safe_discover()` wrapper handles timeouts and exceptions so per-
protocol bugs don't crash the orchestrator.

Currently 7 protocols (mDNS, SSDP, ONVIF, ARP, ping, HTTP probe,
SNMP).

### FR-EXT-004 — New registry backends via DeviceRegistry ABC ✅
Subclass `admz/device_registry.py::DeviceRegistry`. Implement the
required abstract methods (~10 of them — read/write across devices
and accounts) plus optionally the write methods (`add_device`,
`update_device`, etc. raise `NotImplementedError` in the ABC by
default).

Register the new backend in `admz/factory.py::create_device_registry`
with a lazy import (so installing without that backend's library —
e.g. `hvac` for Vault — doesn't break unrelated installs).

See [ADR-0011](../decisions/0011-pluggable-backends.md).

### FR-EXT-005 — New snapshot facets via FacetAdapter ✅
Subclass `admz/snapshot/facets/base.py::FacetAdapter` (or
`SimpleParamFacet` for prefix-based param facets), decorate with
`@register_facet`. The facet declares:
- `name` — short identifier
- `applies_to: list[DeviceCriteria]` — model/device_type/firmware filters
- `read_ops: list[str]` — catalog operations that populate this facet
- `restore_order: int` — order in restore plans (smaller = applied earlier)
- `serialize(raw_responses) -> dict` — raw → normalized YAML
- `deserialize(yaml_doc) -> list[dict]` — normalized → write params

See [ADR-0015](../decisions/0015-pluggable-facets.md).

## Non-functional requirements

### NFR-EXT-001 — Contracts are documented in the ABC ✅
Each ABC has a module-level docstring + per-method docstrings
explaining the contract. New contributors don't need a separate
"how to extend" guide — they read the ABC.

### NFR-EXT-002 — Extension points share architectural shape ✅
All five (catalog, executor, discovery, registry, facets) use the
same pattern: ABC + concrete subclass + lazy registration. Knowing
one is most of knowing the others.

### NFR-EXT-003 — Catalog changes ship without ADMZ releases ✅
The catalog is loaded from disk at process startup. Adding YAML
files and restarting picks them up. No package version bump, no
release cycle.

## Conventions for contributors

- **Operation IDs** use `<cgi-or-rest-or-soap>:<action>` format
  (e.g. `param.cgi:update`, `cert:listCertificates`,
  `door-control-service:LockDoor`).
- **Catalog directories** mirror the API path (`mqtt-client.cgi/` for
  `/axis-cgi/mqtt/client.cgi`).
- **Risk levels** are exactly: `read-only`, `normal`,
  `service-affecting`, `dangerous`. No synonyms.
- **YAML key ordering**: `id`, `cgi`, `method`, `risk_level` near the
  top.
- **`rollback:` is mandatory** for any non-read-only operation, even
  if `strategy: none`.
- **Inverted indices are updated** when an operation is added or its
  risk level changes.
- **Tests** live in `tests/` with one `test_*.py` per module.

## Known gaps

### KL-EXT-001 — JSON-RPC-over-WebSocket isn't a recognized generation ⚠️
The intercom service uses JSON-RPC over a WebSocket endpoint
(`/vapix/intercomws`). The current `VapixExecutor` only handles
`legacy-cgi` / `json-rpc` (HTTP) / `config-rest` / `soap`. Adding
intercom support means either a new executor family or extending
`VapixExecutor` with a fifth generation.

### KL-EXT-002 — No `extra.yaml` pass-through for snapshot facets ⚠️
A facet that doesn't know how to handle a new firmware-introduced
field today just drops it. The ADR-0015 design calls for raw
pass-through into a generic `extra.yaml` — not yet implemented.

### KL-EXT-003 — No public CLI for catalog validation ⚠️
Operators writing catalog YAMLs locally have to run pytest to
validate. A `python -m admz catalog validate <path>` would be more
ergonomic. Small follow-up.

## References

- ADRs: [0001](../decisions/0001-organize-catalog-by-cgi.md), [0002](../decisions/0002-one-yaml-per-operation.md), [0003](../decisions/0003-yaml-not-generated-code.md), [0011](../decisions/0011-pluggable-backends.md), [0015](../decisions/0015-pluggable-facets.md), [0019](../decisions/0019-inverted-index-files.md)
- Persona: [catalog-contributor](../personas/catalog-contributor.md)
- Code: `admz/executor/base.py`, `admz/discovery/base.py`, `admz/device_registry.py`, `admz/snapshot/facets/base.py`, `admz/catalog/loader.py`
