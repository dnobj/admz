"""REST routes for the operation catalog + per-operation execution."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from admz.api.context import AppContext, get_context
from admz.api.confirm_store import confirm_store, ConfirmStatus
from admz.exceptions import DeviceNotFoundError

router = APIRouter()


# Phase 2E: confirm tokens live in the shared SQLite ConfirmStore so that
# tokens issued via MCP and via REST are interchangeable. The previous
# in-memory _confirm_tokens dict + _purge_expired() helper here have been
# removed — see docs/specification/review-followup.md.
CONFIRM_TOKEN_TTL_SECONDS = 300


class QueryRequest(BaseModel):
    device_id: str
    intent: str
    family: str = "vapix"


class ExecuteRequest(BaseModel):
    device_id: str
    operation_id: str
    params: Dict[str, str] = Field(default_factory=dict)
    family: str = "vapix"


class ConfirmRequest(BaseModel):
    confirm_token: str


@router.post("/catalog/query")
async def query_catalog(
    req: QueryRequest, ctx: AppContext = Depends(get_context)
):
    device_info = None
    if ctx.registry.device_exists(req.device_id):
        device_info = ctx.registry.get_device_info(req.device_id)

    result = ctx.resolver.resolve(
        device_id=req.device_id,
        intent=req.intent,
        family=req.family,
        device_info=device_info,
    )
    return {
        "operations": result.operations,
        "parameter_groups": result.parameter_groups,
        "device": result.device,
        "risk_summary": result.risk_summary,
        "notes": result.notes,
    }


@router.post("/catalog/execute")
async def execute_operation(
    req: ExecuteRequest, ctx: AppContext = Depends(get_context)
):
    risk = ctx.catalog.get_risk_level(req.family, req.operation_id)
    if risk == "dangerous":
        op = ctx.catalog.get_operation(req.family, req.operation_id)
        session = confirm_store.create_session(
            device_id=req.device_id,
            operation_id=req.operation_id,
            family=req.family,
            params=dict(req.params),
            risk_level="dangerous",
            confirmation_level="llm_confirm",
            danger_description=(op.danger_description if op else ""),
            ttl=CONFIRM_TOKEN_TTL_SECONDS,
        )
        return {
            "blocked": True,
            "risk_level": "dangerous",
            "reason": op.danger_description if op else "Operation classified as dangerous.",
            "confirm_token": session.token,
            "confirm_endpoint": "/api/catalog/confirm",
        }

    operation = ctx.catalog.get_operation(req.family, req.operation_id)
    if not operation:
        raise HTTPException(
            status_code=404,
            detail=f"Operation '{req.operation_id}' not found in {req.family} catalog",
        )

    executor = ctx.executors.get(req.family)
    if not executor:
        raise HTTPException(
            status_code=400,
            detail=f"No executor available for family '{req.family}'",
        )

    if not ctx.registry.device_exists(req.device_id):
        raise HTTPException(
            status_code=404, detail=f"Device not found: {req.device_id}"
        )

    device = ctx.registry.get_device_info(req.device_id)
    device["device_id"] = req.device_id
    credentials = ctx.registry.get_credentials(req.device_id)

    result = await executor.execute(
        operation.to_executor_dict(), device, credentials, req.params
    )

    response = {
        "success": result.success,
        "operation_id": result.operation_id,
        "device_id": result.device_id,
        "status_code": result.status_code,
        "duration_ms": result.duration_ms,
    }
    if result.success:
        response["data"] = result.parsed_data
    else:
        response["error"] = result.error
    if result.warnings:
        response["warnings"] = result.warnings

    return response


@router.post("/catalog/confirm")
async def confirm_dangerous(
    req: ConfirmRequest, ctx: AppContext = Depends(get_context)
):
    session = confirm_store.get_session(req.confirm_token)
    if session is None or session.effective_status != ConfirmStatus.PENDING:
        raise HTTPException(
            status_code=400, detail="Invalid or expired confirmation token"
        )

    if not confirm_store.complete_session(req.confirm_token, confirmed_by="rest"):
        # Lost the race with another consumer (MCP or web UI).
        raise HTTPException(
            status_code=409,
            detail="Confirmation token already used or expired before this request completed.",
        )

    operation = ctx.catalog.get_operation(session.family, session.operation_id)
    if not operation:
        raise HTTPException(
            status_code=404,
            detail=f"Operation '{session.operation_id}' no longer in catalog",
        )

    executor = ctx.executors.get(session.family)
    device = ctx.registry.get_device_info(session.device_id)
    device["device_id"] = session.device_id
    credentials = ctx.registry.get_credentials(session.device_id)

    result = await executor.execute(
        operation.to_executor_dict(), device, credentials, session.params
    )

    response = {
        "success": result.success,
        "confirmed_dangerous": True,
        "operation_id": result.operation_id,
        "device_id": result.device_id,
        "status_code": result.status_code,
        "duration_ms": result.duration_ms,
    }
    if result.success:
        response["data"] = result.parsed_data
    else:
        response["error"] = result.error
    return response
