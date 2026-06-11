# ADR-0032: Tags replace the device Group level (Org and Site stay)

**Status:** Accepted, in production (2026-06-11).
**Date:** 2026-06-11.
**Relates to:** ADR-0014 (config in git, creds in DB), ADR-0031
(Live/Observation/Baseline), ADR-0027/0028 (which referenced the old
Org → Site → Group wording; this ADR records the supersession — per project
convention those ADRs are not retro-edited).

## Context

The device hierarchy was designed as Org → Site → Group → Device. In
practice the three levels earned their keep very differently:

- **Org** has real meaning: *who owns the cameras*. It owns the git config
  repo (`repo_path`, optional `repo_remote_url`) and is the tenant/isolation
  boundary.
- **Site** has real meaning: *which site (usually a local network) the
  cameras are installed on*. It scopes the fleet view and the site switcher.
- **Group** was pure scaffolding. It had no REST CRUD, no MCP tools, no
  schedule scoping (schedules already use `tag_filter`; the planned
  `group_id` scope in FR-SCH-012 was never built), and the git layout that
  was supposed to embed the primary group (`{site}/{group}/{device}`) was
  never built either — the repo is flat `fleet/{device_id}/`. Every real
  device sat in the bootstrap "ungrouped" group, while **tags** did all the
  actual organizing: scheduling, drift/snapshot scoping, search, and the
  dev auto-approver all filter by tag. The UI showed a "Groups" sidebar
  with a single "Ungrouped" row — pure confusion.

Running two parallel membership systems (a rigid tree + free-form tags)
means every future feature must answer "group or tag?" forever.

## Decision

**Remove the Group level. Keep Org and Site. Tags are the one
device-grouping primitive.**

- The registry loses the 10 group methods (`add_device_group`,
  `add_device_to_group`, `set_device_primary_group`, …) and the two SQLite
  tables (`device_groups`, `device_group_memberships`). Opening a legacy DB
  drops them idempotently — they held only the bootstrap "ungrouped" row,
  so nothing operator-authored is lost. `org_id`/`site_id` columns and all
  Org/Site CRUD stay.
- The web sidebar lists **tags** (with per-site device counts, plus an
  "Untagged" pseudo-row only when untagged devices exist); `/devices?tag=`
  filters the fleet (the reserved value `untagged` selects tagless
  devices). Device pages show clickable tag chips where the Group label
  was. Tag matching is exact membership, case-sensitive — identical to
  `tag_filter` semantics in scheduling/drift/snapshot.
- The hierarchy backfill migration assigns org/site only.
- The precedent is Kubernetes labels / AWS resource groups: one labeling
  primitive, with "groups" as *views over it* — not a parallel tree.

**Future extension (deliberately not built now):** named saved
tag-selectors ("smart groups" — e.g. `lobby-cams = lab AND camera`) as
stored queries surfaced in the sidebar. The future config-**branch**
feature ("main + intentional overrides", EXPERIENCE_CENTER doc Phase 5)
will target a device or a *tag selection*, not a Group.

## Consequences

**Positive:**
- One mental model for "which devices": tags, everywhere — UI, schedules,
  drift, snapshot, chat. The "Ungrouped (7)" sidebar confusion is gone.
- ~700 lines of scaffolding (schema, registry methods, nav plumbing,
  migration step, tests) removed; no dual-membership question for future
  features.
- Org keeps its repo-ownership role unchanged, so per-Org repo isolation
  remains available when multi-tenancy actually arrives.

**Negative:**
- Tags are flat and untyped: no per-group metadata (`purpose`), no
  enforced single "primary" membership, no rename-in-one-place (renaming a
  tag means re-tagging devices). Saved selectors can restore most of this
  if needed.
- A device with many tags shows many chips where Group showed one label.

**Alternatives considered:**
- **Keep Group alongside tags.** Rejected: two parallel membership systems,
  one of them unused scaffolding, each future feature pays the "group or
  tag?" tax.
- **Tags-only including Org/Site.** Rejected: Org genuinely owns the config
  repo (tags can't express "exactly one repo per device"), and Site is the
  physical/network locality the operator thinks in.

## References

- Requirements: [hierarchy.md](../requirements/hierarchy.md) (rewritten),
  [scheduling.md](../requirements/scheduling.md) FR-SCH-012
- Code: `admz/backends/sqlite_backend.py` (`_DROPPED_TABLES`),
  `admz/api/templating.py::build_nav` (nav.tags),
  `admz/api/routes/web.py::devices_page` (`?tag=`),
  `admz/migrations/hierarchy_backfill.py`
- Tests: `tests/test_web_tags.py`, `tests/test_hierarchy_data_model.py`
