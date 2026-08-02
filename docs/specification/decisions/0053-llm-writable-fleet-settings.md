# ADR-0053: Fleet settings are deny-by-default for the LLM — writability is declared, not withheld

**Status:** Accepted (planning). Implementation tracked by [#212](https://github.com/dnobj/admz/issues/212).
**Date:** 2026-08-02.
**Amends:** [ADR-0020](0020-protected-fleet-settings.md) — the deny-list model this inverts. ADR-0020's *reasoning* stands unchanged; only its mechanism is replaced.
**Plan:** [`docs/plans/invert-setting-allowlist.md`](../../plans/invert-setting-allowlist.md).

## Context

ADR-0020 established that some fleet-setting keys are **protected**: the MCP
`set_fleet_setting` tool, callable by the chat model, refuses to write them.
Its reasoning — *"an LLM that can change its own guardrails has no
guardrails"* — is correct and is not in question here.

Its mechanism was an enumerated set, `PROTECTED_SETTING_KEYS`. That makes a new
setting **LLM-writable the moment it exists**, and protected only if its author
remembered to add it. Four independent audit loops have now found holes in that
set:

| | Key | Consequence | Outcome |
|---|---|---|---|
| #152 | `confirm_level_action` | disable the confirmation gate on 68 ACS operations | fixed in #176 |
| #168 | `health_verify_credentials` | a stale password reports healthy | open |
| #195 | `acs_pro` | enable the ACS module at an arbitrary host; 23 new MCP tools | open |
| #203 | `config_ignore_patterns` | one `*` suppresses all drift detection fleet-wide | open |

That is not four bugs. It is one wrong default, found four times.

**The decisive evidence is not the four failures but the three enumerations.**
Three independent attempts to list the unprotected keys — a naming-convention
regex (#212), a literal grep (orientation), and a per-module call-path sweep —
produced **8, 10 and 18** keys, and *each missed keys the others found*. #212's
own amendment diagnoses the mechanism: its regex required `[A-Z]` at position 0,
so `_TOKEN_KEY` (`acs_webhook_token`) was invisible. Every enumeration method
inherits its author's blind spot.

18 of the ~44 known keys — 41% — are writable by the chat model, and 18 should
be read as a floor rather than a total.

Two further observations settled the decision:

1. **The same mistake recurs across independent authors.** Three features now
   guard their switch and leave their target writable: `acs_pro`'s children are
   protected but the parent is not (#195); `acs_firebird_enabled` is protected
   but the `acs_fb_*` paths that steer the loader are not; `event_ingest_enabled`
   is protected but the topic, tag and retention keys that decide what it
   records are not. A deny-list cannot fix this class, because the error is a
   *judgement about which half of a feature is dangerous*, made by whoever adds
   the setting.
2. **The requirement document drifted the same way as the code.** FR-SEC-012
   listed three protected keys while the set held thirty. Even the prose
   description of an enumerated deny-list could not be kept current.

3. **The spec had already decided something stricter, and it was never built.**
   ADR-0024 §42-44 and US-CB-006 (`chatbot-driven-workflows.md:119-123`) both
   say the chatbot's tool allowlist should exclude `set_fleet_setting`
   outright. No such filtering exists — `admz/chatbot/mcp_bridge.py:51` exposes
   *"the same 19 tools that external MCP clients see"*. This decision is
   therefore **less** restrictive than what the specification already accepted,
   which is a strong reason to think it is not an over-correction. (The missing
   chatbot allowlist is a broader question and is not resolved here.)

The two-key allow-set below was reached by attempted **falsification** rather
than by assumption: an exhaustive search of the demos subsystem, the full system
prompt, module-contributed prompt sections, every MCP tool module, the chatbot
package, the user stories and every test found no evidence of the model writing,
or being instructed to write, any third key. Exactly one test in the repository
asserts a successful `set_fleet_setting` write, and it writes `default_username`.

## Decision

**A fleet setting is not writable by the chat model unless it is explicitly
declared writable.**

1. A new leaf module `admz/setting_policy.py` — importing nothing from `admz`,
   the same placement and for the same import-cycle reason as
   `admz/confirm_policy.py` (ADR-0020's #176 amendment) — declares
   `LLM_WRITABLE_SETTING_KEYS`.

2. That set is **two keys**: `default_password` and `default_username`. This is
   not a judgement call; it is what the system already documents. The MCP tool's
   own description (`admz/mcp/tools/fleet.py:23`) advertises exactly one key to
   the model, `default_password`; `default_username` is its documented other
   half and the positive control in `tests/test_confirm_store.py:481-500`. No
   user story, requirement, system prompt, demo or test evidences the model
   writing any other key.

3. `is_protected_setting(key)` becomes `not is_llm_writable(key)`, retaining the
   `confirm_level_*` namespace clause as a second, redundant refusal — it can
   only ever deny more, and it covers keys built at runtime, which a static
   declaration cannot.

4. **`default_password` is capture-only.** A supplied value is refused; omitting
   the value returns the out-of-band capture URL as today. This makes the code
   match what FR-MCP-008 and two user stories already require — *"never typed
   into the LLM chat"* — rather than adding a restriction.

5. The set is named for what it **grants**. `UNPROTECTED_SETTING_KEYS` would
   describe the same keys while inviting the opposite reflex: a contributor
   blocked by a red test takes the shortest path out, and "add my key to the
   not-protected list" reads as bookkeeping. "Add my key to
   `LLM_WRITABLE_SETTING_KEYS`" reads as a grant, and a reviewer asks why.

6. `PROTECTED_SETTING_KEYS` **survives**, derived and explicitly
   non-authoritative. Nine test sites and five spec documents reference it;
   deleting the name to make a point would turn nine assertions into assertions
   about nothing — the precise vacuity #176 diagnosed in the test that let #152
   through.

7. A guard test enumerates keys **from behaviour, not from names** — an AST walk
   resolving module-level constants bound to string literals. The three-way
   enumeration disagreement above is the argument: a name-keyed guard inherits
   whichever blind spot its author had. Its known limit — runtime-computed keys
   are invisible to a static scan — is why clause 3 keeps the namespace rule.

8. **Purpose-built gated tools are outside this model, deliberately.** The MCP
   tool `set_event_ingest` writes the protected key `event_ingest_enabled`
   without consulting the predicate, because it is gated by an ADR-0034 approval
   card instead — a stronger control, since a human approves each use. Two
   different doors: the *generic* tool is governed by the allow-set; a
   *purpose-built* tool is governed by its own gate. This is recorded so that a
   future reader neither routes `set_event_ingest` through the allow-set
   (silently removing its approval card) nor adds `event_ingest_enabled` to the
   allow-set to "make it consistent".

9. **`python -m admz settings` ships with the inversion.** Nine of the eighteen
   newly protected keys have no writer at all except the MCP tool — no route, no
   form, no environment variable. Protecting them without an operator path would
   remove nine documented controls. ADR-0020 already listed the missing CLI as a
   negative consequence and a *"small Phase-5 follow-up"*; inversion is what
   makes it load-bearing, and one subcommand restores control over every
   protected key at once — today's, the new ones, and every key added later.

## Consequences

**Positive:**

- The next fleet setting anyone adds is protected **by forgetting**. The failure
  direction is inverted, which is the whole point.
- FR-SEC-012 stops being a list that goes stale and becomes a sentence that
  cannot: *the tool may write the allow-set; everything else is refused.*
- Granting the model write access to a setting becomes a reviewed, one-line,
  visibly-a-grant diff.
- The blast radius is small: `is_protected_setting` has exactly one production
  caller (`admz/mcp/server.py:3598`), and there is no generic REST write route.
- ADR-0020's open CLI gap is closed rather than widened.
- As a side effect of clause 4, no password value reaches the `set_fleet_setting`
  call, which removes this tool's exposure to the audit-log leak in
  [#217](https://github.com/dnobj/admz/issues/217). #217 still ships separately —
  a name-only redactor is blind to every `{key, value}`-shaped tool.

**Negative:**

- An operator scripting initial setup must use the CLI or the web UI for
  eighteen more keys than before. This is the intended friction, but it is
  friction.
- The declaration is still hand-maintained; it is merely *short*, and wrong in
  the safe direction. A key that genuinely should be LLM-writable will now be
  discovered by something breaking rather than by a security audit — an
  acceptable trade, and the reason the allow-set was validated against the
  documented chat surface before being fixed at two.
- The static scanner cannot see runtime-computed keys. Mitigated, not solved, by
  keeping the namespace rule.

**Deliberately unchanged:**

- No confirmation gate is added, removed or altered. ADR-0034 is untouched: this
  changes *which keys a low-privilege caller may write*, never *whether* an
  approval fires.
- Authenticated web writers keep every path they have today.

**Edge case, recorded because it is a landmine.**
`capture_store.create_fleet_session()` has exactly one caller,
`admz/mcp/server.py:3610`, which sits *below* the protection gate at
`server.py:3598`; and `admz/api/routes/capture.py:325-326` is the only non-MCP
writer of the credential pair, reachable only with a token that line 3610 mints.
Protecting `default_password` outright would therefore destroy the capture flow
and orphan both keys. This ADR avoids that by allow-listing the pair and
refusing only a *supplied value* — a distinction that is load-bearing rather
than stylistic.

## References

- ADR-0020 — protected fleet-setting keys (the model this amends)
- ADR-0006 / ADR-0034 — the confirmation gates this must not touch
- ADR-0009 — out-of-band credential capture (the flow clause 4 preserves)
- ADR-0052 — advanced capability switches; a *declaration* registry, explicitly
  not a security boundary. Its shape was considered and not adopted for the
  allow-set, precisely because this one must enforce.
- Requirements: [security.md](../requirements/security.md) FR-SEC-012,
  [mcp-server.md](../requirements/mcp-server.md) FR-MCP-008
- Issues: #212 (this work), #152/#168/#195/#203/#177 (the four failures and the
  derivation-guard gaps), #217 (audit-log redaction), #164 (events authz)
- Code: `admz/setting_policy.py`, `admz/fleet_settings.py::is_protected_setting`,
  `admz/mcp/server.py::_set_fleet_setting`, `admz/api/routes/capture.py`
