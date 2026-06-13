# ADR-0036: Slot vs unit device identity (stable slot + replaceable hardware)

**Status:** Accepted (2026-06-12).
**Date:** 2026-06-12.
**Relates to:** ADR-0014 (git as config source of truth), ADR-0031 (baselines),
ADR-0034 (widget-gated actions).

## Context

A device is identified by `device_id`, and git config is keyed
`fleet/{device_id}/config/{facet}.yaml`. Auto-registration set
`device_id = MAC`, so the identity was the physical hardware. Replacing a
unit (RMA, upgrade) gives a new MAC → a new `device_id` → the slot's
baseline/config/history is orphaned, and a saved config can't be applied to
the replacement (restore is same-`device_id` only). The device page already
showed a "Device · ADMZ slot (stable) / Installed hardware · unit
(replaceable) / Replace hardware" UI gesturing at this — but no backing
identity existed (the `devices` PK was `device_id` only; no slot/surrogate).

Separately, deleting a device was **silent in git**: the registry row went,
the config just stopped being updated — no marker that it was retired on
purpose vs. merely gone stale.

## Decision

Treat **`device_id` as the stable ADMZ *slot* identity** and **`mac_address`
as the currently-installed *unit*.** Crucially, git config is *already* keyed
by `device_id`, so keeping `device_id` across a hardware swap means the slot's
config/baseline/history **follow automatically — no git re-keying.**

- **No surrogate key, no migration.** `device_id` keeps its MAC-derived value
  (it's a convenient unique default); it is now *semantically* the slot, which
  happens to be the first unit's MAC. We deliberately did **not** mint a
  separate `slot_id` UUID — it would force re-keying every git path and every
  `device_id` reference for no functional gain. (Revisit only if a slot must
  outlive all MAC history, e.g. an id that should never look like a MAC.)
- **`mac_address` is authoritative for hardware matching.** The MAC collision
  check (`device_registry._assert_no_mac_collision`) and discovery
  IP-reconcile (`discovery/reconcile.py`) already prefer the stored
  `mac_address`, falling back to `device_id` only for un-backfilled legacy
  rows. `add_device` now defaults `mac_address = device_id` when the slot id
  is a MAC, and a one-time idempotent backfill
  (`components._backfill_mac_addresses`) fills legacy rows. So after a swap
  (which updates `mac_address`), reconcile/collision track the new unit, not
  the stale slot id.
- **Replace hardware = rebind, then offer restore.**
  `POST /api/devices/{id}/replace-hardware` points the slot at the new unit's
  host, re-probes `basicdeviceinfo` through the executor (which knows
  scheme/auth and self-heals), and updates the unit attributes
  (`mac_address`/`serial_number`/`firmware_version`/`model`) — keeping
  `device_id`. The slot's baseline is then immediately restorable onto the new
  unit via the existing widget-gated `restore_device` (unchanged, because the
  `device_id` is the same).
- **Deliberate deletion writes a git tombstone.**
  `operations.tombstone_device` writes `fleet/{device_id}/REMOVED.yaml`
  (`removed_at`/`removed_by`/`reason`) and commits `Removed: <id>` (reusing the
  ADR-0031 Audit-commit pattern) before the registry row is removed — keeping
  the config history but recording the retirement. Best-effort: a tombstone
  failure never blocks the delete. Both the MCP action executor and the REST
  `DELETE` go through it.

## Consequences

**Positive:**
- Hardware replacement preserves identity, baseline, and config history with
  zero git surgery — the slot just points at a new unit.
- The git repo now distinguishes "retired on purpose" (a `Removed:` commit)
  from "went stale," and never loses a removed device's config.
- Minimal blast radius: no schema migration, no re-keying; mostly hardening
  paths that were already structured for the slot/unit split.

**Negative / caveats:**
- A slot's `device_id` still *looks* like a MAC (its first unit's), which can
  read as "the current MAC" — the UI labels it "ADMZ slot" and shows the
  installed unit's MAC separately to disambiguate.
- Replace-hardware should be used *instead of* re-provisioning the new unit;
  provisioning the new MAC fresh would create a second slot (the collision
  check only catches it once `mac_address` is set on the original slot).
- Multi-org per-repo git is still future work; tombstone/replace use the
  single global config repo today.

## References
- Code: `admz/operations.py` (`tombstone_device`, `_action_delete_device`,
  `execute_approved_session` git_repo), `admz/components.py`
  (`_backfill_mac_addresses`), `admz/backends/sqlite_backend.py`
  (`add_device` mac default), `admz/api/routes/devices.py`
  (`DELETE` tombstone, `replace-hardware`),
  `admz/api/templates/device_detail.html` (Replace hardware UI)
- Tests: `tests/test_slot_identity.py`, `tests/test_device_replace_hardware.py`
- Reuse: ADR-0031 Audit-commit, the refresh-info re-probe
  (`_extract_device_facts` + `run_execution_tail`), `canonical_mac`/
  `_serial_to_mac`, the widget-gated `restore_device` (ADR-0034).
