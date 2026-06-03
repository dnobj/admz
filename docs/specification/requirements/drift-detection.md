# Requirements: drift detection

Compare a device's live state against the configuration stored in
git. Surface field-level differences so operators can decide:
re-snapshot, restore, or investigate.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-DRF-001 — DriftReport is the unit of result ✅
`admz/snapshot/models.py::DriftReport`:
- `device_id`, `has_drift`
- `fields` — list of `DriftField` (facet, dotted path, expected,
  actual)
- `facets_checked`, `facets_drifted`, `timestamp`

Empty `fields` + `has_drift=False` means "in sync." Each
`DriftField` is a single point of disagreement, so a report with
20 changed values has 20 entries.

### FR-DRF-002 — DriftDetector reuses facets ✅
`admz/snapshot/drift.py::DriftDetector.check_drift(device_id,
ref="HEAD")` reads the device's live state via the same facet
adapters that captured the snapshot (FR-SNP-002), and compares
against the YAML in `~/.admz/configs/<device_id>/<facet>.yaml` at
the given git ref.

### FR-DRF-003 — Field-level diffing via flatten ✅
Both stored and live facet outputs are flattened to dotted-key
strings (`network.dns.servers.0 = "8.8.8.8"`), which gives stable
per-field diffs even when nested. The flattening is in
`admz/snapshot/drift.py::_flatten`.

### FR-DRF-004 — Compare against an arbitrary git ref ✅
The `ref` parameter accepts any git-resolvable name — `HEAD`, a
specific commit SHA, a tag (`pre-firmware-upgrade`), or a date
(`HEAD@{2026-04-01}`). Lets operators ask: "what changed since
last Tuesday?"

### FR-DRF-005 — Fleet-wide drift sweep ✅
`check_fleet_drift(device_ids=None, ref="HEAD")` runs drift checks
across many devices concurrently, bounded by the same fleet
semaphore as snapshot (FR-SNP-004). Returns a list of
DriftReports; the caller filters to `has_drift=True`.

### FR-DRF-006 — Drift report is read-only ✅
`check_drift` never modifies the device or the git repo. It's
safe to schedule against the whole fleet hourly. Acting on the
report — restoring or accepting the new state — is an explicit
follow-up.

### FR-DRF-007 — Per-facet skip when unstored ✅
If a facet has never been snapshotted (no file in git), it's
skipped, not flagged as drift. `facets_checked` counts only facets
with stored baselines. This lets operators roll out drift checks
incrementally as new facet adapters land.

### FR-DRF-008 — Drift exposed via MCP and REST ✅
Actual surface (corrected — earlier revisions cited a `/api/v2/...`
surface and `check_device_drift` tool that never shipped):
- MCP: `check_drift(device_id?, tag_filter?)` — one tool covers both
  single-device and fleet (omit `device_id` for a fleet sweep); plus
  `diff_device(device_id, ref_a, ref_b)` for historical snapshot-to-
  snapshot diffs.
- REST: `GET /api/snapshot/drift?device_id=&tag_filter=`,
  `GET /api/snapshot/diff/{device_id}?ref_a=&ref_b=`.

Both surface the DriftReport JSON; agents typically narrow the
result to `fields` matching a particular path before acting.

### FR-DRF-009 — Scheduled configuration audit 📋
A recurring, unattended configuration audit — the operator-facing
framing of a scheduled fleet drift sweep. Rather than a bespoke drift
scheduler, it rides the unified job scheduler as `job_type="drift_audit"`
(see [scheduling](scheduling.md) FR-SCH-010/011, ADR-0026):
1. Runs `check_fleet_drift(scope)` on its interval — no LLM, no MCP
   subprocess (attributed to the `scheduler` principal, FR-SCH-013).
2. Persists per-device results (including clean runs, so "nothing
   drifted" is a recorded positive, not silence).
3. Reuses the `drift_alerts` transition logic (`appeared` / `changed` /
   `cleared`) so each run emits *changes*, not the standing drift set.
4. `scope` is hierarchy-aware (`org_id`/`site_id`/`group_id`) alongside
   `tag_filter` / `device_ids`.

### FR-DRF-010 — Drift-alert history is queryable via API ✅
`DriftAlertStore.list_alerts(...)` already persists transitions
(KL-DRF-004) and is now surfaced via:
- MCP: `get_drift_alerts(device_id?, since?, transitions?, limit?)`
- REST: `GET /api/drift/alerts?device_id=&since=&transition=&limit=`
Both are read-only, anonymous-allowed + audited; `device_id` flows
through `validate_identifier` (CR-5); `transition` is validated
against the {appeared, changed, cleared} allow-list; `since`
accepts ISO-8601 or unix timestamps; `limit` caps at 1000.
Implemented in `admz/api/routes/drift.py` and
`admz.mcp.server._get_drift_alerts`. This is the read side of
US-SCHED-005 (observable outcomes).

## Non-functional requirements

### NFR-DRF-001 — No side effects on the device ✅
Drift checks issue only the read operations that the facet
adapters use during snapshot. No state-changing call ever fires
from `check_drift`.

### NFR-DRF-002 — Normalized comparison is firmware-tolerant ✅
The compared values are the *normalized* facet outputs, not raw
VAPIX response strings. Whitespace differences, key ordering, and
representation quirks (e.g. `"true"` vs `"yes"`) are absorbed by
the facet adapter.

## Known limitations

### KL-DRF-001 — String-equality compare ⚠️
The diff treats every value as a string after flatten. Numeric
fields like `image.fps = 30` vs `30.0` would surface as drift.
None of the current facets emit ambiguous numerics, but this is a
latent issue if a new facet does.

### KL-DRF-002 — No "accept current state" shortcut ⚠️
To accept the live state as the new baseline, operators run a
fresh `snapshot_device`. There's no `accept_drift` command. This
is intentional — accepting drift should be an explicit recorded
event — but operators sometimes ask for a one-call shortcut.

### KL-DRF-003 — Drift sweep cost grows with fleet × facets ⚠️
A fleet of 500 devices with 6 facets each is ~3000 read calls per
sweep. The semaphore caps in-flight concurrency, but wall-clock
time still scales linearly. See KL-PERF-001.

### KL-DRF-004 — Transition alerting on top of pull-based checks ✅
Resolved in Phase 8. `admz/snapshot/drift_alerts.py` hooks into
every `DriftDetector.check_drift` call and compares the report
against the last-known drift signature for that device. Three
transitions are recorded:

  - `appeared` — device was in sync; drift fields appeared.
  - `changed` — drift set or values changed.
  - `cleared` — drift is gone.

The first observation for a device is the baseline — no alert.
Alerts persist to the `drift_alerts` SQLite table with timestamp,
device, transition, field counts, signature hash, and a one-line
summary. Operators query via `DriftAlertStore.list_alerts(since=…,
device_id=…, transitions=…, limit=…)`.

The check itself is still pull-based — drift sweeps via the
scheduler or operator-initiated checks feed the alert log
naturally. `clear_baseline(device_id)` lets an operator accept
the current state as the new baseline without manually editing
the DB.

A true push-based notifier (webhook, chat alert, Slack) is the
next layer up — not in Phase 8.

## References

- ADRs: [0012](../decisions/0012-snapshot-on-plans.md), [0014](../decisions/0014-config-in-git-creds-in-db.md), [0015](../decisions/0015-pluggable-facets.md), [0026](../decisions/0026-unified-job-scheduler.md)
- User stories: [drift-and-monitoring](../user-stories/drift-and-monitoring.md), [scheduled-operations](../user-stories/scheduled-operations.md)
- Cross-cutting: [observability.md](observability.md), [performance.md](performance.md)
- Sibling: [snapshot-restore.md](snapshot-restore.md), [scheduling.md](scheduling.md)
- Code: `admz/snapshot/drift.py`, `admz/snapshot/drift_alerts.py`
