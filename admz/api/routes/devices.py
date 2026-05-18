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

    principal = await get_current_principal(request)
    audit_requester = requester or principal.name
    resource = f"device:{device_id}/account:{account_id}"

    # Gate on the same fleet flag the MCP server uses
    if fleet_settings.get("tool_get_credentials_enabled") != "true":
        record_event(
            principal, "get_credentials",
            resource=resource,
            success=False,
            error_message="disabled by fleet flag",
            details={"requester_override": requester},
        )
        raise HTTPException(
            status_code=403,
            detail=(
                "Credential retrieval is disabled. Enable it by setting "
                "'tool_get_credentials_enabled' to 'true' via the web UI at "
                "/confirm-settings."
            ),
        )

    try:
        credentials = registry.get_credentials(device_id, account_id, audit_requester)
        record_event(
            principal, "get_credentials",
            resource=resource,
            details={"requester_override": requester},
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
