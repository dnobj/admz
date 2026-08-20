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

### FR-KNW-009 — ADMZ keeps a local record of each device's API capabilities ✅
`device_capabilities(device_id, probe_key, supported, firmware, source, reason, fail_streak,
observed_at, expires_at)`, keyed `(device_id, probe_key)`, in the same SQLite file as every other
per-device store and on the #428 cascade list. `probe_key` is derived from the operation a facet
reads — the catalog `api_id` for that operation's API, else the API name — so facets declare
nothing and operations whose API carries no `api_id` are learnable. A row is **stale** when its
firmware differs from the device's current firmware or it has expired; a firmware upgrade therefore
invalidates every row with no code. Rows are forgotten on a hardware rebind (ADR-0036). See
[ADR-0063](../decisions/0063-capability-knowledge-is-local-first.md).

### FR-KNW-010 — The drift audit consults the local record before probing, and learns from the outcome ✅
Applied **in the engine only** — `get_facets_for_device` remains the static adapter index its nine
other callers need. A facet's extra read is skipped iff a non-stale row says `supported = 0`;
anything else probes. Every outcome is recorded, classified with the **same-cycle readability
control** (the shared `param.cgi` dump succeeded ⇒ the device is readable now): 2xx → `present`;
404/405/501/400/410 or JSON-RPC error → `absent` (7-day TTL); 401/403/5xx/parse/transport/timeout
**on a readable device** → `absent_unconfirmed` (24h·2^(streak−1), capped 7d); device unreadable →
no row. `absent` rows expiring IS the cadence: an API enabled later (an ACAP install) is noticed
within a week by the audit that already runs. An explicit operator snapshot may pass `force_probe`
to ignore absent rows.

### FR-KNW-011 — The atlas advises; it never suppresses a probe 📋
Atlas negatives are demonstrably partial — legacy-only snapshots lack every DCA-only api id, the
latest-snapshot tie-break prefers partial captures, and ADMZ passes the wrong firmware key (ADR-0063
records the evidence). A wrong skip costs a facet its drift coverage silently and permanently; an
unnecessary probe costs one request. So the atlas resolver answers **after** the local row (in
`check_api_support`), with the device's firmware passed correctly and the match labelled `exact` or
`none` — never the latest-snapshot fallback — and it is never consulted for selection.

### FR-KNW-012 — Surveying is for everyone; contributing is exclusive ✅
The full enumeration — `apidiscovery.cgi:getApiList` **through the executor**, so it reaches a
`limited_api` device — runs for every install: after credentials resolve on add, on firmware change,
on a 30-day cadence (a fleet setting), and on demand (REST + MCP). It writes **positives only**
(getApiList is legacy-only); a positive clears an `absent` row. Pushing a bundle to the atlas
requires `survey.contributor`, including the "Run now" path. ADR-0030 is amended accordingly.

### FR-KNW-013 — Firmware change is an event ✅
At the health sweep's existing delta and at the engine's own fact refresh (which lifts
`root.Properties.Firmware.Version` from the raw param dump before the volatile filter drops it):
`device.firmware_changed` when the prior value was non-empty and differs — audit row, enqueue a
capability survey — and `device.firmware_observed` on first sight. Answers #123's open question:
the attestation home is the local table.

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
