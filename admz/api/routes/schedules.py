"""REST routes for scheduled jobs (snapshot, drift_audit, …).

FR-SCH-014 (partial) — generalized management surface: the
create/update/list/run-now endpoints work uniformly across job
types via the handler registry. The legacy ``snapshot_schedule``
naming is kept on the endpoint paths for back-compat; new
deployments should think of them as "scheduled jobs."
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from admz.api.context import AppContext, get_context
from admz.snapshot.scheduler import (
    SnapshotSchedule,
    list_job_types,
    parse_interval,
)

router = APIRouter()


class CreateScheduleRequest(BaseModel):
    schedule_id: str
    description: str
    interval: str
    tag_filter: Optional[str] = None
    device_ids: Optional[List[str]] = None
    # FR-SCH-010 — operator can pick any registered job type. When
    # omitted, defaults to "snapshot" so pre-PR clients keep working.
    job_type: str = Field(
        "snapshot",
        description=(
            "Registered job type: 'snapshot' (default) or 'drift_audit'. "
            "Run /api/schedules/job-types to see the live set."
        ),
    )
    params: Dict[str, Any] = Field(default_factory=dict)


class UpdateScheduleRequest(BaseModel):
    interval: Optional[str] = None
    enabled: Optional[bool] = None
    tag_filter: Optional[str] = None
    description: Optional[str] = None


@router.get("/schedules/job-types")
async def get_job_types():
    """FR-SCH-014 — list registered job types so the operator (or
    LLM) can introspect what they're allowed to create."""
    return {"job_types": list_job_types()}


@router.post("/schedules")
async def create_schedule(
    request: Request,
    req: CreateScheduleRequest,
    ctx: AppContext = Depends(get_context),
):
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    resource = f"schedule:{req.schedule_id}"

    # Reject unknown job types up-front with a helpful message —
    # avoids the awkward "schedule created, then crashes on first
    # execution" failure mode.
    if req.job_type not in list_job_types():
        msg = (
            f"Unknown job_type {req.job_type!r}. "
            f"Registered: {list_job_types()}."
        )
        record_event(
            principal, "schedule.create", resource=resource,
            success=False, error_message=msg,
        )
        raise HTTPException(status_code=400, detail=msg)

    try:
        interval_seconds = parse_interval(req.interval)
    except ValueError as e:
        record_event(principal, "schedule.create", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    # Non-interactive callers (api-key/anonymous) take the confirmation
    # widget — same policy as the unified /api/tasks route (the console
    # form is exempt: a human filling it is the approval).
    from admz.tasks.gated import describe_create, gate_task_write, is_interactive
    if not is_interactive(principal):
        spec = {
            "trigger_kind": "schedule", "action_type": req.job_type,
            "task_id": req.schedule_id, "description": req.description,
            "interval": req.interval, "tag_filter": req.tag_filter,
            "device_ids": req.device_ids, "action_params": req.params or {},
        }
        target = (f"tag:{req.tag_filter}" if req.tag_filter
                  else (req.device_ids[0] if req.device_ids else "fleet"))
        return gate_task_write("create_task", target, spec, describe_create(spec))

    schedule = SnapshotSchedule(
        id=req.schedule_id,
        description=req.description,
        interval_seconds=interval_seconds,
        tag_filter=req.tag_filter,
        device_ids=req.device_ids,
        job_type=req.job_type,
        params=req.params or {},
    )
    ctx.scheduler.add_schedule(schedule)
    record_event(
        principal, "schedule.create", resource=resource,
        details={
            "interval": req.interval,
            "tag_filter": req.tag_filter,
            "job_type": req.job_type,
        },
    )
    return schedule.to_dict()


@router.get("/schedules")
async def list_schedules(ctx: AppContext = Depends(get_context)):
    schedules = ctx.scheduler.list_schedules()
    return {
        "count": len(schedules),
        "schedules": [s.to_dict() for s in schedules],
    }


@router.patch("/schedules/{schedule_id}")
async def update_schedule(
    request: Request,
    schedule_id: str,
    req: UpdateScheduleRequest,
    ctx: AppContext = Depends(get_context),
):
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    resource = f"schedule:{schedule_id}"

    from admz.tasks.gated import describe_update, gate_task_write, is_interactive
    if not is_interactive(principal):
        fields = {"interval": req.interval, "enabled": req.enabled,
                  "tag_filter": req.tag_filter, "description": req.description}
        return gate_task_write(
            "update_task", schedule_id, {"task_id": schedule_id, **fields},
            describe_update(schedule_id, fields))

    kwargs = {}
    if req.interval is not None:
        try:
            kwargs["interval_seconds"] = parse_interval(req.interval)
        except ValueError as e:
            record_event(principal, "schedule.update", resource=resource,
                         success=False, error_message=str(e))
            raise HTTPException(status_code=400, detail=str(e))
    if req.enabled is not None:
        kwargs["enabled"] = req.enabled
    if req.tag_filter is not None:
        kwargs["tag_filter"] = req.tag_filter
    if req.description is not None:
        kwargs["description"] = req.description

    schedule = ctx.scheduler.update_schedule(schedule_id, **kwargs)
    if not schedule:
        record_event(principal, "schedule.update", resource=resource,
                     success=False, error_message="not-found")
        raise HTTPException(status_code=404, detail=f"Schedule not found: {schedule_id}")
    record_event(principal, "schedule.update", resource=resource,
                 details={"fields": list(kwargs.keys())})
    return schedule.to_dict()


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    request: Request, schedule_id: str, ctx: AppContext = Depends(get_context),
):
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    resource = f"schedule:{schedule_id}"
    removed = ctx.scheduler.remove_schedule(schedule_id)
    if not removed:
        record_event(principal, "schedule.delete", resource=resource,
                     success=False, error_message="not-found")
        raise HTTPException(status_code=404, detail=f"Schedule not found: {schedule_id}")
    record_event(principal, "schedule.delete", resource=resource)
    return {"message": f"Schedule '{schedule_id}' deleted"}


@router.post("/schedules/{schedule_id}/run")
async def run_schedule_now(
    request: Request, schedule_id: str, ctx: AppContext = Depends(get_context),
):
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    resource = f"schedule:{schedule_id}"
    result = await ctx.scheduler.run_now(schedule_id)
    if not result.get("success"):
        record_event(principal, "schedule.run", resource=resource,
                     success=False, error_message=result.get("error", "failed"))
        raise HTTPException(status_code=404, detail=result.get("error", "Failed"))
    record_event(principal, "schedule.run", resource=resource)
    return result
