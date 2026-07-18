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
from collections import defaultdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _set_scenario_safe(registry: Any, device_id: str, name: Optional[str]) -> None:
    """Set/clear the ``active_scenario`` marker, tolerating a backend without
    pointer support (the stubbed Vault, H-4)."""
    try:
        registry.set_active_scenario(device_id, name)
    except NotImplementedError:
        pass
    except Exception:  # noqa: BLE001 — a marker write must never break the flow
        logger.warning("set_active_scenario failed for %s", device_id, exc_info=True)


def on_markers_complete(plan: Any, args: Dict[str, Any], registry: Any = None) -> None:
    """``scenario_markers`` completion handler (ADR-0048) — the task_7f8c285b fix.

    Set/clear ``active_scenario`` ONLY for devices whose steps in this plan ALL
    succeeded, and ONLY once the plan has run. A device with any failed/unrun step
    keeps its prior marker — honest in both directions: a half-pushed scenario
    reads as drift, a half-returned device stays marked. ``markers`` maps
    device_id → scenario name (activate) or None (return-to-baseline).
    """
    markers: Dict[str, Optional[str]] = args.get("markers") or {}
    if registry is None or not markers:
        return
    ok: Dict[str, List[bool]] = defaultdict(list)
    for r in getattr(plan, "results", []) or []:
        ok[getattr(r, "device_id", None)].append(bool(getattr(r, "success", False)))
    for did, name in markers.items():
        outcomes = ok.get(did, [])
        if outcomes and all(outcomes):
            _set_scenario_safe(registry, did, name)


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
        # The marker is NOT set here (that was the marker-before-approval bug):
        # it rides the plan's completion hook and flips only after the push runs.
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
        # No push needed (already matches) → no plan to ride the hook, so set the
        # marker directly. This is the deliberate direct-set the wizard keeps.
        for a in applied:
            _set_scenario_safe(ctx.registry, a["device_id"], name)
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
            on_complete={"handler": "scenario_markers",
                         "markers": {a["device_id"]: name for a in applied}},
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
        # Marker cleared by the completion hook after the baseline push runs, not
        # here at request time (the marker-before-approval bug).
        applied.append({"device_id": did})

    resource = "scenario:return-to-baseline"
    if not applied:
        record_event(principal, "snapshot.scenario_return", resource=resource,
                     details={"outcome": "none-with-baseline"})
        return {"message": "No devices in scope have a baseline to return to.",
                "applied": [], "skipped": skipped}
    if not all_steps:
        # Already at baseline → no plan; clear the marker directly.
        for a in applied:
            _set_scenario_safe(ctx.registry, a["device_id"], None)
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
            on_complete={"handler": "scenario_markers",
                         "markers": {a["device_id"]: None for a in applied}},
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
