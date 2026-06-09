"""REST routes for multi-step execution plans."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
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


class ExecutePlanRequest(BaseModel):
    # Opt-in for plans whose strictest step resolves to the ``llm_confirm``
    # tier. Plans at a ``url_*`` tier ignore this and require web/widget
    # approval (a blocked envelope with a confirm_url is returned).
    confirm_dangerous: bool = False


@router.post("/plans")
async def create_plan(
    request: Request,
    req: CreatePlanRequest,
    ctx: AppContext = Depends(get_context),
):
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    try:
        plan = ctx.plan_engine.create_plan(
            description=req.description,
            steps=[s.model_dump(exclude_none=True) for s in req.steps],
            on_failure=req.on_failure,
        )
    except ValueError as e:
        record_event(principal, "plan.create", success=False, error_message=str(e),
                     details={"step_count": len(req.steps)})
        raise HTTPException(status_code=400, detail=str(e))

    record_event(principal, "plan.create",
                 resource=f"plan:{plan.plan_id}",
                 details={"step_count": len(req.steps),
                          "on_failure": req.on_failure})
    return plan.to_summary()


@router.post("/plans/{plan_id}/execute")
async def execute_plan(
    request: Request,
    plan_id: str,
    req: Optional[ExecutePlanRequest] = None,
    ctx: AppContext = Depends(get_context),
):
    """Execute an approved plan through the shared per-risk gate.

    CR-3: requires an authenticated principal — plan execution drives real
    VAPIX calls against fleet devices. ``operations.execute_gated_plan``
    applies the same configurable per-risk confirmation policy single ops use:
    a plan whose strictest step resolves above ``none`` returns a blocked
    envelope (``llm_confirm`` → opt in with ``confirm_dangerous=true``;
    ``url_*`` → approve at the returned ``confirm_url``) instead of running.
    """
    from admz import operations
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    resource = f"plan:{plan_id}"
    confirm_dangerous = req.confirm_dangerous if req else False

    try:
        result = await operations.execute_gated_plan(
            ctx.plan_engine, plan_id, confirm_dangerous=confirm_dangerous
        )
    except ValueError as e:
        record_event(principal, "plan.execute", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    if result.get("error") and not result.get("blocked"):
        record_event(principal, "plan.execute", resource=resource,
                     success=False, error_message=str(result["error"]))
        raise HTTPException(status_code=404, detail=str(result["error"]))

    record_event(principal, "plan.execute", resource=resource,
                 details={"blocked": bool(result.get("blocked"))})
    return result


@router.get("/plans/{plan_id}")
async def get_plan_status(plan_id: str, ctx: AppContext = Depends(get_context)):
    status = ctx.plan_engine.get_plan_status(plan_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Plan not found: {plan_id}")
    return status
