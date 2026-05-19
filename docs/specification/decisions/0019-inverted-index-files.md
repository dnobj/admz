# ADR-0019: Inverted index files for catalog routing

**Status:** Accepted, in production.
**Date:** Original design 2026-02; recorded as ADR 2026-05-18.

## Context

ADR-0001 puts operations under `catalog/vapix/{cgi,rest,ws}/`. ADR-0004
puts tags only in index files. This ADR records the **format** of the
index files themselves.

## Decision

Index files live under `catalog/vapix/index/`. Each is a YAML
key-to-list mapping:

```yaml
# by-task.yaml — user intent → operations
change-resolution:
  - cgi/param.cgi/unversioned/groups/root.Image.yaml
  - cgi/param.cgi/unversioned/update.yaml
  - cgi/param.cgi/unversioned/list.yaml

grant-door-access:
  - ws/door-control-service/AccessDoor.yaml
  - ws/door-control-service/GetDoorState.yaml
```

```yaml
# by-risk.yaml — risk level → operations
dangerous:
  - cgi/factorydefault.cgi/unversioned/factory-reset.yaml
  - cgi/hardfactorydefault.cgi/unversioned/hard-factory-reset.yaml
  - cgi/firmwaremanagement.cgi/1.0/upgrade.yaml
  - ws/door-control-service/LockDownDoor.yaml
```

Properties:

- **Inverted.** Keys are categories; values are operation paths. Lookup
  cost is O(1) by key, O(N) over operations in the result.
- **Human-curated.** Index entries express *intent* ("operators
  searching for 'change resolution' should see these"). Auto-generation
  drifts from intent.
- **Path-based references.** Operations are pointed at by file path,
  not by ID. Cheap to grep, cheap to validate (path exists), works
  with `git mv`.
- **Multiple indices can coexist.** Currently `by-task` and `by-risk`;
  future `by-feature`, `by-device-type`, `by-firmware-minimum` slot
  in without changing the consumers.

CI validates:
- Every path in every index file exists on disk.
- (Optional, future) Every operation file appears in at least one
  index — orphans are flagged for human review.

## Consequences

**Positive:**
- The `CatalogResolver` does cheap key lookups when answering
  "operations relevant to intent X."
- Risk classification (Gate 2 of the two-gate model — ADR-0005) reads
  `by-risk.yaml` to know which ops require confirm tokens.
- Adding new lookup dimensions is just a new file — no schema change,
  no migration.

**Negative:**
- Two writes per new operation: the YAML itself + at least one index
  entry. Forgetting the index makes the operation unreachable via
  intent search.
- Renaming a file requires updating every index entry that pointed at
  it. `git mv` doesn't fix this automatically.

**Alternatives considered:**
- **Embed tags in operation files** (rejected: see ADR-0004).
- **Database-backed index** (rejected: see ADR-0003).
- **Auto-generated index from tagged operation files** (rejected:
  reintroduces ADR-0004's problem of mixing concerns).

## References

- [VAPIX catalog design doc](../../VAPIX_CATALOG_DESIGN.md) §5 "Index files are hand-curated"
- ADR-0001, ADR-0002, ADR-0004
- Requirements: [catalog](../requirements/catalog.md)
