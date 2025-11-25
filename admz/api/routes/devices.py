"""
REST API routes for device management.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse

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
    Ensure proper authentication and authorization before exposing this endpoint.

    Parameters:
    - device_id: Device identifier
    - account_id: Account identifier (default: 'default')
    - requester: Optional requester identifier for audit logging
    """
    try:
        credentials = registry.get_credentials(device_id, account_id, requester)
        return credentials

    except DeviceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BackendError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
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
    Update a device in the registry.

    Note: This is implemented as remove + add, so it may not be supported by all backends.
    Only provided fields will be updated.
    """
    try:
        # Get existing device info
        existing_device = registry.get_device_info(device_id)

        # Get existing accounts
        existing_accounts = {}
        try:
            accounts = registry.list_accounts(device_id)
            for account in accounts:
                account_id = account.get("account_id")
                if account_id:
                    # Get full credentials for each account
                    creds = registry.get_credentials(device_id, account_id)
                    existing_accounts[account_id] = creds
        except Exception:
            # If we can't get accounts, continue anyway
            pass

        # Merge updates with existing device info
        updated_info = {**existing_device}
        update_dict = device_update.model_dump(exclude_none=True)
        updated_info.update(update_dict)

        # Remove device_id from the info dict (it's the key)
        updated_info.pop("device_id", None)

        # Remove and re-add device
        registry.remove_device(device_id)
        registry.add_device(device_id, updated_info, existing_accounts)

        # Return the updated device
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
