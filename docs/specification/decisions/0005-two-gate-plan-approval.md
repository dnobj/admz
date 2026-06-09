# ADR-0005: Two-gate plan approval (semantic + mechanical)

**Status:** Accepted, implemented.
**Date:** Original design 2026-02 (`ARCHITECTURE.md`); plan-level gate added 2026-05-18 (Phase 2D).
**Supersedes:** none.

> **Update 2026-06-08 (shared gated core).** The plan-level mechanical gate is
> now the *same configurable per-risk policy* used for single ops, not a
> dangerous-only boolean. Plan execution computes the strictest confirmation
> level across its steps (`admz.operations.resolve_plan_confirmation`) and gates
> accordingly: `none` runs; `llm_confirm` runs when the caller passes
> `confirm_dangerous=True`; `url_only`/`url_and_password` require deterministic
> web/widget approval (a blocked envelope with a `confirm_url`) — a boolean is no
> longer sufficient for those. Under default config a `dangerous` step resolves
> to `url_and_password`, so a dangerous plan now requires web/widget approval
> (was: `confirm_dangerous=True` alone). This makes plans and single ops
> consistent and closes the "route a destructive op through a plan to get a
> weaker gate" hole. The gate lives in `admz/operations.py::execute_gated_plan`;
> `PlanEngine.run_plan` is the un-gated executor it calls.

## Context

ADMZ is designed to be driven by LLM agents. LLMs:
- Can hallucinate.
- Can be manipulated by prompt injection inside user data or device responses.
- Can mis-classify a destructive operation as safe ("just a config change").

A single approval gate — even a thoughtfully designed one — has a single point of failure. Either:
- A reasoning bug in the LLM bypasses the gate (the LLM convinces itself, then the user, then proceeds).
- A misconfiguration in the gate's metadata bypasses the LLM (an operation incorrectly marked safe slips through user review).

We needed a model where neither failure alone is sufficient to execute a destructive operation.

## Decision

Every operation that writes to a device passes through **two independent gates**:

1. **Semantic gate (LLM/user)** — The LLM presents the proposed change in natural language; the human approves or rejects. This is the soft gate — judgment-based, fallible, but operates with full context.
2. **Mechanical gate (catalog)** — The MCP server consults `catalog.get_risk_level(family, op_id)`. If the operation is `dangerous`, the execution is blocked and a `confirm_token` is returned. The user (or LLM acting on the user's behalf) must present the token via `confirm_dangerous_operation` to proceed.

Both gates apply at three call sites:
- `execute_operation` (single op via MCP)
- `/api/catalog/execute` (single op via REST)
- `execute_plan` (multi-step plan — added in Phase 2D)

For plans, the gate is plan-level: any plan containing a `dangerous` step requires `confirm_dangerous=True`. Routing a destructive operation through a plan does NOT bypass the gate (this was a known hole closed in Phase 2D).

## Consequences

**Positive:**
- A reasoning bug in the LLM cannot bypass the mechanical check. Even if the LLM "decides" to factory-reset, the catalog's `risk_level: dangerous` blocks it.
- A misconfigured catalog (an op incorrectly marked safe) cannot bypass user review either — the LLM still has to present the change for human approval first.
- The token roundtrip is auditable: confirmation sessions are stored in SQLite (`ConfirmStore`) and cross-surface (MCP token can be confirmed via REST and vice versa).
- The mechanism is uniform across MCP, REST, and plans, so a contributor adding a new entry point only needs to consult the catalog.

**Negative:**
- Friction for operators with high trust in their LLM workflow: every dangerous op is a two-call dance.
- The catalog must classify every operation correctly. An operation missing `risk_level: dangerous` for something destructive is a load-bearing CI concern.
- The token TTL (5 minutes) creates a small window where a token theoretically could be replayed by an attacker who observed it — mitigated by single-use enforcement (`UPDATE … WHERE status='pending'`) but not by encryption-in-transit.

**Alternatives considered:**
- **Single gate (just LLM/user approval).** Rejected: too fragile, every LLM bug or prompt injection becomes a vulnerability.
- **Single gate (just catalog risk check, auto-block dangerous).** Rejected: too rigid, no path for explicit operator override.
- **Three-or-more gates.** Considered: e.g. require a typed password for `dangerous`. Partially adopted via the `url_and_password` confirmation level (ADR-0006), but it's an optional escalation rather than a third mandatory gate.

## Implementation

- Catalog YAML: `risk_level: read-only | normal | service-affecting | dangerous`
- MCP: `mcp/server.py::_execute_operation` blocks dangerous ops; `_confirm_dangerous` consumes tokens
- REST: `api/routes/catalog.py::execute_operation` and `confirm_dangerous`
- Plans: `plans/engine.py::execute_plan(plan_id, confirm_dangerous=False)`; raises `PermissionError` for dangerous steps without consent (Phase 2D)
- Token storage: `api/confirm_store.py` (Phase 2E unified the two previously-separate in-memory dicts)

## References

- [Personas: security-conscious-operator](../personas/security-conscious-operator.md)
- [Requirements: security FR-SEC-001, FR-SEC-002, FR-SEC-003](../requirements/security.md)
- [User stories: US-LLM-002, US-LLM-003](../user-stories/llm-driven-configuration.md)
- [ADR-0006 — multi-level confirmation](0006-multi-level-confirmation.md) builds on this with risk-class-specific levels
- `docs/ARCHITECTURE.md` — original two-gate model description
