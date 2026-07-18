"""Fragment demo activation pushes (ADR-0047 slice 3 / ADR-0048 wizard, Phase A).

A *fragment* demo owns a sparse set of config keys (``fragments.py``). Preparing
it means **pushing those keys to its devices** in one gated plan, then flipping
``demo.active`` — but only after the push actually lands. We reuse the existing
device-touch path rather than invent one: synthesize the demo's owned keys as
push DriftFields whose ``expected`` is the *fragment value*, and hand them to
``RestoreBuilder.build_targeted_revert_plan`` — which writes each field's
``expected`` back through the facet's ``revert_param``. Setting ``expected`` to
the fragment value turns "revert" into "push".

State flips ride the plan's completion hook (``plans/completion.py``):
``demo.active`` becomes True only on a COMPLETED plan; a partially-failed push
leaves the demo inactive (its half-pushed keys read as ``candidate`` drift, and a
re-run converges). Deactivation is the mirror: push base values back, flip
``active`` False only on completion.

v1 pushes only **param-writable** set-keys (``facet.revert_param``); API-backed
(``op_revertable``) keys are prefiltered with a warning — their whole-object
revert writes BASE values, not the fragment's, so they can't be pushed this way.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

from admz.demos import service

logger = logging.getLogger(__name__)


# ── Synthesis ────────────────────────────────────────────────────────────────


def synthesize_push_fields(
    git, demo, device_id: str, facets_by_name: Dict[str, Any],
) -> Tuple[List[Any], List[str]]:
    """The demo's owned set-keys for this device as push DriftFields.

    Each field's ``expected`` is the fragment value, so
    ``build_targeted_revert_plan`` writes the fragment value (push). Op-revertable
    / non-param-writable keys are prefiltered (the builder would push BASE values
    for them) and returned as warnings — guard against a mis-captured fragment.
    """
    from admz.demos import fragments as fr
    from admz.snapshot.models import DriftField

    fields: List[Any] = []
    warnings: List[str] = []
    for (facet_name, path), value in sorted(fr._set_map_for(git, demo, device_id).items()):
        facet = facets_by_name.get(facet_name)
        if facet is not None and facet.op_revertable(path):
            warnings.append(
                f"{facet_name}/{path}: skipped — API-backed facet (push unsupported in v1)")
            continue
        if facet is None or facet.revert_param(path, value) is None:
            warnings.append(f"{facet_name}/{path}: skipped — not param-writable")
            continue
        fields.append(DriftField(
            facet=facet_name, path=path, expected=str(value), actual="",
            canonical_key=facet.canonical_key(path) if facet else None,
        ))
    return fields, warnings


def demo_has_fragments(ctx, demo) -> bool:
    """True when the demo owns ≥1 ``set`` key across its role fragments."""
    from admz.demos import fragments as fr

    for facets in fr.load_all_fragments(ctx.git_repo, demo.id).values():
        if fr.fragment_entry_count(facets).get(fr.MODE_SET, 0) > 0:
            return True
    return False


# ── Prepare / End (device-touching, gated) ───────────────────────────────────


async def prepare_fragment_demo_core(ctx, demo, principal) -> Dict[str, Any]:
    """Push a fragment demo's owned keys to its devices in ONE gated plan;
    ``demo.active`` flips only on the plan's completion hook. Zero pushable steps
    → ``already_matches`` (steer to adopt; never silently activate)."""
    from admz import operations
    from admz.audit import record_event
    from admz.demos import fragments as fr
    from admz.demos.actions import DemoActionError
    from admz.snapshot.facets import get_facets_for_device

    targets = service.resolve_devices(demo, ctx.registry)
    if not targets:
        raise DemoActionError("This demo has no devices.")

    # Guard (also re-checked at completion): a device held by a legacy scenario,
    # or same-key overlap with another active demo, blocks activation.
    held = sorted({
        f"{d.get('device_id')} (scenario '{d.get('active_scenario')}')"
        for d in targets if d.get("active_scenario")})
    if held:
        raise DemoActionError(
            "Held by a legacy scenario — end it before preparing: " + ", ".join(held),
            status=409)
    others = [d for d in ctx.demo_store.list() if d.active and d.id != demo.id]
    conflicts = fr.overlap_conflicts(ctx.git_repo, demo, others, ctx.registry)
    if conflicts:
        lines = sorted({
            f"{c['facet']}/{c['path']} on {c['device_id']} (claimed by '{c['other_demo']}')"
            for c in conflicts})
        raise DemoActionError(
            "Key conflict with another active demo: " + "; ".join(lines), status=409)

    all_steps: List[dict] = []
    warnings: List[str] = []
    applied: List[dict] = []
    for d in targets:
        did = d.get("device_id")
        if not did:
            continue
        device_info = ctx.registry.get_device_info(did)
        device_info["device_id"] = did
        facets_by_name = {f.name: f for f in get_facets_for_device(device_info)}
        fields, warns = synthesize_push_fields(ctx.git_repo, demo, did, facets_by_name)
        warnings.extend(warns)
        if not fields:
            continue
        spec = ctx.restore_builder.build_targeted_revert_plan(did, fields)
        all_steps.extend(spec.get("steps", []))
        warnings.extend(spec.get("warnings", []))
        applied.append({"device_id": did, "keys": len(fields)})

    resource = f"demo:{demo.id}"
    if not all_steps:
        record_event(principal, "demo.prepare_fragment", resource=resource,
                     details={"outcome": "already-matches", "warnings": warnings})
        return {
            "success": True, "already_matches": True, "demo_id": demo.id,
            "warnings": warnings,
            "message": ("The device(s) already match this demo's config — nothing "
                        "to push. Adopt the demo to mark it active."),
        }

    plan = ctx.plan_engine.create_plan(
        description=f"Prepare demo '{demo.name}' — push {len(all_steps)} config change(s)",
        steps=all_steps, on_failure="stop",
        on_complete={"handler": "demo_activation",
                     "demo_id": demo.id, "demo_name": demo.name},
    )
    record_event(principal, "demo.prepare_fragment", resource=resource,
                 details={"plan_id": plan.plan_id, "applied": applied,
                          "step_count": len(all_steps)})
    result = await operations.execute_gated_plan(ctx.plan_engine, plan.plan_id)
    result["demo_id"] = demo.id
    result["applied"] = applied
    result["warnings"] = warnings
    return result


async def end_fragment_demo_core(ctx, demo, principal) -> Dict[str, Any]:
    """Push each device's BASE values back for keys this demo owns (deactivate-
    with-restore), in one gated plan; ``active`` flips False on completion. When
    nothing was pushed, degrade to a plain (no-push) deactivate."""
    from admz import operations
    from admz.audit import record_event
    from admz.demos.actions import DemoActionError, deactivate_demo_core
    from admz.snapshot.models import DriftField

    targets = service.resolve_devices(demo, ctx.registry)
    if not targets:
        raise DemoActionError("This demo has no devices.")

    all_steps: List[dict] = []
    warnings: List[str] = []
    for d in targets:
        did = d.get("device_id")
        if not did:
            continue
        # Fresh check so base_value reflects the current baseline.
        report = await ctx.drift_detector.check_drift(did)
        owned = [f for f in report.fields
                 if f.owner == demo.id and f.bucket in ("demo_set", "demo_broken")]
        restore: List[Any] = []
        for f in owned:
            # demo_set: `expected` already holds the base. demo_broken: `expected`
            # holds the DEMO value, so use `base_value` (the baseline).
            base = f.base_value if f.bucket == "demo_broken" else f.expected
            if base is None or str(base) == "<missing>":
                warnings.append(f"{f.facet}/{f.path} on {did}: no baseline value to restore")
                continue
            restore.append(DriftField(
                facet=f.facet, path=f.path, expected=str(base),
                actual=f.actual, canonical_key=f.canonical_key))
        if not restore:
            continue
        spec = ctx.restore_builder.build_targeted_revert_plan(did, restore)
        all_steps.extend(spec.get("steps", []))
        warnings.extend(spec.get("warnings", []))

    if not all_steps:
        return deactivate_demo_core(ctx, demo, principal)

    plan = ctx.plan_engine.create_plan(
        description=f"End demo '{demo.name}' — restore base config ({len(all_steps)} change(s))",
        steps=all_steps, on_failure="stop",
        on_complete={"handler": "demo_deactivation",
                     "demo_id": demo.id, "demo_name": demo.name},
    )
    record_event(principal, "demo.end_fragment", resource=f"demo:{demo.id}",
                 details={"plan_id": plan.plan_id, "step_count": len(all_steps)})
    result = await operations.execute_gated_plan(ctx.plan_engine, plan.plan_id)
    result["demo_id"] = demo.id
    result["warnings"] = warnings
    return result


# ── Completion handlers (registered in plans/completion.py) ──────────────────


def _flip_demo_active(plan, args: Dict[str, Any], active: bool) -> None:
    """Flip ``demo.active`` via the app context (web process). Records an audit
    row. Degrades to a note if the context isn't reachable."""
    from admz.audit import record_event

    try:
        from admz.api.context import get_context
        ctx = get_context()
    except Exception:  # noqa: BLE001 — only reachable if gating is relaxed off-web
        plan.completion_note = "config pushed, but the demo's active state couldn't be updated here"
        return
    demo_id = args.get("demo_id")
    demo = ctx.demo_store.get(demo_id) if demo_id else None
    if demo is None:
        plan.completion_note = f"demo {demo_id} not found after the plan ran"
        return
    if active:
        # The world may have changed between approval and completion — re-check
        # overlap before claiming the keys.
        from admz.demos import fragments as fr
        others = [d for d in ctx.demo_store.list() if d.active and d.id != demo.id]
        if fr.overlap_conflicts(ctx.git_repo, demo, others, ctx.registry):
            plan.completion_note = (
                "Config pushed, but another active demo now claims the same key(s) — "
                "not marking active. Deactivate the other demo, then adopt.")
            return
    demo.active = active
    ctx.demo_store.update(demo)
    plan.completion_note = (
        f"Demo '{demo.name}' is now active." if active
        else f"Demo '{demo.name}' ended — devices restored to baseline.")
    try:
        record_event(
            SimpleNamespace(name=f"demo:{demo.name}", source="plan-completion"),
            "demo.activated" if active else "demo.deactivated",
            resource=f"demo:{demo.id}", success=True,
            details={"name": demo.name, "plan_id": getattr(plan, "plan_id", None)})
    except Exception:  # noqa: BLE001 — audit best-effort
        logger.debug("activation audit failed", exc_info=True)


def on_activation_complete(plan, args: Dict[str, Any], registry: Any = None) -> None:
    """``demo_activation`` handler: flip active True only on a COMPLETED push."""
    from admz.plans.models import PlanStatus

    if getattr(plan, "status", None) != PlanStatus.COMPLETED:
        plan.completion_note = (
            "Demo stays inactive — the config push didn't fully complete. Its "
            "half-pushed keys read as candidate drift; re-run prepare to converge.")
        return
    _flip_demo_active(plan, args, True)


def on_deactivation_complete(plan, args: Dict[str, Any], registry: Any = None) -> None:
    """``demo_deactivation`` handler: flip active False only on a COMPLETED restore."""
    from admz.plans.models import PlanStatus

    if getattr(plan, "status", None) != PlanStatus.COMPLETED:
        plan.completion_note = (
            "Demo stays active — the base restore didn't fully complete; owned keys "
            "read as demo_broken (a targeted revert repairs them). Re-run to converge.")
        return
    _flip_demo_active(plan, args, False)
