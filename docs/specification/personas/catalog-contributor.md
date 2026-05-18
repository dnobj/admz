# Persona: Catalog Contributor

## Profile

**Who:** An external developer extending ADMZ — adding a new VAPIX operation, a new API family (e.g. ACS, AOA), a new discovery protocol, a new snapshot facet, or a new registry backend. May be an Axis employee, a partner integrator, an open-source contributor, or an internal developer at a customer org.

**Technical level:** Python developer. Familiar with YAML, dataclasses, ABCs. Comfortable reading the codebase and adding tests. Has done at least one open-source contribution before.

**Scale:** One contributor working on one extension at a time. May submit a PR adding 10–80 catalog entries in a batch.

**Frequency of use:** Periodic. Comes back when a new firmware adds an API, when a customer asks for a new device family, when a new discovery protocol is worth supporting.

## Goals

- **Add a new operation by writing YAML only**, with no Python changes for ordinary cases.
- **Add a new API family** (e.g. a non-VAPIX vendor) by implementing `BaseExecutor` and dropping YAMLs under `catalog/<family>/`.
- **Add a new discovery protocol** by implementing `DiscoveryProtocolBase` and registering it in the orchestrator.
- **Add a new snapshot facet** for a device type with a configuration shape no existing facet covers — by implementing `FacetAdapter` and decorating with `@register_facet`.
- **Add a new registry backend** (e.g. a different cloud secrets manager) by subclassing `DeviceRegistry`.
- **Validate their work** against the existing test suite + new tests.
- **Understand the existing conventions** without reading every file in the codebase.

## Pains today (without good documentation)

- "I want to add 12 new lightcontrol operations — where do they go and what's the YAML format?"
- "I added a new discovery protocol but it doesn't appear in `discover_network_devices` output — why?"
- "My snapshot facet captures the data but restore doesn't apply it — what's wrong?"
- "The catalog has both `_cgi.yaml` and `_api.yaml` files — which is current?"
- "I can't tell which operations the executor's request templates actually support."

## Use cases (this persona drives the existence of these requirements docs)

- [Extensibility](../requirements/extensibility.md) — the four documented extension points.
- [Catalog](../requirements/catalog.md) — YAML format, conventions, schema.
- [Executor](../requirements/executor.md) — how the executor consumes a YAML operation.
- [Discovery](../requirements/discovery.md) — protocol contract, orchestrator wiring.
- [Snapshot and restore](../requirements/snapshot-restore.md) — FacetAdapter contract.

## What ADMZ owes this persona

- **A documented YAML schema** for catalog operations. (`schema/operation.schema.yaml` is referenced in `docs/VAPIX_CATALOG_DESIGN.md`; CI validates against it.)
- **A documented FacetAdapter contract.** Methods, registration, `applies_to` filtering, restore_order semantics.
- **A documented executor contract.** `family` property, `execute(operation, device, credentials, params) → StepResult`.
- **A documented backend contract.** Required methods on `DeviceRegistry`, what `add_device`/`update_device`/etc. should do.
- **A documented discovery contract.** `DiscoveryProtocolBase` lifecycle, `safe_discover()` wrapping, the shape of `DiscoveredDevice`.
- **A consistent operation-ID format** (`<cgi-or-rest-or-soap>:<action>`).
- **Index validation** in CI — adding an operation file that isn't referenced in any index file is flagged.
- **Tests they can run locally** before submitting.
- **Naming conventions** documented for catalog directories, operation files, parameter groups, knowledge files.

## What ADMZ does *not* owe this persona

- **Hot reloading.** Catalog changes are picked up at process restart, not at runtime.
- **A registry of "approved" external authors.** Contributions go through PR review like any other change.
- **Backwards compatibility for unstable interfaces.** WIP modules (`capabilities/`, the confirm flow) may change shape.

## Conventions this persona must respect

- **Operation IDs** use `:` separator (`param.cgi:update`, `cert:listCertificates`).
- **Catalog directory names** mirror the API path (`mqtt-client.cgi/` for `/axis-cgi/mqtt/client.cgi`).
- **Risk levels** are one of `read-only`, `normal`, `service-affecting`, `dangerous` — no synonyms.
- **YAML key ordering**: `id`, `method`, `risk_level` near the top.
- **One operation per file.** Files stay under ~80 lines.
- **Tags belong only in `index/by-task.yaml`** — not in operation files.
- **Request templates** use `{name}` and `{name:type}` placeholders; the executor handles type coercion.
- **`requires:` fields** declare any device-side preconditions (auth level, firmware version, properties).
- **`rollback:` is mandatory** for any non-read-only operation, even if it's `strategy: none`.
- **Inverted indices** are updated when an operation is added or its risk changes.
- **Tests** live in `tests/` with a corresponding `test_*.py` file.

## Anti-personas

- Not the end-user operator — though their contributions enable end-user workflows.
- Not the LLM agent — though their contributions are consumed by the LLM agent.
- Not a security officer — though they must respect security conventions (no MCP tools that return credentials, etc.).
