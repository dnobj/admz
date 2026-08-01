"""MCP Tool definitions: the advanced-capability inventory (GH #132, ADR-0052).

One tool, read-only. It answers the question the registry exists to answer —
*"what non-default powers is this installation running with?"* — for the agent
rather than for a human reading a startup log, so a diagnosis that starts in
chat does not have to end in the source tree. The payload is the same shape
``GET /api/capabilities`` returns (``admz.capabilities.snapshot``), so the two
readers cannot drift.

======================================================================
THERE IS DELIBERATELY NO ENABLE/DISABLE TOOL HERE, AND THERE NEVER
SHOULD BE. Do not "complete the pair" by adding one.
======================================================================

These capabilities change how the model's own gates behave: ``dev.auto_approve``
lets a script satisfy a confirmation gate meant for a human, ``dev.test_auth``
decides who the calling principal even is, ``acs.rule_write`` writes an
unsupported database directly. A write tool would put the LLM one tool call
away from granting itself those powers — and an LLM that can enable its own
approver is not gated at all, whatever the gate code says.

The refusal is enforced **twice**, on purpose, so removing one half is not
enough to open the hole:

1. **No tool exists.** This module exports exactly one ``Tool`` and the
   dispatch table has exactly one matching entry
   (``tests/test_advanced_capabilities.py`` asserts no advertised tool name
   matches ``set_.*capabilit``).
2. **Every ``setting_key`` in the registry is in ``PROTECTED_SETTING_KEYS``.**
   So even the generic ``set_fleet_setting`` tool refuses them — an LLM that
   went looking for the back door finds it already shut, by the same mechanism
   that has protected the survey keys since ADR-0020.

Enabling a capability stays what it should be: a deliberate act by a human with
service control on the box (an env var + a restart), or, for the ``privileged``
rows only, a reveal-gated, typed-acknowledged, audited toggle on
``/settings/advanced``. Neither is reachable from here.

If a future deployment genuinely needs an agent to flip a capability, that is
its own issue with its own threat model — not a quietly-added second entry in
this list.
"""

from typing import List

from mcp.types import Tool

TOOLS: List[Tool] = [
    Tool(
        name="get_advanced_capabilities",
        description=(
            "Read the advanced-capability registry: which powerful, dangerous, "
            "or privileged-install switches this ADMZ installation is running "
            "with, and which are merely available. Read-only — there is no "
            "tool to turn one on or off, by design.\n\n"
            "Use it when the answer depends on what mode the install is in: "
            "'why did adding a device return credentials_needed?' (onboarding "
            "probes may be suppressed), 'why didn't my schedule fire?' "
            "(a subprocess role marker), 'is anything unsafe switched on "
            "here?', or before telling the operator an approval is waiting on "
            "them — under `dev.auto_approve` a script may complete it, and "
            "under `dev.test_auth` the caller may be a synthetic test "
            "principal rather than the human you are addressing.\n\n"
            "Returns every declared capability with its danger class "
            "(dev-only / dangerous / privileged / test-suppressor / internal), "
            "whether it is enabled and from where (`env` or `setting`), the "
            "NAME of the environment variable or fleet setting that controls "
            "it (never its value), and notes on what it changes. `active` "
            "lists the ids currently on; `auth_backend` is the install's "
            "authentication posture, which is context rather than a "
            "capability.\n\n"
            "A capability changes WHO the principal is or WHAT runs in the "
            "background. It never removes a confirmation gate (ADR-0034) — "
            "never tell the operator a gate was skipped because a capability "
            "is on."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
]
