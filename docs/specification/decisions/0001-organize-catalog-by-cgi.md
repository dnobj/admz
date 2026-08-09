# ADR-0001: Organize the operation catalog by CGI endpoint

**Status:** Accepted, in production since v2.0.0.
**Date:** Original design 2026-02; recorded as ADR 2026-05-18.

## Context

Axis devices expose hundreds of VAPIX operations across multiple
generations (legacy CGI, JSON-RPC, config-REST, SOAP). Each operation
needs a catalog entry the LLM can consume + the executor can replay.
The directory hierarchy under `catalog/vapix/` had to make some
organizational call: by category ("Image", "Network", "Security"), by
risk level, by frequency of use, or by something else.

## Decision

Organize by **CGI / service endpoint**, not by category. The filesystem
mirrors the actual API surface:

```
catalog/vapix/
  cgi/                  — legacy CGI + JSON-RPC under /axis-cgi/
    param.cgi/
    factorydefault.cgi/
    pwdgrp.cgi/
    ...
  rest/                 — config-rest under /config/rest/
    cert/
    ssh/
    firewall/
    ...
  ws/                   — SOAP services at /vapix/services
    certificates/
    door-control-service/
    action-service/
    ...
```

No "categories" subdirectory, no "by-feature" layout. Every VAPIX
operation hits exactly one endpoint; that endpoint becomes the path.

Semantic routing — "which operations help with feature X?" — is the
concern of the **index files** (ADR-0019), not the directory layout.

## Consequences

**Positive:**
- No judgment calls about where a thing belongs. "Set HTTPS cert" lives
  with cert operations; no debate about whether it's "security" or
  "network."
- The catalog tree directly mirrors Axis's published API surface,
  making it cheap to verify completeness against
  developer.axis.com/vapix/.
- Multiple risk levels, feature tags, and discovery dimensions can
  all coexist in the index layer without forcing the directory to
  pick one.

**Negative:**
- Browsing the tree to find "stream profile operations" requires
  knowing the CGI is `streamprofile.cgi`. The index files
  (`by-task.yaml`, `by-risk.yaml`) bridge this, but they have to be
  maintained. _(The catalog left this repo in `712a8b3` / PR #37, "consume
  axis-api-atlas as the catalog source of truth". It now lives in
  `axis-api-atlas` as `src/axis_api_atlas/data/vapix/index/`. The links here
  pointed at the deleted in-repo copy and had been dangling since.)_
- Some operations on the same conceptual feature live across multiple
  CGIs (e.g. "stream config" touches both `streamprofile.cgi` and
  `param.cgi:root.StreamProfile`). The index layer is what
  collapses those.

## References

- [VAPIX catalog design doc](../../VAPIX_CATALOG_DESIGN.md) §1 "Organize by CGI, not by category"
- ADR-0002 (one file per operation), ADR-0003 (YAML not code), ADR-0019 (indices)
- Requirements: [catalog](../requirements/catalog.md)
