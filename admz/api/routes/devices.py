"""
REST API routes for device management.
"""

from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.responses import JSONResponse

from admz.fleet_settings import (
    fleet_settings,
    is_sensitive_setting_key,
    mask_setting_value,
    mask_settings_for_display,
)
from admz.api.models import (
    DeviceCreate,
    DeviceUpdate,
    DeviceResponse,
    AccountCreate,
    AccountResponse,
    CredentialsResponse,
    ErrorResponse,
)
from admz.exceptions import (
    DeviceNotFoundError,
    AccountNotFoundError,
    PermissionDeniedError,
    BackendError,
)
from admz.device_registry import DeviceRegistry


router = APIRouter()


def get_registry() -> DeviceRegistry:
    """Dependency to get the device registry instance."""
    from admz.api.main import registry

    if registry is None:
        raise HTTPException(status_code=503, detail="Registry not initialized")
    return registry


@router.get("/devices", response_model=List[DeviceResponse])
async def list_devices(
    registry: DeviceRegistry = Depends(get_registry),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    location: Optional[str] = Query(None, description="Filter by location"),
):
    """
    List all devices in the registry.

    Optional filters:
    - tag: Filter devices by tag
    - location: Filter devices by location (case-insensitive partial match)
    """
    try:
        devices = registry.list_devices()

        # Apply filters
        if tag:
            devices = [d for d in devices if tag in d.get("tags", [])]

        if location:
            location_lower = location.lower()
            devices = [
                d
                for d in devices
                if location_lower in d.get("location", "").lower()
            ]

        return devices

    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BackendError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/devices/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: str,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Get device information by device ID.

    Can also use nickname instead of device_id by prefixing with 'nickname:'.
    Example: /api/devices/nickname:Front%20Door%20Camera
    """
    try:
        # Check if this is a nickname lookup
        if device_id.startswith("nickname:"):
            nickname = device_id[9:]  # Remove 'nickname:' prefix
            device = registry.get_device_by_nickname(nickname)
            if device is None:
                raise HTTPException(
                    status_code=404, detail=f"Device with nickname '{nickname}' not found"
                )
            return device
        else:
            # Normal device_id lookup
            device = registry.get_device_info(device_id)
            return device

    except DeviceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BackendError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/devices/{device_id}/accounts", response_model=List[AccountResponse])
async def list_device_accounts(
    device_id: str,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    List all accounts for a device.

    Returns account metadata without passwords.
    """
    try:
        accounts = registry.list_accounts(device_id)
        return accounts

    except DeviceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BackendError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get(
    "/devices/{device_id}/credentials", response_model=CredentialsResponse
)
async def get_device_credentials(
    request: Request,
    device_id: str,
    registry: DeviceRegistry = Depends(get_registry),
    account_id: str = Query("default", description="Account identifier"),
    requester: Optional[str] = Query(
        None, description="Requester identifier for audit logging"
    ),
):
    """
    Get credentials for a device account.

    WARNING: This endpoint returns sensitive credentials including passwords.
    Disabled by default; enable by setting the fleet setting
    ``tool_get_credentials_enabled = "true"`` via the ``/confirm-settings``
    web UI. Mirrors the gating of the MCP ``get_credentials`` tool —
    the LLM and REST surfaces must agree on whether credential retrieval
    is allowed.

    Every call is audit-logged with the authenticated principal as
    requester (Phase 4D).
    """
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import principal_can_reveal, reveal_groups

    principal = await get_current_principal(request)
    audit_requester = requester or principal.name
    resource = f"device:{device_id}/account:{account_id}"

    # Two-layer gate:
    #   1. Authenticated principals: must be in one of the configured
    #      reveal groups (ADMZ_REVEAL_GROUPS — default Administrators
    #      + ADMZ-Admins). This is the Phase-4 RBAC path: trust real
    #      identity, not a fleet-wide on/off flag.
    #   2. Anonymous principals (ADMZ_AUTH_BACKEND=none — the default
    #      for local single-user installs): fall back to the existing
    #      web_reveal_credentials_enabled / tool_get_credentials_enabled
    #      flag pair. Without this fallback the Reveal button would
    #      stop working entirely for every dev who hasn't stood up IIS.
    allowed, reason = principal_can_reveal(principal)
    flag_fallback_used = False
    if not allowed:
        if reason == "anonymous-fallback":
            web_enabled = fleet_settings.get("web_reveal_credentials_enabled") == "true"
            llm_enabled = fleet_settings.get("tool_get_credentials_enabled") == "true"
            if web_enabled or llm_enabled:
                allowed = True
                reason = (
                    "flag:web_reveal_credentials_enabled"
                    if web_enabled
                    else "flag:tool_get_credentials_enabled"
                )
                flag_fallback_used = True

    if not allowed:
        # Build a message that's actionable for both deployment shapes.
        if reason == "anonymous-fallback":
            detail = (
                "Plaintext credential retrieval is disabled. Enable the "
                "Reveal button via 'Allow web UI to reveal passwords' at "
                "/confirm-settings (preferred — does not expose passwords "
                "to LLMs), or — for LLM access too — 'Allow LLMs to "
                "retrieve plaintext'. Underlying fleet settings: "
                "'web_reveal_credentials_enabled' (web only) or "
                "'tool_get_credentials_enabled' (also exposes the MCP tool)."
            )
        else:
            detail = (
                "Reveal denied: your account is authenticated but not in "
                f"any of the configured reveal groups ({', '.join(reveal_groups())}). "
                f"Decision: {reason}. Ask an administrator to add you to "
                "one of those groups, or override the list via the "
                "ADMZ_REVEAL_GROUPS environment variable."
            )
        record_event(
            principal, "get_credentials",
            resource=resource,
            success=False,
            error_message=f"reveal-denied:{reason}",
            details={
                "requester_override": requester,
                "decision": reason,
            },
        )
        raise HTTPException(status_code=403, detail=detail)

    try:
        credentials = registry.get_credentials(device_id, account_id, audit_requester)
        record_event(
            principal, "get_credentials",
            resource=resource,
            details={
                "requester_override": requester,
                "decision": reason,
                "flag_fallback": flag_fallback_used,
            },
        )
        return credentials

    except DeviceNotFoundError as e:
        record_event(principal, "get_credentials", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except AccountNotFoundError as e:
        record_event(principal, "get_credentials", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedError as e:
        record_event(principal, "get_credentials", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=403, detail=str(e))
    except BackendError as e:
        record_event(principal, "get_credentials", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        record_event(principal, "get_credentials", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/devices", response_model=DeviceResponse, status_code=201)
async def create_device(
    device: DeviceCreate,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Create a new device in the registry.

    Note: This endpoint may not be supported by all backends.
    """
    try:
        # Prepare device info dict
        device_info = device.model_dump(exclude={"device_id"}, exclude_none=True)

        # Create device
        registry.add_device(device.device_id, device_info)

        # Return the created device
        return registry.get_device_info(device.device_id)

    except NotImplementedError as e:
        raise HTTPException(
            status_code=501, detail="This registry does not support adding devices"
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BackendError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: str,
    device_update: DeviceUpdate,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Update a device in the registry. Only provided fields are merged
    into the existing device info; accounts are preserved.
    """
    try:
        updates = device_update.model_dump(exclude_none=True)
        updates.pop("device_id", None)
        registry.update_device(device_id, updates)
        return registry.get_device_info(device_id)

    except DeviceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(
            status_code=501, detail="This registry does not support updating devices"
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BackendError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/devices/{device_id}", status_code=204)
async def delete_device(
    device_id: str,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Delete a device from the registry.

    Note: This endpoint may not be supported by all backends.
    This will also delete all accounts associated with the device.
    """
    try:
        registry.remove_device(device_id)
        return None

    except DeviceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(
            status_code=501, detail="This registry does not support removing devices"
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BackendError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post(
    "/devices/{device_id}/accounts", response_model=AccountResponse, status_code=201
)
async def create_device_account(
    device_id: str,
    account: AccountCreate,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Create a new account for a device.

    Note: This endpoint may not be supported by all backends.
    """
    try:
        # Prepare account data
        account_data = account.model_dump(exclude={"account_id"})

        # Create account
        registry.add_account(device_id, account.account_id, account_data)

        # Return the created account (without password)
        accounts = registry.list_accounts(device_id)
        for acc in accounts:
            if acc.get("account_id") == account.account_id:
                return acc

        # Fallback if we can't find it in the list
        return AccountResponse(
            account_id=account.account_id,
            username=account.username,
            account_type=account.account_type,
            purpose=account.purpose,
            permissions=account.permissions,
            metadata=account.metadata,
        )

    except DeviceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(
            status_code=501, detail="This registry does not support adding accounts"
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BackendError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/devices/{device_id}/accounts/{account_id}", status_code=204)
async def delete_device_account(
    device_id: str,
    account_id: str,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Delete an account from a device.

    Note: This endpoint may not be supported by all backends.
    """
    try:
        registry.remove_account(device_id, account_id)
        return None

    except DeviceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(
            status_code=501, detail="This registry does not support removing accounts"
        )
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BackendError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ---- Fleet settings endpoints ----


@router.get("/fleet/settings")
async def get_fleet_settings() -> Dict[str, str]:
    """Get all fleet-wide settings. Password-shaped values are masked
    to match the MCP ``get_fleet_settings`` tool — the REST surface must
    not leak plaintext fleet passwords."""
    return mask_settings_for_display(fleet_settings.list_all())


@router.get("/fleet/settings/{key}")
async def get_fleet_setting(key: str):
    """Get a single fleet setting value. Password-shaped values are masked."""
    value = fleet_settings.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    if is_sensitive_setting_key(key):
        value = mask_setting_value(value)
    return {"key": key, "value": value}


@router.get("/fleet/settings/{key}/reveal")
async def reveal_fleet_setting(key: str, request: Request):
    """Return the plaintext value of a fleet setting.

    Uses the same RBAC gate as the per-account Reveal: caller must be
    in one of the configured ADMZ_REVEAL_GROUPS (default
    ``Administrators`` + ``ADMZ-Admins``). For ``ADMZ_AUTH_BACKEND=none``
    deployments, falls back to the ``web_reveal_credentials_enabled``
    fleet flag so local single-user installs still work.

    Non-sensitive keys are returned without any gate — there's nothing
    to protect — so the JS on the Fleet Settings page can use this one
    endpoint uniformly.

    Every successful reveal is audit-logged with the principal.
    """
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import principal_can_reveal, reveal_groups

    value = fleet_settings.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    # Non-sensitive keys are returned without an authz gate. The web
    # JS will still call this endpoint for them; that's fine — we
    # only need the gate for keys whose values would otherwise be
    # masked by mask_settings_for_display.
    if not is_sensitive_setting_key(key):
        return {"key": key, "value": value}

    principal = await get_current_principal(request)
    resource = f"fleet_setting:{key}"

    allowed, reason = principal_can_reveal(principal)
    flag_fallback_used = False
    if not allowed and reason == "anonymous-fallback":
        web_enabled = fleet_settings.get("web_reveal_credentials_enabled") == "true"
        llm_enabled = fleet_settings.get("tool_get_credentials_enabled") == "true"
        if web_enabled or llm_enabled:
            allowed = True
            reason = (
                "flag:web_reveal_credentials_enabled"
                if web_enabled
                else "flag:tool_get_credentials_enabled"
            )
            flag_fallback_used = True

    if not allowed:
        if reason == "anonymous-fallback":
            detail = (
                "Reveal denied: fleet-setting plaintext is gated. Enable "
                "the Reveal button via 'Allow web UI to reveal passwords' "
                "at /confirm-settings, or configure ADMZ_AUTH_BACKEND so "
                "your Windows identity can be checked against the reveal "
                "groups."
            )
        else:
            detail = (
                "Reveal denied: your account is authenticated but not in "
                f"any of the configured reveal groups ({', '.join(reveal_groups())}). "
                f"Decision: {reason}."
            )
        record_event(
            principal, "reveal_fleet_setting",
            resource=resource,
            success=False,
            error_message=f"reveal-denied:{reason}",
            details={"decision": reason},
        )
        raise HTTPException(status_code=403, detail=detail)

    record_event(
        principal, "reveal_fleet_setting",
        resource=resource,
        details={"decision": reason, "flag_fallback": flag_fallback_used},
    )
    return {"key": key, "value": value}
