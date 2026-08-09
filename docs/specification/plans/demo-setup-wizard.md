# Plan: Demo setup wizard — activation pushes, rule↔demo correlation, guided setup (ADR-0047 slice 3+)

Status: **implemented** — the decision record is
[ADR-0050](../decisions/0050-demo-setup-wizard.md) (Accepted 2026-07-18), shipped in
PR #118. This header was added by #206: the file previously opened straight into
Context, so a reader had no cue whether the work had landed — unlike every plan in
`docs/plans/`, which all carry one.

## Context

The operator's goal: *"a demo would automatically make any necessary configuration changes, prompt
user to accept them (baseline or demo-bound), create rules, select watched events that correlate to
that demo."* Today those are four disconnected manual flows, and the 2026-07-18 console session
showed the chat model dropping parts of exactly this sequence. Operator decisions (2026-07-18):
**all three phases** (as three independently-landable PRs), **event ingest prompted + gated, never
auto**.

Exploration verified (against `feat/rule-grounding` working tree):
- ADR-0047 slice 3 already prescribes the push mechanism: synthetic DriftFields (expected =
  fragment value) → `RestoreBuilder.build_targeted_revert_plan` ([restore.py:155](../../../admz/snapshot/restore.py))
  → one gated plan (the `scenarios.py` concat pattern) — no new device-touch path.
- **"Activation state transitions on plan COMPLETION"** is mandated but unmechanized — and the same
  gap is the live marker-before-approval bug (`scenarios.py:57/:125` set `active_scenario` before
  `execute_gated_plan`; chip task_7f8c285b).
- Plan steps are catalog-ops-only with no inter-step data flow; but action executors are arbitrary
  async Python behind one approval, and `plan_summary_json` round-trips through
  `_register_plan_from_session` ([operations.py:448](../../../admz/operations.py)) — a JSON completion payload
  crosses the MCP-subprocess→web-process boundary for free.
- **A rule's condition topic is published by the device independent of the rule** (AOA scenario, VMD
  ProfileANY, IO/Port) — it IS the "watched event that correlates to the demo". Signals are free-form
  `{label, topic|category, device_id|role}` dicts matched by substring against the event store.
- `validate_assignment` ([fragments.py:143](../../../admz/demos/fragments.py)) already accepts
  `mode="require"` for non-writable facets; only the MCP schema hardcodes `mode:"set"`.
- Ingest is one global fleet flag, toggled only where `ctx.event_supervisor` lives (web process) —
  which is exactly where approved action sessions execute.

## The completion hook (shared foundation)

**Declarative `on_complete` payload on the plan, dispatched at the tail of `PlanEngine.run_plan`**
(the single choke point for all four execution paths; a Python callback can't cross processes, a
JSON blob riding `plan_summary_json` can).

- `admz/plans/models.py`: `ExecutionPlan.on_complete: Optional[Dict] = None` (`{"handler": name, ...args}`)
  + `completion_note: str`. `to_summary()` includes `on_complete` only when set (existing summaries
  stay byte-identical); `to_results()` includes `completion_note` when non-empty (flows to chat/REST/
  confirm automatically).
- **New `admz/plans/completion.py`** (~80 lines): handler registry (name → lazily-imported fn, avoids
  import cycles), `run_completion(plan, registry)` — NEVER raises; unknown handler / handler exception
  → log + note. Runs on both COMPLETED and FAILED; the handler decides (per-handler partial-failure
  semantics).
- `engine.py`: `create_plan(..., on_complete=None)`; `run_plan` tail calls `run_completion`.
- `operations.py`: `_register_plan_from_session` gains `on_complete=summary.get("on_complete")` —
  that one line is the whole cross-process story.

Handlers:
- `demo_activation` — flip `demo.active=True` only on COMPLETED (re-run `overlap_conflicts` first
  via `get_context()`, degrade to flip-without-recheck if ctx unavailable). On FAILED: stay inactive;
  half-pushed keys read as `candidate` drift (self-describing); re-run converges. Audit rows.
- `demo_deactivation` — flip `active=False` only on COMPLETED; on FAILED keys read `demo_broken`
  (revert repairs) — honest both directions.
- `scenario_markers` — `{markers: {device_id: name|null}}`; set/clear per device whose steps ALL
  succeeded (walk `plan.results`). **This is the task_7f8c285b fix.**

## Phase A — fragment activation pushes (PR 1)

**New `admz/demos/activation.py`** (~200 lines):
- `synthesize_push_fields(git, demo, device_id, facets_by_name)` → from
  `fragments._set_map_for`, build `DriftField(facet, path, expected=<fragment value>, actual="")`.
  **Prefilter**: skip op-revertable / `revert_param`-None keys with a warning (the builder's
  baseline-doc branch would push BASE values — guard 3 should make this empty, but don't trust it).
- `prepare_fragment_demo_core(ctx, demo, principal)`: resolve devices; 409 on legacy-scenario hold +
  `overlap_conflicts`; per device synthesize → `build_targeted_revert_plan` → concat steps (already
  service-affecting → url-gated); zero steps → `{"already_matches": True}` steering to `adopt_demo`
  (never silently activate); one plan with `on_complete={"handler":"demo_activation", demo_id, demo_name}`
  → `execute_gated_plan` → envelope + applied/skipped/warnings.
- `end_fragment_demo_core` (deactivate-with-restore): fresh `check_drift` per device → rows
  `owner == demo.id`; `demo_set` rows push `expected` (holds base), `demo_broken` rows push new
  `base_value`; nothing to push → plain `deactivate_demo_core`. Plan with `demo_deactivation` handler.
- `admz/snapshot/models.py`: `DriftField.base_value: Optional[str] = None`, set at the
  `demo_set`/`demo_broken` construction sites in [drift.py:185-201](../../../admz/snapshot/drift.py)
  (`base_val` already in scope).
- `admz/demos/actions.py`: `prepare_demo_core`/`end_demo_core` three-way routing — legacy scenario
  branch unchanged; fragments non-empty → the new cores; else current error reworded toward capture.
- `admz/snapshot/scenarios.py`: delete in-loop `set_active_scenario`; pass
  `on_complete={"handler":"scenario_markers", markers}` (keep the direct-set on the "already matches,
  no plan" early return). Demos-page copy: "activating…" during the pending window.
- MCP: no new tools; update `prepare_demo`/`end_demo` descriptions.

## Phase B — rule↔demo correlation (PR 2)

- `admz/demos/store.py`: `rules_json` column (try-ALTER pattern); `Demo.rules: List[Dict]` entries
  `{device_id, rule_id, rule_name, condition_id, condition_topic, created_at}`. **System-managed —
  NOT in `DEMO_FIELDS`** (device-assigned rule_ids rot as require-fragments; membership is a
  read-time join instead).
- `admz/demos/actions.py`: `attach_rule_to_demo(...)` — membership entry + auto-signal
  `{"label": rule_name, "topic": condition_topic, "device_id": device_id}` (deduped on
  (topic, device_id); normalize the topic through `events/normalize.py` if live verify shows the
  stored event type diverges from the raw tns form) + implicit device bind + audit.
  `detach_rule_from_demo(...)` reverse-scan on delete.
- `admz/mcp/tools/rules.py` + `server.py::_create_action_rule`: optional `demo` (name-or-id) param —
  resolve early (fail fast), carry `demo_id`/`demo_name` in the action payload, extend the card reason.
- `admz/operations.py`: `_action_create_action_rule` success → `attach_rule_to_demo` (try/except —
  bookkeeping failure never falsifies rule creation); `_action_delete_action_rule` → detach.
- `assign_demo_fragment` MCP schema gains `mode` enum `["set","require"]` (core already supports it) —
  the operator's demo-bound disposition for rule/API-facet drift once a snapshot has observed it.

## Phase C — guided setup surface (PR 3)

- **New `admz/demos/wizard.py`**: `setup_status(ctx, demo)` — deterministic checklist, cache/DB reads
  only: devices/roles; fragments + active + per-device verdicts (reuse `demo_view`); rules
  present/missing/unknown (join `demo.rules` vs latest observed `action_rules` facet via
  `git.read_facet`); signals + last-seen (`service.signal_activity`); ingest state
  (`events.config.event_ingest_enabled()` + tag-scope warning + any-rows evidence for the demo's
  devices); **`next_actions`** — ordered strings naming exact remaining tool calls.
- **Two new MCP tools (67 → 69)**: `demo_setup_status` (read-only, after `end_demo` in demos.py);
  `set_event_ingest` (GATED: action session `set_event_ingest` → new executor
  `_action_set_event_ingest` — flips the fleet flag + starts/stops+reconciles `ctx.event_supervisor`
  in the web process, mirroring `POST /api/events/control`). **Prompted, never auto** (user decision).
- No watched-event MCP CRUD (signals cover the demo-scoped need; watched events stay console
  bookmarks).
- `system_prompt.py` `# Demos` gains "Setting a demo up end-to-end": create_demo → capture
  (`check_drift` → `assign_demo_fragment`, baseline-vs-demo-bound is the user's call) → rules
  (`create_action_rule` with `demo=`) → activation (`prepare_demo` / `adopt_demo` when already live)
  → ingest offered via `set_event_ingest` when off → `demo_setup_status` verify + checklist report;
  hooks the existing compound-intent rule (gated stages count when their card is presented; continue
  on approval notes).
- Docs: **ADR-0050** (wizard + completion hook), tool-count bumps, MCP reference entries.

  Two corrections from #206. This line said **ADR-0048**, which is the events
  watch-scoping decision shipped the same day — ADR-0050's own header records the
  collision and the renumbering, but this plan was never updated to match. It also cited
  **US-DW-013**, which belongs to the ADR-0051 *inference* story ("ADMZ already knows my
  demos"); `demo-workflows.md` ends at US-DW-013, so **no user story was ever written for
  the wizard.** The citation is dropped rather than repointed, because the honest state is
  a gap, not a different id.

## Tests (per phase; all fixtures rebind confirm_store/audit singletons per test_rule_tools.py:23-43)

- `tests/test_plan_completion.py` (new): dispatch on COMPLETED/FAILED; unknown handler → note, no
  raise; summary round-trip via `_register_plan_from_session`; `completion_note` in results.
- `tests/test_demo_activation.py` (new): synthesize (values + prefilter warning); guards; **active
  flips only after approval+run** (session → `complete_session` → `execute_approved_session`);
  partial failure → inactive + note; end-with-restore pushes base/`base_value`.
- `tests/test_scenarios.py`: task_7f8c285b regression — markers unset until completion; per-device on
  partial success.
- `tests/test_rule_tools.py`: `demo` param in payload+reason; attach on success / detach on delete;
  attach failure doesn't fail the rule.
- `tests/test_mcp_demos.py`: `demo_setup_status` shape + `next_actions` order; `mode="require"`.
- `tests/test_mcp_tool_order.py` (+ the acs_pro import of it): append the 2 new tools same-commit.
- Full suite green per phase.

## Live verification (deployed on 4242; speaker announcement demo + C1710/I8016; dev auto-approver)

1. (A) "prepare the speaker announcement demo" → card shows per-key push plan → **`demo.active`
   still False while pending** → approve → active flips, keys read `demo_set`, roster in-sync.
2. (A) "end the demo" → approve → base pushed, inactive, keys gone from drift.
3. (A) Partial failure (stale cred on one device) → approve → demo stays inactive, note names the
   device, pushed keys read `candidate`; re-run converges.
4. (B) "create a rule on the C1710: play the announcement on PIR, for the speaker demo" → approve →
   `get_demo` shows membership + PIR-topic signal.
5. (C) "is the speaker demo set up?" → checklist; ingest off → model OFFERS `set_event_ingest` card →
   approve → trip the PIR → status shows signal `seen: true` (validates topic-string alignment).
6. Chat continues remaining wizard parts after each approval note (compound-intent behavior).

## Out of scope (staged later, per ADR-0047)

Readiness v2 software/manual checks (slice 4); scenario→fragment migration (slice 5); swap/rebind
(slice 6); fragment templating; ordered signal sequences (ADR-0041 L4); per-device ingest scoping;
heterogeneous plan steps.

## Risks

- Op-revertable set-keys would push baseline objects — closed by the synthesize prefilter; verify
  against real facet adapters during implementation.
- `demo_broken` restore needs `base_value` from a FRESH check (planned path always re-checks).
- Completion handlers needing `get_context()` degrade gracefully outside the web process (only
  reachable if an operator relaxes ADR-0034 gating).
- Crash mid-run loses the hook for that run → markers stay unflipped (safe direction; re-run
  converges). Not new.

## Critical files

New: `admz/plans/completion.py`, `admz/demos/activation.py`, `admz/demos/wizard.py`,
`tests/test_plan_completion.py`, `tests/test_demo_activation.py`.
Edit: `admz/plans/models.py`, `admz/plans/engine.py`, `admz/operations.py`,
`admz/snapshot/models.py`, `admz/snapshot/drift.py`, `admz/snapshot/scenarios.py`,
`admz/demos/actions.py`, `admz/demos/store.py`, `admz/mcp/tools/{rules,demos,fleet}.py`,
`admz/mcp/server.py`, `admz/mcp/dispatch.py`, `admz/chatbot/system_prompt.py`, docs.
Reuse, don't reimplement: `build_targeted_revert_plan` + facet `revert_param`,
`fragments._set_map_for`/`overlap_conflicts`, `execute_gated_plan` + `_register_plan_from_session`,
action-session machinery, `service.signal_activity`, `events/config.py` + supervisor.
