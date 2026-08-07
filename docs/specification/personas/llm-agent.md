# Persona: LLM Agent

## Profile

**Who:** An LLM driving ADMZ via its MCP server. Could be Claude (via Claude Code, Claude Desktop, or a custom Anthropic SDK client), GPT-driven agents, custom in-house agents, or any other MCP-compatible client.

**Technical level:** N/A — the agent is software. But the agent's *operator* (a human directing it) and the agent's *reasoning quality* are relevant: an LLM can hallucinate, get confused by ambiguous device states, and propose actions a human would never propose.

**Scale:** One LLM session at a time, interacting with the same fleet a human operator works with.

**Frequency of use:** Per session — could be many tool calls per minute during a single workflow.

## Goals (from the LLM's perspective)

- **Discover what operations are available** for a given device + intent, without needing the full VAPIX reference in its context window.
- **Get device metadata** (model, firmware, supported features) so it can pick the right operation for the device at hand.
- **Execute one operation at a time** for simple tasks; or build multi-step plans for complex tasks.
- **Receive structured success/failure** for every operation, with enough information to recover or escalate.
- **Be prevented from doing harm** — even when the LLM proposes something reckless, the system should block dangerous operations.
- **Be told when it's reached a confirmation boundary** and pass control back to the human cleanly.

## Goals (from the LLM's *operator's* perspective)

- **The LLM cannot bypass safety gates** by clever prompting, misreading, or hallucinating.
- **Credentials never enter the LLM's context** — the LLM should never see a plaintext password.
- **The LLM cannot loosen its own guardrails** by writing to its own configuration.
- **Audit trail of what the LLM did** — every operation it executed, every plan it ran.

## Use cases (links to user stories)

- [LLM-driven configuration](../user-stories/llm-driven-configuration.md) — the central workflow.
- [Network discovery](../user-stories/network-discovery.md) — the LLM scans, registers, provisions.
- [Snapshot and restore](../user-stories/snapshot-and-restore.md) — LLM-initiated snapshot before risky changes.
- [Credential management](../user-stories/credential-management.md) — LLM initiates capture but never sees credentials.
- [Firmware operations](../user-stories/firmware-operations.md) — LLM-built firmware upgrade plans.

## What ADMZ owes this persona

- **A catalog-in-the-loop interface.** `query_catalog(device_id, intent)` returns just the operations relevant to *this device and this intent*, so the LLM's context isn't drowned in 329 YAML files.
- **Structured tool inputs and outputs.** Every tool input is a typed JSON shape; every output is `{success, ...}` with a documented schema.
- **Risk-aware blocking.** Dangerous operations return `{blocked: true, confirm_token, confirm_tool: "..."}` so the LLM knows it cannot proceed without explicit human approval through a token round-trip.
- **No credentials in tool returns.** `get_credentials` is gated behind a fleet setting and disabled by default. `test_device_credentials`, `provision_device`, `create_temp_credentials` (the exception — temp creds *are* meant for the LLM to use), and `check_capture_status` all hide passwords by default.
- **Two-gate safety.** Even if the LLM's reasoning agrees with a user-approved plan, the catalog risk-level check is independent and mechanical.
- **Knowledge hints** alongside catalog returns: "this is a network switch, it doesn't speak VAPIX" surfaces *before* the LLM tries.
- **Idempotent reads.** `list_devices`, `get_device`, `search_devices`, `query_catalog`, `query_knowledge`, etc. always return current state.

## What ADMZ doesn't owe this persona

- **Full VAPIX reference.** The LLM is expected to use the catalog, not free-form VAPIX construction. If an operation isn't in the catalog, the system can't do it via MCP.
- **Approving its own dangerous operations.** Tokens are single-use and require the human to relay them back.
- **Reading its own audit log.** Audit data is for the human operator and may not be exposed to MCP.
- **Mutating its own safety configuration.** Protected fleet-setting keys (`confirm_level_*`, `confirm_password_hash`, `confirm_approver_groups` — since ADR-0053, everything outside the LLM-writable allow-set) cannot be set via MCP.

## Constraints (for ADMZ developers)

- **Don't add MCP tools that return credentials.** The OOB capture pattern is the right answer.
- **Don't add MCP tools that change confirmation policy.** The `/confirm-settings` web UI is the right answer.
- **Don't add MCP tools that bypass the catalog.** Free-form `vapix_call(host, cgi, params)` would defeat the whole architecture.
- **Don't return raw HTTP responses** when a parsed `StepResult` is available — the LLM doesn't need to parse VAPIX response shapes.
- **Do return structured error envelopes.** `{success: false, error: "...", error_class: "DeviceNotFoundError"}` so the LLM can branch programmatically.

## Anti-personas

- Not a human — but acts on a human's behalf. The human is the principal; the LLM is the tool.
- Not the catalog contributor — the LLM doesn't extend the catalog, it consumes it.
