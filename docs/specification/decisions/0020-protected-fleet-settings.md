# ADR-0020: Protected fleet-setting keys (MCP cannot write them)

**Status:** Accepted, in production.
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
# admz/api/confirm_store.py
PROTECTED_SETTING_KEYS = {
    "confirm_level_dangerous",
    "confirm_level_service-affecting",
    "confirm_level_normal",
    "confirm_level_read-only",
    "confirm_password_hash",
    "tool_get_credentials_enabled",
}
```

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
- Code: `admz/api/confirm_store.py::PROTECTED_SETTING_KEYS`, `admz/mcp/server.py::_set_fleet_setting`
