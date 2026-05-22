"""REST routes for config snapshot, restore, diff, and drift."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from admz.api.context import AppContext, get_context
from admz.exceptions import DeviceNotFoundError

router = APIRouter()


class SnapshotDeviceRequest(BaseModel):
    device_id: str
    message: Optional[str] = None


class SnapshotFleetRequest(BaseModel):
    tag_filter: Optional[str] = None
    message: Optional[str] = None


class RestoreRequest(BaseModel):
    device_id: str
    ref: str = "HEAD"
    facets: Optional[List[str]] = None


@router.post("/snapshot/device")
async def snapshot_device(
    request: Request,
    req: SnapshotDeviceRequest,
    ctx: AppContext = Depends(get_context),
):
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    resource = f"device:{req.device_id}"

    if not ctx.registry.device_exists(req.device_id):
        record_event(principal, "snapshot.device", resource=resource,
                     success=False, error_message="not-found")
        raise HTTPException(status_code=404, detail=f"Device not found: {req.device_id}")
    snapshot = await ctx.snapshot_engine.snapshot_device(
        req.device_id, message=req.message
    )
    record_event(principal, "snapshot.device", resource=resource,
                 details={"has_message": bool(req.message)})
    return snapshot.to_summary()


@router.post("/snapshot/fleet")
async def snapshot_fleet(
    request: Request,
    req: SnapshotFleetRequest,
    ctx: AppContext = Depends(get_context),
):
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    snapshots = await ctx.snapshot_engine.snapshot_fleet(
        tag_filter=req.tag_filter, message=req.message
    )
    record_event(principal, "snapshot.fleet",
                 details={"tag_filter": req.tag_filter,
                          "count": len(snapshots)})
    return {
        "count": len(snapshots),
        "results": [s.to_summary() for s in snapshots],
    }


@router.post("/snapshot/restore")
async def restore_device(
    request: Request,
    req: RestoreRequest,
    ctx: AppContext = Depends(get_context),
):
    """CR-3: requires an authenticated principal. Restore is a
    data-loss operation — it rewrites a live device's config from
    a historical commit. Anonymous restores from the network would
    be a recipe for catastrophic mishaps."""
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    resource = f"device:{req.device_id}"

    if not ctx.registry.device_exists(req.device_id):
        record_event(principal, "snapshot.restore", resource=resource,
                     success=False, error_message="not-found")
        raise HTTPException(status_code=404, detail=f"Device not found: {req.device_id}")

    plan_spec = ctx.restore_builder.build_restore_plan(
        req.device_id, ref=req.ref, facet_names=req.facets
    )
    if not plan_spec["steps"]:
        record_event(principal, "snapshot.restore", resource=resource,
                     details={"ref": req.ref, "outcome": "no-steps"})
        return {
            "message": f"No config found for {req.device_id} at {req.ref}",
            "warnings": plan_spec.get("warnings", []),
        }
    try:
        plan = ctx.plan_engine.create_plan(
            description=plan_spec["description"],
            steps=plan_spec["steps"],
            on_failure=plan_spec["on_failure"],
        )
    except ValueError as e:
        record_event(principal, "snapshot.restore", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    record_event(principal, "snapshot.restore", resource=resource,
                 details={"ref": req.ref, "plan_id": plan.plan_id,
                          "step_count": len(plan_spec["steps"])})
    return {
        "warnings": plan_spec.get("warnings", []),
        "source_ref": plan_spec.get("source_ref", req.ref),
        **plan.to_summary(),
    }


@router.get("/snapshot/diff/{device_id}")
async def diff_device(
    device_id: str,
    ref_a: str = Query("HEAD~1"),
    ref_b: str = Query("HEAD"),
    ctx: AppContext = Depends(get_context),
):
    device_path = f"fleet/{device_id}/"
    diff_text = ctx.git_repo.diff(ref_a, ref_b, path=device_path)
    history = ctx.git_repo.log(path=device_path, max_count=10)
    return {
        "device_id": device_id,
        "ref_a": ref_a,
        "ref_b": ref_b,
        "diff": diff_text if diff_text else "(no changes)",
        "recent_history": history,
    }


@router.get("/snapshot/drift")
async def check_drift(
    device_id: Optional[str] = Query(None),
    tag_filter: Optional[str] = Query(None),
    ctx: AppContext = Depends(get_context),
):
    if device_id:
        if not ctx.registry.device_exists(device_id):
            raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")
        report = await ctx.drift_detector.check_drift(device_id)
        return report.to_summary()
    reports = await ctx.drift_detector.check_fleet_drift(tag_filter=tag_filter)
    return {
        "count": len(reports),
        "drifted": sum(1 for r in reports if r.has_drift),
        "reports": [r.to_summary() for r in reports],
    }
