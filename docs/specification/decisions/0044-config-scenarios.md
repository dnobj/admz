# ADR-0044 — Config scenarios (baseline-stable alternate configs)

**Status:** Accepted (2026-07-05).
**Relates to:** ADR-0031 (baseline_sha / drift), the named-baselines ("alternate
configurations") follow-on (PR #69), ADR-0034 (widget-gated service-affecting
pushes).

## Context

Alternate configurations (per-device named baselines) shipped in PR #69, but the
UX conflated two ideas and the activation semantics fought the operator's mental
model:

1. The per-device "save config" panel showed an **"Apply … across [tag]"**
   control that *looked* like it broadcast a config to a group but actually
   **name-matched** — activating each device's own same-named baseline and
   silently skipping the rest.
2. **Activating** an alternate (both "Make active" and "Apply across tag")
   **re-pointed `baseline_sha`**, so the alternate *became* the baseline. That
   broke "switch back to the baseline": after activating a demo, "baseline" now
   meant the demo.

What operators actually want: per-device full configs (optionally addressed as a
**tag-group**) used as **demo/test "scenarios"** you flip on and snap back from —
not golden templates, not shared-settings profiles.

## Decision

**A scenario is a temporary push; the blessed baseline never moves.** Activating a
scenario pushes that saved config to the device(s) but leaves `baseline_sha`
untouched, so **"return to baseline" is a first-class, always-available
snap-back**. Storage is unchanged (the `device_baselines` name→commit table);
the model adds:

1. **`active_scenario` marker** — a nullable `devices` column recording which
   named config is currently pushed (NULL = on baseline). A new drift state
   **`in_scenario`** supersedes drifted/in_sync when it's set: a scenario device
   differs from baseline *on purpose*, shown as a calm "In scenario: X" badge,
   not an alarming "drifted".

2. **Group-scoped save / activate / return**, addressed by a device or a tag:
   - `POST /api/snapshot/scenario/save` — snapshot each target's live config
     (`snapshot_device(bless=False)` — new param that captures a commit WITHOUT
     blessing it as baseline) → `save_named_baseline`. Not gated (read + commit).
   - `POST /api/snapshot/scenario/activate` — push each device's own config of
     that name in ONE gated plan (reusing `build_restore_plan` + `create_plan` +
     `execute_gated_plan`), set `active_scenario`, **without** moving
     `baseline_sha`. Devices lacking the name are reported in `skipped`.
   - `POST /api/snapshot/scenario/return-to-baseline` — restore each target to
     its `baseline_sha` in one gated plan and clear `active_scenario`.
   - `GET /api/snapshot/scenarios?tag=` — scenario names + per-name device counts.

3. **UI** — the device page's alternate-config panel gains an **Activate**
   (gated temporary push) action and a **Return to baseline** button when in a
   scenario; the misleading "Apply across tag" row is removed. A tag-filtered
   **Devices** page (`?tag=`) shows a group **Scenarios** toolbar
   (activate / return across the tag), modeled on the drift bulk-action toolbar.

4. **Retire `POST /api/snapshot/apply-tag-baseline`** — its baseline-moving
   semantics are exactly what we're replacing; scenario activate supersedes it.

## Consequences

- The demo/test loop is symmetric and honest: activate a scenario on a device or
  a group → run it → return to baseline; the baseline is a stable anchor
  throughout, and scenario devices read as "in scenario," not "drifted."
- Per-device identity/network data is never broadcast — each device pushes its
  OWN saved config (name-matched), reusing the restore path that already skips
  identity/Volatile*/secret params.
- **Known limitation (marker timing):** `active_scenario` is set/cleared at
  request time, when the gated plan is created (mirroring how apply-tag-baseline
  set `baseline_sha` at request time). If the operator cancels the confirm, the
  marker is set but the push didn't happen; "return to baseline" or the next
  drift check reconciles it. A post-approval hook (set the marker only after the
  plan executes) is a possible follow-up.
- **Deferred:** MCP tools (`list_scenarios` / `activate_scenario` /
  `return_to_baseline`) so the chatbot can "activate the demo scenario across the
  lab group." The REST + gate machinery is the substrate; the feature is
  UI-driven in v1.
