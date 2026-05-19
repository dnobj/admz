# Persona: Web-Chatbot User

> **Status:** 📋 Planned. The persona is real; the bundled chatbot
> client this persona uses is **not yet built**. Tracked as a future
> workstream — see [ADR-0024](../decisions/0024-bundled-web-chatbot.md)
> and [requirements/web-chatbot.md](../requirements/web-chatbot.md).

## Profile

**Who:** An operator who wants to drive ADMZ conversationally but
**doesn't already have an MCP-capable agent** running. Typical example:
an Axis Experience Center staff member who knows their device fleet
but isn't going to spin up Claude Code or write a custom Anthropic
SDK client. They just want to open a browser tab, type "snapshot the
lobby cameras before the Acme visit," and have it happen.

This persona is expected to be the **majority of ADMZ users** over
time — the population of "people who'd use an LLM if it were already
there" is much larger than the population of "people running their
own agent."

**Technical level:** Familiar with their device fleet and the
workflows around it; comfortable with browser-based tools. Doesn't
necessarily know what MCP is, doesn't run their own LLM client, may
not have any AI-coding tools installed at all.

**Scale:** Same as the other operator personas — 10–1,000 devices
per fleet, one ADMZ instance. The persona doesn't change scale.

**Frequency of use:** Daily during demo prep / customer visits /
configuration changes; weekly otherwise.

## Goals

- **Talk to ADMZ in natural language** without choosing between Claude
  Code, ChatGPT, a custom CLI, or a sea of REST tabs.
- **See approval prompts inline in the chat**, not as separate browser
  tabs. When the assistant says "I want to factory-reset
  camera-lobby-01," the *next message in the chat* is an approval card
  with [Approve] and [Deny] buttons — no clicking a separate
  `/confirm/{token}` URL.
- **Have the assistant act as the same user they are**. Whatever
  identity their Windows session has (or whatever API key the chatbot
  is authenticated under), every operation should be attributed back
  to them in the audit log.
- **Have it work without configuring a separate LLM provider** unless
  they want to. The operator who installs ADMZ should also be the
  operator who plugs in the LLM API key; both UI panels live in the
  same web app.
- **Have the chatbot be optional.** Power users with their own MCP
  client should not be forced through the bundled chatbot. The MCP
  server remains a co-equal entry point.

## Use cases (planned)

All of these are the same workflows the LLM-Agent persona drives via
MCP, but rendered through the bundled chat UI:

- **Pre-visit baseline:** "Snapshot all lobby cameras and tag it
  `pre-acme-visit-2026-06-01`."
- **Demo prep:** "Set up camera-conference-01 with stream profile
  'demo-mode' and bitrate 8 Mbps."
- **Post-visit restore:** "Restore the lobby cameras to the
  `pre-acme-visit-2026-06-01` tag." → Approval card for the plan
  shows the destructive steps inline; one click confirms.
- **Diagnostics:** "What's drifted on the lobby cameras since
  yesterday?" → Tool call → drift report rendered as a table in chat.
- **Onboarding:** "Discover new Axis devices on the network and tell
  me what you found." → Scan + tabulated results.

## What ADMZ owes this persona

- **A first-party chat UI bundled with the web app.** Left-side message
  list, streaming responses from the configured LLM, right-side input
  with a "send" button.
- **An LLM bridge running server-side.** ADMZ talks to the LLM
  provider; the browser talks to ADMZ. Provider API keys never reach
  the browser; ADMZ tool execution never reaches the LLM provider as
  arbitrary code.
- **Inline approval cards** for dangerous operations. The same
  `confirm_store` machinery from the MCP and REST paths, but rendered
  in-conversation instead of via a separate URL.
- **Identity continuity.** The chatbot inherits the user's Windows
  IWA session (or API key) — every tool call is attributed to that
  principal in the audit log.
- **The same safety gates** as MCP and REST: two-gate model,
  `dangerous`-risk blocking, get_credentials opt-in, etc. The chatbot
  doesn't get more privilege than any other client.
- **An LLM provider abstraction.** Anthropic, OpenAI, Azure OpenAI,
  local Ollama — operator chooses via env / fleet setting.
- **Tool-subset configurability.** Operators may want to expose fewer
  tools to the chatbot than to MCP (e.g. hide firmware upgrades from
  the chat interface even when allowed via MCP).

## What ADMZ does NOT owe this persona

- **Multi-conversation history with cross-session memory** — out of
  scope for v1. Each chat session is independent; the conversation
  doesn't have to survive a page refresh.
- **Chat-only access for power users.** People with their own MCP
  client keep using it. The chatbot is additive, not replacement.
- **A custom LLM hosted in-process.** ADMZ calls an external provider;
  it does not ship its own model weights.

## Constraints (for ADMZ developers when this lands)

- **Server-side conversation loop.** The browser must not see tool
  schemas or provider API keys. The LLM bridge stays in the FastAPI
  process.
- **Tool execution goes through the same code paths as MCP.** No
  duplicate "REST handler" plus "MCP handler" plus "chatbot handler"
  for the same tool. Extract the tool implementations into shared
  functions that all three surfaces call.
- **Approval cards reuse the `confirm_store` and the same token
  lifecycle.** The card's [Approve] button does the same thing the
  current `/confirm/{token}` POST does, plus pushes the result back
  into the chat conversation.
- **Auth identity flows through.** The chatbot session inherits the
  user's authentication; the LLM is just a tool the user is operating,
  not a separate principal.

## Anti-personas

- **Not the LLM-Agent persona.** That persona is software (an external
  agent). This persona is a human using a chat UI.
- **Not the Experience-Center-Operator** strictly — though there's
  substantial overlap. An Experience Center operator might be a power
  user with their own Claude Code instance (in which case they're
  primarily LLM-Agent-driven) OR they might be the typical persona
  with no separate agent (in which case they're primarily Web-Chatbot
  driven). The chatbot path is the larger of the two cohorts.
- **Not the Enterprise-Fleet-Operator** for routine work. Enterprise
  ops more often use REST/API-key for automation. The chatbot is
  available to them but isn't their primary surface.
