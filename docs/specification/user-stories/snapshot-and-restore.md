# User stories: snapshot, restore, drift

The git-backed configuration management workflow — the original Experience Center driver. Capture device state, version it, diff it, restore it, branch it.

## US-SR-001 — Snapshot one device

**As an** Experience Center operator preparing for a demo, **I want to** snapshot a camera's current configuration **so that** I can return to it after the demo.

**Acceptance criteria:**
1. `snapshot_device(device_id, message="pre-demo-baseline")` runs the device's applicable facet adapters (`image`, `network`, `time_config`, `stream_profiles`, `users`, `events`).
2. Each facet's read produces both a normalized YAML (`config/<facet>.yaml`) and a raw API response (`raw/<facet>.yaml`).
3. Volatile prefixes (`root.Properties.System.Soc.`, `root.Properties.Firmware.`) are stripped.
4. Sensitive prefixes (`root.HTTPS.PrivateKey`, `root.Network.Wireless.WPA.`, `root.RemoteService.`) are filtered entirely — never written to disk.
5. The snapshot is committed to a local git repo at `$ADMZ_CONFIG_REPO_PATH`. If `$ADMZ_CONFIG_REPO_REMOTE` is set, the commit is pushed.
6. The response includes the git SHA, per-facet success/fail counts, and the commit message.

**Related requirements:** [snapshot-restore](../requirements/snapshot-restore.md).

**Related decisions:** [0012 — snapshot on plans](../decisions/0012-snapshot-on-plans.md), [0013 — hybrid YAML + raw](../decisions/0013-hybrid-yaml-and-raw.md).

## US-SR-002 — Snapshot the whole fleet

**As an** operator with a 50-device fleet, **I want to** snapshot everything in one commit **so that** I have a coherent point-in-time view.

**Acceptance criteria:**
1. `snapshot_fleet(tag_filter="auto-snapshot", message="nightly")` runs `snapshot_device` against every registered device matching the tag.
2. All snapshots land in **one** git commit with the given message.
3. Devices that fail produce a `FacetResult(success=False, error=…)` but don't abort the others.
4. The response summarizes per-device success/failure counts.

**Related requirements:** [snapshot-restore](../requirements/snapshot-restore.md), [performance](../requirements/performance.md).

## US-SR-003 — Diff two snapshots

**As an** operator, **I want to** see what changed between two snapshots **so that** I can audit a demo's effects.

**Acceptance criteria:**
1. `diff_device(device_id, ref_a="HEAD~1", ref_b="HEAD")` returns a text diff plus recent commit history for that device's subtree.
2. The diff is over normalized YAML (clean diffs), not raw responses.
3. Defaults work intuitively: omit args → diff yesterday's snapshot vs today's.

**Related requirements:** [snapshot-restore](../requirements/snapshot-restore.md).

## US-SR-004 — Restore a device

**As an** operator after a broken demo, **I want to** restore a device to the last known-good configuration **so that** the device is usable for the next visitor.

**Acceptance criteria:**
1. `restore_device(device_id, ref="HEAD")` reads each facet YAML from git at the given ref.
2. The `RestoreBuilder` produces a list of write operations (e.g. `param.cgi:update`, `pwdgrp.cgi:add-user`).
3. The plan is **not** auto-executed — it's returned as a `plan_id` for review.
4. The operator (or LLM) calls `execute_plan(plan_id)` to apply.
5. Dangerous steps in the restore plan are gated by the same two-gate model that protects any plan (US-LLM-003).
6. Restore order respects facet `restore_order` hints (network last so the device doesn't disconnect mid-restore; firmware first if it's changing).

**Related requirements:** [snapshot-restore](../requirements/snapshot-restore.md), [plans](../requirements/plans.md).

## US-SR-005 — Drift detection

**As an** operator concerned about unauthorized changes, **I want** ADMZ to tell me which devices have diverged from their committed configuration.

**Acceptance criteria:**
1. `check_drift(device_id)` reads the device's current state and diffs it against the latest git HEAD.
2. The response includes `has_drift`, `facets_checked`, `facets_drifted`, and a list of `DriftField(facet, path, expected, actual)`.
3. `check_drift()` with no `device_id` scans the entire fleet; `check_drift(tag_filter=…)` scans a subset.
4. Drift detection never modifies the device. It **does** commit the observation it took to the config repo — see [US-DM-001](drift-and-monitoring.md) criterion 4 for what and why, rather than a second copy of the rule here (#214).

**Related requirements:** [drift-detection](../requirements/drift-detection.md).

## US-SR-006 — Scheduled snapshots

**As an** enterprise operator, **I want** nightly snapshots of my tagged devices **so that** I have continuous point-in-time recovery without manual intervention.

**Acceptance criteria:**
1. `create_snapshot_schedule(schedule_id, description, interval="1d", tag_filter="auto-snapshot")` persists a schedule to `~/.admz/schedules.json`.
2. The `SnapshotScheduler` runs the schedule as an asyncio task at the configured interval.
3. Schedules survive process restarts (re-loaded from JSON on startup).
4. `list_snapshot_schedules`, `update_snapshot_schedule`, `delete_snapshot_schedule`, and `run_snapshot_schedule` cover the CRUD + manual-trigger.
5. There is **exactly one** scheduler instance per ADMZ process even when MCP and FastAPI are both running (Phase 3B fix).

**Related requirements:** [scheduling](../requirements/scheduling.md).

## US-SR-007 — Fork a known-good config

**As an** operator with `camera-conference-01` perfectly configured, **I want to** create `camera-conference-03` with the same configuration as a starting point.

**Acceptance criteria:** 📋 (planned — `fork_device_config` MCP tool exists in design docs but not yet implemented).

**Related decisions:** [0014 — config in git, creds in DB](../decisions/0014-config-in-git-creds-in-db.md).

## Known limitations (as of 2026-05)

- 🚧 **Restore rollback is incomplete.** Only `param.cgi:update` operations have pre-read rollback. REST-API writes, SOAP writes, and `pwdgrp.cgi:add-user` do not currently capture rollback data — a failed restore mid-flight may leave the device in an intermediate state.
- 📋 **Profiles and forking.** `profiles/` directory layout is documented (in `EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md`) but no `fork_device_config` MCP tool exists yet.
- 📋 **CI validation on the config repo.** No GitHub Actions workflows ship with ADMZ — operators add their own.
- ⚠️ **No automatic restore order across firmware boundaries.** The catalog says "firmware first if changing," but the restore builder doesn't yet detect firmware changes specifically.
- ⚠️ **Fleet snapshot is unbounded fan-out.** One asyncio task per device with no semaphore — fine at ~100 devices, problematic at 1000+ (see [performance.md](../requirements/performance.md)).
