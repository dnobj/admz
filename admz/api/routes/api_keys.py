"""REST routes for API key management.

Operators authenticated via Windows IWA can mint, list, and revoke API
keys for programmatic clients. The plaintext key is shown **once** in
the create response — there's no path to retrieve it later.

Authorization model for v1: any authenticated principal may manage
keys. (RBAC-by-group will tighten this in a later phase.)
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from admz.api_keys import ApiKey, ApiKeyStore
from admz.auth import Principal, get_current_principal


router = APIRouter()


def _store() -> ApiKeyStore:
    """Build a fresh store reading the current ADMZ_DB_PATH env var.

    Same reasoning as :class:`admz.auth.ApiKeyAuth`: the module-level
    singleton is created at import time, which leaks state across tests
    that redirect the DB path. Per-request stores are cheap
    (short-lived SQLite connections, WAL mode).
    """
    return ApiKeyStore()


class CreateApiKeyRequest(BaseModel):
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Human-readable name shown in the UI (e.g. 'nightly-bot').",
    )
    expires_at: Optional[float] = Field(
        default=None,
        description="Optional unix timestamp; omit for non-expiring.",
    )


class ApiKeyResponse(BaseModel):
    """Public view of an API key — does NOT include the plaintext."""

    id: int
    display_name: str
    created_by: str
    created_at: float
    expires_at: Optional[float] = None
    last_used_at: Optional[float] = None
    revoked: bool
    scopes: str
    groups: List[str]


class CreatedApiKeyResponse(ApiKeyResponse):
    """One-time response when a key is freshly minted; contains the
    plaintext that the operator must copy and store."""

    plaintext: str = Field(
        ...,
        description=(
            "The unhashed API key. Shown ONLY in this response — there "
            "is no path to retrieve it later. Copy and store it now."
        ),
    )


def _to_response(key: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=key.id,
        display_name=key.display_name,
        created_by=key.created_by,
        created_at=key.created_at,
        expires_at=key.expires_at,
        last_used_at=key.last_used_at,
        revoked=key.revoked,
        scopes=key.scopes,
        groups=key.groups,
    )


@router.get("/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    include_revoked: bool = False,
    principal: Principal = Depends(get_current_principal),
) -> List[ApiKeyResponse]:
    """List API keys. Hashed values are never returned."""
    return [_to_response(k) for k in _store().list(include_revoked=include_revoked)]


@router.post("/api-keys", response_model=CreatedApiKeyResponse, status_code=201)
async def create_api_key(
    req: CreateApiKeyRequest,
    principal: Principal = Depends(get_current_principal),
) -> CreatedApiKeyResponse:
    """Mint a new API key. The plaintext is returned exactly once."""
    from admz.audit import record_event

    try:
        # Inherit the creator's groups so the key has equivalent
        # group-derived permissions in the future (RBAC).
        created = _store().create(
            display_name=req.display_name,
            created_by=principal.name,
            expires_at=req.expires_at,
            groups=list(principal.groups),
        )
    except ValueError as e:
        record_event(
            principal, "api_key.create",
            resource=f"api-key:{req.display_name}",
            success=False, error_message=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e))

    record_event(
        principal, "api_key.create",
        resource=f"api-key:{created.record.id}",
        details={"display_name": req.display_name, "expires_at": req.expires_at},
    )

    response = _to_response(created.record)
    return CreatedApiKeyResponse(**response.model_dump(), plaintext=created.plaintext)


@router.delete("/api-keys/{id}", status_code=204)
async def revoke_api_key(
    id: int,
    principal: Principal = Depends(get_current_principal),
):
    """Revoke an API key. The row is preserved (marked ``revoked=1``)
    so the audit trail of who minted it remains intact."""
    from admz.audit import record_event

    if not _store().revoke(id):
        record_event(
            principal, "api_key.revoke",
            resource=f"api-key:{id}",
            success=False, error_message="not found or already revoked",
        )
        raise HTTPException(
            status_code=404,
            detail=f"API key {id} not found or already revoked.",
        )
    record_event(
        principal, "api_key.revoke", resource=f"api-key:{id}",
    )
    return None
