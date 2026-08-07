# ADR-0020: Protected fleet-setting keys (MCP cannot write them)

**Status:** Accepted, in production. **The enumerated-deny-list mechanism below is being inverted** — see [ADR-0053](0053-llm-writable-fleet-settings.md) ✅ (#212). The *reasoning* in this ADR stands unchanged; only the mechanism is replaced, because an opt-in deny-list failed four times in the same direction (#152, #168, #195, #203) and three independent enumerations of what it missed returned three different answers.
**Amendment (2026-08-07, #151):** `tool_get_credentials_enabled` — used throughout this ADR as the motivating example — no longer exists. The `get_credentials` MCP tool it gated was removed (CR-1), after which the flag's only live effect was letting *anonymous* callers bypass the fleet-setting reveal gate; the owner chose deletion over relabeling. The examples below are kept as written: they describe why protection was needed at the time, and the protection story they motivated now lives in ADR-0053's deny-by-default.
**Date:** Original design 2026-04; recorded as ADR 2026-05-18.

## Context

The fleet-settings store (`admz/fleet_settings.py`) holds operational
configuration that affects every device interaction: default
provisioning credentials, confirmation levels per risk class, password
hashes, the toggle that enables the `get_credentials` MCP tool.

The MCP `set_fleet_setting` tool can write to fleet settings. That's
useful for things like rotating the default password. But the same
tool, unrestricted, could rewrite:

- `confirm_level_dangerous` from `url_and_password` → `none`, removing
  every safety gate from every dangerous operation.
- `tool_get_credentials_enabled` from `false` → `true`, unlocking
  plaintext credential return from MCP itself.
- `confirm_password_hash`, blanking out the confirm password.

An LLM that can change its own guardrails has no guardrails.

## Decision

A defined set of keys is **protected** — the MCP `set_fleet_setting`
tool refuses to write them, returning a structured error pointing
operators at the web UI:

```python
# admz/fleet_settings.py
PROTECTED_SETTING_KEYS = {
    # derived from confirm_policy._DEFAULT_CONFIRMATION_LEVELS, never listed
    *(confirm_level_key(risk) for risk in _DEFAULT_CONFIRMATION_LEVELS),
    "confirm_password_hash",
    "tool_get_credentials_enabled",
    # … plus the chatbot, health, survey, capability and GitHub App keys
}


def is_protected_setting(key: str) -> bool:
    return is_confirm_level_key(key) or key in PROTECTED_SETTING_KEYS
```

> **Update 2026-08-01 (GH #152).** Two amendments, both from the same
> defect. The confirmation-level keys were originally written out by
> hand; when the risk vocabulary grew an ACS Pro `action` class
> (default `url_only`, governing 68 operations) the protected set was
> not updated, so the MCP tool could write `confirm_level_action=none`
> and remove the gate. The guard test iterated its own hardcoded
> four-tuple and passed throughout.
>
> 1. The `confirm_level_*` names are now **derived** from the policy
>    table, which moved to the leaf module `admz/confirm_policy.py` so
>    that `fleet_settings` can import it without a cycle
>    (`confirm_store` already imports `fleet_settings`).
> 2. Protection is additionally a **namespace** rule —
>    `is_confirm_level_key` — because `get_confirmation_level`
>    interpolates a risk string that comes from catalog YAML, not from
>    the table. This is what the glossary and both personas already
>    described.
>
> **Callers must use `is_protected_setting()`**, not `key in
> PROTECTED_SETTING_KEYS`; the set alone does not carry the namespace
> rule. `mcp/server.py::_set_fleet_setting` tested the set directly,
> which is why a fix applied only to the predicate would have been a
> no-op.

Reading these is allowed (with masking for password-shaped values per
ADR-0006). Writing requires the operator to open `/confirm-settings`
in a browser and use the web UI form.

## Consequences

**Positive:**
- A compromised LLM, prompt-injection attack, or unintended tool call
  chain cannot disable safety gates. The mechanical floor stays
  mechanical.
- The web UI form path makes setting these changes deliberate — same
  cognitive friction as the OOB credential capture flow (ADR-0009).
- Easy to extend: adding `tool_X_enabled` to the protected set is one
  line.

**Negative:**
- An operator who wants to script the initial setup (Terraform,
  Ansible) can't drive these settings from the LLM-driven MCP path.
  They have to either click through the web UI manually OR use the
  CLI (`python -m admz` could add a CLI subcommand for protected-key
  management — small Phase-5 follow-up).
- Two surfaces for fleet-settings management (web for protected, MCP
  for everything else) is slightly awkward to document. Documented in
  [requirements/security.md](../requirements/security.md) FR-SEC-012.

**Edge case:** the LLM agent persona running ADMZ for the first time
sometimes needs to enable `tool_get_credentials_enabled` to actually
*be useful*. The intended UX is: operator opens `/confirm-settings`,
flips the toggle, the chatbot/agent can now retrieve credentials.
This is fine — that one click is the right friction.

## References

- ADR-0005 — two-gate plan approval (the safety model this protects)
- ADR-0006 — multi-level confirmation (uses these keys)
- ADR-0024 — bundled web chatbot (will respect these via the same
  mechanism)
- Requirements: [security.md](../requirements/security.md) FR-SEC-012
- Persona: [security-conscious-operator](../personas/security-conscious-operator.md)
- Code: `admz/fleet_settings.py::PROTECTED_SETTING_KEYS` / `::is_protected_setting`, `admz/confirm_policy.py::_DEFAULT_CONFIRMATION_LEVELS`, `admz/mcp/server.py::_set_fleet_setting`
