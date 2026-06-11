# Requirements: organization hierarchy (Org → Site, + tags)

ADMZ organizes devices in a two-level structural hierarchy plus a
free-form labeling primitive (ADR-0032 — the former Group level was
removed; its draft requirements FR-HIER-003/004/005 and the group parts
of 006/008/009/013 are resolved-by-removal):

```
Organization     (e.g. "Axis Communications" — WHO OWNS the cameras;
  │               owns the git config repo: repo_path / repo_remote_url)
  └── Site       (e.g. "AEC Experience Center Chicago" — WHICH SITE /
        │         local network the cameras are installed on)
        └── Device   (tagged with zero-or-more free-form TAGS,
                      e.g. "lab", "lobby", "camera")
```

- A **Site** belongs to exactly one **Organization**.
- A **Device** belongs to exactly one Org and one Site.
- **Tags** are the one operational-grouping primitive (k8s-labels
  style): they drive the web sidebar/filtering, scheduling
  (`tag_filter`), drift/snapshot scoping, search, and the dev
  auto-approver. Exact membership, case-sensitive.
- A default Org and Site exist out of the box so zero-config installs
  keep working.

Related: device-side concerns are covered in
[core-platform.md](core-platform.md); the git layout interacts with
[snapshot-restore.md](snapshot-restore.md); scoped permissions are a
follow-up that will touch [authentication.md](authentication.md) and
[security.md](security.md).

## Status legend

✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Terminology guard

> **Naming hazard:** `Principal.groups` means *AD security groups*
> (populated by LDAP, consumed by `principal_can_reveal`) — user
> identity, not device organization. Device-side "groups" no longer
> exist (ADR-0032); the device-side word is **tag**. Do not repurpose
> `Principal.groups`. (The reveal-gate tests depend on its meaning.)

## Functional requirements

### FR-HIER-001 — Organization entity ✅
An Organization is the top-level container and the ownership/isolation
boundary. Fields: `org_id` (validated per CR-5 `validate_identifier`),
`name`, `repo_path` (absolute path of the Org's git config repo;
immutable), `repo_remote_url` (optional), `created_at`, `metadata`.
CRUD on the SQLite registry; remove refuses while child Sites or
devices exist.

### FR-HIER-002 — Site entity ✅
A Site belongs to exactly one Organization. Fields: `site_id`,
`org_id` (FK), `name`, `location` (free text), `created_at`,
`metadata`. CRUD on the SQLite registry; remove refuses while devices
still belong to it. The AEC maps to a Site; Axis Communications maps
to the Org.

> **Multi-ACS note:** A single Site may contain **multiple Axis Camera
> Station Pro servers** (e.g. separate ACS instances per building wing).
> ACS server records are site-scoped targets — `site_id` is a required
> field on every ACS record. See
> [multi-target-support.md](multi-target-support.md) FR-MT-009.

### FR-HIER-003 — Tags are the device-grouping primitive ✅
Devices carry zero-or-more free-form `tags` (stored in the device
info). Matching is exact membership, case-sensitive — identical
semantics across the web `?tag=` filter, `tag_filter` in
scheduling/drift/snapshot, `search_devices`, and the dev
auto-approver's scope guard. (ADR-0032; replaces the former Group
entity + N:N membership draft.)

### FR-HIER-006 — Default Org / Site bootstrap ✅
On first run, ADMZ ensures `org=default` and `site=default` exist
(idempotent; `components._bootstrap_default_hierarchy`). The default
Org adopts the legacy `~/.admz/config-repo/` path + its `origin`
remote when present.

### FR-HIER-007 — Existing devices migrate into defaults ✅
`migrations/hierarchy_backfill.py` assigns every device lacking
`org_id`/`site_id` to `(default, default)`. Idempotent; continues past
per-device errors. (The former assign-to-"ungrouped" step was removed
with the Group level; legacy `device_groups`/`device_group_memberships`
tables are dropped idempotently on registry open.)

### FR-HIER-011 — Scoped filtering ✅/📋
The web fleet view scopes to the active Site (cookie switcher) and
filters by `?tag=` (reserved value `untagged` selects tagless
devices). ✅ MCP/REST list surfaces accept `tag_filter`. 📋 `org_id` /
`site_id` filters on `search_devices`/`snapshot_fleet`/scheduler land
with FR-SCH-012.

### FR-HIER-012 — Web UI navigation ✅
The sidebar shows the Site switcher and a **Tags** section (per-tag
device counts for the active site, plus an Untagged pseudo-row only
when untagged devices exist). Device pages show clickable tag chips.

### FR-HIER-013 — MCP/REST hierarchy tools 📋
Org/Site CRUD is registry-level only; REST/MCP management surfaces
(create_site, move_device_to_site, …) are future work, prioritized
when a second real Org/Site appears.

## Non-functional requirements

### NFR-HIER-001 — Additive schema, reversible-safe migration ✅
Tables `organizations` + `sites`, nullable `org_id`/`site_id` device
columns. The ADR-0032 drop of the two group tables is the one
destructive step — safe because they only ever held the bootstrap
"ungrouped" row (nothing operator-authored).

### NFR-HIER-002 — Identifiers validated at entry ✅
`org_id`, `site_id` reuse `validate_identifier` (CR-5) so they're safe
to embed in git paths.

### NFR-HIER-003 — Backward-compatible REST defaults ✅
`POST /api/devices` without hierarchy fields leaves `org_id`/`site_id`
NULL; the backfill (FR-HIER-007) sweeps them into the defaults.

### NFR-HIER-004 — Authz unchanged ✅ (scoping 📋)
Every authenticated principal sees the whole fleet. Site-scoped
permissions are a future follow-up (KL-HIER-001).

### NFR-HIER-005 — Vault backend parity ⚠️📋
The Org/Site methods are declared on the `DeviceRegistry` ABC; the
Vault backend stubs them (`NotImplementedError`) — mirrors the H-4
parity gap.

## Known limitations / out of scope

### KL-HIER-001 — No hierarchy-scoped authorization ⚠️📋
Nothing restricts *who* can see/act on which Site. A follow-up will
let API keys + `Principal.groups` scope to a Site.

### KL-HIER-002 — Per-Site settings deferred ⚠️📋
`fleet_settings` stays global. Per-Site overrides (e.g. a different
`default_password` per Site) are a future enhancement.

### KL-HIER-003 — Tags are flat and untyped ⚠️
No per-tag metadata, no enforced "primary", renaming a tag means
re-tagging devices. **Saved tag-selectors** ("smart groups" — named,
stored queries like `lobby-cams = lab AND camera`, surfaced in the
sidebar) are the designed future extension (ADR-0032) if richer
grouping is needed.

### KL-HIER-004 — Per-Org git repos designed, not active ⚠️📋
Each Org stores `repo_path`/`repo_remote_url`, but the runtime still
uses one global config repo (flat `fleet/{device_id}/` layout).
Per-Org repo routing lands when real multi-tenancy arrives.

## References

- ADR-0032 (tags replace Groups; Org/Site retained) — the decision
  record for this file's shape.
- Personas: [experience-center-operator](../personas/experience-center-operator.md),
  [enterprise-fleet-operator](../personas/enterprise-fleet-operator.md)
- Cross-cutting: [snapshot-restore.md](snapshot-restore.md),
  [core-platform.md](core-platform.md), [scheduling.md](scheduling.md)
  FR-SCH-012, [web-ui.md](web-ui.md), [mcp-server.md](mcp-server.md)
- Code: `admz/backends/sqlite_backend.py` (organizations/sites +
  `_DROPPED_TABLES`), `admz/api/templating.py::build_nav`,
  `admz/api/routes/web.py::devices_page`,
  `admz/migrations/hierarchy_backfill.py`
- ID-safety: `admz/validators.py::validate_identifier` (CR-5)
