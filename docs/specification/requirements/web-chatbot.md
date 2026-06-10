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

### FR-CB-004 — Inline approval cards for dangerous operations ✅
When the LLM proposes a `dangerous`-risk operation or executes a
plan containing one, the chat renders an approval card (not plain
text) showing the operation, the device(s), the
`danger_description`, and [Approve] / [Dismiss] buttons.

Implementation (Phase 5C):
- A JSON twin of the existing form endpoint —
  `GET /api/chat/confirm/{token}` (session details) and
  `POST /api/chat/confirm/{token}` (approval submission) — backs
  the card. Same `ConfirmStore`, same per-token lockout, same
  rate limiter, same fleet-password gate. The HTML route
  (`/confirm/{token}`) is untouched, so out-of-band approval via
  a separate tab still works.
- The browser-side renderer detects `/confirm/{token}` URLs in
  the assistant's streamed text using a regex over the
  accumulated text buffer (chunk boundaries don't break it). Each
  unique token gets one card inserted after the assistant bubble.
- "Dismiss" closes the card without consuming the token —
  matches the semantics of closing the browser tab on the HTML
  flow.

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

### FR-CB-008 — Per-user model selection ✅
The chat UI exposes a model selector spanning the Gemini 2.5 and 3.x
lines (the authoritative list is `SELECTABLE_MODELS` in
`admz/chatbot/config.py`):
- `gemini-2.5-flash` — **default** (proven, cheap floor for chat-style turns)
- `gemini-2.5-pro`, `gemini-2.5-flash-lite`
- `gemini-3.1-pro-preview`, `gemini-3.5-flash`, `gemini-3.1-flash-lite`

The default is intentionally **not** the newest 3.x line — 2.5-flash is
cheaper and reliable for tool-calling turns; operators pick a 3.x model
explicitly or set `ADMZ_GEMINI_DEFAULT_MODEL`. Selection persists per
principal. (Pricing shifts with Google's tiers; see
`admz/chatbot/usage.py` `PRICING` for the values ADMZ bills against.)

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

### FR-CB-013 — JSON endpoint for programmatic testing ✅
`POST /api/chat` is the scriptable twin of `POST /chat/stream`:
accepts `{message, model?, use_tools?}` JSON, returns the full
turn result as JSON (`success`, `response`, `model`,
`input_tokens`, `output_tokens`, `cost_usd`, `interaction_id`,
`tool_calls`, `error`, `rejected_by_budget`). Same auth, budget
gate, audit log, and MCP tool surface as the SSE route — only
the wire format differs.

Curl example:
```
curl -X POST http://localhost:4242/api/chat \
     -H 'Content-Type: application/json' \
     -d '{"message": "list my devices"}'
```

Suitable for end-to-end smoke tests, scripted demos, or driving
the chatbot from automation. Internal: both the SSE and JSON
routes share a single `_run_chat_turn` helper so policy (budget,
audit, usage) stays in one place.

### FR-CB-014 — Chat is the new home page ✅
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
hanging the LLM's tool-call response. Deferred — the native MCP
path means tool execution latency is hidden inside the SDK loop.

### NFR-CB-003 — Cost telemetry visible to operators ✅
Each chat response footer shows token counts + model + an
approximate USD cost (Phase 5D). Pricing table embedded in
`admz/chatbot/usage.py` covers the three selectable Gemini 3.1
models (Pro / Flash / Flash-Lite). Per-principal per-day usage is
recorded in the `chat_token_usage` SQLite table; the Chat
Settings page surfaces both the configured budget and the user's
running total.

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

### NFR-CB-006 — Per-principal daily token budget ✅
A fleet-wide setting `chat_daily_token_budget` (added to
`PROTECTED_SETTING_KEYS` per ADR-0020 — MCP can't write it) caps
how many tokens any one principal may consume in a single UTC
day. Set to `0` (default) to disable enforcement. Over-budget
turns are rejected at the route layer *before* the SDK call,
with the rejection recorded in the audit log.

### NFR-CB-007 — Audit log records every chat turn ✅
After each turn (success or rejected by budget), the route emits
one audit entry with `via_chatbot=true`, the principal, the
model, the token counts, and the estimated USD cost. Failed
turns include the error message. Audit-log filters can
distinguish chatbot-initiated work from direct MCP / REST
calls via the flag.

## Known limitations

### KL-CB-001 — Native MCP support in google-genai is experimental ⚠️
The Gemini Interactions API's native-MCP feature is marked
experimental. If the API breaks, the fallback is hand-translating
the 19 MCP tools into Gemini `FunctionDeclaration` objects. The
fallback path isn't built yet — it's contingency.

**Specific observed regression** (May 2026, google-genai 2.5.0):
`gemini-3.5-flash` + MCP tools sometimes ends the stream after
the first tool call without making the AFC continuation request,
producing a "10 output tokens, empty text" turn. `gemini-2.5-flash`
doesn't have this issue. The empty-response backstop catches it
and surfaces a clear error pointing operators at 2.5-flash for
reliable tool use. Tracking upstream.

### KL-CB-002 — Conversation history lives in Google's storage ⚠️
With `previous_interaction_id`-based memory, transcripts live in
Google's servers attached to the org's API key. Operators with
data-residency or confidentiality constraints need to know this.
The "Clear chat" button only releases ADMZ's pointer; whether
Google retains the transcript after that is governed by the
Google data-handling agreement, not ADMZ.

ADMZ itself does **not** persist user messages or assistant
responses. The audit log records turn metadata (model, tokens,
cost, success/error) but never the message bodies. The one
exception is **DEBUG-level logging**: when the operator sets
`ADMZ_LOG_LEVEL=DEBUG`, the chat routes emit a per-turn
`[chat] user=… message=…` line before the call and a
`[chat] user=… response=…` line after. These go to whatever sink
the operator's logging configuration uses (stderr by default).
DEBUG is opt-in and noisy; it's the right knob for short-term
investigation, not production observability.

### KL-CB-003 — Streaming requires SSE, which is new for ADMZ ✅
Resolved in Phase 5B: `POST /chat/stream` is the first SSE
endpoint in the codebase. The wire format uses `event:` + `data:`
SSE lines; the browser-side consumer reads via `fetch()` +
`ReadableStream.getReader()` rather than `EventSource` (so that
POST + form-encoded args work without round-tripping through GET).
The non-streaming `POST /chat` remains for clients without JS.

### KL-CB-004 — Provider rate limits aren't centrally managed 🚧
Partial resolution: ADMZ now auto-retries 429 + 5xx responses
from Gemini with exponential backoff (defaults 3 attempts at
0.5s, 1.0s, 2.0s with ±25% jitter). Configurable via
`ADMZ_GEMINI_RETRY_MAX_ATTEMPTS` and `ADMZ_GEMINI_RETRY_BASE_DELAY`.

Retries only fire *before* any chunk has been forwarded to the
user — once text starts flowing we can't un-yield it, so a
mid-stream 503 still surfaces immediately. Read-only AFC tool
calls retry safely; write operations are gated behind the
/confirm flow so the actual operation isn't re-executed.

Still missing: cross-request rate-limit coordination, sustained
overload backpressure (currently a steady 503 hammer would just
make every turn slow). Per-user daily budget (Phase 5D) remains
the primary cost lever; retry is the latency-smoothing lever.

### KL-CB-005 — Gemini Pro is not on Google's free tier ⚠️
As of April 2026, only Flash and Flash-Lite are free-tier-eligible.
Operators evaluating ADMZ on the free tier should default to
Flash-Lite via `ADMZ_GEMINI_DEFAULT_MODEL=gemini-3.1-flash-lite`.

### KL-CB-007 — Approval card detection is URL-text based ⚠️
The inline approval card (FR-CB-004) is triggered by detecting a
`/confirm/{token}` URL in the streamed assistant text. This is
robust to typical LLM behavior — the MCP tool's response always
includes the URL and Gemini relays it — but it's not a structured
channel. If a future model variant omits the URL or rewrites the
token, the card won't render and the user falls back to the
out-of-band HTML form route (which still works).

A more robust path would be to wrap the MCP session and intercept
tool responses server-side, surfacing structured "approval needed"
events through the SSE stream. Deferred — would require changing
the FastMCP integration model, see ADR-0025 fallback note.

### KL-CB-006 — MCP subprocess pool with idle timeout ✅
Resolved in Phase 7. `admz/chatbot/mcp_pool.py` runs a
per-principal pool of MCP subprocesses. The first chat turn for
a principal pays the ~1–2 s spawn + handshake cost; subsequent
turns reuse the live subprocess.

Lifecycle:

- Pool entries are created on first acquire and held with an
  `AsyncExitStack` so the underlying `stdio_client` + `ClientSession`
  contexts stay open across turns.
- A background reaper task scans every minute and evicts entries
  idle past the configured timeout (default 300 s, override via
  `ADMZ_MCP_POOL_IDLE_SECONDS`).
- On FastAPI shutdown the pool is drained — every entry's
  `aclose()` runs so no MCP subprocess is orphaned.
- Same-principal concurrency is serialized on a per-entry lock
  (defensive against duplicate-tab scenarios; the UI already
  enforces sequential turns).

Falls back to the per-turn spawn path (Phase 5B-MCP) when the
`principal` argument is omitted — used by tests that don't want
pool semantics.

## References

- ADRs: [0024 — Bundled web chatbot](../decisions/0024-bundled-web-chatbot.md), [0025 — Gemini + native MCP](../decisions/0025-gemini-chatbot-mcp-native.md), [0020 — Protected fleet settings](../decisions/0020-protected-fleet-settings.md)
- Persona: [Web-Chatbot User](../personas/web-chatbot-user.md)
- User stories: [Chatbot-driven workflows](../user-stories/chatbot-driven-workflows.md)
- Cross-cutting: [authentication.md](authentication.md), [security.md](security.md)
- Sibling: [mcp-server.md](mcp-server.md) — the surface the chatbot reuses verbatim
- Code: `admz/chatbot/`, `admz/api/routes/chat.py`
