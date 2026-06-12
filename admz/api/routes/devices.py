"""
REST API routes for device management.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.responses import JSONResponse

from admz.api.context import AppContext, get_context
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
    DeviceSiteUpdate,
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


# NOTE: the device-credential reveal endpoint (GET
# /api/devices/{id}/credentials) was removed — device-account passwords are
# never displayed through the web/REST surface. ADMZ reads them from the
# secrets backend only at execution time. The LLM path (`get_credentials`
# MCP tool, gated by tool_get_credentials_enabled) and the short-lived
# `create_temp_credentials` flow are unaffected. Fleet-setting reveal (admin
# secrets like API keys) lives at GET /api/fleet/settings/{key}/reveal.


@router.post("/devices", response_model=DeviceResponse, status_code=201)
async def create_device(
    request: Request,
    device: DeviceCreate,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Create a new device in the registry.

    Note: This endpoint may not be supported by all backends.
    """
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    resource = f"device:{device.device_id}"

    try:
        # Prepare device info dict
        device_info = device.model_dump(exclude={"device_id"}, exclude_none=True)

        # Create device
        registry.add_device(device.device_id, device_info)

        # Return the created device
        result = registry.get_device_info(device.device_id)
        record_event(principal, "device.create", resource=resource)
        return result

    except NotImplementedError as e:
        record_event(principal, "device.create", resource=resource,
                     success=False, error_message=f"NotImplemented: {e}")
        raise HTTPException(
            status_code=501, detail="This registry does not support adding devices"
        )
    except PermissionDeniedError as e:
        record_event(principal, "device.create", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=403, detail=str(e))
    except BackendError as e:
        record_event(principal, "device.create", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        record_event(principal, "device.create", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/devices/{device_id}", response_model=DeviceResponse)
async def update_device(
    request: Request,
    device_id: str,
    device_update: DeviceUpdate,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Update a device in the registry. Only provided fields are merged
    into the existing device info; accounts are preserved.
    """
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    resource = f"device:{device_id}"

    try:
        updates = device_update.model_dump(exclude_none=True)
        updates.pop("device_id", None)
        registry.update_device(device_id, updates)
        result = registry.get_device_info(device_id)
        record_event(principal, "device.update", resource=resource,
                     details={"fields": list(updates.keys())})
        return result

    except DeviceNotFoundError as e:
        record_event(principal, "device.update", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except NotImplementedError as e:
        record_event(principal, "device.update", resource=resource,
                     success=False, error_message=f"NotImplemented: {e}")
        raise HTTPException(
            status_code=501, detail="This registry does not support updating devices"
        )
    except PermissionDeniedError as e:
        record_event(principal, "device.update", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=403, detail=str(e))
    except BackendError as e:
        record_event(principal, "device.update", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        record_event(principal, "device.update", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def _extract_device_facts(parsed: Any) -> Dict[str, str]:
    """Pull model / serial / firmware out of a basicdeviceinfo response.

    Robust to shape: the props can sit under ``data.propertyList``,
    ``data.properties``, or at the top level, and the payload may arrive as
    a dict (json-rpc) or a ``key=value`` string (legacy). Keys are matched
    case-insensitively (ProdNbr / SerialNumber / Version)."""
    import json as _json

    props: Dict[str, str] = {}

    def _walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    _walk(v)
                else:
                    props.setdefault(str(k).lower(), v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    if isinstance(parsed, str):
        try:
            _walk(_json.loads(parsed))
        except Exception:
            for line in parsed.splitlines():
                if "=" in line:
                    k, _, v = line.partition("=")
                    props.setdefault(k.strip().lower(), v.strip())
    else:
        _walk(parsed)

    facts: Dict[str, str] = {}
    if props.get("prodnbr"):
        facts["model"] = str(props["prodnbr"])
    if props.get("serialnumber"):
        facts["serial_number"] = str(props["serialnumber"])
    if props.get("version"):
        facts["firmware_version"] = str(props["version"])
    return facts


@router.post("/devices/{device_id}/refresh-info")
async def refresh_device_info(
    request: Request,
    device_id: str,
    ctx: AppContext = Depends(get_context),
):
    """Re-read the device's observed facts (model, serial, firmware) from
    the device itself and update the registry.

    These fields describe what the hardware *is* — they're discovered, not
    operator-set, and feed facet selection, capability checks, and atlas
    contributions. The correct way to change them is to re-read reality
    (this endpoint), not to hand-edit. Runs ``basicdeviceinfo.cgi`` through
    the executor (which knows the device's scheme/auth and self-heals);
    credentials never leave the server.
    """
    from admz import operations
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    resource = f"device:{device_id}"

    if not ctx.registry.device_exists(device_id):
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")

    status = "ok"
    facts: Dict[str, str] = {}
    try:
        result = await operations.run_execution_tail(
            device_id=device_id,
            operation_id="basicdeviceinfo.cgi:getAllProperties",
            family="vapix",
            params={},
            catalog=ctx.catalog,
            registry=ctx.registry,
            executors=ctx.executors,
        )
        if result.success:
            facts = _extract_device_facts(result.parsed_data)
        else:
            status = "unreachable"
    except operations.OperationNotFoundError:
        raise HTTPException(
            status_code=501,
            detail="basicdeviceinfo operation not in the catalog.",
        )
    except Exception as exc:
        status = f"error: {exc}"

    if facts:
        try:
            ctx.registry.update_device_info(device_id, facts)
        except NotImplementedError:
            pass

    record_event(principal, "device.refresh_info", resource=resource,
                 success=bool(facts),
                 details={"status": status, "updated": list(facts)})

    if not facts:
        return {
            "device_id": device_id,
            "status": status,
            "updated": {},
            "message": (
                "Couldn't read device facts — check the device is reachable "
                "and its credentials are stored."
            ),
        }
    return {"device_id": device_id, "status": status, "updated": facts}


@router.put("/devices/{device_id}/site")
async def move_device_to_site(
    request: Request,
    device_id: str,
    body: DeviceSiteUpdate,
    registry: DeviceRegistry = Depends(get_registry),
):
    """Move a device to a different Site (ADR-0032).

    A device always belongs to exactly one Site — there's no "site-less"
    state — so this reassigns it. The owning Org is derived from the
    target Site. To remove a device from ADMZ entirely, delete it
    (``DELETE /api/devices/{id}``).
    """
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    resource = f"device:{device_id}"

    try:
        site = registry.get_site(body.site_id)
        if site is None:
            raise HTTPException(status_code=404, detail=f"Site '{body.site_id}' not found")
        registry.set_device_org_site(device_id, site["org_id"], body.site_id)
        record_event(principal, "device.move_site", resource=resource,
                     details={"site_id": body.site_id, "org_id": site["org_id"]})
        return {"device_id": device_id, "site_id": body.site_id,
                "org_id": site["org_id"]}
    except DeviceNotFoundError as e:
        record_event(principal, "device.move_site", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except NotImplementedError:
        record_event(principal, "device.move_site", resource=resource,
                     success=False, error_message="sites-unsupported")
        raise HTTPException(
            status_code=501, detail="This registry does not support sites"
        )
    except BackendError as e:
        record_event(principal, "device.move_site", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/devices/{device_id}", status_code=204)
async def delete_device(
    request: Request,
    device_id: str,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Delete a device from the registry.

    CR-3: requires an authenticated principal. Anonymous deletion is
    too easy to do by accident in shared-host setups. Mint an API
    key (ADMZ_AUTH_BACKEND=api-key) or use Windows IWA to invoke.

    This also deletes all accounts associated with the device.
    Note: not supported by all backends.
    """
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    resource = f"device:{device_id}"

    try:
        registry.remove_device(device_id)
        record_event(principal, "device.delete", resource=resource)
        return None

    except DeviceNotFoundError as e:
        record_event(principal, "device.delete", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except NotImplementedError as e:
        record_event(principal, "device.delete", resource=resource,
                     success=False, error_message=f"NotImplemented: {e}")
        raise HTTPException(
            status_code=501, detail="This registry does not support removing devices"
        )
    except PermissionDeniedError as e:
        record_event(principal, "device.delete", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=403, detail=str(e))
    except BackendError as e:
        record_event(principal, "device.delete", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        record_event(principal, "device.delete", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post(
    "/devices/{device_id}/accounts", response_model=AccountResponse, status_code=201
)
async def create_device_account(
    request: Request,
    device_id: str,
    account: AccountCreate,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Create a new account for a device.

    Note: This endpoint may not be supported by all backends.
    """
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    resource = f"device:{device_id}/account:{account.account_id}"

    try:
        # Prepare account data
        account_data = account.model_dump(exclude={"account_id"})

        # Create account
        registry.add_account(device_id, account.account_id, account_data)

        # Return the created account (without password)
        accounts = registry.list_accounts(device_id)
        record_event(principal, "account.create", resource=resource)
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
        record_event(principal, "account.create", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except NotImplementedError as e:
        record_event(principal, "account.create", resource=resource,
                     success=False, error_message=f"NotImplemented: {e}")
        raise HTTPException(
            status_code=501, detail="This registry does not support adding accounts"
        )
    except PermissionDeniedError as e:
        record_event(principal, "account.create", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=403, detail=str(e))
    except BackendError as e:
        record_event(principal, "account.create", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        record_event(principal, "account.create", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/devices/{device_id}/accounts/{account_id}", status_code=204)
async def delete_device_account(
    request: Request,
    device_id: str,
    account_id: str,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Delete an account from a device.

    Note: This endpoint may not be supported by all backends.
    """
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    resource = f"device:{device_id}/account:{account_id}"

    try:
        registry.remove_account(device_id, account_id)
        record_event(principal, "account.delete", resource=resource)
        return None

    except DeviceNotFoundError as e:
        record_event(principal, "account.delete", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except AccountNotFoundError as e:
        record_event(principal, "account.delete", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=404, detail=str(e))
    except NotImplementedError as e:
        record_event(principal, "account.delete", resource=resource,
                     success=False, error_message=f"NotImplemented: {e}")
        raise HTTPException(
            status_code=501, detail="This registry does not support removing accounts"
        )
    except PermissionDeniedError as e:
        record_event(principal, "account.delete", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=403, detail=str(e))
    except BackendError as e:
        record_event(principal, "account.delete", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        record_event(principal, "account.delete", resource=resource,
                     success=False, error_message=str(e))
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
    """Return the plaintext value of a fleet setting (admin secrets like
    API keys — NOT device-account passwords, which are never revealable).

    Gate: the caller must be in one of the configured ADMZ_REVEAL_GROUPS
    (default ``Administrators`` + ``ADMZ-Admins``). For
    ``ADMZ_AUTH_BACKEND=none`` deployments — where there's no identity to
    group-check — it falls back to the ``tool_get_credentials_enabled``
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
        if fleet_settings.get("tool_get_credentials_enabled") == "true":
            allowed = True
            reason = "flag:tool_get_credentials_enabled"
            flag_fallback_used = True

    if not allowed:
        if reason == "anonymous-fallback":
            detail = (
                "Reveal denied: fleet-setting plaintext is gated. Configure "
                "ADMZ_AUTH_BACKEND so your Windows identity can be checked "
                "against the reveal groups, or (for a single-user install) "
                "enable 'Allow LLMs to retrieve plaintext' at "
                "/confirm-settings."
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
