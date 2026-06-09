# ADR-0008: Both MCP and REST API as first-class surfaces

**Status:** Accepted, in production.
**Date:** Original design 2026-02; recorded as ADR 2026-05-18.

> **Update 2026-06-08.** The "shared `admz/tools/` package" anticipated in the
> Consequences below (to remove cross-surface duplication) is realized as
> `admz/operations.py` — the single gated-execution core that the MCP server,
> the REST API, and the plan engine all delegate to for device operations +
> their confirmation gate. See ADR-0006's 2026-06-08 update.

## Context

ADMZ needs to be driven both by LLM agents (operating via the Model
Context Protocol) and by humans (browsers, scripts, integrations).
Three options for serving both:

1. **MCP only.** Humans drive the MCP server via Claude Code or a
   custom client. No browser UI, no REST.
2. **REST only.** Humans use the REST/web UI. LLMs call REST via
   adapters.
3. **Both, sharing implementation.** First-class MCP server AND
   first-class REST/web UI on top of a shared core.

## Decision

Option 3 — **both surfaces, equivalent functionality, shared core.**

- The MCP server (`admz/mcp/server.py`) exposes 41 tools mapped onto
  the catalog + registry + plans + snapshot engines.
- The FastAPI app (`admz/api/main.py`) exposes the same functionality
  via REST endpoints (`/api/devices`, `/api/catalog/execute`,
  `/api/plans`, `/api/snapshot/*`, etc.) plus a Jinja2 web UI for
  human-driven CRUD and the OOB confirm/capture forms.
- Both surfaces share the orchestration core via
  `admz/components.py::build_components()` — same registry, same
  catalog, same plan engine, same scheduler. **Exactly one** scheduler
  instance per process even when both surfaces are running.

The two surfaces are **co-equal**, not primary/secondary. Anything an
LLM can do via MCP, a human can do via REST. Anything the web UI shows
(e.g. `/confirm-settings`), the LLM has no equivalent tool for —
intentionally, per ADR-0020.

## Consequences

**Positive:**
- Humans without an MCP client are first-class users.
- LLM agents (Claude Code, custom Anthropic SDK clients, etc.) drive
  ADMZ directly via MCP — no REST proxy layer.
- Shared core means no logic drift between surfaces. Phase 2E unified
  the confirm-token store so a token issued via one is usable via the
  other.
- The bundled web chatbot (ADR-0024, planned) becomes a **third**
  surface on the same core, not a parallel reimplementation.

**Negative:**
- Two surfaces means two places where new operations need to be
  exposed. The chatbot's planned extraction of tool implementations
  into a shared `admz/tools/` package addresses this; today some
  duplication exists.
- Documentation has to cover both. The README maps tools and REST
  paths; spec docs cover the requirements for each.
- Auth must be solved for both. Phase 4 added Windows IWA + API keys
  for the REST/web surface; MCP runs over stdio in the user's trust
  zone and doesn't need protocol-level auth.

## References

- ADR-0024 — bundled web chatbot (third surface, same core)
- Requirements: [mcp-server.md](../requirements/mcp-server.md), [web-api.md](../requirements/web-api.md), [web-ui.md](../requirements/web-ui.md)
- Code: `admz/components.py`, `admz/mcp/server.py`, `admz/api/main.py`
