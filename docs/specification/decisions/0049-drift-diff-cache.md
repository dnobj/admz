# ADR-0049 — Cache the drift diff at detection time

**Status:** Accepted (2026-07-18). Builds on **ADR-0031** (config drift vs a
blessed `baseline_sha`; audits record observations) and the drift-alert store
(the `drift_signatures` / `drift_alerts` tables).

## Context

Drift detection (`snapshot/drift.py::check_drift`) is expensive: it probes the
live device, captures + commits an `Audit:` observation, reads each baseline
facet from git, and diffs. Only the *signature + field count* of the result was
cached (`drift_signatures`, surfaced as the roster's drifted/in-sync state). The
**full field-level diff was recomputed live on every inspect**
(`GET /api/snapshot/drift`) — and again on revert — so opening a device's drift
panel meant waiting for a fresh device round-trip, and revert re-probed a second
time.

## Decision

**Cache the full `DriftReport` when drift is detected, and serve/accept/revert
from that cache.** A detection already runs `process_report` at the end of every
`check_drift`; that is the single write point, so the background audit / health
sweep warms the cache and an inspect renders instantly with no device probe.

- **Store** — a `drift_reports` table (one row per device) holding
  `DriftReport.to_summary()` JSON + `observed_sha` + `signature` + `computed_at`.
  Written on every `process_report` (drift or in-sync); dropped by `clear_report`
  (called from `clear_baseline`).
- **Inspect** — `GET /api/snapshot/drift?device_id=…` returns the cached report
  by default (`cached: true`, `computed_at`), annotated with the same
  `revertable` flags as before (a pure, no-probe step). `?refresh=true` forces a
  live recompute (and re-caches). No cache yet (never audited) falls back to live.
- **Accept / revert operate on the cached diff** — revert reverts the cached
  fields (not a fresh check); accept blesses the cached report's `observed_sha`
  (the exact commit inspected). This is the point of the feature: the operator
  acts on what they're looking at.
- **Staleness is accepted by design.** Further drift can occur after a report is
  cached; that is reconciled by the next audit, exactly as the operator expects.
  The one hard invariant is protected by a **baseline-match guard**: the report
  is stamped with its `baseline_sha`, and any consumer ignores the cache the
  moment it no longer matches the device's current baseline (accept, re-snapshot).
  A stale-baseline cache must never drive a revert (it would push wrong values) —
  so on a baseline change the cache falls back to a live check.
- **UI** — the Devices drift panel shows an "as of <time> · Refresh" stamp;
  Refresh re-checks live.

## Consequences

- Inspecting drift is instant (a cache read), and revert no longer re-probes.
- The cached diff can lag reality between audits — intentional, and bounded by
  the audit cadence; the freshness stamp makes it visible and Refresh forces a
  live check when it matters.
- Correctness is preserved across baseline changes by the baseline-match guard
  and by `clear_report` on every accept path (`refresh_drift_after_accept` /
  `clear_baseline`), so accept/revert can never act on a diff computed against a
  superseded baseline.

## Rollout

Branch `feat/drift-cache` (worktree, off `feat/demo-chat-tools`). The
`drift_reports` table is created idempotently; nothing to migrate. On deploy the
cache warms itself on the first audit / first live inspect per device.
