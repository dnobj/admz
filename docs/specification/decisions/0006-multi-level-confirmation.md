# ADR-0006: Multi-level confirmation by risk class

**Status:** Accepted, partially implemented (WIP), in production for `dangerous`.
**Date:** Original design 2026-04; recorded as ADR 2026-05-18.

## Context

ADR-0005 establishes the two-gate model: every write passes through
a semantic gate (LLM/user agreement) and a mechanical gate (catalog
risk-level check). For `dangerous`-risk operations, the mechanical
gate blocks until a confirm token is consumed.

But "confirm token" can mean different things:
- The LLM proposes, the user says "yes" in chat, the LLM calls
  `confirm_dangerous_operation(token)`.
- The user opens a browser URL, clicks [Confirm].
- The user opens a browser URL, clicks [Confirm], **and enters a
  password.**

These represent escalating levels of friction. We needed a
configurable mapping from operation risk → required confirmation
ceremony.

## Decision

Four confirmation levels, ordered from strictest to most permissive:

1. **`url_and_password`** — User opens the confirm URL in a browser
   AND enters a password (hashed via PBKDF2-SHA256, stored in fleet
   settings). The LLM cannot complete this remotely.
2. **`url_only`** — User opens the confirm URL and clicks [Confirm].
   No password.
3. **`llm_confirm`** — LLM calls `confirm_dangerous_operation(token)`
   in-tool, after presenting the change to the user in chat. Same
   trust model as today's plan engine.
4. **`none`** — No gate; operation runs immediately.

**Default mapping** (operator-overridable per fleet via fleet
settings `confirm_level_<risk>`):

| Risk level         | Default confirmation level |
|--------------------|---------------------------|
| dangerous          | `url_and_password`        |
| service-affecting  | `llm_confirm`             |
| normal             | `none`                    |
| read-only          | `none`                    |

The mapping is per-fleet, not per-operation — operators tighten or
loosen by risk class, not by clicking through every operation.

The keys controlling this (`confirm_level_*`, `confirm_password_hash`)
are in [`PROTECTED_SETTING_KEYS`](../../../admz/api/confirm_store.py):
the MCP `set_fleet_setting` tool refuses to write them. Only the
`/confirm-settings` web UI can change them — see ADR-0020 for why.

## Status

The `ConfirmStore` (SQLite-backed, multi-level) is implemented and
unified with MCP/REST via Phase 2E. `dangerous` operations route
through it. `service-affecting` operations are currently always
`llm_confirm` regardless of the fleet setting — the per-risk lookup
exists in `confirm_store.get_confirmation_level()` but the
`execute_operation` paths don't consult it yet for non-dangerous
risk levels. Closing this gap is a small Phase-4-stretch follow-up.

## Consequences

**Positive:**
- Operators with stricter security postures can require a password
  for every dangerous op without code changes.
- Lower-stakes operations don't suffer friction they don't need.
- The web confirmation UX is the same for all levels — UI just adds
  a password field when required.
- All four levels share one token lifecycle (`ConfirmStore`), one
  expiry policy (5 min default), one single-use guarantee.

**Negative:**
- Four levels is more than most products ship. Operators have to
  understand the matrix to configure it well.
- Password recovery is operator-driven (forget the password, lose
  the gate). No "magic restore" path.

## References

- ADR-0005 — two-gate plan approval (the framework this layers onto)
- ADR-0020 — protected fleet settings (why these keys can't be written from MCP)
- ADR-0009 — OOB credential capture (same URL pattern)
- Requirements: [security.md](../requirements/security.md) FR-SEC-001 / FR-SEC-002
- Code: `admz/api/confirm_store.py`, `admz/api/routes/confirm.py`, `admz/api/templates/confirm_*.html`
