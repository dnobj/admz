"""Widget-gating for the drift-affecting demo writes (ADR-0047 policy).

Assign-fragment and adopt change what counts as drift — together they could
re-label real drift as "deliberate demo config" — so when an LLM (chat/MCP) or
an api-key caller initiates them, the write is held in a ``url_only`` confirm
session and only runs when a human approves at the widget. Metadata edits stay
direct, and the interactive web console (Windows principal clicking its own UI)
is exempt — mirroring :mod:`admz.tasks.gated` exactly.
"""

from __future__ import annotations

from typing import Any, Mapping

from admz import operations


def is_interactive(principal) -> bool:
    """True when the write comes from a signed-in human at the console UI.

    Same rule as tasks: windows-local sessions (/login password or SSO) are a
    person clicking; api-key, chat/MCP, and anonymous principals are not.
    """
    return getattr(principal, "source", "") == "windows"


def gate_demo_write(action: str, target: str, payload: Mapping[str, Any],
                    reason: str) -> dict:
    """Hold a demo write behind the approval widget.

    Returns the standard blocked envelope — identical shape to a gated VAPIX
    operation, so the chat approval card, the /confirm page, audit, and the
    console event notes all just work. On approval,
    ``operations.execute_approved_session`` runs the registered
    ``_action_<action>`` executor, which re-validates before writing.
    """
    session = operations.create_action_session(
        action=action, device_id=target, payload=dict(payload), reason=reason,
    )
    env = operations.blocked_envelope(session, reason=reason)
    env["success"] = False
    return env
