"""REST routes for config snapshot, restore, diff, and drift."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, field_validator

from admz.api.context import AppContext, get_context
from admz.exceptions import DeviceNotFoundError
from admz.validators import validate_git_ref, validate_identifier

router = APIRouter()


class SnapshotDeviceRequest(BaseModel):
    device_id: str
    message: Optional[str] = None

    @field_validator("device_id")
    @classmethod
    def _check_device_id(cls, v: str) -> str:
        return validate_identifier(v, "device_id")


class SnapshotFleetRequest(BaseModel):
    tag_filter: Optional[str] = None
    message: Optional[str] = None


class RestoreRequest(BaseModel):
    device_id: str
    # None -> restore the device's blessed baseline (ADR-0031). An explicit
    # ref restores from that commit/tag/branch instead.
    ref: Optional[str] = None
    facets: Optional[List[str]] = None
    note: Optional[str] = None

    @field_validator("device_id")
    @classmethod
    def _check_device_id(cls, v: str) -> str:
        return validate_identifier(v, "device_id")

    @field_validator("ref")
    @classmethod
    def _check_ref(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return validate_git_ref(v)

    @field_validator("facets")
    @classmethod
    def _check_facets(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        for f in v:
            validate_identifier(f, "facet_name")
        return v


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


class AcceptBaselineRequest(BaseModel):
    device_id: str
    # None -> accept the device's latest recorded observation.
    commit_sha: Optional[str] = None
    note: Optional[str] = None

    @field_validator("device_id")
    @classmethod
    def _check_device_id(cls, v: str) -> str:
        return validate_identifier(v, "device_id")

    @field_validator("commit_sha")
    @classmethod
    def _check_commit_sha(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return validate_git_ref(v)


@router.post("/snapshot/accept-baseline")
async def accept_baseline(
    request: Request,
    req: AcceptBaselineRequest,
    ctx: AppContext = Depends(get_context),
):
    """Bless a commit (default: the latest observation) as a device's
    baseline (ADR-0031 slice 3). Metadata-only, but it re-points what
    drift compares against and what restore replays — so, like restore,
    it requires an authenticated principal (CR-3 parity)."""
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    resource = f"device:{req.device_id}"

    if not ctx.registry.device_exists(req.device_id):
        record_event(principal, "snapshot.accept_baseline", resource=resource,
                     success=False, error_message="not-found")
        raise HTTPException(
            status_code=404, detail=f"Device not found: {req.device_id}"
        )

    device_info = ctx.registry.get_device_info(req.device_id)
    target = req.commit_sha or device_info.get("latest_observed_sha")
    if not target:
        record_event(principal, "snapshot.accept_baseline", resource=resource,
                     success=False, error_message="no-target")
        raise HTTPException(
            status_code=400,
            detail=(
                "No commit to accept: pass commit_sha, or snapshot/audit "
                "the device first so there is a recorded observation."
            ),
        )

    facets = ctx.git_repo.list_facets_at(req.device_id, target)
    if not facets:
        record_event(principal, "snapshot.accept_baseline", resource=resource,
                     success=False, error_message="no-config-at-commit")
        raise HTTPException(
            status_code=400,
            detail=(
                f"Commit {target[:12]} holds no config for "
                f"{req.device_id} — not accepting it as a baseline."
            ),
        )

    previous = device_info.get("baseline_sha")
    ctx.registry.set_config_pointers(req.device_id, baseline_sha=target)
    note = (req.note or "").strip()
    record_event(principal, "snapshot.accept_baseline", resource=resource,
                 details={"baseline_sha": target, "previous": previous,
                          **({"note": note} if note else {})})
    if note:
        try:
            import time as _t
            import yaml as _yaml
            device_dir = ctx.git_repo.device_path(req.device_id)
            device_dir.mkdir(parents=True, exist_ok=True)
            (device_dir / "BASELINE.yaml").write_text(
                _yaml.safe_dump({
                    "accepted_at": _t.time(),
                    "accepted_by": str(principal),
                    "baseline_sha": target,
                    "note": note,
                }, default_flow_style=False, sort_keys=True)
            )
            ctx.git_repo.commit_snapshot(
                req.device_id,
                message=f"Accept baseline: {req.device_id}",
                auto_push=True,
            )
        except Exception:
            import logging as _log
            _log.getLogger(__name__).warning(
                "baseline note commit failed for %s", req.device_id, exc_info=True
            )
    return {
        "success": True,
        "device_id": req.device_id,
        "baseline_sha": target,
        "previous_baseline_sha": previous,
        "facets": facets,
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
    resolved_ref = plan_spec.get("source_ref", req.ref)
    if not plan_spec["steps"]:
        record_event(principal, "snapshot.restore", resource=resource,
                     details={"ref": resolved_ref, "outcome": "no-steps"})
        return {
            "message": f"No config found for {req.device_id} at {resolved_ref}",
            "warnings": plan_spec.get("warnings", []),
        }
    note = (req.note or "").strip()
    description = plan_spec["description"]
    if note:
        description = f"{description} — {note}"
    try:
        plan = ctx.plan_engine.create_plan(
            description=description,
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
