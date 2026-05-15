"""REST routes for the operation catalog + per-operation execution."""

import secrets
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from admz.api.context import AppContext, get_context
from admz.exceptions import DeviceNotFoundError

router = APIRouter()


CONFIRM_TOKEN_TTL_SECONDS = 300
_confirm_tokens: Dict[str, Dict[str, Any]] = {}


def _purge_expired():
    now = time.time()
    expired = [
        t
        for t, d in _confirm_tokens.items()
        if now - d.get("issued_at", 0) > CONFIRM_TOKEN_TTL_SECONDS
    ]
    for t in expired:
        _confirm_tokens.pop(t, None)


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
        _purge_expired()
        token = secrets.token_urlsafe(32)
        _confirm_tokens[token] = {
            "device_id": req.device_id,
            "operation_id": req.operation_id,
            "params": req.params,
            "family": req.family,
            "issued_at": time.time(),
        }
        return {
            "blocked": True,
            "risk_level": "dangerous",
            "reason": op.danger_description if op else "Operation classified as dangerous.",
            "confirm_token": token,
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
    _purge_expired()
    details = _confirm_tokens.pop(req.confirm_token, None)
    if not details:
        raise HTTPException(
            status_code=400, detail="Invalid or expired confirmation token"
        )

    operation = ctx.catalog.get_operation(
        details["family"], details["operation_id"]
    )
    if not operation:
        raise HTTPException(
            status_code=404,
            detail=f"Operation '{details['operation_id']}' no longer in catalog",
        )

    executor = ctx.executors.get(details["family"])
    device = ctx.registry.get_device_info(details["device_id"])
    device["device_id"] = details["device_id"]
    credentials = ctx.registry.get_credentials(details["device_id"])

    result = await executor.execute(
        operation.to_executor_dict(), device, credentials, details["params"]
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
