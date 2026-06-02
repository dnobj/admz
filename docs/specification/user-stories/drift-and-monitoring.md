# User stories: drift and monitoring

Detecting and reconciling unauthorized changes to device configurations — somebody logged into a camera's own web UI and changed something, a firmware update changed defaults silently, an integration partner pushed a config without going through ADMZ.

## Terminology: "configuration audit" vs "audit log"

A **configuration audit** is the operator-facing name for *comparing a
device's current configuration against its known-good baseline and
reporting what changed* — the user-facing framing of **drift
detection**. It runs in two modes:

- **Just-in-time audit** — operator- or LLM-initiated, on demand
  (US-DM-001, US-DM-002, US-DM-007). Goes through the chatbot / MCP /
  REST surface.
- **Scheduled audit** — recurring, unattended, no LLM (US-DM-003). Runs
  on ADMZ's [scheduled-operations](scheduled-operations.md) framework.

Do **not** confuse this with the **audit log** (`admz/audit.py`), which
records *who-did-what to ADMZ* (credential reveals, dangerous-op
confirmations, API-key events). The configuration audit is about *device
config*; the audit log is about *operator actions*. The two intersect
only in US-DM-006 (attribution).

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

## US-DM-003 — Scheduled configuration audit

**As an** operator who wants visibility without remembering to check, **I want** ADMZ to audit configuration automatically every hour and tell me what changed.

**Acceptance criteria:** 📋 (planned — runs on the unified scheduler).

This is a **scheduled audit**: recurring, unattended, no LLM. Rather than a bespoke "drift scheduler," it rides the general [scheduled-operations](scheduled-operations.md) framework as the `drift_audit` job type (US-SCHED-007).

When implemented:
1. A job with `job_type="drift_audit"`, an interval, and a `scope` runs `check_fleet_drift(scope)` on its cadence — directly, with no Gemini call or MCP subprocess (US-SCHED-003).
2. Each run persists results (which devices drifted, which fields) to a queryable store; a clean run is recorded too, so "nothing drifted" is a positive signal rather than silence.
3. Reuses the existing `drift_alerts` transition logic (`appeared` / `changed` / `cleared`) so the schedule surfaces *changes*, not the same standing drift every hour.
4. `scope` accepts `org_id` / `site_id` / `group_id` (hierarchy-aware) alongside the existing `tag_filter` / `device_ids` (US-SCHED-006).
5. Alerting hooks (webhook / email / syslog) are a follow-on layer on the persisted transitions.

**Related requirements:** [scheduling](../requirements/scheduling.md), [drift-detection](../requirements/drift-detection.md).

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

## US-DM-007 — Just-in-time configuration audit

**As an** Experience Center operator about to start a customer demo, **I want to** ask the chatbot "audit the lobby cameras — is anything different from the last known-good?" and get an immediate clean pass/fail before the visitor walks in.

**Acceptance criteria:**
1. A natural-language audit request resolves to `check_drift` on the chosen scope — one device, a tag, or (hierarchy-aware) a Group / Site — through the MCP / chatbot surface.
2. The result distinguishes three outcomes clearly: **clean** (no drift), **drifted** (with the per-field diff), and **no baseline** (device never snapshotted — so the honest answer is "I can't audit this yet," not "clean").
3. The audit is pure-read — it never modifies the device or the repo (same guarantee as US-DM-001).
4. When drift is found, the operator can pivot in the same conversation to reconcile it (US-DM-004) — accept-as-baseline or revert — without leaving chat.
5. This is the **just-in-time** counterpart to US-DM-003's scheduled audit: same `DriftDetector` engine, operator-initiated and LLM-mediated rather than timer-driven.

**Related requirements:** [drift-detection](../requirements/drift-detection.md), [web-chatbot](../requirements/web-chatbot.md).

## Known limitations

- 📋 **No scheduled configuration audits.** The scheduler is snapshot-only today (`_execute_schedule` hardcodes `snapshot_fleet`). Scheduled audits depend on generalizing it to a `drift_audit` job type — see [scheduled-operations](scheduled-operations.md) US-SCHED-007. Scripting drift checks externally (cron + REST) works in the meantime.
- 📋 **No drift-history table.** A standalone `check_drift` call is independent and not persisted. The `drift_alerts` store *does* persist per-device drift signatures + transitions, but there's no general "drift events over time" table for trend analysis ("device X drifted 3× this week"), and no REST/MCP endpoint surfaces the alert history yet.
- ⚠️ **Drift detection requires the device to have been snapshotted at least once.** A device that was never snapshotted has no baseline to compare against; the report is empty (not "everything's drifted").
- ⚠️ **Drift is whole-facet, not field-level granularity.** If a facet has any committed state, every field is compared. There's no way to mark "ignore this field on this device" today.
- ⚠️ **Live-state-read uses the same VAPIX surface as device control.** If a device is offline or its API is unreachable, drift detection fails the same way any read fails — degrades gracefully but doesn't surface "device unreachable" as a distinct state from "no drift."
