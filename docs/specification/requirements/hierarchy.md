# Requirements: organization hierarchy (Org → Site → Group)

> **STATUS: DRAFT SKELETON.** This is a seed scaffold for the
> Org → Site → Group → Device hierarchy. Every requirement below is
> 📋 *planned* and most need expansion. Flesh out, split, or
> renumber freely — the FR/NFR numbers are placeholders, not
> contracts. Open design questions are collected at the bottom;
> resolve them into ADRs as they settle.

ADMZ today is a single flat fleet — every device sits under one logical
"fleet" with `tags` as the only grouping primitive. This document
specifies an explicit organizational hierarchy that mirrors how Axis
customers actually organize physical reality:

```
Organization     (e.g. "Axis Communications")
  └── Site       (e.g. "AEC Experience Center Chicago")
        └── Group   (e.g. "lobby", "rooftop", "demo-wall")
              └── Device
```

- A **Site** belongs to exactly one **Organization**.
- A **Group** belongs to exactly one **Site**.
- A **Device** belongs to exactly one Org and one Site, and to
  **zero-or-more Groups** (N:N) — one of which is marked *primary*.
- A default Org, Site, and Group exist out of the box so zero-config
  installs keep working.

Related: device-side concerns are covered in
[core-platform.md](core-platform.md); the git layout interacts with
[snapshot-restore.md](snapshot-restore.md); scoped permissions are a
follow-up that will touch [authentication.md](authentication.md) and
[security.md](security.md).

## Status legend

✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Terminology guard

> **Naming hazard:** `Principal.groups` already exists and means *AD
> security groups* (populated by LDAP, consumed by
> `principal_can_reveal`). The hierarchy's "Group" is a **different
> concept** — a device-organization unit. To avoid collision, code
> uses `device_group` / `DeviceGroup` / `group_id`; user-facing UI
> may say "Group" because there's no ambiguity at that layer. Do not
> repurpose `Principal.groups`. (23 reveal-gate tests depend on its
> current meaning.)

## Functional requirements

### FR-HIER-001 — Organization entity 📋
An Organization is the top-level container. Fields: `org_id` (stable
identifier, validated per CR-5 `validate_identifier`), `name`
(human-readable), `created_at`, `metadata`. An Org contains many Sites.
<!-- TODO: define rename semantics, deletion rules (cascade vs refuse-if-nonempty) -->

### FR-HIER-002 — Site entity 📋
A Site belongs to exactly one Organization. Fields: `site_id`,
`org_id` (FK), `name`, `location` (free-text, e.g. "Chicago, IL"),
`created_at`, `metadata`. The AEC maps to a Site; Axis Communications
maps to the Org.
<!-- TODO: can a site move between orgs? default = no -->

> **Multi-ACS note:** A single Site may contain **multiple Axis Camera Station
> Pro servers** (e.g. a large facility with separate ACS instances per building
> wing). ACS server records are site-scoped targets — `site_id` is a required
> field on every ACS record. The data model must support N ACS servers per Site
> from the start; a 1:1 assumption would require a breaking migration later.
> See [multi-target-support.md](multi-target-support.md) FR-MT-009.

### FR-HIER-003 — Group entity 📋
A Group belongs to exactly one Site. Fields: `group_id`, `site_id`
(FK), `name`, `purpose` (short description, e.g. "vendor demo"),
`created_at`, `metadata`. Groups organize devices by goal and/or
locality.
<!-- TODO: nested groups? default = flat (no group-within-group) for v1 -->

### FR-HIER-004 — Device ↔ Group membership is N:N 📋
A device may belong to multiple Groups (e.g. `lobby` for locality +
`vendor:Acme` for goal). Membership lives in a junction table
`device_group_memberships(device_id, group_id, is_primary, added_at)`.
<!-- TODO: confirm N:N is final (user leaning yes); cap on # of groups per device? -->

### FR-HIER-005 — Exactly one primary Group per device 📋
Of a device's Group memberships, exactly one carries `is_primary=1`.
The primary Group determines the device's git path
(see FR-HIER-010). Enforced by a partial unique index.
<!-- TODO: what happens when the primary group is deleted? auto-reassign to default? -->

### FR-HIER-006 — Default Org / Site / Group bootstrap 📋
On first run, ADMZ ensures a default `org=default`, `site=default`,
`group=ungrouped` exist (idempotent). New installs and existing
devices need no manual hierarchy setup to function.
<!-- TODO: exact default names/ids; whether operators can rename vs delete defaults -->

### FR-HIER-007 — Existing devices migrate into defaults 📋
A migration backfills every existing device to
`org=default, site=default, primary_group=ungrouped`. No device is
left without a home. Operators reorganize afterward.

### FR-HIER-008 — CRUD for Org / Site / Group 📋
Create, read, update (rename/re-describe), delete for all three
entities. Delete semantics TBD (refuse-if-nonempty vs cascade —
see open questions). Surfaced via REST and MCP.
<!-- TODO: which deletes cascade; reassign-on-delete vs block -->

### FR-HIER-009 — Move a device between Sites / Groups 📋
An operator can reassign a device to a different Site, and
add/remove/re-prime its Group memberships. Moving Site implies the
git path changes (see FR-HIER-010).
<!-- TODO: does moving site move git history or start fresh at the new path? -->

### FR-HIER-010 — Git config-repo follows the hierarchy 📋
Snapshot layout becomes
`{repo}/{org_id}/{site_id}/{primary_group_id}/{device_id}/`
(was `{repo}/fleet/{device_id}/`). One unified repo; `git log` /
`git diff` scope naturally by any subtree (org, site, group, device).
Additional (non-primary) group memberships are recorded as metadata
in `device.yaml`, not as extra directories.
See [snapshot-restore.md](snapshot-restore.md), ADR-00XX (to be written).

### FR-HIER-011 — Hierarchy-scoped filtering 📋
List/search surfaces (web device list, `search_devices`,
`snapshot_fleet`, scheduler) accept `org_id` / `site_id` / `group_id`
filters alongside the existing `tag_filter`.

### FR-HIER-012 — Web UI navigation by hierarchy 📋
The web UI lets operators browse Org → Site → Group → Device with
breadcrumb navigation and filter the device list by hierarchy level.
<!-- TODO: tree view vs dropdown selectors vs both -->

### FR-HIER-013 — MCP tools for hierarchy 📋
New tools: `list_orgs`, `create_site`, `list_sites`, `create_group`,
`list_groups`, `add_device_to_group`, `set_device_primary_group`,
`move_device_to_site`. Existing tools gain hierarchy filters.
<!-- TODO: full tool list + which require confirmation gating -->

## Non-functional requirements

### NFR-HIER-001 — Additive schema, no destructive migration 📋
New tables (`organizations`, `sites`, `device_groups`,
`device_group_memberships`) + two nullable columns on `devices`
(`org_id`, `site_id`). No existing column is dropped or retyped.
Migration is forward-only and idempotent.

### NFR-HIER-002 — Identifiers validated at entry 📋
`org_id`, `site_id`, `group_id` reuse `validate_identifier` (CR-5)
so they're safe to embed in git paths (no traversal, no shell metachar).

### NFR-HIER-003 — Backward-compatible REST defaults 📋
`POST /api/devices` without hierarchy fields defaults to the bootstrap
`default/default/ungrouped` so existing API clients and tests keep
working unchanged.

### NFR-HIER-004 — Authz unchanged in v1 📋
v1 is data-model + UI only. Every authenticated principal still sees
the whole fleet. Site/Group-scoped permissions are explicitly
**out of scope** for v1 (see KL-HIER-001).

### NFR-HIER-005 — Vault backend parity 📋
The hierarchy methods are declared on the `DeviceRegistry` ABC.
The Vault backend may stub them (`NotImplementedError`) initially,
documented as a follow-up — mirrors the existing `update_device`
parity gap.
<!-- TODO: decide whether Vault parity is required before merge -->

## Known limitations / out of scope (v1)

### KL-HIER-001 — No hierarchy-scoped authorization (v1) ⚠️📋
v1 does not restrict *who* can see/act on which Site or Group. A
follow-up PR will let API keys + `Principal.groups` scope to a Site
or Group (e.g. `ADMZ-Site-Chicago-Admins` grants reveal only on
Chicago devices). Deferred to keep the data model stable first and
the test suite green.

### KL-HIER-002 — Per-Site / per-Group settings deferred ⚠️📋
`fleet_settings` stays global in v1. Per-Site overrides (e.g. a
different `default_password` per Site) are a future enhancement, not
part of this work.

### KL-HIER-003 — Single primary group constrains git layout ⚠️📋
Because a device lives in exactly one git directory, only its
*primary* group is reflected in the filesystem path. Re-priming a
device moves its config directory (and the associated git history
question — see FR-HIER-009 open question).

## Open design questions

These are unsettled and should be resolved (each into an ADR or a
crisp requirement) before / during implementation:

1. **Primary-group deletion** — when a device's primary group is
   deleted, auto-reassign to the Site's default group, or refuse the
   delete? (FR-HIER-005, FR-HIER-008)
2. **Move-site git history** — does moving a device to a new Site
   carry its snapshot history to the new path (`git mv`) or start
   fresh? (FR-HIER-009, FR-HIER-010)
3. **Delete cascade rules** — delete Org with Sites under it: cascade,
   or refuse? Same for Site→Group, Group→devices. (FR-HIER-008)
4. **Nested groups** — flat groups only (current assumption), or allow
   group-within-group? (FR-HIER-003)
5. **Group cap per device** — unbounded N:N, or a sane limit? (FR-HIER-004)
6. **Default rename/delete** — can operators rename or delete the
   `default` Org/Site/`ungrouped` Group, or are they permanent? (FR-HIER-006)
7. **Vault parity timing** — must Vault implement hierarchy before
   merge, or ship SQLite-only with a documented gap? (NFR-HIER-005)
8. **Tags vs Groups** — do Groups subsume `tags`, coexist, or is there
   a migration story from tags → groups? (relationship to existing
   `tags` N:N primitive)

## References

- Implementation plan (point-in-time, may drift):
  `C:\Users\dnich\.claude\plans\majestic-munching-marble.md`
- Personas: [experience-center-operator](../personas/experience-center-operator.md),
  [enterprise-fleet-operator](../personas/enterprise-fleet-operator.md)
- Cross-cutting: [snapshot-restore.md](snapshot-restore.md),
  [core-platform.md](core-platform.md), [web-api.md](web-api.md),
  [web-ui.md](web-ui.md), [mcp-server.md](mcp-server.md)
- Future authz interaction: [authentication.md](authentication.md),
  [security.md](security.md)
- ADR to be written: `decisions/00XX-org-site-group-hierarchy.md`
  (cover: git-layout choice, N:N membership + primary group,
  default-bootstrap, v1 authz-deferral)
- Prior art for N:N: existing `tags` (device metadata list)
- ID-safety: `admz/validators.py::validate_identifier` (CR-5)
