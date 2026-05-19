# User stories: drift and monitoring

Detecting and reconciling unauthorized changes to device configurations — somebody logged into a camera's own web UI and changed something, a firmware update changed defaults silently, an integration partner pushed a config without going through ADMZ.

## US-DM-001 — Single-device drift check

**As an** operator suspicious that `camera-lobby-01` isn't behaving like it used to, **I want to** check what's different from the last committed snapshot.

**Acceptance criteria:**
1. `check_drift(device_id)` reads live device state via the same facet adapters that snapshot uses (no separate "drift code path").
2. Live state is diffed against the latest snapshot at git HEAD for that device.
3. The response is a `DriftReport` with `has_drift` (bool), `facets_checked`, `facets_drifted`, and a flat list of `DriftField(facet, path, expected, actual)` entries.
4. Drift detection never modifies the device or the git repo — pure read.
5. If a facet has no committed state (never snapshotted), it's skipped (logged), not flagged as drift.

**Related requirements:** [drift-detection](../requirements/drift-detection.md).

## US-DM-002 — Fleet-wide drift sweep

**As an** enterprise fleet operator, **I want to** see which devices in my fleet have drifted overnight.

**Acceptance criteria:**
1. `check_drift()` (no `device_id`) iterates over the registered fleet — or `tag_filter="production"` for a subset — and returns a summary.
2. Response shape: `{count, drifted, reports: [...]}`. Each report is a `DriftReport` per device.
3. Per-device failures (e.g. device offline) appear as a report with `__error__` facet entries — they don't abort the whole sweep.
4. The sweep respects the bounded-fan-out semaphore (Phase 3D) so a 1000-device fleet doesn't open 1000 simultaneous httpx connections.

**Related requirements:** [drift-detection](../requirements/drift-detection.md), [performance](../requirements/performance.md).

## US-DM-003 — Scheduled drift sweep

**As an** operator who wants visibility without remembering to check, **I want** ADMZ to run a drift sweep automatically every hour.

**Acceptance criteria:** 📋 (planned — see Known limitations below).

The current snapshot scheduler runs snapshots on a recurring interval. A drift scheduler — recurring `check_drift` with results written somewhere queryable — is a natural follow-on. For v1, operators script this externally via `python -m admz` or REST calls.

When implemented:
1. `create_drift_schedule(schedule_id, interval, tag_filter)` persists alongside snapshot schedules.
2. Each run writes results to a queryable table (or extends the audit log).
3. The operator can configure alerting per their stack (Slack webhook, email, syslog).

## US-DM-004 — Reconcile detected drift

**As an** operator looking at a drift report showing `camera-lobby-01` has a different bitrate than the snapshot, **I want to** decide between accepting the drift as the new baseline or reverting to the snapshot.

**Acceptance criteria:**
1. **Accept-as-new-baseline:** `snapshot_device(device_id, message="accept-drift")` captures the current state, commits to git. Future drift checks pass.
2. **Revert:** `restore_device(device_id, ref="HEAD")` builds a plan to re-apply the snapshotted state. Plan is reviewed and executed normally (same two-gate model).
3. Either decision is reversible — git history preserves both states.

**Related requirements:** [snapshot-restore](../requirements/snapshot-restore.md).

## US-DM-005 — Visualizing drift in chat

**As an** operator working through the chatbot (when it lands), **I want to** see drift as a clean diff rendering, not raw JSON.

**Acceptance criteria:** 📋 (planned — depends on web chatbot).

Once the chatbot exists:
1. `check_drift` invocations from chat render as a table or per-facet sections.
2. Per-field rows show expected (snapshot) → actual (live), with diffs highlighted.
3. Each row has [Revert] / [Accept] inline buttons that map to the snapshot or restore calls.

## US-DM-006 — Drift attribution

**As an** auditor investigating why a configuration changed, **I want to** find out who or what made the change.

**Acceptance criteria:**
1. The git commit history of the snapshot repo shows when configurations changed (commit timestamp + message).
2. The audit log (Phase 4D) records every `get_credentials`, dangerous-op confirm, and API-key event with the authenticated principal.
3. ADMZ-driven changes appear in both places. **Non-ADMZ changes** (someone logging into the device's own web UI) appear only as drift — there's no way for ADMZ to know who made an out-of-band change.

**Related requirements:** [security](../requirements/security.md) FR-AUTH-011 + 012.

## Known limitations

- 📋 **No scheduled drift sweeps.** Snapshot schedules exist; drift schedules don't yet. Scripting drift checks externally works for now.
- 📋 **No drift-history table.** Each `check_drift` call is independent; results aren't recorded persistently. A future "drift events" table would enable trend analysis.
- ⚠️ **Drift detection requires the device to have been snapshotted at least once.** A device that was never snapshotted has no baseline to compare against; the report is empty (not "everything's drifted").
- ⚠️ **Drift is whole-facet, not field-level granularity.** If a facet has any committed state, every field is compared. There's no way to mark "ignore this field on this device" today.
- ⚠️ **Live-state-read uses the same VAPIX surface as device control.** If a device is offline or its API is unreachable, drift detection fails the same way any read fails — degrades gracefully but doesn't surface "device unreachable" as a distinct state from "no drift."
