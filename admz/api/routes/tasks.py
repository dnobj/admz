"""Unified REST surface for Tasks (ADR-0037).

A task is either a **schedule** (time-based, recurring) or a **detection**
(event-based, one-shot) — one list, one create form, one set of actions. Schedule
tasks route through the scheduler (so loops start/stop); detection tasks are
pre-authorizations written straight to the store (they require an authenticated
principal, like the recovery route).

The legacy ``/api/schedules`` + ``/api/devices/{id}/recovery|pending`` endpoints
remain as back-compat aliases over the same store.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from admz.api.context import AppContext, get_context
from admz.snapshot.scheduler import SnapshotSchedule, parse_interval
from admz.tasks.handlers import list_action_types
from admz.tasks.store import (
    TRIGGER_DETECTION,
    TRIGGER_SCHEDULE,
    VALID_EVENTS,
)

router = APIRouter()


class CreateTaskRequest(BaseModel):
    trigger_kind: str = Field(description="'schedule' or 'detection'")
    action_type: str = Field(description="snapshot | drift_audit | survey | reprovision")
    description: str = ""
    action_params: Dict[str, Any] = Field(default_factory=dict)
    task_id: Optional[str] = None
    # schedule trigger
    interval: Optional[str] = None        # '6h', '30m', '1d', or seconds
    tag_filter: Optional[str] = None
    device_ids: Optional[List[str]] = None
    # detection trigger
    event: Optional[str] = None           # on_needs_setup | on_online
    device_id: Optional[str] = None


class UpdateTaskRequest(BaseModel):
    interval: Optional[str] = None
    enabled: Optional[bool] = None
    tag_filter: Optional[str] = None
    description: Optional[str] = None


def _store(ctx: AppContext):
    return ctx.scheduler.store


@router.get("/tasks/action-types")
async def get_action_types():
    """Action types the builder may offer."""
    return {"action_types": list_action_types(),
            "events": sorted(VALID_EVENTS),
            "trigger_kinds": [TRIGGER_SCHEDULE, TRIGGER_DETECTION]}


@router.get("/tasks")
async def list_tasks(
    device_id: Optional[str] = None,
    kind: Optional[str] = None,
    ctx: AppContext = Depends(get_context),
):
    """All tasks (schedule + detection), with an optional device or kind filter."""
    tasks = _store(ctx).list(trigger_kind=kind, device_id=device_id)
    return {"count": len(tasks), "tasks": [t.to_dict() for t in tasks]}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, ctx: AppContext = Depends(get_context)):
    t = _store(ctx).get(task_id)
    if t is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return t.to_dict()


@router.post("/tasks")
async def create_task(
    request: Request,
    req: CreateTaskRequest,
    ctx: AppContext = Depends(get_context),
):
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)

    if req.action_type not in list_action_types():
        raise HTTPException(
            status_code=400,
            detail=f"Unknown action_type {req.action_type!r}. "
                   f"Registered: {list_action_types()}.",
        )

    if req.trigger_kind == TRIGGER_SCHEDULE:
        if not req.interval:
            raise HTTPException(status_code=400,
                                detail="schedule tasks need an 'interval'")
        try:
            interval_seconds = parse_interval(req.interval)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        schedule = SnapshotSchedule(
            id=req.task_id or _new_id(),
            description=req.description,
            interval_seconds=interval_seconds,
            tag_filter=req.tag_filter,
            device_ids=req.device_ids,
            job_type=req.action_type,
            params=req.action_params or {},
        )
        ctx.scheduler.add_schedule(schedule)
        record_event(principal, "task.create", resource=f"task:{schedule.id}",
                     details={"trigger_kind": "schedule", "action": req.action_type,
                              "interval": req.interval})
        return _store(ctx).get(schedule.id).to_dict()

    if req.trigger_kind == TRIGGER_DETECTION:
        # A detection task is a pre-authorization — require an authenticated
        # principal (parity with the recovery queue route).
        from admz.authz import require_authenticated_principal
        require_authenticated_principal(principal)
        if not req.device_id:
            raise HTTPException(status_code=400,
                                detail="detection tasks need a 'device_id'")
        if req.event not in VALID_EVENTS:
            raise HTTPException(status_code=400,
                                detail=f"event must be one of {sorted(VALID_EVENTS)}")
        if not ctx.registry.device_exists(req.device_id):
            raise HTTPException(status_code=404,
                                detail=f"Device not found: {req.device_id}")
        tid = _store(ctx).create_detection(
            device_id=req.device_id, event=req.event, action_type=req.action_type,
            action_params=req.action_params or {}, approved_by=str(principal),
            description=req.description or
            f"{req.action_type} {req.device_id} on {req.event}",
            task_id=req.task_id,
        )
        record_event(principal, "task.create", resource=f"task:{tid}",
                     details={"trigger_kind": "detection", "action": req.action_type,
                              "event": req.event, "device_id": req.device_id})
        return _store(ctx).get(tid).to_dict()

    raise HTTPException(status_code=400,
                        detail="trigger_kind must be 'schedule' or 'detection'")


@router.patch("/tasks/{task_id}")
async def update_task(
    request: Request,
    task_id: str,
    req: UpdateTaskRequest,
    ctx: AppContext = Depends(get_context),
):
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    task = _store(ctx).get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    if task.trigger_kind != TRIGGER_SCHEDULE:
        raise HTTPException(status_code=400,
                            detail="only schedule tasks are editable; "
                                   "cancel a detection task instead")
    kwargs: Dict[str, Any] = {}
    if req.interval is not None:
        try:
            kwargs["interval_seconds"] = parse_interval(req.interval)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    if req.enabled is not None:
        kwargs["enabled"] = req.enabled
    if req.tag_filter is not None:
        kwargs["tag_filter"] = req.tag_filter
    if req.description is not None:
        kwargs["description"] = req.description
    updated = ctx.scheduler.update_schedule(task_id, **kwargs)
    record_event(principal, "task.update", resource=f"task:{task_id}",
                 details={"fields": list(kwargs.keys())})
    return _store(ctx).get(task_id).to_dict()


@router.delete("/tasks/{task_id}")
async def delete_task(
    request: Request, task_id: str, ctx: AppContext = Depends(get_context),
):
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    task = _store(ctx).get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    if task.trigger_kind == TRIGGER_SCHEDULE:
        ctx.scheduler.remove_schedule(task_id)
        record_event(principal, "task.delete", resource=f"task:{task_id}")
        return {"success": True, "deleted": task_id}
    # detection → cancel (only if still pending)
    cancelled = _store(ctx).cancel(task_id)
    record_event(principal, "task.cancel", resource=f"task:{task_id}",
                 success=cancelled)
    if not cancelled:
        raise HTTPException(status_code=409,
                            detail="detection task is no longer pending")
    return {"success": True, "cancelled": task_id}


@router.post("/tasks/{task_id}/run")
async def run_task_now(
    request: Request, task_id: str, ctx: AppContext = Depends(get_context),
):
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    task = _store(ctx).get(task_id)
    if task is None or task.trigger_kind != TRIGGER_SCHEDULE:
        raise HTTPException(status_code=400,
                            detail="only schedule tasks can be run on demand")
    result = await ctx.scheduler.run_now(task_id)
    record_event(principal, "task.run", resource=f"task:{task_id}",
                 success=result.get("success", False))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed"))
    return result


def _new_id() -> str:
    import uuid
    return uuid.uuid4().hex
