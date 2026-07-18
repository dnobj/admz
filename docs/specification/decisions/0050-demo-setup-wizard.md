# ADR-0050 — Demo setup wizard: activation pushes, rule↔demo correlation, guided setup

**Status:** Accepted (2026-07-18). Implements **ADR-0047 slice 3+** (demo config
fragments) as three landable phases on a shared foundation. Closes issue #114.
(Numbering note: the approved plan doc said "ADR-0048"; that number was taken by
the events watch-scoping ADR shipped the same day, so the wizard is ADR-0050.)

## Context

The operator's goal: *"a demo would automatically make any necessary
configuration changes, prompt the user to accept them (baseline or demo-bound),
create rules, select watched events that correlate to that demo."* Those were
four disconnected manual flows. This wires them into one guided sequence, every
device write still behind the approval widget (ADR-0034).

## Foundation — declarative plan-completion hook

State that must flip **only after a gated push actually runs** couldn't be
expressed: plan steps are catalog-ops with no post-run callback, and a Python
callback can't cross the MCP-subprocess → web-process boundary. So a plan carries
a JSON `on_complete = {handler, ...args}` payload, dispatched at the tail of
`PlanEngine.run_plan` (the single choke point for all execution paths) via a
never-raising registry (`admz/plans/completion.py`). Being JSON, it round-trips
through `plan_summary_json` (`_register_plan_from_session`). A handler failure is
recorded as the plan's `completion_note` (surfaced in `to_results`), never raised.
Handlers run on COMPLETED and FAILED and own their own partial-failure semantics.

## Phase A — fragment activation pushes

Preparing a fragment demo pushes its owned set-keys to its devices, and flips
`demo.active` only after the push completes. Rather than a new device-touch path,
`synthesize_push_fields` builds synthetic `DriftField`s whose `expected` is the
*fragment value*, and hands them to `build_targeted_revert_plan` — which writes
each field's `expected` via the facet's `revert_param`, so "revert" becomes
"push". v1 pushes only param-writable keys; op-revertable (API-backed) keys are
prefiltered with a warning (their whole-object revert would write BASE values).

`on_activation_complete` flips `active=True` only on COMPLETED (a partial push
leaves it inactive; half-pushed keys read as `candidate` drift and a re-run
converges) and re-checks overlap at completion. `end_fragment_demo_core` is the
mirror: a fresh `check_drift` yields the demo's owned rows, and base values are
pushed back (`DriftField.base_value` carries the baseline for `demo_broken` rows,
whose `expected` holds the demo value); `active` flips False on completion.

The **same hook fixes the pre-existing marker-before-approval bug**
(task_7f8c285b): `scenarios.py` set `active_scenario` in-loop at request time;
now it rides `on_complete={scenario_markers, markers}` and flips per device only
after that device's steps succeed. The direct-set is kept only on the no-plan
"already matches" branch.

## Phase B — rule ↔ demo correlation

`create_action_rule` gains an optional `demo=` (name-or-id, resolved early → fail
fast). On approved creation the rule's membership is recorded on the demo
(system-managed `rules_json`, a read-time list — device-assigned rule ids rot,
so they aren't a fragment) and its **condition topic becomes the demo's signal**:
the device publishes that topic independently of the rule, so it IS the
correlated watched event. Signals dedupe on (topic, device); the device is bound
implicitly. Deleting a rule reverse-scans and detaches (dropping the auto-signal
only when no remaining rule shares that topic). `assign_demo_fragment` exposes
`mode = set | require` for demo-binding non-writable drift.

## Phase C — guided setup surface

`demo_setup_status` (read-only, cache/DB/git only — no probe) returns a
deterministic checklist — devices/roles, fragments + active, rules (recorded vs
observed), signals + last-seen, ingest state — ending in ordered `next_actions`
that name the exact remaining tool calls. `set_event_ingest` (GATED) flips the
fleet capture flag + reconciles the WS supervisor — **prompted, never auto** (a
user decision). Tool count 67 → 69. The `# Demos` prompt gains a "Setting a demo
up end-to-end" sequence, hooked into the compound-intent rule.

## Consequences

- A demo can be set up end-to-end by conversation, each gated stage a card.
- Activation/scenario state is now truthful — it flips only after the push runs,
  and a crash/partial mid-run leaves the safe (unflipped) direction; re-run
  converges. Bookkeeping (markers, rule membership) never fails its device op.
- Event capture is never turned on silently.

## Out of scope (staged later per ADR-0047)

Readiness v2 software/manual checks (slice 4), scenario→fragment migration
(slice 5), swap/rebind (slice 6), fragment templating, ordered signal sequences
(ADR-0041 L4), per-device ingest scoping, heterogeneous plan steps.

## Rollout

Branch `feat/demo-setup-wizard` (worktree, off master). New `drift_reports`-style
`rules_json` column is created idempotently (try-ALTER); nothing else migrates.
Live verification on 4242 (speaker-announcement demo + C1710/I8016) is the
follow-up gate.
