"""REST routes for snapshot schedules."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
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
    req: CreateScheduleRequest, ctx: AppContext = Depends(get_context)
):
    try:
        interval_seconds = parse_interval(req.interval)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    schedule = SnapshotSchedule(
        id=req.schedule_id,
        description=req.description,
        interval_seconds=interval_seconds,
        tag_filter=req.tag_filter,
        device_ids=req.device_ids,
    )
    ctx.scheduler.add_schedule(schedule)
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
    schedule_id: str,
    req: UpdateScheduleRequest,
    ctx: AppContext = Depends(get_context),
):
    kwargs = {}
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

    schedule = ctx.scheduler.update_schedule(schedule_id, **kwargs)
    if not schedule:
        raise HTTPException(status_code=404, detail=f"Schedule not found: {schedule_id}")
    return schedule.to_dict()


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str, ctx: AppContext = Depends(get_context)
):
    removed = ctx.scheduler.remove_schedule(schedule_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Schedule not found: {schedule_id}")
    return {"message": f"Schedule '{schedule_id}' deleted"}


@router.post("/schedules/{schedule_id}/run")
async def run_schedule_now(
    schedule_id: str, ctx: AppContext = Depends(get_context)
):
    result = await ctx.scheduler.run_now(schedule_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Failed"))
    return result
