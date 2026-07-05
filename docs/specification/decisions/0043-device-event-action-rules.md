# ADR-0043 — Device event action rules from natural language

**Status:** Accepted (2026-07-04).
**Relates to:** ADR-0034 (uniform widget-gated destructive actions), ADR-0037
(unified tasks — deferred device work), the axis-api-atlas rule-builder pillar
(`Atlas.build_rule`), the credential-capture flow (onboarding).

## Context

Users want to describe device automation in chat — *"play the ding-dong clip
when input port 2 activates on the C1710"*, *"flash the LED green when input 1
activates"* — and have ADMZ create the rule on the device. This previously
failed: an event rule on Axis is a multi-call SOAP `action1` choreography
(`AddActionConfiguration` → parse ConfigurationID → `AddActionRule` → parse
RuleID; delete is the reverse), and the chatbot burned its whole tool-iteration
budget (`ADMZ_GEMINI_MAX_TOOL_ITERATIONS`, default 8) trying to hand-assemble it
in June. The per-device vocabulary (which topics, which action templates, the
exact device-accepted param values, StartEvent-vs-Conditions trigger shape) is
finicky and model-specific.

In parallel, axis-api-atlas grew a **rule-builder pillar**: `Atlas.build_rule(
model, condition_id, action_token, param_choices)` renders the two device-proven
SOAP bodies from a model's events survey, applying the verified `ui_to_soap`
value maps and picking the trigger shape — and declines (`available=False`) when
a model isn't surveyed or a pairing is invalid. All 7 fleet models are surveyed.

## Decision

**ADMZ orchestrates; the atlas composes.** ADMZ never builds SOAP or re-derives
device quirks — it selects a `(condition_id, action_token, param_choices)`
triple, calls `Atlas.build_rule`, and runs the returned bodies through the
existing self-healing VAPIX executor behind the standard approval gate.

1. **A high-level tool surface** (3 new MCP tools, 53 → 56):
   - `list_rule_capabilities(device_id)` — read-only discovery: the model's
     conditions + actions (from the survey) and the device's current rules.
   - `create_action_rule(device_id, condition_id, action_token, param_choices?,
     rule_name?)` — validates via `build_rule` (fail-fast in chat if
     unbuildable), then returns the `url_only` approval card.
   - `delete_action_rule(device_id, rule_id)` — gated removal (rule + its
     linked config).
   Editing a rule = delete + create (SOAP `action1` has no in-place edit).

2. **A thin SOAP runner** (`admz/rules/runner.py`) reuses the catalog's
   `action-service` SOAP ops via `to_executor_dict()`, overriding only the
   rendered `body_xml`, so scheme/auth self-heal and the POST to
   `/vapix/services` come from the existing execution path. Auth comes from the
   registry device profile, not the op. Create cleans up the orphan
   configuration if the rule step fails.

3. **Gated, at execute time.** `create_action_rule`/`delete_action_rule` are
   ADR-0034 widget-gated actions (`operations._ACTION_EXECUTORS`). The confirm
   session holds only the rule **spec** (no rendered body, no secret); the
   executor re-renders via `build_rule` and runs the SOAP sequence only after
   approval. The action-executor dispatch is now await-aware (rule actions do
   async device I/O; prior actions stay synchronous).

4. **Secret-safe notifications.** Notification/`send_*` actions inline a
   recipient login + password into the config. To keep the secret out of the
   LLM conversation, `create_action_rule` returns a **capture** response
   (`/capture/rule/<token>`, keyed by the rule's confirm token) instead of the
   normal card. The user enters the recipient credentials on that form; they are
   held **only in web-process memory** (`admz/rules/capture.py`), never in chat,
   the confirm-session payload, the audit log, or any on-disk store. On approval
   the executor consumes the stash (single-use) and merges it into the rendered
   config; if it's missing, execution fails closed. The rule *spec* crosses the
   MCP-subprocess → web-process boundary through the ordinary `confirm_store`
   (SQLite) — the secret does not.

## Consequences

- Both flagship examples work end-to-end for credential-free actions (audio
  clip, LED, I/O, TCP notification), gated and audited, with console event
  notes on approval.
- Rules created via ADMZ show as drift vs the baseline (`ActionRulesFacet`) —
  expected; the user accepts or re-snapshots, like any chat-made change.
- **Unsurveyed models decline** with the atlas's reason, surfaced verbatim —
  ADMZ never guesses conditions/actions.
- v1 captures only the **primary** recipient login/password; secondary
  credentials (`proxy_*`, `pop_*`) are not collected (build_rule warns). The
  secret-capture path is unit-tested but was **not** live-verified against a
  real notification recipient in the shipping session.
- **Deferred (phase 2):** cross-device rules (source rule → notification →
  target `virtualinput/activate.cgi` → target rule) with a server-side scoped
  operator account, and standalone reusable REST recipient objects (whose bodies
  the atlas has not verified).
