# ADR-0029: The Axis API Atlas as a maintained, reusable asset (DCA-refreshed capability matrix + standalone extraction)

**Status:** ✅ Implemented. The extraction is done: `axis-api-atlas` is a
standalone repo/package, and ADMZ consumes it as a dependency (imports
`axis_api_atlas.{catalog,knowledge,capabilities}`; see `admz/components.py`
and `requirements.txt`). The DCA-refresh tooling lives in the atlas repo.
**Date:** 2026-06-05. **Updated:** 2026-06-10.
**Relates to:** ADR-0027 (control families / ConfigCollector), ADR-0001 (organize catalog by CGI), ADR-0003 (YAML not generated code), ADR-0015 (pluggable facets), [requirements/knowledge-and-capabilities.md](../requirements/knowledge-and-capabilities.md), [AXIS_API_ATLAS_MAINTENANCE.md](../../AXIS_API_ATLAS_MAINTENANCE.md)

---

## Context

ADMZ's VAPIX catalog has grown into something more broadly valuable than an
internal implementation detail. It is, in effect, an **Axis API Atlas** with three
layers:

1. **Executable catalog** — `catalog/<family>/{cgi,rest,ws}/…`: per-operation
   specs (path, method, request-body template with typed params, response shape,
   risk level) that are *machine-actionable*, not prose.
2. **Semantic layer** — resolver synonyms, `by-task` / `by-risk` indexes, and the
   `knowledge/**` product/series/product-line hints that map natural-language
   intent to operations.
3. **Capability matrix** — `catalog/capabilities/models/<model>.yaml`: a
   `(model, firmware) → {api_id: version}` index, plus `_api_id_map.yaml`
   reconciling catalog names with device-reported names.

This is arguably **more useful than Axis's own published VAPIX documentation** for
agent/automation use: it's indexed, semantically searchable, and ready to execute.
It is also valuable **outside ADMZ** — other projects could consume the same Atlas.

Two gaps motivated this ADR:

- **The capability matrix was captured once, via the *legacy* `apidiscovery.cgi`.**
  It therefore under-represented reality: it listed `siren-and-light` only as the
  CGI `1.0` and entirely missed the device's RESTful **`v2beta`** API
  (`2.0.0-beta.15`), which is only visible through the newer **Device Config API
  (DCA)** discovery at `/config/discover` (AXIS OS ≥ 12.3). There was no committed,
  repeatable refresh tool — the data existed; the generator did not.
- **The Atlas's value depends on coverage** (models × firmwares × APIs), which no
  single person can produce. It needs an **ongoing, multi-contributor** maintenance
  process driven by whoever has access to which Axis models.

---

## Decision

### 1. Treat the capability matrix as a first-class, refreshable asset

A committed, read-only tool, `tools/refresh_capabilities.py`, discovers a live
device's APIs via **both** mechanisms and writes a firmware-stamped snapshot:

- Legacy `apidiscovery.cgi:getApiList` (CGI/JSON-RPC APIs), and
- DCA `GET /config/discover/apis` (RESTful APIs incl. beta).

The snapshot schema is **extended additively**: the existing
`apis: {id: version}` flat map is preserved (the capability loader reads it and
ignores unknown keys), and a new **`apis_detail`** map records, per API, what each
source reported — version, `state` (released/beta/alpha), `rest_api` path, and the
**OpenAPI spec link** for DCA APIs. Snapshots are keyed by `(model, firmware)` and
are idempotent and additive, so the matrix accumulates coverage across firmwares
and contributors.

### 2. Ingestion is deterministic for the executable layer, reasoning for the rest

- **Deterministic (no LLM):** OpenAPI specs (DCA `/config/discover/apis/<id>/v<n>/openapi.json`)
  → draft executable catalog operations (path, method, typed params, request/response
  schema) + a **safe-default risk** from HTTP method/path keywords.
- **Reasoning (LLM-assisted, human-reviewed):** intent synonyms / `by-task` mapping,
  confirmed risk classification, `params_doc`/`notes`, and knowledge hints. These are
  the discoverability + safety layers an OpenAPI spec does not carry.

This preserves ADR-0003 (the catalog is *reviewed* YAML): the deterministic stage
produces drafts; enrichment is reviewed before commit.

### 3. Maintenance is an ongoing, multi-contributor process

[AXIS_API_ATLAS_MAINTENANCE.md](../../AXIS_API_ATLAS_MAINTENANCE.md) is the runbook
that directs an agent or human with device access through: refresh the matrix →
detect gaps → seed catalog ops (deterministic) → enrich (reasoning) → verify
(read-only) → commit. Each contributor covers the models they can reach;
contributions are additive and merge-friendly.

### 4. Extract the Atlas as a standalone, reusable package (planned)

The three layers + their loaders have **no dependency on the ADMZ web/MCP app** and
should be extractable into a standalone package/repo (proposed name
**`axis-api-atlas`**), which ADMZ then consumes as a dependency.

---

## Standalone extraction sketch

**Moves into `axis-api-atlas`:**
- Data: `catalog/` (operations, indexes), `catalog/capabilities/`, `catalog/knowledge/`.
- Libraries (pure, no FastAPI/MCP imports): `admz/catalog/{loader,resolver,models}`,
  `admz/knowledge/**`, `admz/capabilities/**`.
- Tooling: `tools/refresh_capabilities.py`, the runbook, and the deterministic
  OpenAPI→draft-operation generator (to be built).

**Stays in ADMZ:**
- The executor (`admz/executor/**`) — *actuation* is product-specific (auth,
  credentials, transport, the `ConfigCollector`/`Actuator` split of ADR-0027). The
  Atlas describes operations; ADMZ executes them. (An optional thin reference
  executor could ship with the Atlas for testing, but production execution stays in
  the consuming app.)
- All web/MCP/registry/snapshot code.

**Package boundary / API:** the Atlas exposes read-only lookups — "resolve intent →
candidate operations," "get operation spec by id," "does (model, firmware) support
api X / at what version + state," "list capability gaps." ADMZ depends on it via a
pinned version and supplies the execution + credentials.

**Consumption:** ADMZ replaces its in-tree `catalog/` + loaders with the package.
Versioned releases let ADMZ pin a known-good Atlas; the Atlas evolves on its own
cadence driven by the multi-contributor discovery effort.

---

## Consequences

**Positive:**
- The capability matrix reflects reality (DCA + beta + REST), refreshable in one
  read-only command per device; the C1110-E refresh already added a `12.9.57`
  snapshot capturing `siren-and-light` `v2beta` that the legacy data missed.
- The asset becomes reusable across projects, and its coverage compounds via
  distributed contribution.
- The deterministic/reasoning split lets the executable layer scale by codegen
  while keeping the safety-critical layers human-reviewed (ADR-0003 intact).

**Negative / trade-offs:**
- Extraction is real refactoring work (package boundary, dependency wiring, release
  process) and is deferred until the boundary is proven in-tree.
- `apis_detail` adds schema surface; consumers beyond the current loader must be
  taught to read it (the loader tolerates it today by ignoring unknown keys).
- Beta APIs recorded in the matrix can change upstream; the executable catalog
  should prefer documented/official APIs where both exist and treat beta as flagged.

---

## Alternatives considered

**Keep the matrix as a one-shot, legacy-only artifact.** Rejected: it silently
misrepresents devices (missed `v2beta`) and can't be maintained as firmware evolves.

**Fully LLM-driven catalog generation.** Rejected: the executable layer is
deterministically derivable from OpenAPI; using an LLM for it adds cost and
non-determinism. Reserve the LLM for the semantic/risk layers where judgment is real.

**Leave everything embedded in ADMZ forever.** Rejected as a *long-term* stance: the
Atlas is independently valuable and the layers are already dependency-clean; embedding
forfeits reuse. (Extraction is still deferred until justified.)

---

## References

- Runbook: [AXIS_API_ATLAS_MAINTENANCE.md](../../AXIS_API_ATLAS_MAINTENANCE.md)
- Tool: `tools/refresh_capabilities.py`
- Discovery mechanism: Axis Device Configuration API (DCA), `/config/discover` (AXIS OS ≥ 12.3)
- Related ADRs: [0027](0027-pluggable-control-families-and-config-collectors.md),
  [0001](0001-organize-catalog-by-cgi.md), [0003](0003-yaml-not-generated-code.md),
  [0015](0015-pluggable-facets.md)
- Capability layer: `admz/capabilities/**`, `catalog/capabilities/**`
