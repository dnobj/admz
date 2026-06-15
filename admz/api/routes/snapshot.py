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
    from admz import operations as _ops
    _ops.refresh_drift_after_accept(
        req.device_id, target, device_info.get("latest_observed_sha")
    )
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


class RevertFieldSelector(BaseModel):
    """A single drifted field a caller chose to revert: which device, which
    facet, and the flattened field path within that facet (as surfaced by the
    drift report). ``path``/``facet`` are matched verbatim against the live
    drift diff, so they aren't constrained to the identifier charset."""
    device_id: str
    facet: str
    path: str

    @field_validator("device_id")
    @classmethod
    def _check_did(cls, v: str) -> str:
        return validate_identifier(v, "device_id")


class RevertRequest(BaseModel):
    """One or more devices to revert to their blessed baseline.

    A single combined plan is built across every device and gated ONCE at
    the confirm widget (the plan engine already serializes multi-device
    plans — ``device_id="multiple"``). ``note`` is an audit annotation:
    revert re-applies the existing baseline to the device and makes NO git
    change, so the note lives only in the plan description + audit log.

    ``fields`` scopes the revert to a chosen SUBSET of the drifted fields
    (the UI's per-row checkboxes). When omitted, every auto-revertable
    drifted field on each device is reverted (device-level revert).
    """
    device_ids: List[str]
    note: Optional[str] = None
    facets: Optional[List[str]] = None
    fields: Optional[List[RevertFieldSelector]] = None

    @field_validator("device_ids")
    @classmethod
    def _check_ids(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("device_ids must not be empty")
        return [validate_identifier(d, "device_id") for d in v]

    @field_validator("facets")
    @classmethod
    def _check_facets(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        for f in v:
            validate_identifier(f, "facet_name")
        return v


@router.post("/snapshot/revert")
async def revert_devices(
    request: Request,
    req: RevertRequest,
    ctx: AppContext = Depends(get_context),
):
    """Revert one or more devices to their blessed baseline in a single
    gated plan. CR-3: authenticated principal required (data-loss). The
    response is the standard blocked envelope — approve at ``confirm_url``
    to run the whole plan at once."""
    from admz import operations
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)

    # TARGETED revert: undo only the fields that actually drifted (back to
    # their baseline values), NOT a full-baseline re-push. We check drift per
    # device to get the exact diff + each field's baseline value, then build a
    # minimal plan. (Full restore-from-a-commit stays on build_restore_plan,
    # reachable via the MCP restore_device tool.)
    #
    # When the caller passes ``fields``, scope the revert to that exact subset
    # (the UI's per-row checkboxes) — matched by (device_id, facet, path)
    # against the live drift diff. With no ``fields``, every revertable drifted
    # field on each device is reverted (device-level revert).
    selected_by_device = None
    if req.fields is not None:
        selected_by_device = {}
        for sel in req.fields:
            selected_by_device.setdefault(sel.device_id, set()).add(
                (sel.facet, sel.path)
            )

    all_steps: List[dict] = []
    warnings: List[str] = []
    missing: List[str] = []
    no_config: List[str] = []
    for did in req.device_ids:
        if not ctx.registry.device_exists(did):
            missing.append(did)
            continue
        report = await ctx.drift_detector.check_drift(did)
        fields = report.fields
        if selected_by_device is not None:
            chosen = selected_by_device.get(did, set())
            fields = [f for f in fields if (f.facet, f.path) in chosen]
        spec = ctx.restore_builder.build_targeted_revert_plan(did, fields)
        if not spec["steps"]:
            no_config.append(did)
        all_steps.extend(spec["steps"])
        warnings.extend(spec.get("warnings", []))

    if not all_steps:
        record_event(principal, "snapshot.revert", resource="device:multiple",
                     details={"device_ids": req.device_ids, "outcome": "no-steps"})
        return {
            "message": (
                "Nothing to revert — the selected device(s) are in sync, or "
                "the drifted fields aren't auto-revertable (read-only / "
                "uncategorized)."
            ),
            "warnings": warnings,
            "missing": missing,
            "no_config": no_config,
        }

    device_count = len({s["device_id"] for s in all_steps})
    note = (req.note or "").strip()
    description = (
        f"Revert {device_count} device" + ("s" if device_count != 1 else "")
        + " to baseline"
    )
    if note:
        description = f"{description} — {note}"

    try:
        plan = ctx.plan_engine.create_plan(
            description=description, steps=all_steps, on_failure="stop",
        )
    except ValueError as e:
        record_event(principal, "snapshot.revert", resource="device:multiple",
                     success=False, error_message=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    record_event(
        principal, "snapshot.revert", resource="device:multiple",
        details={"device_ids": req.device_ids, "plan_id": plan.plan_id,
                 "step_count": len(all_steps), "device_count": device_count,
                 **({"note": note} if note else {})},
    )
    result = await operations.execute_gated_plan(ctx.plan_engine, plan.plan_id)
    # url_* plans come back blocked with confirm_url; pass through extras.
    result.setdefault("warnings", warnings)
    if missing:
        result["missing"] = missing
    return result


class AcceptBaselineBulkRequest(BaseModel):
    """Bless the current observed state of several devices as their new
    baselines in one combined git commit (Slice: drift visualization)."""
    device_ids: List[str]
    note: Optional[str] = None

    @field_validator("device_ids")
    @classmethod
    def _check_ids(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("device_ids must not be empty")
        return [validate_identifier(d, "device_id") for d in v]


@router.post("/snapshot/accept-baseline-bulk")
async def accept_baseline_bulk(
    request: Request,
    req: AcceptBaselineBulkRequest,
    ctx: AppContext = Depends(get_context),
):
    """Accept the latest observation as baseline for many devices at once.

    Metadata-only (re-points each baseline pointer); when a ``note`` is
    given, every device's ``BASELINE.yaml`` is written and the whole set
    lands in a SINGLE commit (``Accept baseline: N devices — <note>``).
    CR-3 parity with single accept: authenticated principal required."""
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)

    note = (req.note or "").strip()
    accepted: List[dict] = []
    skipped: List[dict] = []
    for did in req.device_ids:
        if not ctx.registry.device_exists(did):
            skipped.append({"device_id": did, "reason": "not-found"})
            continue
        info = ctx.registry.get_device_info(did)
        target = info.get("latest_observed_sha")
        if not target:
            skipped.append({"device_id": did, "reason": "no-observation"})
            continue
        facets = ctx.git_repo.list_facets_at(did, target)
        if not facets:
            skipped.append({"device_id": did, "reason": "no-config-at-commit"})
            continue
        ctx.registry.set_config_pointers(did, baseline_sha=target)
        # Bulk accept always blesses the latest observation → the cache can
        # be marked in-sync deterministically (no re-probe needed).
        from admz import operations as _ops
        _ops.refresh_drift_after_accept(did, target, target)
        if note:
            try:
                import time as _t
                import yaml as _yaml
                device_dir = ctx.git_repo.device_path(did)
                device_dir.mkdir(parents=True, exist_ok=True)
                (device_dir / "BASELINE.yaml").write_text(
                    _yaml.safe_dump({
                        "accepted_at": _t.time(),
                        "accepted_by": str(principal),
                        "baseline_sha": target,
                        "note": note,
                    }, default_flow_style=False, sort_keys=True)
                )
            except Exception:
                import logging as _log
                _log.getLogger(__name__).warning(
                    "baseline note write failed for %s", did, exc_info=True
                )
        accepted.append({"device_id": did, "baseline_sha": target})

    # One combined commit for the whole accepted set (only if a note made
    # BASELINE.yaml files dirty; pointer moves alone touch no git state).
    committed_sha = None
    if accepted and note:
        try:
            ids = [a["device_id"] for a in accepted]
            committed_sha = ctx.git_repo.commit_fleet_snapshot(
                ids,
                message=f"Accept baseline: {len(ids)} device"
                        + ("s" if len(ids) != 1 else "") + f" — {note}",
            )
        except Exception:
            import logging as _log
            _log.getLogger(__name__).warning(
                "bulk baseline commit failed", exc_info=True
            )

    record_event(
        principal, "snapshot.accept_baseline_bulk", resource="device:multiple",
        details={"accepted": [a["device_id"] for a in accepted],
                 "skipped": skipped, "commit": committed_sha,
                 **({"note": note} if note else {})},
    )
    return {
        "success": True,
        "accepted": accepted,
        "skipped": skipped,
        "commit": committed_sha,
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
        summary = report.to_summary()
        # Annotate each drifted field with whether a TARGETED revert can write
        # it back — the UI uses this to enable/disable the per-row checkbox.
        # Uses the SAME facet.revert_param the revert plan builder uses, so the
        # checkbox state matches exactly what revert would actually do.
        from admz.snapshot.facets import get_facets_for_device

        device_info = ctx.registry.get_device_info(device_id)
        device_info["device_id"] = device_id
        facets_by_name = {
            f.name: f for f in get_facets_for_device(device_info)
        }
        for fld in summary.get("drifted_fields", []):
            facet = facets_by_name.get(fld.get("facet"))
            revertable = False
            reason = "read-only"
            if str(fld.get("expected")) == "<missing>":
                reason = "added"  # appeared live; no baseline value to restore
            elif facet is not None and facet.revert_param(
                fld.get("path"), fld.get("expected")
            ) is not None:
                revertable = True
            fld["revertable"] = revertable
            if not revertable:
                fld["revert_skip_reason"] = reason
        return summary
    reports = await ctx.drift_detector.check_fleet_drift(tag_filter=tag_filter)
    return {
        "count": len(reports),
        "drifted": sum(1 for r in reports if r.has_drift),
        "reports": [r.to_summary() for r in reports],
    }
