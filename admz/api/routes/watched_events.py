"""REST surface for watched events — bookmarked event patterns (ADR-0041).

A watched event is the trigger half of a detection (``source`` + scope +
``match``), with no action. Creating one requires an authenticated principal (so
it's attributable + auditable), but — unlike a detection — it does **not** turn
live ingest on: bookmarking a pattern is a cheap, side-effect-free act.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from admz.api.context import AppContext, get_context
from admz.events.watched import WatchedEvent

router = APIRouter()


class CreateWatchedEventRequest(BaseModel):
    name: str = ""
    source: str = "device"
    device_id: Optional[str] = None
    tag: Optional[str] = None
    match: Dict[str, Any] = Field(default_factory=dict)
    notes: str = ""


@router.get("/api/watched-events")
async def list_watched_events(ctx: AppContext = Depends(get_context)):
    return {"success": True, "watched": [w.to_dict() for w in ctx.watched_event_store.list()]}


@router.post("/api/watched-events")
async def create_watched_event(req: CreateWatchedEventRequest, request: Request,
                               ctx: AppContext = Depends(get_context)):
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    w = WatchedEvent(
        id="", name=req.name or "watched event", source=req.source or "device",
        device_id=req.device_id or None, tag=req.tag or None,
        match=req.match or {}, notes=req.notes or "", created_by=str(principal),
    )
    wid = ctx.watched_event_store.create(w)
    record_event(principal, "watched_event.create", resource=f"watched_event:{wid}",
                 details={"name": w.name, "source": w.source,
                          "scope": w.device_id or w.tag or "all"})
    return {"success": True, "watched": ctx.watched_event_store.get(wid).to_dict()}


@router.patch("/api/watched-events/{watch_id}")
async def update_watched_event(watch_id: str, request: Request,
                               ctx: AppContext = Depends(get_context)):
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    body = await request.json()
    fields = {k: body[k] for k in ("name", "device_id", "tag", "match", "notes") if k in body}
    if not ctx.watched_event_store.update(watch_id, **fields):
        raise HTTPException(404, "watched event not found")
    record_event(principal, "watched_event.update", resource=f"watched_event:{watch_id}",
                 details={"fields": list(fields)})
    return {"success": True, "watched": ctx.watched_event_store.get(watch_id).to_dict()}


@router.delete("/api/watched-events/{watch_id}")
async def delete_watched_event(watch_id: str, request: Request,
                               ctx: AppContext = Depends(get_context)):
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    if not ctx.watched_event_store.delete(watch_id):
        raise HTTPException(404, "watched event not found")
    record_event(principal, "watched_event.delete", resource=f"watched_event:{watch_id}")
    return {"success": True}
