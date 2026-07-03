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
    from admz.tasks.gated import (
        TaskSpecError,
        apply_create_task,
        describe_create,
        gate_task_write,
        is_interactive,
        validate_create_spec,
    )

    principal = await get_current_principal(request)

    spec = {
        "trigger_kind": req.trigger_kind,
        "action_type": req.action_type,
        "description": req.description,
        "action_params": req.action_params or {},
        "task_id": req.task_id,
        "interval": req.interval,
        "tag_filter": req.tag_filter,
        "device_ids": req.device_ids,
        "event": req.event,
        "device_id": req.device_id,
    }
    if req.trigger_kind == TRIGGER_DETECTION:
        # A detection task is a pre-authorization — require an authenticated
        # principal (parity with the recovery queue route). Checked before
        # validation so unauthenticated callers learn nothing else.
        from admz.authz import require_authenticated_principal
        require_authenticated_principal(principal)

    try:
        validate_create_spec(spec, ctx.registry)
    except TaskSpecError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # An operator filling the Tasks-page form is already a deliberate
    # human action — writes directly. Every other caller (api-key,
    # anonymous, scripts) takes the confirmation-widget path: the task
    # is written only when a human approves the card.
    if not is_interactive(principal):
        target = req.device_id or (
            f"tag:{req.tag_filter}" if req.tag_filter else "fleet")
        return gate_task_write(
            "create_task", target, spec, describe_create(spec))

    task = apply_create_task(
        spec, scheduler=ctx.scheduler, registry=ctx.registry,
        approved_by=str(principal),
    )
    record_event(principal, "task.create", resource=f"task:{task['id']}",
                 details={"trigger_kind": req.trigger_kind,
                          "action": req.action_type,
                          "interval": req.interval, "event": req.event,
                          "device_id": req.device_id})
    return task


@router.patch("/tasks/{task_id}")
async def update_task(
    request: Request,
    task_id: str,
    req: UpdateTaskRequest,
    ctx: AppContext = Depends(get_context),
):
    from admz.audit import record_event
    from admz.auth import get_current_principal

    from admz.tasks.gated import (
        TaskSpecError,
        apply_update_task,
        describe_update,
        gate_task_write,
        is_interactive,
    )

    principal = await get_current_principal(request)
    fields = {"interval": req.interval, "enabled": req.enabled,
              "tag_filter": req.tag_filter, "description": req.description}

    # Same surface rule as creation: the console form edits directly,
    # everything else needs the confirmation card.
    if not is_interactive(principal):
        if _store(ctx).get(task_id) is None:
            raise HTTPException(status_code=404,
                                detail=f"Task not found: {task_id}")
        return gate_task_write(
            "update_task", task_id, {"task_id": task_id, **fields},
            describe_update(task_id, fields))

    try:
        task = apply_update_task(task_id, fields, scheduler=ctx.scheduler)
    except TaskSpecError as e:
        code = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=code, detail=str(e))
    record_event(principal, "task.update", resource=f"task:{task_id}",
                 details={"fields": [k for k, v in fields.items()
                                     if v is not None]})
    return task


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
