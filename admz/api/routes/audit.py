"""REST routes for reading the audit log (Phase 4D).

Audit writes happen at the source of each interesting action (credential
retrieval, API-key minting, dangerous-op confirms, ...). This module
exposes a read endpoint for operators.

Authorization model for v1: any authenticated principal may read the
audit log. RBAC-by-group will tighten this in a later phase — typically
to "admin role only."
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from admz.audit import AuditLog
from admz.auth import Principal, get_current_principal


router = APIRouter()


class AuditEntryResponse(BaseModel):
    id: int
    timestamp: float
    requester: str
    auth_source: str
    action: str
    resource: str
    details: dict
    success: bool
    error_message: str


@router.get("/audit", response_model=List[AuditEntryResponse])
async def list_audit_entries(
    limit: int = Query(100, ge=1, le=1000),
    action: Optional[str] = None,
    requester: Optional[str] = None,
    since: Optional[float] = None,
    principal: Principal = Depends(get_current_principal),
):
    """List recent audit-log entries, newest first.

    Filters are optional and combinable.
    """
    log = AuditLog()
    entries = log.list_recent(
        limit=limit, action=action, requester=requester, since=since,
    )
    return [
        AuditEntryResponse(
            id=e.id,
            timestamp=e.timestamp,
            requester=e.requester,
            auth_source=e.auth_source,
            action=e.action,
            resource=e.resource,
            details=e.details,
            success=e.success,
            error_message=e.error_message,
        )
        for e in entries
    ]
