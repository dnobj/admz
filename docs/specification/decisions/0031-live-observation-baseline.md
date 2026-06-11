# ADR-0031: Live / Observation / Baseline — separating "what we saw" from "what we bless"

**Status:** Accepted, in progress. Slice 1 (the baseline pointer) landed
2026-06-11; observations, accept/revert, and retention follow as slices 2–4.
**Date:** 2026-06-11.
**Relates to:** ADR-0014 (config in git, creds in DB), ADR-0012 (snapshot on
plans), ADR-0013 (hybrid YAML + raw), ADR-0026 (unified job scheduler).

## Context

The snapshot/drift system conflated three distinct ideas into a single git
ref, **HEAD**:

- `DriftDetector.check_drift` compared live config against `ref="HEAD"`.
- Every `snapshot` commits and moves HEAD.

So "the baseline" silently followed the latest snapshot. Three consequences:

1. **Scheduled snapshots silently re-baseline.** A periodic `snapshot` job
   moves HEAD to the current (possibly drifted) state — drift-vs-HEAD then
   reads zero, masking the very drift the operator wanted to catch.
2. **Audits discard what they saw.** `check_drift` kept only a hash
   *signature* + a field count (for de-duped alerts); the actual observed
   config was never recorded. "What did this device look like on June 5?"
   was unanswerable.
3. **No way to pin or revert.** There was no "this exact config is blessed"
   marker, and `restore` defaulted to HEAD (which audits would later move).

These are really three different things the system only modelled as one:

- **Live** — what's physically on the device now (ephemeral; known only when probed).
- **Observation** — what an audit/snapshot *saw* and recorded (a historical fact).
- **Baseline** — the config an operator has *blessed* as intended (what drift is measured against).

## Decision

Model all three. Keep ADR-0014 intact — git remains the single source of
truth for config *bytes* and history; the DB gains only **pointers**, never a
second copy of the config.

**Per-device pointers (DB columns on the `devices` row):**

- `baseline_sha` — the commit an operator blessed as the baseline.
- `latest_observed_sha` — the most recent commit an audit/snapshot recorded.
- `last_observed_at` — Unix epoch of that observation.

Set via `DeviceRegistry.set_config_pointers(...)` (SQLite implements it; the
stubbed Vault backend inherits the ABC's `NotImplementedError` and callers
degrade best-effort, consistent with the H-4 deferral).

**Semantics:**

- **Drift = `diff(live, baseline_sha)`**, not vs HEAD. No `baseline_sha` →
  the report is `no_baseline=True` (explicitly "nothing blessed to compare",
  *not* "in sync").
- **`snapshot`** captures config and **sets `baseline_sha` = HEAD** ("this
  state is good now"). Commit-on-change still holds: an unchanged device
  produces no commit, and HEAD remains a valid baseline ref.
- **Audit** (slice 2) records the observed config to git as an `Audit:`
  commit (commit-on-change) and advances `latest_observed_sha` only —
  **never** `baseline_sha`.
- **accept/promote** (slice 3) sets `baseline_sha` to a chosen commit
  (default: the latest observation). **revert** restores from `baseline_sha`.
- **`restore`** defaults to `baseline_sha` (an explicit ref still overrides).
- Commit messages carry intent: `Baseline:` / `Snapshot:` / `Audit:`.

**Migration:** a one-time, idempotent backfill (`components._backfill_baselines`)
pins `baseline_sha = HEAD` for devices that have committed config but no
pointer yet, so existing baselines aren't orphaned.

## Consequences

**Positive:**
- The scheduler is safe in both modes: a `drift_audit` records observations
  and alerts but can't move the baseline; only an explicit snapshot/accept
  re-baselines.
- Audits become a time-series — "what changed and when" is answerable from
  `git log`, and any observation can be promoted to baseline (it's already a
  commit) with no re-capture.
- Single source of truth preserved: the DB holds SHAs + drift status, not the
  config bytes — no dual-write to drift out of sync (ADR-0014 holds).
- The Configuration roster, drift checks, and restore all agree on one notion
  of "baseline".

**Negative:**
- Recording every audit grows git history. Mitigated by commit-on-change
  (stable devices add nothing) and a retention pass (slice 4) that never
  prunes a baseline commit and thins old observations.
- One more migration on the `devices` table (three nullable columns) — cheap
  via the existing `_apply_device_extra_columns` idempotent ALTER.

**Alternative considered:**
- **Keep baseline == HEAD, just stop scheduled snapshots from auto-moving it.**
  Rejected: it doesn't give observations a home, can't pin, and "restore to
  baseline" stays ambiguous once any commit lands on HEAD.
- **Store the observed config in the DB too.** Rejected: a second copy of the
  config that drifts out of sync with git — exactly the dual-write ADR-0014
  exists to avoid. The DB caches the pointer, not the bytes.
- **A separate `baseline` git branch/ref per device.** Rejected for now as
  heavier than a SHA pointer; the named-**branches** feature
  (`EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md` §Phase 5, "main + intentional
  overrides") is a distinct, later concern kept orthogonal to this.

## References

- Requirements: [drift-detection.md](../requirements/drift-detection.md)
  (FR-BAS-*), [snapshot-restore.md](../requirements/snapshot-restore.md),
  [scheduling.md](../requirements/scheduling.md)
- User stories: [drift-and-monitoring.md](../user-stories/drift-and-monitoring.md)
- Builds on ADR-0014 (config in git, creds in DB).
- Code: `admz/backends/sqlite_backend.py::set_config_pointers`,
  `admz/snapshot/drift.py::DriftDetector.check_drift`,
  `admz/snapshot/engine.py::_set_baseline_pointers`,
  `admz/snapshot/restore.py::build_restore_plan`,
  `admz/components.py::_backfill_baselines`.
