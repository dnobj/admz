"""REST routes for the operation catalog + per-operation execution."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from admz.api.context import AppContext, get_context
from admz.exceptions import (
    DeviceNotFoundError,
    NoExecutorError,
    OperationNotFoundError,
)

router = APIRouter()


# Phase 2E: confirm tokens live in the shared SQLite ConfirmStore so that
# tokens issued via MCP and via REST are interchangeable. The gate +
# execution + token consumption now live in admz.operations, so both
# surfaces enforce the identical per-risk confirmation policy (ADR-0006/0008).


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
    request: Request,
    req: ExecuteRequest,
    ctx: AppContext = Depends(get_context),
):
    """Execute a single catalog operation through the shared gated core.

    The same ``admz.operations.execute_gated_operation`` the MCP server uses:
    the operation's ``risk_level`` is mapped to its configured confirmation
    level and, for anything above ``none``, the op is NOT run — a blocked
    envelope (``confirm_token`` + ``/confirm/{token}`` URL) is returned. This
    replaces the old hardcoded ``if risk == "dangerous"`` check so REST honors
    the per-risk policy (incl. fleet overrides) exactly like MCP.
    """
    from admz import operations
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    resource = f"device:{req.device_id}/op:{req.operation_id}"

    try:
        result = await operations.execute_gated_operation(
            device_id=req.device_id,
            operation_id=req.operation_id,
            family=req.family,
            params=req.params,
            catalog=ctx.catalog,
            registry=ctx.registry,
            executors=ctx.executors,
        )
    except OperationNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Operation '{req.operation_id}' not found in {req.family} catalog",
        )
    except NoExecutorError:
        raise HTTPException(
            status_code=400,
            detail=f"No executor available for family '{req.family}'",
        )
    except DeviceNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Device not found: {req.device_id}"
        )

    blocked = bool(result.get("blocked"))
    record_event(
        principal, "catalog.execute", resource=resource,
        success=(not blocked and bool(result.get("success"))),
        error_message=(
            "" if (blocked or result.get("success"))
            else str(result.get("error") or "")
        ),
        details={
            "risk": result.get("risk_level"),
            "blocked": blocked,
            "confirm_token": result.get("confirm_token"),
            "status_code": result.get("status_code"),
        },
    )
    return result


@router.post("/catalog/confirm")
async def confirm_dangerous(
    request: Request,
    req: ConfirmRequest,
    ctx: AppContext = Depends(get_context),
):
    """Consume an ``llm_confirm`` token and execute the held operation.

    Delegates to the shared ``operations.consume_confirmation`` (the same path
    MCP uses). ``enforce_url_flow_block=True``: a ``url_only`` /
    ``url_and_password`` token cannot be completed by this passwordless JSON
    endpoint — only the password-collecting web form (``/confirm/{token}``)
    may. Gate/lookup failures map to HTTP status codes; an operation that ran
    but failed is returned as a 200 body with ``success: false``.
    """
    from admz import operations
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    resource = f"confirm_token:{req.confirm_token[:8]}..."

    result = await operations.consume_confirmation(
        req.confirm_token,
        catalog=ctx.catalog,
        registry=ctx.registry,
        executors=ctx.executors,
        confirmed_by="rest",
        enforce_url_flow_block=True,
    )

    if not result.get("confirmed"):
        # The op never executed — a token/gate/lookup failure. Map to the
        # historical HTTP status codes.
        err = str(result.get("error", ""))
        if "Invalid or expired" in err:
            record_event(principal, "catalog.confirm", resource=resource,
                         success=False, error_message="invalid-or-expired-token")
            raise HTTPException(
                status_code=400, detail="Invalid or expired confirmation token"
            )
        if "already used" in err:
            record_event(principal, "catalog.confirm", resource=resource,
                         success=False, error_message="token-already-used")
            raise HTTPException(status_code=409, detail=err)
        if "no longer found in catalog" in err:
            record_event(principal, "catalog.confirm", resource=resource,
                         success=False, error_message="operation-not-found")
            raise HTTPException(
                status_code=404,
                detail=f"Operation no longer in catalog: {err}",
            )
        # url_* token submitted to the JSON endpoint, missing executor, etc.
        record_event(principal, "catalog.confirm", resource=resource,
                     success=False, error_message="confirm-rejected")
        raise HTTPException(status_code=400, detail=err)

    record_event(
        principal, "catalog.confirm",
        resource=f"device:confirmed/op:{req.confirm_token[:8]}",
        success=bool(result.get("success")),
        error_message="" if result.get("success") else str(result.get("error") or ""),
        details={"status_code": result.get("status_code")},
    )
    return result
