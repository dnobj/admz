# Requirements: plans

Multi-step execution plans with risk classification, dependency
tracking, snapshot-on-write rollback, and three failure policies.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-PLN-001 — ExecutionPlan + PlanStep models ✅
`admz/plans/models.py`:
- `ExecutionPlan` — `plan_id`, `description`, `steps`,
  `on_failure`, `status`, `risk_summary`, `results`,
  `rollback_steps`, `created_at`, `created_by`
- `PlanStep` — `step_number`, `operation_id`, `device_id`,
  `params`, `description`, `risk_level`, `family`, `depends_on`,
  `condition`

### FR-PLN-002 — Plan status state machine ✅
`PlanStatus`: `pending_approval` → `approved` → `executing` →
(`completed` | `failed` | `cancelled`). One-way transitions; the
engine refuses re-execution of a terminal plan.

### FR-PLN-003 — Step-level dependency tracking ✅
`PlanStep.depends_on` lists prerequisite step numbers. The engine
runs ready-steps in parallel where possible, blocks dependents
until prerequisites complete. A failed prerequisite triggers
`FailurePolicy.SKIP_DEPENDENTS` behavior for that subtree.

### FR-PLN-004 — Three failure policies ✅
`FailurePolicy`:
- `stop` — first failure halts the plan
- `skip_dependents` — failures don't block independent steps,
  but anything `depends_on` the failed step is skipped
- `continue` — every step runs; the result list reports
  individual outcomes (implemented Phase 3D)

### FR-PLN-005 — Mechanical gate by aggregate risk ✅
`admz/plans/engine.py::PlanEngine.create_plan(...)` computes the
plan's `risk_summary` from per-step `risk_level`. The engine sets
`PlanStatus.PENDING_APPROVAL` and returns the plan — execution
only proceeds after `approve_plan(plan_id, ...)` validates the
caller's confirmation per FR-PLN-007. See
[ADR-0005](../decisions/0005-two-gate-plan-approval.md).

### FR-PLN-006 — Risk classification from catalog ✅
Each `PlanStep.risk_level` is sourced from the operation YAML's
`risk_level`, not chosen by the caller. The plan creator can only
*assemble* operations; they can't relabel a `dangerous` op as
`normal`. The MCP tool `create_plan` enforces this by reading
risk_level from the catalog as it builds steps.

### FR-PLN-007 — Multi-level confirmation policy ✅
Fleet setting `confirm_level_<risk>` picks the gate per risk:
- `none` — auto-approve (only allowed for `read-only`)
- `llm_confirm` — caller passes a confirmation string the LLM
  generated for this specific plan
- `url_only` — caller follows a one-time approval URL
- `url_and_password` — URL + the operator's password

See [ADR-0006](../decisions/0006-multi-level-confirmation.md).
Defaults err on the side of `url_and_password` for `dangerous`.

### FR-PLN-008 — Snapshot before write ✅
Before any step with `risk_level >= normal`, the engine takes a
device snapshot (FR-SNP-001) and commits it to the git-backed
configs repo. Rollback uses the snapshot to restore the
pre-execution state. See
[ADR-0012](../decisions/0012-snapshot-on-plans.md).

### FR-PLN-009 — Per-step rollback strategy ✅
After execution, the engine inverts each completed write step
using the operation's `rollback` spec:
- `revert-params` — re-apply pre-write values (param.cgi)
- `delete` — call the delete counterpart (add-user → remove-user)
- `none` — explicitly irreversible; the operation can still run
  but only with elevated confirmation

`rollback_steps` is the inverted plan; `rollback_plan(plan_id)`
executes it.

### FR-PLN-010 — Plan store ✅
Plans persist to `~/.admz/plans/` (one JSON file per plan). This
survives process restart so an approved-but-not-yet-executed plan
isn't lost on a server reboot. The store is keyed by `plan_id`.

### FR-PLN-011 — Per-plan audit trail ✅
Each plan records `created_by` (the principal that called
`create_plan`) and emits audit events at create / approve /
execute / complete / rollback. Audit log lives at
`~/.admz/audit.log` (Phase 4D).

### FR-PLN-012 — Plan templates for common patterns 📋
A `template:` parameter on `create_plan` that expands a known pattern (e.g.
"configure ntp + timezone + verify") into a multi-step plan without the LLM
having to assemble the operations.

> **Corrected 2026-08-04 (#214).** Marked ✅ while pointing at `admz/plans/templates.py`, which does not exist — `admz/plans/` holds `__init__`, `completion`, `engine` and `models` only. A ✅ on an absent artifact is worse than a 📋 on a present one: it invites a reader to depend on something that was never built.

## Non-functional requirements

### NFR-PLN-001 — Plan ID is unguessable ✅
`plan-<uuid hex>` — 12-char hex from uuid4. Approval URLs embed
the plan_id; an attacker who knows the URL scheme but not the
plan_id cannot guess it.

### NFR-PLN-002 — Approvals are single-use ✅
The fleet setting `confirm_password_hash` is checked on each
approval; the approval URL token is consumed once. Re-approving a
completed or in-flight plan fails.

### NFR-PLN-003 — Bounded fleet concurrency ✅
When a plan targets multiple devices, the engine respects the
fleet semaphore (`ADMZ_SNAPSHOT_FLEET_CONCURRENCY`, default in
`admz/snapshot/engine.py`). Phase 3D, validated by
[test_fleet_concurrency.py](../../../tests/test_fleet_concurrency.py).

### FR-PLN-013 — A plan approval authorises an envelope 📋
An approval covers a **device set + risk ceiling + operation set**, not a fixed
list of steps. Execution inside it needs no further approval; any step outside
stops the plan and re-gates. An envelope may only ever **narrow** — a replan may
drop devices, drop operations or lower risk, never widen. See
[ADR-0062](../decisions/0062-approve-an-envelope-not-a-step-list.md).

This is what makes replanning compatible with the up-front approval FR-PLN-005
already implements. The security property of plan-then-execute is control-flow
integrity — untrusted content cannot hijack the sequence — and a plan that
changes after approval destroys it. Narrow-only restores it: the operator knows
the true blast radius is at most what they saw.

The approval widget presents the envelope **as an envelope**. Showing a step
list that then changes is a lie even when the envelope holds.

### NFR-PLN-004 — The record shows what was approved AND what ran 📋
One `confirm.approve` row covering a plan is no longer sufficient once the plan
can change. Every replan is audited with what changed and why: a plan that
rewrote itself four times inside its envelope is compliant and worth seeing.

## Known limitations

### KL-PLN-001 — `condition:` is parsed but not yet evaluated ⚠️
`PlanStep.condition` is reserved for "skip if X" semantics
(e.g. `condition: "previous_step.result.has_ntp == false"`). The
field is in the model and round-trips through the plan store, but
the engine doesn't evaluate it yet — steps always run when their
dependencies complete.

### KL-PLN-002 — Rollback only works for catalogued ops ⚠️
Hybrid raw-HTTP calls (ADR-0013) flow through the executor but
have no `rollback` spec. A plan that mixes catalogued and raw
steps can roll back the catalogued ones; the raw ones are
irreversible. The plan creator should mark raw steps as
`dangerous` to surface this.

### KL-PLN-003 — Multi-device snapshots fan out unbounded outside the semaphore ⚠️
The pre-execution snapshot loop uses the same fleet concurrency
semaphore as `snapshot_fleet`, but per-step execution within an
approved plan does not — a plan with 50 simultaneous writes to
50 devices will issue 50 concurrent HTTPS calls. Tradeoff with
total wall time; a per-plan concurrency cap is planned.

### KL-PLN-004 — Approval URL is in-process state ⚠️
The one-time-token store for approval URLs is in-memory. A server
restart between create_plan and approval invalidates the URL —
operators have to re-create the plan. Persistence is planned.

## References

- ADRs: [0005](../decisions/0005-two-gate-plan-approval.md), [0006](../decisions/0006-multi-level-confirmation.md), [0012](../decisions/0012-snapshot-on-plans.md)
- Cross-cutting: [security.md](security.md), [reliability.md](reliability.md)
- Sibling: [catalog.md](catalog.md), [executor.md](executor.md), [snapshot-restore.md](snapshot-restore.md)
- Code: `admz/plans/`
