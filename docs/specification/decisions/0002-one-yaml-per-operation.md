# ADR-0002: One YAML file per operation

**Status:** Accepted, in production.
**Date:** Original design 2026-02; recorded as ADR 2026-05-18.

## Context

The catalog needs to scale to hundreds of operations across dozens of
CGIs, but each individual operation also needs to fit comfortably in
an LLM's context window. A 5,000-line `param.cgi.yaml` would be
useless to either humans reviewing it or models consuming it.

## Decision

Break operations down to the **smallest useful unit** — one operation
per file, ~20–80 lines each.

Specifically:

- **Per action** for CGIs with distinct verbs (list, update, add, remove).
- **Per parameter group** for `param.cgi`'s massive namespace
  (root.Image, root.Network, root.Time, root.PTZ, etc. — each its own
  file under `groups/`).
- **Per method** for JSON-RPC CGIs (getAllProperties, getServiceCapabilities, …).
- **Per version** when different versions have meaningfully different
  method sets (e.g. lightcontrol.cgi 1.0 vs 1.1).

Each file is self-contained — opening one tells you everything about
that operation without cross-referencing.

## Consequences

**Positive:**
- LLMs can consume a single operation in one shot without bringing
  irrelevant context.
- PR reviews are clean: changing `setStreamProfile` doesn't show diffs
  for `listStreamProfiles`.
- Bugs are contained: a malformed YAML breaks one operation, not the
  whole catalog.
- File system tools (grep, find, mv) work naturally.

**Negative:**
- Many files. Loading the full catalog means reading hundreds of small
  YAMLs. The `CatalogLoader` caches aggressively (`_cgi_cache`,
  `_operation_cache`, `_index_cache`) to amortize.
- A bulk change (e.g. adding a new field to every operation) touches
  every file. Tooling: `sed`/scripts, or accept the breadth.
- Schema drift is easier to introduce one file at a time. CI schema
  validation against `schema/operation.schema.yaml` catches this.

## References

- [VAPIX catalog design doc](../../VAPIX_CATALOG_DESIGN.md) §2 "One file per operation"
- ADR-0001, ADR-0003, ADR-0019
- Requirements: [catalog](../requirements/catalog.md)
