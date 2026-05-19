# ADR-0004: Tags live only in index files, never in operation files

**Status:** Accepted, in production.
**Date:** Original design 2026-02; recorded as ADR 2026-05-18.

## Context

Operations have two distinct kinds of metadata:

1. **API facts** — endpoint, method, request shape, response shape,
   risk classification. These describe the API; they don't change
   unless Axis changes the API.
2. **Discovery metadata** — what user intents this operation serves,
   what taxonomies it belongs to, whether it's "common" or "obscure."
   These are about how operators *find* operations, not about the
   operations themselves.

We could put both in the operation files. We chose not to.

## Decision

**Operation YAML files contain only API facts.** Tags, task slugs,
feature labels, and any other discovery metadata live exclusively in
the **index files** under `catalog/vapix/index/`:

- `by-task.yaml` — task slug → list of operation file paths
- `by-risk.yaml` — risk level → list of operation file paths
- (future: `by-feature.yaml`, `by-device-type.yaml`, etc.)

Operations are referenced by file path. Multiple index entries can
point at the same operation; an operation file has no idea what tags
reference it.

## Consequences

**Positive:**
- **Clean change boundary.** Updating an operation's YAML (because
  Axis added a parameter) doesn't require thinking about tags. Adding
  a new tag (because operators want a "vacation mode" task slug)
  doesn't require touching operation files.
- **Multiple tag dimensions** can coexist without forcing a
  hierarchy. An operation can appear in `by-task`, `by-risk`,
  `by-feature`, and a future `by-device-type` simultaneously.
- **Index curation is human work.** Tags are about how humans find
  operations; humans curate them. Auto-generated tags drift from
  human intent.
- **CI can validate.** Every file path in every index must exist;
  every operation should (ideally) appear in at least one index.
  Both checks are cheap.

**Negative:**
- The index is a second set of files to maintain. Adding a new
  operation means writing its YAML AND deciding which index entries
  it belongs to.
- Renaming a CGI breaks every index entry referencing it. (Not common;
  CI catches it.)

## References

- [VAPIX catalog design doc](../../VAPIX_CATALOG_DESIGN.md) §3-4
- ADR-0019 — inverted index file structure
- Requirements: [catalog](../requirements/catalog.md)
