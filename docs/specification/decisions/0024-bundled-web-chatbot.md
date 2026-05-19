# ADR-0024: Bundled web-based chatbot client

**Status:** 📋 Accepted (direction), deferred (implementation).
**Date:** 2026-05-18.

## Context

ADMZ is designed to be driven by LLM agents through the MCP server.
That's the right primary entry point for users who already operate an
MCP-capable client (Claude Code, custom Anthropic SDK clients, etc.).
But that user population is small. Most operators don't run an
agent — they have a browser and an opinion.

Conversation with the project owner (2026-05-18) crystallized two
things:

1. The Axis Experience Center use case the snapshot/restore work was
   built for is dominated by *non-developer* operators — demo staff,
   instructors, customer-success engineers. They want to type "make
   the lobby camera ready for the Acme demo" and have it happen.
2. The two-gate safety model the MCP path uses (semantic + mechanical
   confirm) is awkward when split across surfaces — the LLM does the
   semantic part in chat, then hands the user a `/confirm/{token}`
   URL to click in a separate browser tab. That's friction for the
   primary user persona.

A bundled chatbot client, integrated into the ADMZ web app, addresses
both: gives non-developer users a chat surface, and lets the approval
flow happen *inline* in the conversation rather than via a separate
URL click.

## Decision

ADMZ will ship a **first-party web chatbot client** as part of its
FastAPI app. The chatbot:

- Runs server-side (LLM bridge in `admz/chatbot/`), browser-side is
  display + input only.
- Talks to an operator-configured LLM provider (Anthropic, OpenAI,
  Azure OpenAI, Ollama — pluggable behind an `LlmProvider` ABC).
- Exposes a configurable subset of ADMZ tools to its LLM, defaulting
  to a safety-conscious allowlist that excludes the most sensitive
  ones (`get_credentials`, `set_fleet_setting`, etc.).
- Renders **inline approval cards** for dangerous operations and
  capture flows — same `ConfirmStore` machinery, no separate URL
  click.
- Authenticates the user via the same backends as the REST API
  (Windows IWA + API keys); every tool call is attributed to the
  user in the audit log.
- Is **opt-in via configuration** — disabled by default; ADMZ runs
  normally (MCP + REST + classic web UI) without any LLM provider
  configured.

The MCP server is **not** retired. It remains a co-equal entry point
for users with their own clients. The chatbot is additive.

## Status

**Accepted as a direction; deferred for implementation** until the
rest of the application is "otherwise complete" (per the project
owner). When implementation starts, this ADR will be updated with
the actual landing date and any course corrections.

## Alternatives considered

1. **MCP-only.** No bundled chatbot. Users either install Claude Code
   etc. or use the REST/web UI directly. **Rejected:** misses the
   majority of the target persona, leaves Experience Center operators
   (the principal customer) underserved.

2. **Light "command-line in a textbox" UI.** Operator types a tool
   name + JSON args, ADMZ executes it, no LLM in the loop. **Rejected:**
   useful for power users but doesn't unlock the "natural language"
   experience the persona wants, and most operators won't memorize the
   tool catalog.

3. **External agent registration.** Operator installs a separate
   chatbot product (someone else's) and points it at ADMZ's MCP server.
   **Rejected:** asks the user to install + operate + secure two
   things rather than one. Also forks the safety-gate UX across two
   apps that don't know about each other.

4. **Server-rendered LLM-augmented REST surface** (the chatbot lives in
   the existing web UI, no chat metaphor — every page has an
   "ask AI" sidebar). **Rejected:** the chat metaphor is the well-known
   pattern, and the inline-approval workflow needs the conversation
   substrate to work cleanly.

## Consequences

**Positive:**
- Brings the majority persona into the product surface.
- Approval workflows become a single coherent UX rather than splitting
  across LLM context + separate URL clicks.
- Audit log gets real human attribution for every chatbot-initiated
  action (Phase 4 auth already in place).
- The architecture forces an extraction of tool implementations from
  `mcp/server.py` into a shared `admz/tools/` package — improves
  testability and reduces the size of the MCP server file. This is a
  desirable refactor independent of the chatbot.

**Negative:**
- New deployment dependency: LLM provider API key + ongoing cost.
  Operators have to budget for it.
- New attack surface: provider API keys, conversation logs (which may
  contain device IDs / config snippets), browser-server streaming.
- Streaming requires SSE or WebSockets — currently the FastAPI app
  uses neither.
- Maintenance burden: provider SDKs evolve, model deprecations
  happen, the chat UI needs the typical web-app care.
- Coupling to LLM industry conventions (tool-use schema, streaming
  protocol) — when those change, ADMZ has to track.

**Mitigations:**
- Disabled by default. Operators who don't configure a provider get
  the same ADMZ they had before, no LLM-related code paths exercised.
- Tool-subset allowlist defaults to a safety-conscious set; operators
  who want more must opt in.
- Provider abstraction (`LlmProvider` ABC) limits coupling to any one
  vendor.
- Inline approval cards reuse the existing `ConfirmStore` — no new
  approval primitive to maintain.

## Open questions to revisit at implementation time

- **Conversation memory.** Single-session for v1, or persist threads
  across page refresh? Threads add a table and a UX, but make the
  chatbot meaningfully more useful.
- **Cost telemetry.** Token-count footer per response is the v1 plan,
  but per-user / per-fleet budgets are an obvious next step.
- **Provider preference for v1.** Anthropic first (it's where MCP
  came from, native tool-use support is mature), then OpenAI, then
  Ollama. Order may shift based on operator demand.
- **Browser-side tech.** Vanilla JS / HTMX / Alpine / a real SPA?
  The existing web UI is Jinja2 server-rendered. The chatbot is a
  natural place to introduce more client-side state — but introducing
  a JS toolchain has costs.

## References

- Persona: [Web-Chatbot User](../personas/web-chatbot-user.md)
- User stories: [Chatbot-driven workflows](../user-stories/chatbot-driven-workflows.md)
- Requirements: [web-chatbot.md](../requirements/web-chatbot.md)
- Foundation: [ADR-0008 — MCP and REST surfaces](0008-mcp-and-rest-surfaces.md)
  (still valid; chatbot is a third surface, not a replacement)
- Auth: [ADR-0021](0021-windows-iwa-via-reverse-proxy.md),
  [ADR-0022](0022-api-keys-for-agents.md) — chatbot inherits identity
  from these
