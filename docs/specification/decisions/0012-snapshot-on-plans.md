# ADR-0012: Snapshot and restore implemented on top of the plan engine

**Status:** Accepted, in production.
**Date:** Original design 2026-04 (`EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md`).

## Context

The snapshot system needs to:
- Read every facet on every targeted device (parallelism, failure
  handling, retry, per-step status reporting).
- Restore by applying writes back to devices (also parallelism,
  failure policies, two-gate safety, dependency ordering).

The plan engine (`admz/plans/engine.py`) already does all of this for
arbitrary catalog operations: validation, fleet-parallel execution,
failure policies, rollback pre-reads, dependency tracking.

We could build a separate snapshot orchestrator. Or we could reuse
the plan engine.

## Decision

**Reuse the plan engine.** Snapshot = a read-only plan; restore = a
write plan generated from git YAML.

Concretely:

- **Snapshot:** `SnapshotEngine.snapshot_device(device_id)` builds a
  list of read operations from the applicable facet adapters, executes
  them via the executor (the same path catalog operations take), and
  routes responses to facet serializers instead of returning to the
  caller. Fleet snapshot fans out across devices with the same
  bounded-concurrency model as fleet plans (Phase 3D).
- **Restore:** `RestoreBuilder.build_restore_plan(device_id, ref)`
  reads facet YAMLs from git, calls each facet's `deserialize()` to
  produce a list of write operations, and hands the result to
  `PlanEngine.create_plan()`. The operator approves and executes the
  plan exactly like any other.

So the snapshot system "owns" the facet abstraction (what to read,
how to normalize) and the git layer (where to write the result); the
plan engine owns the execution mechanics.

## Consequences

**Positive:**
- **Parallelism for free.** A 100-device fleet snapshot is a 100-device
  plan with no cross-device dependencies — fleet-parallel mode kicks
  in automatically.
- **Two-gate safety for free.** A restore plan with any
  `dangerous`-risk write step requires the same `confirm_dangerous=True`
  flag (Phase 2D). No special-case "restores skip the gate" — that
  would be a footgun.
- **Failure policies inherited.** `on_failure: stop` aborts a restore
  at first failure; `skip_dependents` continues with independent
  branches.
- **Rollback pre-reads** inherited where they exist (currently
  `param.cgi:update` only — known broader limitation).
- **One execution code path** to test, profile, harden.

**Negative:**
- The plan engine had to grow features the snapshot system needed
  (e.g. fleet-parallel mode). Coupling is mostly good but means the
  engine's contract is wider than "execute LLM-built plans" might
  imply.
- Snapshot operations are slightly noisy in the audit log — they
  appear as plan-executions rather than a distinct "snapshot"
  audit category. Filterable, but a separate `snapshot.*` action
  type in audit might be clearer (small follow-up).

## References

- [EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md](../../EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md) §6 "The snapshot plan"
- ADR-0005 — two-gate plan approval (which snapshot/restore inherit)
- ADR-0013 — hybrid YAML + raw artifacts (the snapshot output format)
- ADR-0015 — pluggable facets (where the snapshot-specific logic lives)
- Requirements: [snapshot-restore.md](../requirements/snapshot-restore.md), [plans.md](../requirements/plans.md)
- Code: `admz/snapshot/engine.py`, `admz/snapshot/restore.py`, `admz/plans/engine.py`
