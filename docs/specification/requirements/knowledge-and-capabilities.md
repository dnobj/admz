# Requirements: knowledge and capabilities

The product knowledge base — per-model, per-series, per-product-line
hints that augment the catalog with information VAPIX itself can't
tell us (positioning, lens caveats, "this model also needs X
before Y").

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-KNW-001 — Three-level knowledge hierarchy ✅
`admz/knowledge/models.py::ProductKnowledge.level`:
- `product` — for one specific model (e.g. `P3265-LV`)
- `series` — for a model series (e.g. `P32`)
- `product-line` — for a product line (e.g. `network-cameras`)

Hints inherit upward: a P3265-LV resolves product-level hints
first, then series, then product-line. More-specific overrides
less-specific.

### FR-KNW-002 — Hint structure ✅
`Hint`: `id`, `topic`, `summary`, `text`, `tags`,
`source_level`, `source_file`. A hint is a discrete chunk of
text the LLM can surface to an operator; `summary` is the
one-liner, `text` is the longer body.

### FR-KNW-003 — YAML-based knowledge files ✅
Knowledge files live in `knowledge/products/<model>.yaml`,
`knowledge/series/<series>.yaml`, `knowledge/product-lines/
<line>.yaml`. Format mirrors the catalog YAMLs — operators can
extend coverage by adding files, no code change.

### FR-KNW-004 — KnowledgeLoader caches per-file ✅
`admz/knowledge/loader.py::KnowledgeLoader` reads YAML on demand
and caches the parsed `ProductKnowledge` per file. Similar shape
to `CatalogLoader` (FR-CAT-010).

### FR-KNW-005 — KnowledgeResolver merges by device ✅
`admz/knowledge/resolver.py::KnowledgeResolver.query_knowledge(
device_id, topic=None, tags=None)` walks the device's model →
series → product-line chain, merges hints, returns a
`KnowledgeResult`. The resolver dedupes by `Hint.id` so the same
hint inherited at multiple levels appears once with the most
specific `source_level`.

### FR-KNW-006 — Topic and tag filtering ✅
Callers narrow the result by `topic` (exact match) and `tags`
(any-of). Returned hints carry `source_level` so the LLM can tell
whether a recommendation is product-specific or generic.

### FR-KNW-007 — Knowledge exposed via MCP 🚧
- MCP: `query_knowledge(device_id, topic?, tags?)` ✅
- REST: 📋 — `GET /api/v2/devices/{id}/knowledge` **never shipped**; `api/v2`
  has zero occurrences in `admz/`.

> **Corrected 2026-08-04 (#214).** Marked ✅ while claiming a REST endpoint that does not exist. A ✅ on an absent artifact is worse than a 📋 on a present one: it invites a reader to depend on something that was never built.

LLM agents typically call knowledge before planning a write — the
hints often warn about combinations the catalog risk-level alone
wouldn't flag (e.g. "this lens needs a re-focus after switching
capture mode").

### FR-KNW-008 — Independent of the catalog ✅
Knowledge and catalog are separate loaders. The catalog answers
"what can this API do?"; knowledge answers "what should an
operator know about this model?" The two are joined only at
query time by the LLM (or by the resolver caller).

## Non-functional requirements

### NFR-KNW-001 — Knowledge ships with the package ✅
The `knowledge/` tree is part of the `admz` distribution
(`package_data` in setup.py). No external fetch on first run.

### NFR-KNW-002 — Hints are human-curated, not generated ✅
Knowledge files are committed by humans who've worked with the
device. There's no auto-generation from product specs — that
would dilute the signal-to-noise that makes hints useful.

## Known limitations

### KL-KNW-001 — Coverage is sparse ⚠️
Most products have no knowledge file. The resolver gracefully
falls back to series and product-line; many product-line files
are also stubs. Operators see "no hints" for the majority of
queries. This is OK — knowledge is an enhancement, not a
hard requirement — but coverage growth is gated on human effort.

### KL-KNW-002 — No firmware-version segmentation ⚠️
Hints aren't firmware-version-aware. A hint that applies to
firmware 11.x and is wrong for 12.x has no clean way to express
that distinction. Workaround: encode in the hint text. Planned
field: `applies_to_firmware:`.

### KL-KNW-003 — No structured "if-then" reasoning ⚠️
Hints are free text. The LLM has to read and reason. There's no
machine-readable "if capture_mode = X then re-focus needed" rule
graph. The catalog's `requires` field is the closest structured
hint mechanism; knowledge is intentionally less structured.

### KL-KNW-004 — Indexing is by model only ⚠️
The resolver looks up hints by `device_info.model`. Devices in
the registry without a model field (e.g. provisioned before
basicdeviceinfo discovery) get only product-line hints. Discovery
populates `model` for all reachable devices.

## References

- ADRs: [0008](../decisions/0008-mcp-and-rest-surfaces.md)
- Cross-cutting: [extensibility.md](extensibility.md)
- Sibling: [catalog.md](catalog.md), [mcp-server.md](mcp-server.md)
- Code: `admz/knowledge/`, `knowledge/`
