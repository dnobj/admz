# User stories: chatbot-driven workflows

> **Status:** ✅ Live. These stories describe the experience the bundled
> web chatbot delivers. It ships as a Gemini-powered chat client driving a
> manual tool-calling loop over the MCP surface — see
> [ADR-0024](../decisions/0024-bundled-web-chatbot.md),
> [ADR-0025](../decisions/0025-gemini-chatbot-mcp-native.md), and
> [requirements/web-chatbot.md](../requirements/web-chatbot.md).

The Web-Chatbot User persona drives ADMZ entirely through a built-in
chat interface, without ever installing Claude Code or any other MCP
client. Same safety model, same tool surface, different UX.

## US-CB-001 — Conversational baseline snapshot

**As an** Experience Center operator preparing for an Acme customer
visit tomorrow, **I want to** open the ADMZ web app, type "snapshot
the lobby cameras and tag it pre-acme-visit," and have it just work.

**Acceptance criteria:**
1. The web UI's `/chat` page accepts a typed message.
2. The LLM bridge calls `snapshot_fleet(tag_filter="lobby")` followed
   by `git tag pre-acme-visit-2026-06-01 HEAD` (or equivalent).
3. The assistant's reply is rendered as a streaming message in the
   chat — operator sees the work happening, not a frozen "thinking"
   spinner.
4. The reply includes the commit SHA and the per-device success/fail
   counts.
5. The operator's identity (Windows IWA or API key principal) appears
   as the `requester` in every audit-log entry.

## US-CB-002 — Inline approval card for dangerous operations

**As an** operator chatting with the bundled assistant, **I want to**
approve or deny destructive operations *in the chat itself*, not by
opening a separate browser tab.

**Acceptance criteria:**
1. When the LLM proposes a `dangerous`-risk operation (e.g.
   `factorydefault.cgi:factory-reset`), the next chat message renders
   an **approval card** instead of plain text. The card shows:
   - The operation name and human-readable description
   - The device(s) affected
   - The `danger_description` from the catalog
   - [Approve] and [Deny] buttons
2. Clicking [Approve] consumes the underlying `confirm_token` (same
   single-use SQLite `ConfirmStore` machinery as the existing
   `/confirm/{token}` flow), executes the operation, and posts the
   result as the next chat message.
3. Clicking [Deny] discards the token and posts a denial back to the
   LLM so it can respond appropriately (e.g. "Understood; I won't
   proceed.").
4. The approval card does NOT bypass the two-gate model — both the
   semantic gate (the card itself) and the mechanical gate (the
   catalog risk check + token verify) still apply.
5. Tokens expire normally (5 minutes); an expired card renders as
   "expired" and the operator can ask the LLM to re-propose.

## US-CB-003 — Plan-level approval card

**As an** operator running a multi-step restore, **I want to** see
the whole plan in chat, scan the dangerous steps, and approve once.

**Acceptance criteria:**
1. When the LLM creates a plan containing any `dangerous` step, the
   plan summary renders as an approval card listing every step, with
   dangerous ones highlighted.
2. One [Approve] click executes the plan with `confirm_dangerous=True`
   (the plan-level gate from Phase 2D).
3. Per-step progress streams back into the chat as the plan runs.
4. Failures show the offending step and the error inline; the
   `on_failure` policy from the plan summary is respected.

## US-CB-004 — OOB credential capture from chat

**As an** operator onboarding a new camera, **I want to** tell the
assistant "add camera-lobby-04 with credentials" and have it walk me
through capturing the password without that password ever appearing
in the chat.

**Acceptance criteria:**
1. The LLM calls `capture_credentials(...)` → gets back the
   `/capture/{token}` URL.
2. The assistant's message renders a **capture card** instead of a
   bare URL — clicking it opens the capture form *in a modal or new
   pane within the same web app*, not a separate site/tab if
   possible.
3. The operator submits the password in the form. The credential
   goes directly into the registry; the password never appears in
   the chat.
4. The LLM polls `check_capture_status(token)`, sees "completed,"
   and posts a confirmation back to the chat (e.g. "Credentials for
   camera-lobby-04 stored").

## US-CB-005 — LLM provider chosen by operator, not hard-coded

**As an** operator (or admin), **I want to** point the chatbot at the
LLM provider my organization uses (Anthropic, OpenAI, Azure OpenAI,
local Ollama, etc.) **without** modifying ADMZ source.

**Acceptance criteria:**
1. A new fleet setting `chatbot_llm_provider` selects the backend
   (default: a marker like `disabled` so the chatbot is opt-in).
2. Provider API keys live in env vars or in the protected-keys subset
   of fleet settings (so MCP can't read or change them).
3. Switching providers doesn't require schema migration or restart of
   non-chat ADMZ components — only the chatbot session is rebuilt.
4. Each provider has its own connection-test endpoint
   (`POST /api/chatbot/test-provider`) so operators can verify
   configuration before exposing the chat to users.

## US-CB-006 — Tool subset configurable

**As a** security-conscious operator, **I want to** expose fewer tools
to the chatbot than ADMZ exposes to MCP power users.

**Acceptance criteria:**
1. A fleet setting (`chatbot_tool_allowlist` or
   `chatbot_tool_denylist`) controls which tools the chatbot's LLM
   sees in its tool catalog.
2. Default is a sane subset — likely `*` minus
   `get_credentials`, `create_temp_credentials`,
   `cleanup_temp_credentials`, `set_fleet_setting` — but operators
   can tighten or loosen as needed.
3. Tools not in the allowlist are simply not present in the LLM's
   tool catalog; the LLM never sees them as options.

## US-CB-007 — Identity continuity into audit log

**As a** security-conscious operator, **I want every** chatbot tool
call attributed to the underlying user identity in the audit log,
**not** to some generic "chatbot" pseudo-user.

**Acceptance criteria:**
1. When the chatbot's LLM bridge invokes a tool, the call is made
   *as the user* who started the chat session — same principal that
   IIS/Windows IWA or the user's API key established.
2. `audit_log.requester` carries that principal's name; `auth_source`
   reflects how the user authenticated (`windows` or `api-key`).
3. The audit details include something like `via_chatbot: true` so
   ops can distinguish chatbot traffic from direct MCP/REST traffic.

## US-CB-008 — Graceful degradation when chatbot is disabled

**As an** operator who hasn't configured an LLM provider, **I want**
ADMZ to work normally — REST + MCP + web UI — without the chatbot
in the way.

**Acceptance criteria:**
1. With `chatbot_llm_provider="disabled"` (the default), the `/chat`
   page either doesn't render or shows a clear "chatbot not
   configured; ask your admin" message linking to the deployment
   doc.
2. The MCP server and REST API are entirely unaffected.
3. No background LLM connections are attempted.

## Known constraints (when this lands)

- 🚧 **Streaming.** The current FastAPI app doesn't use Server-Sent
  Events or WebSockets. The chatbot will probably need SSE for
  token-streaming. Adds a dependency or two.
- 🚧 **Conversation memory.** v1 is one-shot conversations only — no
  persistent threading across page refresh. Memory is a v2 concern.
- 🚧 **Cost visibility.** LLM costs accrue per request. v1 shows a
  rough token-count footer; per-user budgets are a future concern.
- ⚠️ **Provider key handling.** Provider API keys are powerful (they
  bill to the operator's account). Same threat-model considerations
  as the Fernet key and Vault tokens. Joint-backup story extends.
