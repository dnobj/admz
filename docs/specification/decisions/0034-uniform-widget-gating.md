# ADR-0034: One human gate — every destructive action goes through the link/widget approval

**Status:** Accepted, in production (2026-06-11).
**Date:** 2026-06-11.
**Relates to:** ADR-0005/0006 (confirmation gate), ADR-0031 (baselines),
ADR-0033 (windows-local auth). Supersedes the CR-4 / Task #41 flat-refusal
posture for destructive MCP tools.

## Context

ADMZ had two coexisting philosophies for "a human must approve this":

1. **The confirmation gate** (ADR-0005/0006): device writes return
   `blocked: true` + a `confirm_token`; the chat renders an approval card;
   the operation executes only when the human approves `/confirm/{token}`.
   This is how a *reboot* — service-affecting — is approved, and it works
   for any principal.
2. **The CR-4 flat refusal**: `delete_device`, `restore_device`,
   `execute_plan` (and later `accept_baseline`) returned `PermissionDenied`
   to anonymous principals outright, with no path through the widget. Born
   of a real incident (an anonymous-principal LLM deleted a real device
   during E2E dogfooding).

The asymmetry surfaced live: a user could approve a P3288 **reboot** via the
widget, but **restoring its baseline** — strictly more recoverable — was
impossible from chat. Worse, `snapshot_device` (deliberately ungated)
*re-baselines* a drifted device since ADR-0031, so the path that silently
redefines "correct" was open while the recovery path was blocked.

The user's ruling: **approval in all cases via the standard link/widget
gate, just like reboot** — with authentication (ADR-0033) making every
approver a named identity.

## Decision

The flat refusal is removed (`_DESTRUCTIVE_MCP_TOOLS` is now empty — the
mechanism is retained for future use). Every destructive tool takes the
widget path:

- **`restore_device`** — builds a plan only (no device writes). Unchanged.
- **`execute_plan`** — already gated: `operations.execute_gated_plan`
  blocks url_*-level plans with a confirm session (cross-process via
  `plan_steps_json`, C-1) and approval runs the plan. Removing the flat
  refusal simply lets callers reach that gate.
- **`accept_baseline` / `delete_device`** — these are *registry actions*,
  not catalog operations, so the per-op gate couldn't hold them. New
  **action sessions**: a nullable `action_json` column on
  `confirm_sessions` carries `{"action": ..., ...payload}`; the MCP handler
  validates the request, creates a **url_only** session via
  `operations.create_action_session` (always url_only — fleet-level
  overrides do not soften actions), and returns the standard blocked
  envelope. On approval, `operations.execute_approved_session` dispatches
  to a registered action executor (`_ACTION_EXECUTORS`) which performs the
  `set_config_pointers` / `remove_device` — through the same web-form and
  in-chat approval paths all other sessions use, with the same audit rows.
- **Validation stays immediate**: bad requests (unknown device, no
  observation to accept, commit without the device's config) error at call
  time; only *valid* requests reach the widget.
- **The snapshot loophole** is addressed at the prompt layer: the model
  must not `snapshot_device` a device with known drift unless the user has
  explicitly chosen to accept its current state (snapshot = re-baseline).
- **REST parity**: the authenticated REST endpoints
  (`/api/snapshot/restore`, `/api/snapshot/accept-baseline`,
  `DELETE /api/devices/{id}`, `/api/plans/{id}/execute`) keep
  `require_authenticated_principal` — deliberate API calls by an
  authenticated operator/agent remain direct; the widget unification
  targets the LLM/MCP surface where the model proposes actions.

## Consequences

**Positive:**
- One mental model: *anything* destructive produces the on-screen approval
  card — for every principal, on every surface the LLM drives. Nothing is
  "impossible from chat" anymore; nothing destructive is LLM-self-servable.
- The CR-4 incident class stays prevented — better, even: previously a
  *non*-anonymous LLM principal could delete devices without any human
  step; now the widget always interposes.
- The recoverable action (revert) is no longer harder than the silent one
  (snapshot-re-baseline), and the latter requires explicit user intent.

**Negative:**
- One more click for operators who used to delete devices via chat tools
  under an authenticated principal (previously direct).
- Action sessions add a third session kind (op / plan / action) to the
  confirm store; the approval executor list must grow with any new
  registry-level destructive action.

**Alternative considered:** keep the flat refusal and rely on ADR-0033
authentication alone. Rejected: it leaves destructive actions executing on
the LLM's say-so for authenticated users (no human approval step), and the
asymmetry with the reboot flow remains.

## References

- Code: `admz/operations.py` (`create_action_session`,
  `_ACTION_EXECUTORS`, `execute_approved_session`),
  `admz/api/confirm_store.py` (`action_json`, `is_action`),
  `admz/mcp/server.py` (`_accept_baseline`, `_delete_device`,
  `_DESTRUCTIVE_MCP_TOOLS`), `admz/chatbot/system_prompt.py`
- Tests: `tests/test_mcp_destructive_gate.py` (rewritten to pin the widget
  semantics)
- Requirements: [mcp-server.md](../requirements/mcp-server.md),
  [drift-detection.md](../requirements/drift-detection.md) FR-BAS-004
