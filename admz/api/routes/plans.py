"""REST routes for multi-step execution plans."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from admz.api.context import AppContext, get_context

router = APIRouter()


class PlanStepIn(BaseModel):
    operation_id: str
    device_id: str
    params: Dict[str, str] = Field(default_factory=dict)
    description: Optional[str] = None
    depends_on: Optional[List[int]] = None


class CreatePlanRequest(BaseModel):
    description: str
    steps: List[PlanStepIn]
    on_failure: str = "stop"


@router.post("/plans")
async def create_plan(
    req: CreatePlanRequest, ctx: AppContext = Depends(get_context)
):
    try:
        plan = ctx.plan_engine.create_plan(
            description=req.description,
            steps=[s.model_dump(exclude_none=True) for s in req.steps],
            on_failure=req.on_failure,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return plan.to_summary()


@router.post("/plans/{plan_id}/execute")
async def execute_plan(plan_id: str, ctx: AppContext = Depends(get_context)):
    try:
        plan = await ctx.plan_engine.execute_plan(plan_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return plan.to_results()


@router.get("/plans/{plan_id}")
async def get_plan_status(plan_id: str, ctx: AppContext = Depends(get_context)):
    status = ctx.plan_engine.get_plan_status(plan_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Plan not found: {plan_id}")
    return status
