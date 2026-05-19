# ADR-0003: Catalog is YAML, not generated code

**Status:** Accepted, in production.
**Date:** Original design 2026-02; recorded as ADR 2026-05-18.

## Context

The operation catalog describes hundreds of VAPIX operations. We
considered generating Python code (`@dataclass` per operation, typed
methods) versus authoring YAML files that the runtime interprets.

## Decision

Author **YAML**. The catalog is data, not code. The Python side has a
fixed schema (`admz/catalog/models.py`); operations are instances of
that schema, parsed at runtime.

## Consequences

**Positive:**
- Adding an operation is a YAML-only change — no Python, no compile,
  no version bump to the package, no migration. External contributors
  can submit catalog PRs without touching the codebase.
- The schema lives in one place (`models.py`); a malformed YAML fails
  at load with a clean error, not at runtime with a `KeyError` ten
  layers deep.
- The catalog is shippable as a separate git repo — operators can
  pull catalog updates without re-deploying ADMZ itself (planned
  future direction).
- LLMs can read the YAML directly to generate new operations from
  Axis's published docs.

**Negative:**
- No compile-time type checking on YAML content. CI validates against
  `schema/operation.schema.yaml` to compensate.
- Slightly slower startup (catalog parsing) vs. import-time data
  structures. Negligible at the catalog sizes we operate at; cached
  anyway.
- Refactoring across many operations is search-and-replace rather
  than a Python-level rename. Acceptable tradeoff for the contributor
  ergonomics.

**Alternatives considered:**
- **Generated Python (dataclasses).** Rejected: cuts out external
  contributors, forces a release cycle for every catalog change.
- **Database-backed catalog.** Rejected: adds a deployment dependency,
  loses the "diff in git" experience for catalog reviews.

## References

- [VAPIX catalog design doc](../../VAPIX_CATALOG_DESIGN.md)
- ADR-0001, ADR-0002
- Requirements: [catalog](../requirements/catalog.md)
