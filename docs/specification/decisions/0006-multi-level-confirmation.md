# ADR-0006: Multi-level confirmation by risk class

**Status:** Accepted, **fully implemented** across MCP, REST, and plans (2026-06-08).
**Date:** Original design 2026-04; recorded as ADR 2026-05-18.

> **Update 2026-06-08 (shared gated core).** The policy is now enforced
> identically on every surface. Previously only the MCP `execute_operation`
> consulted `get_confirmation_level`; the REST `POST /catalog/execute` hardcoded
> a dangerous-only check (running service-affecting ops **inline, ungated**) and
> plans used a separate boolean. All three now delegate to one module,
> `admz/operations.py` (the shared package ADR-0008 anticipated):
> `execute_gated_operation` (single ops), `execute_gated_plan` (plans), and
> `consume_confirmation` / `execute_approved_session` (token consumption). A
> parity test asserts MCP and REST return byte-identical blocked envelopes for
> the same op+risk+config. Also closed: a latent gap where `url_only` /
> `url_and_password` approvals (the default for `dangerous`) completed the token
> at `/confirm/{token}` but **never executed** the operation — the web-form and
> in-chat approval paths now run the held op/plan on approval.

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
| service-affecting  | `url_only`                |
| normal             | `none`                    |
| read-only          | `none`                    |
| action             | `url_only`                |
| read               | `none`                    |

`action` and `read` are the ACS Pro (and other server-target family)
risk vocabulary — see ADR-0034. `action` mutates live server state, so
it gates like `service-affecting`.

> **Update 2026-06-09.** `service-affecting` now defaults to `url_only` (was
> `llm_confirm`). Both device-affecting classes therefore require a
> deterministic, human-only widget approval by default — the LLM cannot
> self-approve a `url_*` gate. Operators who want lower-friction in-chat
> confirmation can opt a risk class back into `llm_confirm` per fleet.

The mapping is per-fleet, not per-operation — operators tighten or
loosen by risk class, not by clicking through every operation.

The keys controlling this (`confirm_level_*`, `confirm_password_hash`)
are protected by
[`is_protected_setting`](../../../admz/fleet_settings.py): the MCP
`set_fleet_setting` tool refuses to write them. Only the
`/confirm-settings` web UI can change them — see ADR-0020 for why.
The risk → level table itself lives in
[`admz/confirm_policy.py`](../../../admz/confirm_policy.py), a leaf
module, so `fleet_settings` can derive the protected key names from it
without an import cycle (GH #152).

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
