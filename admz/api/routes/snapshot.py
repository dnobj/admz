"""REST routes for config snapshot, restore, diff, and drift."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, field_validator

from admz.api.context import AppContext, get_context
from admz.exceptions import DeviceNotFoundError
from admz.validators import validate_git_ref, validate_identifier

logger = logging.getLogger(__name__)

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


def _reject_accept_with_active_demos(ctx, device_id: str, device_info: dict) -> None:
    """The ADR-0047 accept-baseline guard (H1 — non-negotiable).

    An observation commit holds the device's LIVE state, which includes every
    value an active demo set. Blessing it would silently bake the demo's config
    into the base — after which deactivating the demo pushes nothing and the
    demo config survives forever, labelled "baseline". Refuse with names.
    """
    try:
        from admz.demos.fragments import owning_demos

        owners = owning_demos(
            ctx.git_repo, ctx.demo_store.list(), device_id, device_info)
    except Exception:  # noqa: BLE001 — guard failure must not block accepts
        logger.warning("accept-baseline demo guard unavailable for %s",
                       device_id, exc_info=True)
        return
    if owners:
        names = ", ".join(
            f"'{d.name}' ({n} key{'s' if n != 1 else ''})" for d, n in owners)
        raise HTTPException(
            status_code=409,
            detail=(
                f"{device_id} has active demo config loaded — accepting now "
                f"would bake it into the baseline. Deactivate {names} first, "
                "or revert their keys."),
        )


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
    device_info["device_id"] = req.device_id
    _reject_accept_with_active_demos(ctx, req.device_id, device_info)
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
        # Never revert "demo_set" rows (ADR-0047): those values are an active
        # demo's config, deliberately different from base — a whole-device
        # revert would silently kick the demo off the device. Deactivating the
        # demo is the way to undo them. Note demo_broken rows keep the DEMO's
        # value in ``expected``, so reverting them REPAIRS the demo.
        fields = report.real_fields
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
        info["device_id"] = did
        try:
            _reject_accept_with_active_demos(ctx, did, info)
        except HTTPException as e:
            # Bulk semantics: skip-and-report rather than fail the whole set.
            skipped.append({"device_id": did, "reason": "active-demo-config",
                            "detail": e.detail})
            continue
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


# Commit-message prefix -> a short type label the history UI badges + icons.
_HISTORY_TYPES = (
    ("Accept baseline", "baseline"),
    ("Audit:", "audit"),
    ("Snapshot", "snapshot"),
    ("Restore", "restore"),
    ("Delete", "delete"),
)


def _classify_commit(message: str) -> str:
    for prefix, label in _HISTORY_TYPES:
        if message.startswith(prefix):
            return label
    return "other"


@router.get("/snapshot/history/{device_id}")
async def device_history(
    device_id: str,
    limit: int = Query(40, ge=1, le=200),
    ctx: AppContext = Depends(get_context),
):
    """Config commit history for one device (newest first), annotated with
    which commit is the current baseline / latest observation and a type
    label per commit. Read-only — the same versioned config the drift diff
    already exposes, surfaced as a timeline."""
    if not ctx.registry.device_exists(device_id):
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")
    info = ctx.registry.get_device_info(device_id)
    baseline_sha = info.get("baseline_sha")
    latest_sha = info.get("latest_observed_sha")
    commits = ctx.git_repo.log(path=f"fleet/{device_id}/", max_count=limit)
    for c in commits:
        sha = c.get("sha", "")
        c["short_sha"] = sha[:12]
        c["type"] = _classify_commit(c.get("message", ""))
        c["is_baseline"] = bool(baseline_sha) and sha == baseline_sha
        c["is_latest_observed"] = bool(latest_sha) and sha == latest_sha
    return {
        "device_id": device_id,
        "baseline_sha": baseline_sha,
        "latest_observed_sha": latest_sha,
        "count": len(commits),
        "commits": commits,
    }


@router.get("/snapshot/history/{device_id}/{sha}/diff")
async def device_history_diff(
    device_id: str,
    sha: str,
    ctx: AppContext = Depends(get_context),
):
    """Unified diff a single commit introduced for this device (vs its
    parent, or everything it added for a root commit)."""
    validate_identifier(device_id, "device_id")
    validate_git_ref(sha)
    if not ctx.registry.device_exists(device_id):
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")
    diff_text = ctx.git_repo.diff_commit(sha, path=f"fleet/{device_id}/")
    return {
        "device_id": device_id,
        "sha": sha,
        "short_sha": sha[:12],
        "diff": diff_text if diff_text.strip() else "(no config changes in this commit)",
    }


# --------------------------------------------------------------------------
# Named config baselines (alternate configurations), ADR-0031 follow-on.
# A named baseline = a name -> a git commit holding a saved full config for
# the device. The ACTIVE one is whichever commit == the device's baseline_sha,
# so "make active" reuses POST /snapshot/accept-baseline (with that commit_sha)
# and "push to the device" reuses POST /snapshot/revert — this surface only
# manages the name->commit mapping.
# --------------------------------------------------------------------------

class SaveBaselineRequest(BaseModel):
    name: str
    commit_sha: Optional[str] = None  # default: the device's current baseline
    note: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        import re
        v = (v or "").strip()
        if not v:
            raise ValueError("name is required")
        if len(v) > 64:
            raise ValueError("name too long (max 64)")
        if not re.fullmatch(r"[A-Za-z0-9 ._-]+", v):
            raise ValueError("name may only contain letters, digits, space, . _ -")
        return v

    @field_validator("commit_sha")
    @classmethod
    def _check_sha(cls, v: Optional[str]) -> Optional[str]:
        return validate_git_ref(v) if v else None


@router.get("/snapshot/baselines/{device_id}")
async def list_baselines(device_id: str, ctx: AppContext = Depends(get_context)):
    """Named config baselines (alternate configs) for a device, with the
    active one flagged (its commit == the device's ``baseline_sha``)."""
    if not ctx.registry.device_exists(device_id):
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")
    info = ctx.registry.get_device_info(device_id)
    baseline_sha = info.get("baseline_sha")
    try:
        items = ctx.registry.list_named_baselines(device_id)
    except NotImplementedError:
        items = []
    active = None
    for b in items:
        b["short_sha"] = (b.get("commit_sha") or "")[:12]
        b["is_active"] = bool(baseline_sha) and b.get("commit_sha") == baseline_sha
        if b["is_active"]:
            active = b["name"]
    return {
        "device_id": device_id,
        "baseline_sha": baseline_sha,
        "active_name": active,
        "baselines": items,
    }


@router.post("/snapshot/baselines/{device_id}")
async def save_baseline(
    request: Request,
    device_id: str,
    req: SaveBaselineRequest,
    ctx: AppContext = Depends(get_context),
):
    """Save the current baseline (or an explicit ``commit_sha``) as a named
    alternate config. Authenticated + audited, like accept-baseline."""
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    resource = f"device:{device_id}"

    if not ctx.registry.device_exists(device_id):
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")
    info = ctx.registry.get_device_info(device_id)
    target = req.commit_sha or info.get("baseline_sha")
    if not target:
        raise HTTPException(
            status_code=400,
            detail="No commit to save — snapshot the device first, or pass commit_sha.",
        )
    if not ctx.git_repo.list_facets_at(device_id, target):
        raise HTTPException(
            status_code=400,
            detail=f"Commit {target[:12]} holds no config for {device_id}.",
        )
    try:
        ctx.registry.save_named_baseline(
            device_id, req.name, target,
            note=(req.note or "").strip(), created_by=str(principal),
        )
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Backend does not support named baselines.")
    record_event(principal, "snapshot.save_named_baseline", resource=resource,
                 details={"name": req.name, "commit_sha": target})
    return {"success": True, "device_id": device_id, "name": req.name, "commit_sha": target}


@router.delete("/snapshot/baselines/{device_id}/{name}")
async def delete_baseline(
    request: Request,
    device_id: str,
    name: str,
    ctx: AppContext = Depends(get_context),
):
    """Delete a named alternate config (the git commit stays in history)."""
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    if not ctx.registry.device_exists(device_id):
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")
    try:
        removed = ctx.registry.delete_named_baseline(device_id, name)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Backend does not support named baselines.")
    if not removed:
        raise HTTPException(status_code=404, detail=f"No named baseline '{name}' on {device_id}.")
    record_event(principal, "snapshot.delete_named_baseline",
                 resource=f"device:{device_id}", details={"name": name})
    return {"success": True, "device_id": device_id, "name": name}


# --------------------------------------------------------------------------
# Scenarios (ADR-0044) — a named alternate config activated as a TEMPORARY push
# across a device or a tag-group, with the blessed baseline left UNCHANGED so
# "return to baseline" is a clean snap-back. Storage reuses named baselines; the
# per-device `active_scenario` marker records which one is live. This supersedes
# the old apply-tag-baseline (which moved the baseline — the very thing we don't
# want for temporary demo/test modes).
# --------------------------------------------------------------------------

class ScenarioSaveRequest(BaseModel):
    name: str
    # Exactly one of device_id / tag identifies the target(s).
    device_id: Optional[str] = None
    tag: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        import re
        v = (v or "").strip()
        if not v or len(v) > 64 or not re.fullmatch(r"[A-Za-z0-9 ._-]+", v):
            raise ValueError("name must be 1-64 chars: letters, digits, space, . _ -")
        return v


class ScenarioActivateRequest(ScenarioSaveRequest):
    """Same shape as save (name + device_id|tag)."""


class ScenarioReturnRequest(BaseModel):
    device_id: Optional[str] = None
    tag: Optional[str] = None


def _scenario_targets(
    ctx: "AppContext", device_id: Optional[str], tag: Optional[str]
):
    """Resolve target device-info dicts for a scenario op. Exactly one of
    ``device_id`` / ``tag`` must be given (per-device vs the tag-group). Returns
    ``(devices, error_or_None)``."""
    if bool(device_id) == bool(tag):
        return [], "Specify exactly one of device_id or tag."
    if device_id:
        if not ctx.registry.device_exists(device_id):
            return [], f"Device not found: {device_id}"
        info = ctx.registry.get_device_info(device_id)
        info["device_id"] = device_id
        return [info], None
    devices = [d for d in ctx.registry.list_devices() if tag in (d.get("tags") or [])]
    return devices, None


@router.get("/snapshot/scenarios")
async def list_scenarios(tag: str = Query(...), ctx: AppContext = Depends(get_context)):
    """Scenario names available across a tag's devices, each with how many of the
    tag's devices have it saved (so the UI can say '3 of 6 devices have demo'),
    plus how many devices are currently IN each scenario."""
    devices = [d for d in ctx.registry.list_devices() if tag in (d.get("tags") or [])]
    counts: Dict[str, int] = {}
    active: Dict[str, int] = {}
    for d in devices:
        did = d.get("device_id")
        try:
            names = {b.get("name") for b in ctx.registry.list_named_baselines(did)}
        except NotImplementedError:
            names = set()
        for n in names:
            if n:
                counts[n] = counts.get(n, 0) + 1
        cur = d.get("active_scenario")
        if cur:
            active[cur] = active.get(cur, 0) + 1
    return {
        "tag": tag,
        "devices": len(devices),
        "scenarios": [{"name": n, "count": counts[n]} for n in sorted(counts)],
        "active": active,
    }


@router.post("/snapshot/scenario/save")
async def save_scenario(
    request: Request,
    req: ScenarioSaveRequest,
    ctx: AppContext = Depends(get_context),
):
    """Capture the CURRENT live config of the target device(s) as a named
    scenario, WITHOUT moving the baseline (snapshot bless=False → named
    baseline). Not gated (a read + git commit; no device write)."""
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    targets, err = _scenario_targets(ctx, req.device_id, req.tag)
    if err:
        raise HTTPException(status_code=400, detail=err)

    saved: List[str] = []
    failed: List[dict] = []
    for d in targets:
        did = d.get("device_id")
        if not did:
            continue
        try:
            snap = await ctx.snapshot_engine.snapshot_device(
                did, message=f"scenario:{req.name}", bless=False,
            )
            # The commit holding this device's just-captured config: the new
            # commit if one was made, else the current HEAD tree (which already
            # holds it). Same resolution the engine's blessing uses.
            commit = snap.git_sha or ctx.git_repo.head_sha()
            if not commit or not ctx.git_repo.list_facets_at(did, commit):
                failed.append({"device_id": did, "error": "no config captured"})
                continue
            ctx.registry.save_named_baseline(
                did, req.name, commit, created_by=str(principal),
            )
            saved.append(did)
        except Exception as exc:  # noqa: BLE001 — per-device, keep going
            failed.append({"device_id": did, "error": f"{type(exc).__name__}: {exc}"})

    record_event(principal, "snapshot.scenario_save",
                 resource=f"scenario:{req.name}",
                 details={"name": req.name, "saved": saved, "failed": failed})
    return {
        "success": bool(saved), "name": req.name, "saved": saved, "failed": failed,
        "message": (f"Saved scenario '{req.name}' on {len(saved)} device(s)"
                    + (f"; {len(failed)} failed." if failed else ".")),
    }


@router.post("/snapshot/scenario/activate")
async def activate_scenario(
    request: Request,
    req: ScenarioActivateRequest,
    ctx: AppContext = Depends(get_context),
):
    """Activate a named scenario on the target device(s): push each device's own
    saved config of that name in ONE gated plan, and mark it ``active_scenario``.
    The blessed baseline is NOT moved — this is a temporary mode. Devices without
    a scenario by that name are skipped + reported."""
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal
    from admz.snapshot.scenarios import activate_scenario_core

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    targets, err = _scenario_targets(ctx, req.device_id, req.tag)
    if err:
        raise HTTPException(status_code=400, detail=err)
    try:
        return await activate_scenario_core(ctx, req.name, targets, principal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/snapshot/scenario/return-to-baseline")
async def return_to_baseline(
    request: Request,
    req: ScenarioReturnRequest,
    ctx: AppContext = Depends(get_context),
):
    """Return the target device(s) to their blessed baseline in ONE gated plan
    and clear the ``active_scenario`` marker. Devices with no baseline are
    skipped."""
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal
    from admz.snapshot.scenarios import return_to_baseline_core

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    targets, err = _scenario_targets(ctx, req.device_id, req.tag)
    if err:
        raise HTTPException(status_code=400, detail=err)
    try:
        return await return_to_baseline_core(ctx, targets, principal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
            # canonical_key for the "exclude from tracking" action — normally
            # set by the drift loop; backfill here for robustness.
            if not fld.get("canonical_key") and facet is not None:
                fld["canonical_key"] = facet.canonical_key(fld.get("path"))
            revertable = False
            reason = "read-only"
            if facet is not None and facet.op_revertable(fld.get("path")):
                # API-backed facet: revert writes the whole baseline object
                # through the facet's own setter — covers value changes AND
                # live-added fields (the write-back removes additions).
                revertable = True
            elif str(fld.get("expected")) == "<missing>":
                reason = "added"  # appeared live; no baseline value to restore
            elif facet is not None and facet.revert_param(
                fld.get("path"), fld.get("expected")
            ) is not None:
                revertable = True
            # "demo_set" rows aren't drift (ADR-0047) — the value belongs to an
            # active demo. Reverting one would kick the demo off the key, so
            # the row is display-only; deactivate the demo to undo it.
            if fld.get("bucket") == "demo_set":
                revertable = False
                reason = "demo-owned"
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


# ---------------------------------------------------------------------------
# Config-tracking ignore rules (scoped: global / tag:<tag> / device:<id>)
# ---------------------------------------------------------------------------
class IgnoreRuleModel(BaseModel):
    key: str
    scope: str = "global"

    @field_validator("key")
    @classmethod
    def _check_key(cls, v: str) -> str:
        v = (v or "").strip()
        if not v or len(v) > 512 or "\n" in v:
            raise ValueError("key must be a non-empty single-line pattern")
        return v

    @field_validator("scope")
    @classmethod
    def _check_scope(cls, v: str) -> str:
        v = (v or "global").strip() or "global"
        if v == "global" or v.startswith("tag:") or v.startswith("device:"):
            return v
        raise ValueError("scope must be 'global', 'tag:<tag>', or 'device:<id>'")


class IgnoreRulesRequest(BaseModel):
    add: Optional[List[IgnoreRuleModel]] = None
    remove: Optional[List[IgnoreRuleModel]] = None


@router.get("/config/ignore-rules")
async def list_ignore_rules(ctx: AppContext = Depends(get_context)):
    """All config-tracking ignore rules (scoped store + legacy global list)."""
    from admz.snapshot.ignore import get_rules
    return {"rules": get_rules()}


@router.post("/config/ignore-rules")
async def update_ignore_rules(
    request: Request,
    req: IgnoreRulesRequest,
    ctx: AppContext = Depends(get_context),
):
    """Add/remove scoped ignore rules. Authenticated (changes what the fleet
    tracks) + audited. The in-context "exclude from tracking" UI POSTs here."""
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal
    from admz.snapshot import ignore

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)

    added = [r.model_dump() for r in (req.add or [])]
    removed = [r.model_dump() for r in (req.remove or [])]
    if added:
        ignore.add_rules(added)
    if removed:
        ignore.remove_rules(removed)
    record_event(
        principal, "config.ignore_rules", resource="fleet",
        details={"added": added, "removed": removed},
    )
    return {"rules": ignore.get_rules()}
