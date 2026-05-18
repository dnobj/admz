# User stories: LLM-driven configuration

The central workflow ADMZ exists for: an LLM agent makes device-configuration changes on the user's behalf, through the MCP surface, with two independent safety gates that the LLM cannot bypass.

## US-LLM-001 — Catalog-in-the-loop change

**As an** operator chatting with an LLM agent, **I want to** say "set the resolution on `camera-lobby-01` to 1080p" and have it work **without** the LLM needing the full VAPIX reference in context.

**Acceptance criteria:**
1. The LLM calls `query_catalog(device_id="camera-lobby-01", intent="change resolution")`.
2. The MCP server returns filtered operation specs (matching the intent), parameter group docs, and merged knowledge hints.
3. The LLM picks a specific operation (e.g. `param.cgi:update`) and parameters from the returned set.
4. The LLM calls `execute_operation(device_id, operation_id, params)`.
5. ADMZ builds the HTTP request from the YAML spec, authenticates with stored credentials, executes, parses the response, and returns a `StepResult`.
6. The LLM relays success/failure to the operator.

**Related requirements:** [catalog](../requirements/catalog.md), [executor](../requirements/executor.md), [mcp-server](../requirements/mcp-server.md).

## US-LLM-002 — Block a dangerous operation

**As a** security-conscious operator, **I want** dangerous operations (factory reset, firmware change, certificate delete) to be blocked **even when** the LLM agent has been instructed (or tricked) into running them.

**Acceptance criteria:**
1. When `execute_operation` is invoked with an operation whose `risk_level: dangerous`, the call returns `{blocked: true, confirm_token, confirm_tool: "confirm_dangerous_operation", reason, message}` without executing.
2. The confirm token is single-use, 256 bits of entropy, and TTL 5 minutes.
3. The token is stored in the shared SQLite `ConfirmStore` (not in an MCP-process-local dict), so it survives MCP restarts and can be confirmed from either MCP or REST.
4. `confirm_dangerous_operation(confirm_token)` executes the previously-blocked operation, marks the session `completed`, and returns the result.
5. The same token cannot be used twice — the second attempt sees `effective_status != PENDING` and is rejected.
6. The mechanical gate is independent of the LLM's reasoning — there is no LLM-side path that bypasses the catalog's risk-level check.

**Related requirements:** [mcp-server](../requirements/mcp-server.md), [security](../requirements/security.md).

**Related decisions:** [0005 — two-gate plan approval](../decisions/0005-two-gate-plan-approval.md), [0006 — multi-level confirmation](../decisions/0006-multi-level-confirmation.md).

## US-LLM-003 — Block a dangerous step inside a plan

**As a** security-conscious operator, **I want** plans containing dangerous steps to be blocked at execute time, **so that** routing a destructive operation through a plan doesn't bypass the gate.

**Acceptance criteria:**
1. `create_plan(description, steps, on_failure)` accepts plans with steps of any risk level — the gate is at execute time, not plan creation.
2. The plan summary returned by `create_plan` includes a `dangerous_steps` array listing each dangerous step's `step_number`, `operation_id`, and `device_id`.
3. `execute_plan(plan_id)` returns `{blocked: true, reason: "plan_contains_dangerous_steps", error, retry_with: {confirm_dangerous: true}}` when any step is dangerous.
4. `execute_plan(plan_id, confirm_dangerous=True)` proceeds. The MCP tool schema documents that the LLM must obtain explicit user consent before passing this flag.

**Related requirements:** [plans](../requirements/plans.md), [security](../requirements/security.md).

**Related decisions:** [0005 — two-gate plan approval](../decisions/0005-two-gate-plan-approval.md).

## US-LLM-004 — Pre-check API support before building a plan

**As an** LLM agent **with** a request like "rotate the certificate on `camera-lobby-01`", **I want to** verify the device supports the certificate-management API **before** building a plan, **so that** the user doesn't get a plan that's guaranteed to fail at step N.

**Acceptance criteria:**
1. The LLM calls `check_api_support(device_id, api_id="cert")`.
2. The MCP server looks up the device's model + firmware in `catalog/capabilities/models/<model>.yaml`.
3. The response includes `supported: true|false`, `api_version` (if known), and `notes` explaining why if unsupported.
4. With no `api_id` argument, the tool returns the device's full supported-API snapshot.
5. The same flow gracefully handles devices with no capabilities file: returns `supported: None` and a note pointing at how to populate one.

**Related requirements:** [knowledge-and-capabilities](../requirements/knowledge-and-capabilities.md).

## US-LLM-005 — Multi-step plan with rollback intent

**As an** operator, **I want to** review and approve a multi-step plan once **so that** the LLM can run it autonomously across multiple devices, with a rollback path if something fails.

**Acceptance criteria:**
1. `create_plan(description, steps, on_failure)` validates: operations exist in the catalog, devices exist in the registry, dependencies reference earlier step numbers only.
2. The returned plan summary includes `risk_summary` (counts per risk level) and `step_count`.
3. The plan is in `PENDING_APPROVAL` status. Until `execute_plan` is called, nothing runs.
4. For steps where the catalog operation has a `rollback` spec, the engine pre-reads the current state so it can revert if needed. (Currently only `param.cgi:update` is fully supported — see Known limitations.)
5. After execution, `plan.rollback_steps` lists generated revert operations. `rollback_available` flag indicates whether any captured pre-read exists.
6. Plans on different devices with no cross-device dependencies run in parallel (fleet mode).

**Related requirements:** [plans](../requirements/plans.md).

## US-LLM-006 — Temp credentials for delegated work

**As an** LLM agent **with** a complex task (e.g. multi-step diagnostic), **I want** short-lived device credentials **so that** I can interact with the device directly without persisting state in the registry.

**Acceptance criteria:**
1. `create_temp_credentials(device_id, permissions, ttl_seconds)` calls `pwdgrp.cgi:add-user` on the device with an `at_<8 hex>` username and a 16-char random password.
2. The temp credential is returned in the response (this is the one place plaintext is intentional — the whole point is the LLM uses these creds directly).
3. Max 3 temp creds per device; TTL clamped to 60–3600s.
4. A background loop removes expired temp creds via `pwdgrp.cgi:remove-user`. On server shutdown, all active temp creds are cleaned up.
5. `cleanup_temp_credentials(device_id, username)` removes a specific temp cred immediately.

**Related requirements:** [credential-storage](../requirements/credential-storage.md), [mcp-server](../requirements/mcp-server.md).

## Known limitations (as of 2026-05)

- ⚠️ **Per-step risk gate (not just plan-level).** The plan-level gate (US-LLM-003) catches dangerous steps. But if the catalog later adds finer-grained `service-affecting` gating, the plan engine would need additional wiring.
- 🚧 **Rollback breadth.** Pre-read for rollback is currently implemented for `param.cgi:update` only. Other write operations (REST POSTs, SOAP, multipart uploads) capture no rollback data. Tracked as Phase 3 deferred item.
- 🚧 **`FailurePolicy.CONTINUE` semantics.** Declared in the enum and accepted by `create_plan`'s `on_failure` arg, but if a step fails the engine continues regardless. `SKIP_DEPENDENTS` works correctly via `_dependencies_met` short-circuiting. Tracked as Phase 3 deferred.
- 📋 **No automated rollback execution.** The engine *generates* rollback steps but never runs them. A future `rollback_plan(plan_id)` MCP tool would execute them.
