"""Widget-gating for discovery-driven provisioning (#199, ADR-0034).

A network sweep that *registers what it finds* does not stop at registering.
``onboarding.onboard_device_credentials`` sends a factory-defaulted unit through
``provisioning.provision_factory_default`` — ``pwdgrp.cgi:add-user``,
``group=root``, ``auth_method="none"`` — so one call can scan an operator-named
subnet and create an admin account on every unclaimed device on it. Until this
existed there was **no gate at all** on that.

What these gates are for, now that provisioning has its own (ADR-0059)
----------------------------------------------------------------------
**This module used to be the only gate on provisioning.** It no longer is:
ADR-0059 put a gate at the decision point — inside
``onboarding.onboard_device_credentials``, immediately before
``provision_factory_default`` — because the entry-point placement could not be
kept complete. It classified callers by "was the device chosen before the
call?", which is sound about a human and collapses for the model: it can call
``discover_network_devices`` (an ungated read) and then name what it just
found. The proof was in the gate table itself — ``register_discovered_device``
was held while ``register_device``, reaching the identical write, was not.

**These two gates stay, and they are no longer about provisioning.** What each
now approves is narrower and still real:

* the **deep survey** (``api/routes/demos.py``) — the operator approves a
  *blast radius*: scan this subnet, register what you find. The chokepoint
  cannot express that, because by the time it fires the scan has happened.
* **``register_discovered_device``** (``mcp/server.py``) — the operator
  approves registering a device the model discovered rather than one a human
  named. That is a registry write, and the chokepoint does not cover registry
  writes.

**The survey gate is load-bearing for a second reason, and removing it would
be actively harmful.** Approving it runs
``operations._action_start_demo_survey`` inside the approved context, and
``asyncio.create_task`` copies that context into the background survey — so
every factory-defaulted device the survey provisions is covered by the one
approval the operator already gave. Delete this gate and the survey runs
unapproved, which means the chokepoint fires **per device**, from a background
task, with nobody on the page to answer. One approval becomes N widgets nobody
sees.

ADR-0059's plan said slice 3 would "retire the entry-point gate". That
instruction was over-generalised and is not what shipped; see the ADR's
amendment.

Two entry points, one helper
----------------------------
Splitting a gate across call sites is how a guard ends up half-implemented
(#208) or divergent (#255), so both callers come through :func:`gate_scan_write`
— one risk class, one level resolution, one envelope. There is no second
predicate to keep in step.

**No interactive exemption.** ``demos/gated.py`` and ``tasks/gated.py`` let a
signed-in console operator through, because there the operator is editing their
own fleet metadata. Here the operator *is* part of the threat the decision names
— "an authenticated user, or the model in two tool calls, can currently scan a
named subnet and provision root accounts with nothing in the way" — so the
console is gated too. Copying ``is_interactive`` from the neighbouring modules
would have left the REST survey, the louder of the two paths, exactly as it was.
"""

from __future__ import annotations

from typing import Any, Mapping

from admz import operations

#: Actions registered in ``operations._ACTION_EXECUTORS`` for this gate.
ACTION_SURVEY = "start_demo_survey"
ACTION_REGISTER_DISCOVERED = "register_discovered_device"


def gate_scan_write(action: str, target: str, payload: Mapping[str, Any],
                    reason: str) -> dict:
    """Hold a discovery-driven provisioning call behind the approval widget.

    ``operator_configurable=True``: the level resolves through the normal
    ``service-affecting`` row rather than ADR-0034's pin, so ``/confirm-settings``
    can raise it to ``url_and_password`` or lower it. That is the operator's
    explicit decision on #199 — "a click is proportionate, requiring the
    confirmation password by default is not", with the ability to change their
    mind in the UI. It defaults to ``url_only`` because that is what
    ``service-affecting`` already maps to, so this is not a new tier.

    Returns the standard blocked envelope — the same shape a gated VAPIX
    operation returns, so the chat approval card, ``/confirm/{token}``, the
    audit row and the console event notes all work with no special case.
    """
    session = operations.create_action_session(
        action=action, device_id=target, payload=dict(payload), reason=reason,
        operator_configurable=True,
    )
    env = operations.blocked_envelope(session, reason=reason)
    env["success"] = False
    return env


def survey_reason(subnet: Any, register_new: bool) -> str:
    """The operator-facing sentence on the approval card.

    Names the blast radius, because that is the thing being approved: an
    auto-detected sweep and a named CIDR are the same click otherwise.
    """
    where = str(subnet).strip() if subnet else "the local subnet (auto-detected)"
    tail = ("register unknown devices it finds and provision an admin account "
            "on any that are factory-defaulted"
            if register_new else "register unknown devices it finds")
    return (f"Deep survey: scan {where}, then {tail}. This writes to devices "
            f"ADMZ has never seen.")
