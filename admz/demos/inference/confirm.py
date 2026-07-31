"""Confirm / dismiss a demo proposal (#124, slice 3) — the only writes here.

Both cores compose **existing** write cores rather than introducing new ones:
``actions.create_demo_core`` mints the demo and ``actions.attach_rule_to_demo``
records each rule's membership and auto-derives its signal — unchanged, the same
functions the rule executor has used since ADR-0050 Phase B. Inference simply
supplies the same rule dict shape.

Confirm writes **no fragments**
-------------------------------
Resolved DECISION b: a proposal's ``suggested_owned_keys`` are read-only
evidence. Capture only accepts keys that are *currently drifted*
(``actions.py:179`` skips ``not-drifted``; ``fragments.py:177-180`` refuses
``not-in-baseline``), and at first run the baseline is snapshotted *from* live
state — live equals baseline, zero drift, nothing capturable. So the demo is
created with an **empty fragment set** and ``demo_setup_status``
(``wizard.py:110-111``) already emits the right next action for capturing them
later through the normal drift-based path.

That is also why confirm stays **ungated**. ``demos/gated.py`` exists for the
*drift-affecting* writes — ``assign_demo_fragment`` and ``adopt_demo`` — because
together they can re-label real drift as "deliberate demo config". Confirm does
neither: it writes one row to ``demos`` (metadata, the same bar as
``create_demo``, ``0046-demos.md:126``), attaches rule membership, and leaves
``active`` False, so ``fragments.attribution_maps`` sees nothing new on the next
drift check. It touches no device and issues no ACS write. Deleting a demo is
cheap and touches no device, so a wrong confirm is trivially reversible.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from admz.demos.actions import DemoActionError
from admz.demos.inference import proposals as pstore

logger = logging.getLogger(__name__)


def resolve_proposal(store, ref: str):
    """A proposal by id, or by its (unique, case-insensitive) name.

    The chat model says "the speaker demo proposal", not a hex id — the same
    reasoning as ``actions.resolve_demo``, and ambiguity lists the candidates
    rather than guessing.
    """
    ref = (ref or "").strip()
    if not ref:
        raise DemoActionError("proposal id or name is required")
    found = store.get(ref)
    if found is not None:
        return found
    matches = [p for p in store.list(status=None, limit=500)
               if (p.name or "").lower() == ref.lower()]
    open_matches = [p for p in matches if p.status == pstore.STATUS_PROPOSED]
    if len(open_matches) == 1:
        return open_matches[0]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        ids = ", ".join(f"{p.name} ({p.id}, {p.status})" for p in matches)
        raise DemoActionError(
            f"Proposal name {ref!r} is ambiguous — use an id: {ids}")
    raise DemoActionError(f"Proposal not found: {ref}", status=404)


def confirm_proposal_core(ctx, proposal, principal, *,
                          name: Optional[str] = None,
                          purpose: Optional[str] = None,
                          device_ids: Optional[List[str]] = None,
                          roles: Optional[Dict[str, str]] = None,
                          tag: Optional[str] = None) -> Dict[str, Any]:
    """Turn a proposal into a real ADR-0046 demo. Everything is overridable.

    A proposal is a guess, so the operator can correct the name, the purpose,
    the device list and the roles at the moment of confirming — the plan's
    mitigation for "operator confirms a wrong proposal".
    """
    from admz.audit import record_event
    from admz.demos.actions import attach_rule_to_demo, create_demo_core

    store = ctx.proposal_store
    if proposal.status == pstore.STATUS_CONFIRMED:
        raise DemoActionError(
            f"Proposal '{proposal.name}' was already confirmed as demo "
            f"{proposal.demo_id}.", status=409)

    wanted = list(device_ids if device_ids is not None else proposal.device_ids)
    resolved: List[str] = []
    missing: List[str] = []
    for did in wanted:
        try:
            exists = ctx.registry.device_exists(did)
        except Exception:  # noqa: BLE001 — an unreadable registry is not the
            exists = False  # device's fault; treat as gone and report it
        (resolved if exists else missing).append(did)

    if not resolved:
        raise DemoActionError(
            "None of this proposal's devices are in the registry any more"
            + (f" ({', '.join(missing)})" if missing else "")
            + " — nothing left to build a demo from. Re-run inference.",
            status=409)

    demo_name = (name if name is not None else proposal.name).strip()
    if not demo_name:
        raise DemoActionError("name is required")
    demo_roles = dict(roles if roles is not None else (proposal.roles or {}))
    demo_roles = {k: v for k, v in demo_roles.items() if k in set(resolved)}

    demo = create_demo_core(ctx, {
        "name": demo_name,
        "narrative": (purpose if purpose is not None else proposal.purpose) or "",
        "tag": tag or None,
        "device_ids": [] if tag else resolved,
        "roles": demo_roles,
        # Baseline, always: an inferred demo describes what the devices already
        # do. A scenario would claim the demo needs config pushed to run, which
        # inference has no evidence for.
        "config_source": "baseline",
        "signals": [],
        "enabled": True,
    }, principal)

    attached, skipped_rules = 0, []
    for entry in proposal.rules or []:
        did = entry.get("device_id") or ""
        rid = str(entry.get("rule_id") or "")
        if not (did and rid):
            skipped_rules.append({**entry, "reason": "no device or rule id"})
            continue
        if did not in set(resolved):
            skipped_rules.append({**entry, "reason": f"device {did} is not in scope"})
            continue
        try:
            attach_rule_to_demo(ctx, demo, {
                "device_id": did, "rule_id": rid,
                "rule_name": entry.get("rule_name"),
                "condition_id": entry.get("condition_id"),
                "condition_topic": entry.get("condition_topic"),
                # The additive membership field: an ACS rule has no ADMZ device
                # rule to observe, so the wizard must not report it as missing.
                "source": entry.get("source") or "device",
            })
            attached += 1
        except Exception:  # noqa: BLE001 — bookkeeping never falsifies the demo
            logger.warning("proposal %s: attaching rule %s failed",
                           proposal.id, rid, exc_info=True)
            skipped_rules.append({**entry, "reason": "attach failed"})

    updated = store.decide(proposal.id, pstore.STATUS_CONFIRMED,
                           decided_by=str(principal), demo_id=demo.id,
                           name=demo_name,
                           purpose=(purpose if purpose is not None else None))
    # Every other still-open proposal for the same devices is now answered.
    store.supersede_open(proposal.content_key, except_id=proposal.id)

    record_event(principal, "demo.proposal_confirm",
                 resource=f"demo_proposal:{proposal.id}",
                 details={"demo_id": demo.id, "name": demo_name,
                          # Both names, so the record itself tells the story:
                          # what ADMZ guessed vs what the human accepted.
                          "proposed_name": proposal.proposed_name or proposal.name,
                          "renamed": demo_name != (proposal.proposed_name
                                                   or proposal.name),
                          "devices": resolved, "rules_attached": attached,
                          "score": proposal.score,
                          "confidence": proposal.confidence,
                          "fragments_written": 0})

    from admz.demos import service
    return {
        "success": True,
        "demo": service.demo_view(demo, ctx.registry,
                                  getattr(ctx, "event_store", None)),
        "proposal": (updated or proposal).to_dict(),
        "rules_attached": attached,
        "skipped_rules": skipped_rules,
        "skipped_devices": missing,
        # Stated explicitly because it is a product decision, not an omission.
        "fragments_written": 0,
        "suggested_owned_keys": proposal.suggested_owned_keys,
        "message": (
            f"Created demo '{demo_name}' from the proposal with {len(resolved)} "
            f"device(s) and {attached} rule membership(s)"
            + (f"; {len(missing)} device(s) no longer registered were skipped"
               if missing else "")
            + ". No config was captured — the demo owns nothing yet. Its "
            "suggested keys are evidence only; capture them later with "
            "check_drift + assign_demo_fragment once something has actually "
            "changed."),
    }


def dismiss_proposal_core(ctx, proposal, principal, *,
                          reason: str = "") -> Dict[str, Any]:
    """Record that this is not a demo. Remembered, so re-inference respects it."""
    from admz.audit import record_event

    if proposal.status == pstore.STATUS_CONFIRMED:
        raise DemoActionError(
            f"Proposal '{proposal.name}' is already a demo ({proposal.demo_id}) "
            "— delete the demo instead.", status=409)

    updated = ctx.proposal_store.decide(proposal.id, pstore.STATUS_DISMISSED,
                                        decided_by=str(principal))
    record_event(principal, "demo.proposal_dismiss",
                 resource=f"demo_proposal:{proposal.id}",
                 details={"name": proposal.name, "reason": reason,
                          "devices": proposal.device_ids})
    return {
        "success": True,
        "proposal": (updated or proposal).to_dict(),
        "message": (f"Dismissed '{proposal.name}'. Re-running inference will "
                    "not propose these devices again."),
    }


__all__ = ["resolve_proposal", "confirm_proposal_core", "dismiss_proposal_core"]
