"""REST surface for event-pattern detection rules (ADR-0041 layer 3).

Rules fire **autonomously**, so creation requires an authenticated principal (the
creation is the human authorization), and a service-affecting action (ACS record/
bookmark) is refused unless the rule is explicitly ``pre_authorized``. Creating or
enabling a rule also ensures live ingest is running, so a rule never silently
never-fires.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from admz.api.context import AppContext, get_context
from admz.events.detections import (
    EventDetection, SAFE_ACTIONS, SERVICE_AFFECTING_ACTIONS,
)

router = APIRouter()

_ALL_ACTIONS = SAFE_ACTIONS | SERVICE_AFFECTING_ACTIONS


class CreateDetectionRequest(BaseModel):
    name: str = ""
    source: str = "device"
    device_id: Optional[str] = None
    tag: Optional[str] = None
    match: Dict[str, Any] = Field(default_factory=dict)
    action_type: str = "notify"
    action_params: Dict[str, Any] = Field(default_factory=dict)
    pre_authorized: bool = False
    cooldown_seconds: int = 0


async def _ensure_ingest(ctx: AppContext) -> None:
    """Turn live ingest on (a rule is useless if nothing is streaming)."""
    from admz.fleet_settings import fleet_settings

    fleet_settings.set("event_ingest_enabled", "true")
    try:
        await ctx.event_supervisor.start()
        await ctx.event_supervisor.reconcile()
    except Exception:  # noqa: BLE001
        pass


def _reject_unauthorized_action(action_type: str, pre_authorized: bool) -> None:
    if action_type not in _ALL_ACTIONS:
        raise HTTPException(400, f"unknown action_type {action_type!r}; one of {sorted(_ALL_ACTIONS)}")
    if action_type in SERVICE_AFFECTING_ACTIONS and not pre_authorized:
        raise HTTPException(
            400,
            f"action {action_type!r} is service-affecting and fires autonomously; "
            f"set pre_authorized=true to explicitly allow it.",
        )


@router.get("/api/detections")
async def list_detections(ctx: AppContext = Depends(get_context)):
    # The ACS record/bookmark action only makes sense (and the camera picker only
    # works) when the ACS Pro module is connected, so the builder gates on this.
    try:
        from admz.modules.acs_pro.config import acs_enabled
        acs_on = bool(acs_enabled())
    except Exception:  # noqa: BLE001
        acs_on = False
    return {
        "success": True,
        "detections": [d.to_dict() for d in ctx.detection_store.list()],
        "action_types": sorted(_ALL_ACTIONS),
        "service_affecting": sorted(SERVICE_AFFECTING_ACTIONS),
        "acs_enabled": acs_on,
    }


@router.post("/api/detections")
async def create_detection(req: CreateDetectionRequest, request: Request,
                           ctx: AppContext = Depends(get_context)):
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    at = (req.action_type or "").strip()
    _reject_unauthorized_action(at, req.pre_authorized)

    det = EventDetection(
        id="", name=req.name or at, source=req.source or "device",
        device_id=req.device_id or None, tag=req.tag or None,
        match=req.match or {}, action_type=at, action_params=req.action_params or {},
        pre_authorized=bool(req.pre_authorized), cooldown_seconds=int(req.cooldown_seconds or 0),
        created_by=str(principal),
    )
    did = ctx.detection_store.create(det)
    await _ensure_ingest(ctx)
    record_event(principal, "detection.create", resource=f"detection:{did}",
                 details={"name": det.name, "action": at,
                          "scope": det.device_id or det.tag or "all",
                          "pre_authorized": det.pre_authorized})
    return {"success": True, "detection": ctx.detection_store.get(did).to_dict()}


@router.patch("/api/detections/{det_id}")
async def update_detection(det_id: str, request: Request,
                           ctx: AppContext = Depends(get_context)):
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    body = await request.json()
    if "action_type" in body:
        _reject_unauthorized_action(
            body["action_type"], bool(body.get("pre_authorized")),
        )
    fields = {k: body[k] for k in (
        "name", "enabled", "device_id", "tag", "match", "action_type",
        "action_params", "pre_authorized", "cooldown_seconds") if k in body}
    if not ctx.detection_store.update(det_id, **fields):
        raise HTTPException(404, "detection not found")
    if body.get("enabled"):
        await _ensure_ingest(ctx)
    record_event(principal, "detection.update", resource=f"detection:{det_id}",
                 details={"fields": list(fields)})
    return {"success": True, "detection": ctx.detection_store.get(det_id).to_dict()}


@router.delete("/api/detections/{det_id}")
async def delete_detection(det_id: str, request: Request,
                           ctx: AppContext = Depends(get_context)):
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    if not ctx.detection_store.delete(det_id):
        raise HTTPException(404, "detection not found")
    record_event(principal, "detection.delete", resource=f"detection:{det_id}")
    return {"success": True}
