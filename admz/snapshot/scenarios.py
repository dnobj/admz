"""Shared scenario activate / return core (ADR-0044).

The REST routes owned this logic inline until demos (ADR-0046) needed the same
two moves — Prepare *is* activate, End *is* return-to-baseline. Rather than let a
second surface reimplement "build one plan across N devices, mark the marker,
gate it", both now call these. Same shape as the rest of ADMZ's shared cores
(``operations.py``, ``provisioning.py``): a plain function taking already-resolved
targets, raising ``ValueError`` so each surface maps errors its own way.

The invariant both moves protect: **the blessed baseline never moves**. Activating
is a temporary push plus an ``active_scenario`` marker; returning pushes the
baseline back and clears the marker. That's what makes "return to baseline" a
clean snap-back rather than a restore-from-history.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def activate_scenario_core(
    ctx,
    name: str,
    targets: List[Dict[str, Any]],
    principal,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Push each target's saved config named ``name`` in ONE gated plan.

    Devices without a scenario by that name are skipped and reported — honest
    skip-and-report beats a half-applied group.
    """
    from admz import operations
    from admz.audit import record_event

    applied: List[dict] = []
    skipped: List[str] = []
    all_steps: List[dict] = []
    for d in targets:
        did = d.get("device_id")
        if not did:
            continue
        try:
            variants = ctx.registry.list_named_baselines(did)
        except NotImplementedError:
            variants = []
        match = next((b for b in variants if b.get("name") == name), None)
        if not match:
            skipped.append(did)
            continue
        sha = match["commit_sha"]
        spec = ctx.restore_builder.build_restore_plan(did, ref=sha)
        all_steps.extend(spec.get("steps", []))
        ctx.registry.set_active_scenario(did, name)
        applied.append({"device_id": did, "commit_sha": sha})

    resource = f"scenario:{name}"
    if not applied:
        record_event(principal, "snapshot.scenario_activate", resource=resource,
                     details={"name": name, "outcome": "none-matched"})
        return {
            "message": f"No devices in scope have a scenario named '{name}'.",
            "applied": [], "skipped": skipped, "name": name,
        }
    if not all_steps:
        record_event(principal, "snapshot.scenario_activate", resource=resource,
                     details={"name": name,
                              "applied": [a["device_id"] for a in applied],
                              "outcome": "marked-no-push"})
        return {
            "success": True,
            "message": (f"Marked {len(applied)} device(s) as scenario '{name}'; "
                        "they already match — nothing to push."),
            "applied": applied, "skipped": skipped, "name": name,
        }

    desc = description or (f"Activate scenario '{name}' on {len(applied)} device"
                           + ("s" if len(applied) != 1 else ""))
    try:
        plan = ctx.plan_engine.create_plan(
            description=desc, steps=all_steps, on_failure="stop",
        )
    except ValueError as e:
        record_event(principal, "snapshot.scenario_activate", resource=resource,
                     success=False, error_message=str(e))
        raise

    record_event(principal, "snapshot.scenario_activate", resource=resource,
                 details={"name": name, "plan_id": plan.plan_id,
                          "applied": [a["device_id"] for a in applied],
                          "skipped": skipped, "step_count": len(all_steps)})
    result = await operations.execute_gated_plan(ctx.plan_engine, plan.plan_id)
    result["applied"] = applied
    result["skipped"] = skipped
    result["name"] = name
    return result


async def return_to_baseline_core(
    ctx,
    targets: List[Dict[str, Any]],
    principal,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Push the blessed baseline back to each target in ONE gated plan and clear
    the ``active_scenario`` marker. Devices with no baseline are skipped."""
    from admz import operations
    from admz.audit import record_event

    applied: List[dict] = []
    skipped: List[str] = []
    all_steps: List[dict] = []
    for d in targets:
        did = d.get("device_id")
        if not did:
            continue
        if not d.get("baseline_sha"):
            skipped.append(did)
            continue
        spec = ctx.restore_builder.build_restore_plan(did, ref=None)  # → baseline_sha
        all_steps.extend(spec.get("steps", []))
        ctx.registry.set_active_scenario(did, None)  # back on baseline
        applied.append({"device_id": did})

    resource = "scenario:return-to-baseline"
    if not applied:
        record_event(principal, "snapshot.scenario_return", resource=resource,
                     details={"outcome": "none-with-baseline"})
        return {"message": "No devices in scope have a baseline to return to.",
                "applied": [], "skipped": skipped}
    if not all_steps:
        record_event(principal, "snapshot.scenario_return", resource=resource,
                     details={"applied": [a["device_id"] for a in applied],
                              "outcome": "cleared-no-push"})
        return {
            "success": True,
            "message": (f"Cleared the scenario on {len(applied)} device(s); "
                        "already at baseline — nothing to push."),
            "applied": applied, "skipped": skipped,
        }

    desc = description or (f"Return {len(applied)} device"
                           + ("s" if len(applied) != 1 else "") + " to baseline")
    try:
        plan = ctx.plan_engine.create_plan(
            description=desc, steps=all_steps, on_failure="stop",
        )
    except ValueError as e:
        record_event(principal, "snapshot.scenario_return", resource=resource,
                     success=False, error_message=str(e))
        raise

    record_event(principal, "snapshot.scenario_return", resource=resource,
                 details={"plan_id": plan.plan_id,
                          "applied": [a["device_id"] for a in applied],
                          "skipped": skipped, "step_count": len(all_steps)})
    result = await operations.execute_gated_plan(ctx.plan_engine, plan.plan_id)
    result["applied"] = applied
    result["skipped"] = skipped
    return result
