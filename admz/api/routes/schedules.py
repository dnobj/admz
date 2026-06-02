"""REST routes for snapshot schedules."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from admz.api.context import AppContext, get_context
from admz.snapshot.scheduler import SnapshotSchedule, parse_interval

router = APIRouter()


class CreateScheduleRequest(BaseModel):
    schedule_id: str
    description: str
    interval: str
    tag_filter: Optional[str] = None
    device_ids: Optional[List[str]] = None


class UpdateScheduleRequest(BaseModel):
    interval: Optional[str] = None
    enabled: Optional[bool] = None
    tag_filter: Optional[str] = None
    description: Optional[str] = None


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
    try:
        interval_seconds = parse_interval(req.interval)
    except ValueError as e:
        record_event(principal, "schedule.create", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    schedule = SnapshotSchedule(
        id=req.schedule_id,
        description=req.description,
        interval_seconds=interval_seconds,
        tag_filter=req.tag_filter,
        device_ids=req.device_ids,
    )
    ctx.scheduler.add_schedule(schedule)
    record_event(principal, "schedule.create", resource=resource,
                 details={"interval": req.interval, "tag_filter": req.tag_filter})
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
