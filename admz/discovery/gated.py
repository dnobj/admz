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

**One gate stays. The other was retired, and the asymmetry is why.**

The **deep survey** gate (``api/routes/demos.py``) stays: the operator approves
a *blast radius* — scan this subnet, register what you find — which the
chokepoint cannot express, because by the time it fires the scan has happened.

The **``register_discovered_device``** gate is **gone** (slice 3). Once
provisioning is gated downstream, what remained here was a gate on the registry
write, justified by "the model discovered this device rather than a human
naming it". That justification does not survive review: ``register_device``
performs the same ``registry.add_device`` with no gate, one tool call away —
and this ADR's own argument is that "chosen by a scan" versus "named by a
human" is **not distinguishable for an autonomous caller**. A gate one tool
call from an ungated equivalent is not protection; it is false assurance, the
shape this project has now removed five times. Whether registry additions
should be gated at all is a separate, open question for the owner.

**The survey gate is load-bearing for a second reason, and removing it would
be actively harmful.** Approving it runs
``operations._action_start_demo_survey`` inside the approved context, and
``asyncio.create_task`` copies that context into the background survey — so
every factory-defaulted device the survey provisions is covered by the one
approval the operator already gave. Delete this gate and the survey runs
unapproved, which means the chokepoint fires **per device**, from a background
task, with nobody on the page to answer. One approval becomes N widgets nobody
sees.

ADR-0059's plan said slice 3 would retire *both* entry-point gates. Half of
that was right; see the ADR's amendment for why the survey one stays.

**A second entry gate, for the same reason (ADR-0072).** The console's
discovery widget adds the devices an operator ticked, under one approval
(``api/routes/discovery.py``, action :data:`ACTION_ADD_DISCOVERED`). It is an
entry gate like the survey's because what it approves — *these N devices, their
registration and their accounts* — is a batch the per-device chokepoint cannot
express; without it the chokepoint would raise one card per device. It is not a
gate on the registry write alone, so the objection that retired the
``register_discovered_device`` gate does not reach it: the approval carries
provisioning authority, and ``register_device`` offers no ungated path to that.

One entry point, one helper
---------------------------
Splitting a gate across call sites is how a guard ends up half-implemented
(#208) or divergent (#255), so the survey comes through
:func:`gate_scan_write` — one risk class, one level resolution, one envelope.
The chokepoint in ``onboarding`` is the other layer and has its own envelope;
the two answer different questions and neither is a copy of the other.

**No interactive exemption.** ``demos/gated.py`` and ``tasks/gated.py`` let a
signed-in console operator through, because there the operator is editing their
own fleet metadata. Here the operator *is* part of the threat the decision names
— "an authenticated user, or the model in two tool calls, can currently scan a
named subnet and provision root accounts with nothing in the way" — so the
console is gated too. Copying ``is_interactive`` from the neighbouring modules
would have left the REST survey exactly as it was.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from admz import operations

#: Action registered in ``operations._ACTION_EXECUTORS`` for this gate.
ACTION_SURVEY = "start_demo_survey"


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


#: The account writes one approval of a discovery-driven add authorises. Shared
#: by the survey card and the widget's add card (ADR-0072), so the two cannot
#: describe the same writes differently.
_ACCOUNT_WRITES = (
    "create an admin account for ADMZ — on a factory-defaulted device TWO "
    "accounts: 'root' set to the fleet root password, then ADMZ's own "
    "'admz' account (only 'admz' is stored); or on a device that is "
    "already set up, just ADMZ's own 'admz' account if the fleet root "
    "password or an entry credential can log in (that credential is "
    "left in place)"
)


def survey_reason(subnet: Any, register_new: bool) -> str:
    """The operator-facing sentence on the approval card.

    Names the blast radius, because that is the thing being approved: an
    auto-detected sweep and a named CIDR are the same click otherwise.
    """
    where = str(subnet).strip() if subnet else "the local subnet (auto-detected)"
    # This ONE approval covers everything onboarding may then do — it is in
    # `onboarding._APPROVAL_ACTIONS`, so no branch will prompt again. The card
    # therefore has to name every write it authorises, up front, at the risk
    # level of the riskiest one (both are pwdgrp.cgi:add-user → service-
    # affecting, so the level is already the max). Under-describing it here
    # would mean the operator approved something the card never mentioned,
    # which is the failure #411's review caught in the first draft.
    tail = (f"register unknown devices it finds and, on each, {_ACCOUNT_WRITES}"
            if register_new else "register unknown devices it finds")
    return (f"Deep survey: scan {where}, then {tail}. This writes to devices "
            f"ADMZ has never seen.")


#: Action registered in ``operations._ACTION_EXECUTORS`` for the console's
#: discovery widget (ADR-0072).
ACTION_ADD_DISCOVERED = "add_discovered_devices"


def add_reason(devices: Sequence[Mapping[str, Any]]) -> str:
    """The sentence on the widget's add approval (ADR-0072 §3).

    Names every device — by canonical id and address, which ADMZ derived, plus
    the model, sanitized, because it is the device's own claim — and then every
    write the approval authorises, in the survey card's words. Every surface
    that renders the session shows exactly this: the widget, a re-pinned card
    after a reload, and ``/confirm/{token}``.
    """
    from admz.validators import sanitize_display_text

    parts = []
    for device in devices:
        label = sanitize_display_text(device.get("model") or "", max_length=40)
        ident = f"{device.get('device_id', '')} at {device.get('host', '')}"
        parts.append(f"{label} ({ident})" if label else ident)
    count = len(parts)
    noun = "device" if count == 1 else "devices"
    return (f"Add {count} discovered {noun} to ADMZ: {'; '.join(parts)}. "
            + add_consequence())


def add_consequence() -> str:
    """What an add does to each device — the widget shows it above the Add
    button before anything is selected, and :func:`add_reason` ends with it,
    so the sentence the operator reads is the one the session records."""
    return (
        "For each device, ADMZ first checks that the device at that address "
        "still reports that serial number and registers it; then it will "
        f"{_ACCOUNT_WRITES}. A device whose identity cannot be confirmed is "
        "skipped and nothing is written to it."
    )
