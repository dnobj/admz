# Requirements: catalog

The YAML-based operations catalog: per-API metadata, per-operation
specs, parameter groups, indices, risk classification, and the
loader + resolver that the executor and the LLM consume.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-CAT-001 — One YAML per operation ✅
Every operation is a standalone YAML file under
`catalog/<family>/<surface>/<api_name>/<version>/<action>.yaml`.
See [ADR-0002](../decisions/0002-one-yaml-per-operation.md).
File contents map to `admz/catalog/models.py::Operation` (id, cgi,
method, request, response, risk_level, rollback, requires,
service_impact, notes, param_rules).

### FR-CAT-002 — Per-API metadata in `_api.yaml` ✅
Each API directory has an `_api.yaml` (`CgiMetadata`) declaring
`endpoint`, `generation`, `auth`, `min_firmware`, `api_id`,
`description`. Operations inherit these and don't repeat them.

### FR-CAT-003 — Four API generations ✅
The `generation` field selects which executor handles the operation:

| Generation | Examples | Executor |
|---|---|---|
| `legacy-cgi` | param.cgi, jpg-image.cgi, pwdgrp.cgi | `LegacyCgiExecutor` |
| `json-rpc` | basicdeviceinfo.cgi, firmwaremanagement.cgi | `JsonRpcExecutor` |
| `config-rest` | `/config/rest/network/v1`, `/config/rest/time/v1` | `ConfigRestExecutor` |
| `soap` | cert.cgi (certificate management) | `SoapExecutor` |

### FR-CAT-004 — Four risk levels ✅
`risk_level` is required and one of:
- `read-only` — pure GET, no side effect
- `normal` — config write that's reversible
- `service-affecting` — restarts services, brief disruption
- `dangerous` — factory reset, firmware ops, deletes

Risk drives the mechanical gate (FR-PLN-005) and the per-risk
confirmation default (FR-CORE-004 fleet settings).

### FR-CAT-005 — Inverted indices for fast lookup ✅
`catalog/<family>/_index.yaml` and topic-specific
`_index_by_*.yaml` files map tags, intent keywords, and parameter
groups to operation IDs. See
[ADR-0019](../decisions/0019-inverted-index-files.md). The resolver
uses these to keep its result set small without scanning every
YAML.

### FR-CAT-006 — Tag taxonomy for discovery ✅
Each operation lists `tags:` in the index (not the operation YAML
itself — ADR-0004). Tags group operations by intent: `network`,
`firmware`, `users`, `ptz`, `audio`, `record`, `events`, `disks`,
`overlay`, `time`, `image`, `applications`, `access-control`.

### FR-CAT-007 — Parameter groups (param.cgi) ✅
`param.cgi` is special: it's not one operation per parameter, it's
one operation per *group* (root.Image, root.Network, root.Time...).
Each group file (`catalog/.../param.cgi/.../groups/<group>.yaml`)
declares the parameters, types, valid values, defaults, and
service impact. `ParameterGroup.channel_indexed` controls whether
`Iₙ.*` keying applies.

### FR-CAT-008 — Rollback specifications ✅
`rollback:` block per operation (or null if irreversible):
- `revert-params` — read current values before write, re-apply on
  rollback (only param.cgi today — see KL-CAT-001)
- `delete` — create-shaped ops; rollback deletes the created item
- `none` — explicitly irreversible (factory reset, firmware
  upgrade); plan engine treats these as `dangerous` regardless of
  declared `risk_level`

### FR-CAT-009 — Service-impact warnings ✅
`service_impact:` string captures what the operation disrupts
(e.g. "video stream restart on resolution change"). The resolver
surfaces this so the LLM and operator can decide whether to bundle
a precondition.

### FR-CAT-010 — Catalog loader with caching ✅
`admz/catalog/loader.py::CatalogLoader` reads YAML on demand,
caches by `(family, operation_id)`. Cache is per-process and
in-memory — no on-disk index. Suitable up to the current ~150
operations; see KL-CAT-002.

### FR-CAT-011 — Resolver builds LLM-sized result ✅
`admz/catalog/resolver.py::CatalogResolver.query_catalog(...)`
produces a `ResolverResult` containing only the operations
relevant to the LLM's query. Inputs:
- `intent` keyword (e.g. "set hostname")
- `device_info` (model, firmware) for compatibility filtering
- `tags` for narrowing
- `risk_max` to exclude operations above a chosen risk

Output is bounded — the resolver never dumps the whole catalog;
the indices and filters keep it to <10–20 operations typically.

### FR-CAT-012 — Hybrid YAML + raw HTTP ✅
Operations not yet catalogued are still callable via the raw
executor path. See [ADR-0013](../decisions/0013-hybrid-yaml-and-raw.md).
This keeps coverage incremental — operators don't have to wait for
catalog support to use a new VAPIX endpoint.

### FR-CAT-013 — Catalog organized by CGI ✅
Files live under `catalog/vapix/cgi/<api>/<version>/...` so a new
contributor can find "param.cgi update" in the obvious location.
See [ADR-0001](../decisions/0001-organize-catalog-by-cgi.md).

### FR-CAT-014 — Access-control device coverage ✅
`door-control-service` (door commands), `schedules` (recurring
access windows), and related access-control APIs are catalogued
under `catalog/vapix/cgi/` and `catalog/vapix/rest/`. Coverage
added to support Axis Experience Center demo scenarios.

## Non-functional requirements

### NFR-CAT-001 — YAML is the source of truth ✅
Catalog YAML is not generated from VAPIX docs (and vice versa) —
operators edit YAML directly. See
[ADR-0003](../decisions/0003-yaml-not-generated-code.md). The
upstream VAPIX docs in `docs/vapix-docs/` are reference material,
not a build input.

### NFR-CAT-002 — Catalog is read-only at runtime ✅
The loader never writes YAML. New operations land via PR; the
running server picks them up on next restart (or via re-init in
tests).

### NFR-CAT-003 — Catalog ships with the package ✅
The YAML tree is part of the `admz` Python package, not a
separate download. `setup.py` includes `catalog/` in
`package_data`.

## Known limitations

### KL-CAT-001 — Rollback only implemented for param.cgi ⚠️
The `revert-params` strategy works on param.cgi (read-then-update
round trip). Other generations declare `rollback: { strategy: ... }`
but the executor doesn't yet honor them — config-rest, JSON-RPC,
and SOAP rollbacks would each need their own implementation. The
plan engine treats unsupported-rollback operations as if `rollback:
none` were declared. See `admz/plans/engine.py`.

### KL-CAT-002 — In-memory cache only ⚠️
The loader builds its cache lazily as operations are requested.
First reference to an operation is a YAML read; subsequent
references are cache hits. No serialized index on disk. At ~150
operations this is fine; if the catalog grew 10x a build-time
index would matter.

### KL-CAT-003 — Indices are hand-maintained ⚠️
`_index*.yaml` files are committed alongside operations and have
to be updated by hand when new ops land. CI does not validate that
every operation YAML is referenced. Drift between index and YAMLs
is detectable only by tests that exercise the resolver.

### KL-CAT-004 — No firmware-version compatibility check at load ⚠️
`_api.yaml` carries `min_firmware`, but the loader/resolver doesn't
filter operations by firmware version unless the caller passes
`device_info` to the resolver. A query without device_info gets
everything.

## References

- ADRs: [0001](../decisions/0001-organize-catalog-by-cgi.md), [0002](../decisions/0002-one-yaml-per-operation.md), [0003](../decisions/0003-yaml-not-generated-code.md), [0004](../decisions/0004-tags-in-index.md), [0013](../decisions/0013-hybrid-yaml-and-raw.md), [0019](../decisions/0019-inverted-index-files.md)
- Cross-cutting: [extensibility.md](extensibility.md)
- Sibling: [executor.md](executor.md), [plans.md](plans.md)
- Code: `admz/catalog/`, `catalog/vapix/`
