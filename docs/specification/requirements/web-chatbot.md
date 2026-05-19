# Requirements: web-based chatbot

> **Status:** 🚧 In progress (Phase 5). Phase 5A scaffolding is
> implemented; streaming, inline approval cards, and budget
> controls land in later phases. See
> [ADR-0024](../decisions/0024-bundled-web-chatbot.md) for the
> bundle rationale and [ADR-0025](../decisions/0025-gemini-chatbot-mcp-native.md)
> for the Gemini + native-MCP choice.

A first-party web chat interface for users who don't operate
their own MCP client. Co-equal entry point to the MCP server,
sharing every safety gate and tool implementation by going
through the same in-process MCP server.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-CB-001 — Bundled chat UI in the FastAPI web app ✅
A `/chat` page renders a chat interface (message list + input).
Phase 5A added the page + a non-streaming `POST /chat` fallback.
Phase 5B added `POST /chat/stream` returning Server-Sent Events
and a small `chat.js` consumer that renders the stream
progressively, including tool-call cards. The non-streaming
path remains for clients without JavaScript.

The page is served from the same FastAPI app as everything else;
no separate frontend build required.

### FR-CB-002 — Server-side LLM bridge 🚧
ADMZ talks to Gemini over HTTPS from the server. The browser
never sees the Gemini API key, the tool schemas, or raw model
output. The browser-server protocol is a thin streaming display
channel; all logic lives in `admz/chatbot/`.

### FR-CB-003 — Native MCP tool surface (no re-translation) ✅
The chatbot passes the running ADMZ MCP server directly to the
`google-genai` SDK as a tool source. No hand-translation of the
19 MCP tools into Gemini `FunctionDeclaration` objects. New MCP
tools become available in chat the moment they land in
`mcp/server.py`. See
[ADR-0025](../decisions/0025-gemini-chatbot-mcp-native.md).

The bridge in `admz/chatbot/mcp_bridge.py` spawns
`python -m admz mcp` as a stdio subprocess on each turn (Phase
5B-MCP), performs the MCP handshake, and yields a `ClientSession`
into the SDK's `config.tools=[session]`. The subprocess is reaped
at end-of-turn. If the bridge fails (mcp not installed, spawn
error), the turn degrades gracefully: chat continues without tools
and an inline notice tells the user.

### FR-CB-004 — Inline approval cards for dangerous operations 📋
When the LLM proposes a `dangerous`-risk operation or executes
a plan containing one, the chat renders an approval card (not
plain text) showing the operation, the device(s), the
`danger_description`, and [Approve] / [Deny] buttons. Approval
consumes a `ConfirmStore` token the same way the existing
`/confirm/{token}` POST does. Phase 5C.

### FR-CB-005 — Inline capture cards for credential entry 📋
`capture_credentials(...)` returns a capture URL that the chat
renders as a capture card (modal or in-pane form) rather than a
bare link. Password entry goes directly into the registry; the
password never appears in the chat transcript. Phase 5C.

### FR-CB-006 — Identity continuity ✅
The chatbot session authenticates the user via the same backends
as the REST API (Windows IWA or API key). Every tool call invoked
through the chatbot runs as the authenticated user's principal —
`audit_log.requester` carries their name, `auth_source` carries
their method. `details_json` includes `{"via_chatbot": true}` so
ops can distinguish surfaces.

### FR-CB-007 — Gemini as the v1 LLM provider 🚧
v1 uses Google Gemini exclusively. The `LlmProvider` ABC that the
original ADR-0024 sketched is **not** built — that would slow
shipping with no concrete second consumer. If a second provider
is needed later, it lands as a separate ADR + extraction. See
[ADR-0025](../decisions/0025-gemini-chatbot-mcp-native.md).

### FR-CB-008 — Per-user model selection 🚧
The chat UI exposes a model selector:
- `gemini-3.1-pro` (default; $2 in / $12 out per 1M tokens)
- `gemini-3.1-flash` (fast tier)
- `gemini-3.1-flash-lite` (cheapest; $0.25 / $1.50 per 1M)

Selection persists per principal via a UI cookie. The org-wide
default is configurable in `/settings/chat`.

### FR-CB-009 — Disabled by default ✅
With no Gemini API key configured (neither
`ADMZ_GEMINI_API_KEY` env nor `gemini_api_key` fleet setting),
the `/chat` page renders a clear "not configured — ask your
administrator to set up the chatbot" message. The MCP and REST
surfaces are entirely unaffected; no background LLM calls
attempted.

### FR-CB-010 — Connection-test endpoint 📋
`POST /api/chatbot/test-provider` makes a minimal round-trip to
Gemini and returns success/failure with diagnostic detail. Lets
operators verify configuration before exposing the chat to real
users. Phase 5A includes a basic version on the settings page.

### FR-CB-011 — Admin-configured API key via web UI ✅
The Gemini API key is a *protected fleet setting* (per ADR-0020,
joining the existing protected set). Configured via a new admin
page at `/settings/chat`, **never** via the MCP `set_fleet_setting`
tool. The page accepts password-masked input, stores the key
encrypted via the existing Fernet store, and displays a redacted
"configured" indicator once set.

The env var `ADMZ_GEMINI_API_KEY` is read once at startup; if
present, the value is seeded into the fleet setting on first run
to ease bootstrapping. After that, the fleet setting is the
authoritative source.

### FR-CB-012 — Server-side conversation memory via Gemini ✅
Phase 5A persists only `previous_interaction_id` per principal
in a `chat_sessions` SQLite table. Message bodies are stored in
Gemini's server-side conversation store; ADMZ doesn't keep
transcripts locally. "Clear chat" deletes the principal's row,
which makes the next turn start a fresh server-side interaction.

### FR-CB-013 — Chat is the new home page ✅
`GET /` redirects to `/chat`. The previous home (`/devices`)
keeps its URL; users can still navigate to it directly or from
the nav bar. Top-level nav order: Chat, Devices, Search,
Add Device, Fleet Settings, Confirmation Settings, Chat Settings,
API Docs.

## Non-functional requirements

### NFR-CB-001 — Gemini API key never in client code ✅
The key never leaves the FastAPI process. The browser-side
JavaScript talks only to ADMZ; ADMZ talks to Gemini on the
browser's behalf. The key isn't returned by any REST endpoint —
the `/settings/chat` page shows only a redacted indicator.

### NFR-CB-002 — Tool execution time is bounded 📋
Long-running tools (snapshot_fleet on 1000 devices, firmware
download) report progress via the streaming channel rather than
hanging the LLM's tool-call response. Phase 5B / 5D.

### NFR-CB-003 — Cost telemetry visible to operators 📋
Each chat response shows an approximate token count footer so
operators understand the bill they're generating. Per-user
daily budgets are Phase 5D.

### NFR-CB-004 — Safety gates apply uniformly ✅
The chatbot has no privilege the MCP server doesn't. Same
`dangerous`-risk blocking, same `get_credentials` opt-in
toggle, same protected-fleet-keys list, same audit log. The
chatbot reuses the MCP server in-process, so by construction it
can't bypass anything.

### NFR-CB-005 — Conversation history isolation per principal ✅
The `chat_sessions` table is keyed by principal name. Two
operators in the same ADMZ instance never see each other's
conversations — at most, an admin can `DELETE FROM chat_sessions
WHERE principal=…` to forcibly reset someone's session, but they
can't read it.

## Known limitations

### KL-CB-001 — Native MCP support in google-genai is experimental ⚠️
The Gemini Interactions API's native-MCP feature is marked
experimental. If the API breaks, the fallback is hand-translating
the 19 MCP tools into Gemini `FunctionDeclaration` objects. The
fallback path isn't built yet — it's contingency.

### KL-CB-002 — Conversation history lives in Google's storage ⚠️
With `previous_interaction_id`-based memory, transcripts live in
Google's servers attached to the org's API key. Operators with
data-residency or confidentiality constraints need to know this.
The "Clear chat" button only releases ADMZ's pointer; whether
Google retains the transcript after that is governed by the
Google data-handling agreement, not ADMZ.

### KL-CB-003 — Streaming requires SSE, which is new for ADMZ ✅
Resolved in Phase 5B: `POST /chat/stream` is the first SSE
endpoint in the codebase. The wire format uses `event:` + `data:`
SSE lines; the browser-side consumer reads via `fetch()` +
`ReadableStream.getReader()` rather than `EventSource` (so that
POST + form-encoded args work without round-tripping through GET).
The non-streaming `POST /chat` remains for clients without JS.

### KL-CB-004 — Provider rate limits aren't centrally managed ⚠️
Gemini has its own rate-limit story; Phase 5A surfaces 429s back
to the user as-is. No retry-with-backoff yet. Production
deployments hitting limits will see chat hiccups; the per-user
daily budget (Phase 5D) is the primary lever.

### KL-CB-005 — Gemini Pro is not on Google's free tier ⚠️
As of April 2026, only Flash and Flash-Lite are free-tier-eligible.
Operators evaluating ADMZ on the free tier should default to
Flash-Lite via `ADMZ_GEMINI_DEFAULT_MODEL=gemini-3.1-flash-lite`.

### KL-CB-006 — Per-turn MCP subprocess overhead ⚠️
The MCP bridge spawns `python -m admz mcp` once per chat turn.
Python startup + ADMZ import + MCP handshake is ~1–2 s on first
contact (warmer on subsequent turns thanks to OS-level disk
caching). For interactive chat this is noticeable on every
message. A per-principal subprocess pool with idle timeout is the
intended future optimization — out of scope for Phase 5B-MCP.

Mitigation: hide the latency behind the streaming "start" event
that fires immediately, so the user sees activity even while the
subprocess warms up.

## References

- ADRs: [0024 — Bundled web chatbot](../decisions/0024-bundled-web-chatbot.md), [0025 — Gemini + native MCP](../decisions/0025-gemini-chatbot-mcp-native.md), [0020 — Protected fleet settings](../decisions/0020-protected-fleet-settings.md)
- Persona: [Web-Chatbot User](../personas/web-chatbot-user.md)
- User stories: [Chatbot-driven workflows](../user-stories/chatbot-driven-workflows.md)
- Cross-cutting: [authentication.md](authentication.md), [security.md](security.md)
- Sibling: [mcp-server.md](mcp-server.md) — the surface the chatbot reuses verbatim
- Code: `admz/chatbot/`, `admz/api/routes/chat.py`
