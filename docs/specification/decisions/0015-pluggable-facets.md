# ADR-0015: Pluggable snapshot facets

**Status:** Accepted, in production.
**Date:** Original design 2026-04 (`EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md`).

## Context

A snapshot of a camera looks different from a snapshot of an access
controller, an intercom, a network speaker, or AXIS Camera Station.
Each device family has its own shape of configuration:

- Cameras: image, network, time, stream profiles, users, events,
  view areas, privacy masks, AOA scenarios, ACAP apps.
- Access controllers: doors, schedules, cardholder schema, access
  rules, door hardware configuration.
- Intercoms: SIP config, audio profiles, scheduled playback.
- AXIS Camera Station: recording schedules, camera roster, storage
  allocation, smart-search configs.

Hard-coding all of these into the snapshot engine would make it
camera-shaped forever; adding a new device family would mean editing
core code.

## Decision

A **`FacetAdapter` ABC** with a registry pattern. Each facet is a
class that declares:

- **What it applies to** — `applies_to: list[DeviceCriteria]`
  (device_types, model_patterns, families, min_firmware ranges)
- **What it reads** — `read_ops: list[str]` of catalog operation IDs
- **What it writes** — `write_ops: list[str]` for restore
- **Restore ordering** — `restore_order: int` (smaller = applied earlier)
- **Serialize** — raw API response → normalized YAML dict
- **Deserialize** — normalized YAML dict → list of write-operation
  params

Registration is decorator-based:

```python
@register_facet
class ImageFacet(SimpleParamFacet):
    name = "image"
    applies_to = [DeviceCriteria(device_types=["camera"])]
    param_prefixes = ["root.Image."]
```

At snapshot time:
1. `get_facets_for_device(device_info)` filters the registry by
   `applies_to`, sorting by `restore_order`.
2. The engine runs each adapter's read operations, calls
   `serialize()`, writes both forms to git.

At restore time:
1. Read facet YAMLs from git.
2. Sort by `restore_order` (smallest first — network last, firmware
   first, users carefully).
3. Each facet's `deserialize()` produces a list of write operations.
4. Build a plan, hand to the plan engine.

`SimpleParamFacet` handles the common case (a facet that's just a
prefix of `param.cgi` keys) so most camera facets are ~10 lines.

## Consequences

**Positive:**
- **New device family = new facets, no core changes.** Adding intercom
  support is a SIPFacet + AudioFacet + CallScheduleFacet — drop the
  files, register them, done.
- **New firmware version adds parameters?** Either the existing
  prefix-based facet picks them up automatically (good), or a new
  facet covers them (also fine, no core change).
- **Unknown fields don't get lost** — facets that don't claim a
  param prefix leave it in the raw dump and an "extra.yaml" pass-
  through (planned).
- The pattern matches the executor families abstraction (ADR-0011 +
  the BaseExecutor + family registry) and the discovery protocol
  abstraction (ADR-0017) — same "pluggable point" shape everywhere
  for consistency.

**Negative:**
- The facet registry is global module-level state populated at import
  time. Tests have to handle that — re-registering on every test
  would be wrong, so tests use the production registry.
- A facet that misclaims `applies_to` (matches devices it shouldn't)
  produces wrong snapshots. Reviewable in PRs but the only enforcement
  is the test suite.
- Six camera facets ship today (image, network, time_config,
  stream_profiles, users, events). Other device families have **no
  facets yet** — they snapshot to an empty config/ directory. This
  is the access-control-catalog gap also called out in
  `personas/experience-center-operator.md`'s known limitations.

## References

- [EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md](../../EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md) §6 "Facets are pluggable"
- ADR-0012, ADR-0013 — sibling snapshot-architecture ADRs
- Requirements: [snapshot-restore.md](../requirements/snapshot-restore.md), [extensibility.md](../requirements/extensibility.md)
- Code: `admz/snapshot/facets/base.py` (ABC + register_facet decorator)
- Persona: [catalog-contributor](../personas/catalog-contributor.md)
