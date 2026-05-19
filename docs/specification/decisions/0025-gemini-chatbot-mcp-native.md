# ADR-0025: Gemini 3.1 as the chatbot LLM, native MCP integration

**Status:** Accepted, in progress.
**Date:** 2026-05-18.

## Context

[ADR-0024](0024-bundled-web-chatbot.md) committed to bundling a
web chatbot. The original framing left the LLM provider open
behind an `LlmProvider` ABC. With implementation now starting,
the provider choice is on the critical path: it determines the
SDK, the tool-use schema, the streaming protocol, and how the
chatbot integrates with the existing MCP server.

Three things shifted the choice toward Google Gemini:

1. **Gemini 3.1 line is GA (Feb–Mar 2026)** with three points on
   the cost/quality curve:
   - `gemini-3.1-pro` — $2 in / $12 out per 1M tokens, best tool-use
   - `gemini-3.1-flash` — fast tier
   - `gemini-3.1-flash-lite` — $0.25 / $1.50 per 1M, GA Mar 2026,
     1/8 the cost of Pro

2. **`google-genai >= 1.55` ships experimental native MCP
   support.** A local MCP server can be passed directly as the
   model's tool surface — no per-tool `FunctionDeclaration`
   re-translation. ADMZ already exposes 19 MCP tools via
   `admz mcp`; reusing that surface verbatim is a substantial
   simplification.

3. **The Interactions API** (new in `google-genai` 1.55) supports
   server-side conversation state via `previous_interaction_id`,
   so ADMZ doesn't have to store transcripts locally.

The cost of going Gemini-specific is coupling: a future need to
swap providers would require either porting the integration or
restoring the `LlmProvider` ABC. The benefit is shipping the
chatbot far sooner with much less translation code, and getting
the inline-approval UX (FR-CB-004) working over a streaming
protocol that's already battle-tested.

## Decision

The chatbot uses Google Gemini exclusively for the v1
implementation:

- **SDK:** `google-genai >= 1.55` (Interactions API + native MCP).
- **Default model:** `gemini-3.1-pro` (org-wide; configurable).
- **User-selectable models:** `gemini-3.1-pro`, `gemini-3.1-flash`,
  `gemini-3.1-flash-lite`. Stored as a per-user UI preference.
- **Tool surface:** the running ADMZ MCP server is passed
  directly to the Gemini Interactions API as a tool source. No
  hand-translation of the 19 tools into Gemini
  `FunctionDeclaration` objects. The browser → ADMZ chat route
  loops over Interactions API turns; tool calls bounce
  in-process into the existing MCP server.
- **Conversation memory:** `previous_interaction_id` stored in a
  small SQLite table keyed by principal. No message bodies stored
  locally. "Clear chat" deletes the row.
- **API key:** stored as a protected fleet setting
  (`gemini_api_key`, encrypted at rest with the existing Fernet
  store). Configured via a new admin page `/settings/chat`. Env
  var `ADMZ_GEMINI_API_KEY` bootstraps the setting on first run.
  Added to `PROTECTED_SETTING_KEYS` so MCP can't read or change
  it (per ADR-0020).
- **Streaming:** Server-Sent Events from FastAPI to the browser.
  Each Gemini chunk forwards to the browser; tool calls render
  inline as cards.
- **Nav:** `/chat` becomes the new home page; the previous home
  (`/devices`) keeps its URL but is no longer the landing page.

The `LlmProvider` ABC that ADR-0024 sketched is **not built for
v1**. If a second provider is needed later, the ABC can be added
then; over-engineering it now would slow down the milestone with
no concrete consumer.

## Consequences

**Positive:**
- No tool-wiring code. The MCP server's existing 19 tools are
  the chatbot's tool surface verbatim. New tools light up
  automatically in the chat once they're added to MCP.
- Audit log already covers MCP tool calls; chatbot-initiated
  calls inherit that for free with a `via_chatbot=true`
  annotation.
- Three price points let evaluators run on the free tier
  (Flash-Lite) and operators in production choose their own
  cost/quality balance. Pro is no longer on the free tier as of
  April 2026, so the model selector doubles as a "free or paid"
  toggle.
- Server-side conversation state means we don't store
  transcripts. Less data-handling surface, less GDPR exposure.

**Negative:**
- Coupling to a specific provider and a specific (experimental)
  SDK feature. Native MCP support is marked experimental in
  `google-genai`; the API may break before Phase 5C lands.
- Conversation history lives in Google's storage tied to the
  API key. Operators need to understand that — surfaced in
  the security requirements doc and the deployment guide.
- Cost is fully passed through Google. No batch-mode option for
  interactive chat (batch trades latency for 50% discount, which
  doesn't fit chat UX).

**Mitigations:**
- Fallback path on the roadmap: hand-translate the 19 MCP tools
  into Gemini `FunctionDeclaration` objects if the experimental
  MCP support degrades. Keeps the chatbot working without
  porting providers.
- Per-user "clear chat" + per-principal `previous_interaction_id`
  storage means an operator can flush their server-side state on
  demand.
- Token-budget per-user-per-day fleet setting (Phase 5D) caps
  worst-case bill.
- Graceful degradation if the bridge fails: the chat continues
  without tools and emits an inline notice, rather than 503-ing
  the whole turn. The user can still get help that doesn't
  require device access.

## Alternatives considered

1. **Anthropic Claude as v1 provider.** Mature MCP support
   (Anthropic created the protocol), strong tool-use. **Rejected
   for v1:** project owner asked for Gemini specifically. Worth
   revisiting if a second provider is added later.

2. **OpenAI GPT-4 / GPT-5.** Mature function-calling, large
   ecosystem. **Rejected for v1:** no native MCP support — would
   require hand-translating every tool into OpenAI
   `function` schema. Not aligned with the "reuse the MCP
   server verbatim" win.

3. **Build the `LlmProvider` ABC up front and support all three
   from day one.** **Rejected:** classic over-engineering. The
   tool-use schema, streaming protocol, and conversation-memory
   model differ enough across providers that the ABC would
   either leak provider details or constrain features. Pick one,
   ship, abstract later if there's a real second consumer.

4. **Hand-translate ADMZ tools into Gemini
   `FunctionDeclaration` objects.** **Rejected:** doubles the
   maintenance burden for every new MCP tool added. The native
   MCP path keeps the count at one.

## Open questions to revisit

- **When the experimental MCP feature stabilizes** (or breaks),
  reassess whether the fallback hand-translation path is needed
  permanently.
- **Whether to add Anthropic as a second provider** once the
  chatbot has shipped and we know what users actually want from
  it. The ABC question revisits at that point with concrete data.
- **Vision/multimodal in tool responses** — Gemini 3 supports
  images in `functionResponse`. Could surface device snapshots
  (jpg-image.cgi) as chat-rendered images. Out of scope for
  Phase 5A–D; revisit when there's a use case.

## References

- ADR-0024: [Bundled web chatbot](0024-bundled-web-chatbot.md)
  (parent decision; this ADR specifies the provider)
- ADR-0020: [Protected fleet settings](0020-protected-fleet-settings.md)
  (gemini_api_key joins the protected list)
- ADR-0021: [Windows IWA via reverse proxy](0021-windows-iwa-via-reverse-proxy.md)
  (the chatbot inherits the IWA principal)
- Requirements: [web-chatbot.md](../requirements/web-chatbot.md)
- Code (Phase 5A): `admz/chatbot/`, `admz/api/routes/chat.py`
