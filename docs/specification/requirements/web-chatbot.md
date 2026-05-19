# Requirements: web-based chatbot

> **Status:** 📋 Planned. None of this is built. See
> [ADR-0024](../decisions/0024-bundled-web-chatbot.md) for the rationale.

A first-party web chat interface for users who don't operate their
own MCP client. Co-equal entry point to the MCP server, sharing every
safety gate and tool implementation.

## Functional requirements

### FR-CB-001 — Bundled chat UI in the FastAPI web app 📋
A `/chat` page renders a chat interface (message list + input).
Streaming responses use Server-Sent Events from the FastAPI process.
The page is served from the same FastAPI app that exposes everything
else; no separate frontend build is required, though one is allowed.

### FR-CB-002 — Server-side LLM bridge 📋
ADMZ talks to the configured LLM provider over HTTPS from the server.
The browser never sees provider API keys, tool schemas, or raw model
output. The browser-server protocol is a thin streaming
display/input channel; all logic lives in `admz/chatbot/`.

### FR-CB-003 — Tool dispatch goes through the same code paths as MCP 📋
No duplicate "REST handler" + "MCP handler" + "chatbot handler" for
the same tool. Tool implementations are extracted into shared
functions in (TBD: `admz/tools/`) that the MCP server, REST routes,
and chatbot all call. The MCP and REST surfaces continue to exist
unchanged; the chatbot just adds a third caller.

### FR-CB-004 — Inline approval cards for dangerous operations 📋
When the LLM proposes a `dangerous`-risk operation or executes a
plan containing one, the chat renders an approval card (not plain
text) showing the operation, the device(s), the
`danger_description`, and [Approve] / [Deny] buttons. Approval
consumes a `ConfirmStore` token the same way the existing
`/confirm/{token}` POST does. Denial discards the token and posts a
denial back into the conversation.

### FR-CB-005 — Inline capture cards for credential entry 📋
`capture_credentials(...)` returns a capture URL that the chat
renders as a capture card (modal or in-pane form) rather than a
bare link. Password entry goes directly into the registry; the
password never appears in the chat transcript.

### FR-CB-006 — Identity continuity 📋
The chatbot session authenticates the user via the same backends as
the REST API (Windows IWA or API key). Every tool call invoked by
the chatbot's LLM runs as the authenticated user's principal —
`audit_log.requester` carries their name, `auth_source` carries
their method. `details_json` includes `{"via_chatbot": true}` so
ops can distinguish surfaces.

### FR-CB-007 — Provider abstraction 📋
A new `LlmProvider` ABC supports Anthropic, OpenAI, Azure OpenAI,
and Ollama (or any subset of those, behind feature flags). Selection
via `ADMZ_CHATBOT_LLM_PROVIDER` env or fleet setting; provider keys
via env (`ADMZ_CHATBOT_*_API_KEY`) or protected fleet setting.

### FR-CB-008 — Tool subset configurable 📋
A new fleet setting (`chatbot_tool_allowlist` or
`chatbot_tool_denylist`) controls which tools the chatbot's LLM
sees. Default is a sane safety-conscious subset (e.g. excludes
`get_credentials`, `create_temp_credentials`, `set_fleet_setting`).
Tools not in the effective allowlist are simply absent from the
LLM's tool catalog at session start.

### FR-CB-009 — Disabled by default 📋
With no LLM provider configured, the `/chat` page renders a clear
"not configured" message. The MCP and REST surfaces are entirely
unaffected; no background LLM connections attempted; no
configuration files probed.

### FR-CB-010 — Connection-test endpoint 📋
`POST /api/chatbot/test-provider` makes a minimal round-trip to the
configured LLM provider and returns success/failure with diagnostic
detail. Lets operators verify configuration before exposing the
chat to real users.

## Non-functional requirements

### NFR-CB-001 — No provider key in client-side code 📋
Provider API keys never leave the FastAPI process. The browser-side
JavaScript talks only to ADMZ; ADMZ talks to the LLM provider on
the browser's behalf.

### NFR-CB-002 — Tool execution time is bounded 📋
Long-running tools (snapshot_fleet on 1000 devices, firmware
download) report progress via the streaming channel rather than
hanging the LLM's tool-call response. May require a background-job
model for the longest operations.

### NFR-CB-003 — Cost telemetry visible to operators 📋
Each chat response shows an approximate token count or rough
cost-of-completion footer so operators understand the bill they're
generating. Per-user budgets are a v2 concern.

### NFR-CB-004 — Safety gates apply uniformly 📋
The chatbot does not have any privilege the MCP server doesn't have.
Same `dangerous`-risk blocking, same `get_credentials` opt-in,
same protected-fleet-keys list, same audit log. The set of allowed
tools is independently configurable per FR-CB-008, but the safety
gates within each tool are non-negotiable.

## Known constraints

### KL-CB-001 — Streaming needs SSE or WebSockets 🚧
The current FastAPI app does not use either. The chatbot adds the
dependency.

### KL-CB-002 — Conversation memory is single-session for v1 🚧
A page refresh starts a new conversation. Persistent threading
across reloads is a v2 concern.

### KL-CB-003 — Provider rate limits aren't centrally managed 🚧
Each provider has its own rate-limit story; v1 surfaces provider
errors back to the user but doesn't smooth them with retries.

## References

- ADR-0024: [Bundled web chatbot](../decisions/0024-bundled-web-chatbot.md)
- Persona: [Web-Chatbot User](../personas/web-chatbot-user.md)
- User stories: [Chatbot-driven workflows](../user-stories/chatbot-driven-workflows.md)
- Sibling: [Authentication](authentication.md) (the chatbot reuses
  the auth machinery, doesn't add a third auth path)
- Sibling: [MCP server](mcp-server.md) (the chatbot is a sibling
  entry point, not a replacement)
