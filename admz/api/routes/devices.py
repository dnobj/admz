"""
REST API routes for device management.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

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
    DeviceReplaceRequest,
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


logger = logging.getLogger(__name__)

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
# secrets backend only at execution time. The `get_credentials` MCP tool is
# gone too (CR-1) — the short-lived `create_temp_credentials` flow is the
# LLM's path. Fleet-setting reveal (admin secrets like API keys) lives at
# GET /api/fleet/settings/{key}/reveal.


async def _run_onboarding(device_id: str, registry: DeviceRegistry, *, adopt: bool = False) -> dict:
    """Shared credential-onboarding call for the create/onboard routes.

    On ``credentials_needed`` a capture session is opened and its
    same-origin URL returned so the web UI can link straight to the
    secure form. Degrades to a status dict on any internal failure —
    onboarding must never fail a device add."""
    try:
        from admz.api.context import get_context
        from admz.onboarding import (
            APPROVAL_REQUIRED,
            CREDENTIALS_NEEDED,
            onboard_device_credentials,
        )

        ctx = get_context()
        result = await onboard_device_credentials(
            device_id=device_id,
            registry=registry,
            catalog=ctx.catalog,
            executors=ctx.executors,
            adopt=adopt,
        )
        # ADR-0059: a factory-defaulted device now needs approval before ADMZ
        # creates a root account on it. The blocked envelope is already in
        # `result` (confirm_token, confirm_url); pass it up UNCHANGED rather
        # than re-wording it here — three callers each phrasing their own
        # approval message is three places to drift, which is the failure
        # ADR-0059 exists to end.
        if result.get("status") == APPROVAL_REQUIRED:
            return result
        if result.get("status") == CREDENTIALS_NEEDED:
            from admz.api.capture import capture_store

            session = capture_store.create_session(
                device_id=device_id,
                purpose="Device onboarding — automatic resolution failed",
            )
            result["capture_url"] = f"/capture/{session.token}"
        return result
    except Exception as exc:  # noqa: BLE001 - never fail the add
        return {"status": "error", "reason": str(exc)}


@router.post("/devices/{device_id}/onboard")
async def onboard_device(
    request: Request,
    device_id: str,
    adopt: bool = False,
    registry: DeviceRegistry = Depends(get_registry),
):
    """Run credential onboarding for an existing device (e.g. one added
    before this flow existed, or whose stored credentials went stale).
    Returns the outcome status — never credentials."""
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    if not registry.device_exists(device_id):
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")
    result = await _run_onboarding(device_id, registry, adopt=adopt)
    record_event(principal, "device.onboard", resource=f"device:{device_id}",
                 details={"status": result.get("status"), "adopt": adopt})
    return result


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

        # Resolve credentials inline (stored-verify / auto-provision /
        # fleet-pair try / capture needed) — status only, never a password.
        onboarding = await _run_onboarding(device.device_id, registry)
        record_event(principal, "device.onboard", resource=resource,
                     details={"status": onboarding.get("status")})

        # Return the created device + onboarding outcome
        result = registry.get_device_info(device.device_id)
        result["onboarding"] = onboarding
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
        if "tags" in updates:
            _RESERVED = frozenset({"untagged"})
            bad = [t for t in updates["tags"] if t.lower() in _RESERVED]
            if bad:
                raise HTTPException(status_code=422, detail=f"Reserved tag names cannot be used: {bad}")
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


# Shared with the health monitor (admz/device_facts.py); kept as a
# module-local alias so existing call sites and their tests are unchanged.
from admz.device_facts import extract_device_facts as _extract_device_facts


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


@router.post("/devices/{device_id}/replace-hardware")
async def replace_device_hardware(
    request: Request,
    device_id: str,
    body: DeviceReplaceRequest,
    ctx: AppContext = Depends(get_context),
):
    """Rebind a stable slot (``device_id``) to a replacement unit (ADR-0036).

    Points the slot at the new unit's host, re-probes ``basicdeviceinfo``
    through the executor to read the new MAC/serial/firmware/model, and
    updates those *unit* attributes — keeping ``device_id`` (the slot). The
    slot's git config + baseline follow automatically, so the response flags
    whether a baseline is available to restore onto the new unit.
    """
    from admz import operations
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal
    from admz.device_registry import canonical_mac

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    registry = ctx.registry
    resource = f"device:{device_id}"

    if not registry.device_exists(device_id):
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")

    # Point the slot at the new unit so we can probe it.
    new_host = body.host.strip()
    if not new_host:
        raise HTTPException(status_code=400, detail="A replacement host is required.")
    registry.update_device_info(device_id, {"host": new_host, "ip_address": new_host})

    # ADR-0063: capability rows describe the UNIT, the key is the SLOT. What
    # the audit learned about the old unit's APIs says nothing about the new
    # one — forget it, so the next read probes.
    try:
        from admz.device_capabilities import capability_store
        capability_store.forget(device_id)
    except Exception:  # noqa: BLE001 — a rebind must not fail on bookkeeping
        logger.warning("capability rows not cleared for %s", device_id, exc_info=True)

    facts: Dict[str, str] = {}
    status = "ok"
    try:
        result = await operations.run_execution_tail(
            device_id=device_id,
            operation_id="basicdeviceinfo.cgi:getAllProperties",
            family="vapix",
            params={},
            catalog=ctx.catalog,
            registry=registry,
            executors=ctx.executors,
        )
        if result.success:
            facts = _extract_device_facts(result.parsed_data)
        else:
            status = "unreachable"
    except operations.OperationNotFoundError:
        raise HTTPException(
            status_code=501, detail="basicdeviceinfo operation not in the catalog.",
        )
    except Exception as exc:
        status = f"error: {exc}"

    # The new unit's MAC is its serial (Axis), normalized to the stored form.
    unit: Dict[str, str] = dict(facts)
    if facts.get("serial_number"):
        mac = canonical_mac(facts["serial_number"])
        if len(mac) == 12:
            unit["mac_address"] = mac
    if unit:
        try:
            registry.update_device_info(device_id, unit)
        except NotImplementedError:
            pass

    info = registry.get_device_info(device_id)
    has_baseline = bool(info.get("baseline_sha"))

    record_event(principal, "device.replace_hardware", resource=resource,
                 success=status == "ok",
                 details={"status": status, "host": new_host,
                          "updated": list(unit)})

    if status != "ok":
        return {
            "device_id": device_id, "rebound": False, "status": status,
            "host": new_host, "has_baseline": has_baseline,
            "message": (
                f"Pointed the slot at {new_host}, but couldn't read the new "
                "unit's facts (it may be unreachable or need credentials "
                "captured). The slot's config is unchanged and still "
                "restorable."
            ),
        }
    return {
        "device_id": device_id, "rebound": True, "status": status,
        "host": new_host, "unit": unit, "has_baseline": has_baseline,
        "message": (
            f"Slot {device_id} rebound to the new unit. Its saved "
            "configuration is unchanged"
            + (" — restore the baseline onto the new unit when ready."
               if has_baseline else "; snapshot it to set a baseline.")
        ),
    }


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
    ctx: AppContext = Depends(get_context),
):
    """
    Delete a device from the registry.

    CR-3: requires an authenticated principal. Anonymous deletion is
    too easy to do by accident in shared-host setups. Mint an API
    key (ADMZ_AUTH_BACKEND=api-key) or use Windows IWA to invoke.

    This also deletes all accounts associated with the device. A git
    tombstone (``Removed: <id>``) records the deliberate removal while
    keeping the config history. Note: not supported by all backends.
    """
    from admz import operations
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    registry = ctx.registry
    resource = f"device:{device_id}"

    try:
        if not registry.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        operations.tombstone_device(
            device_id, ctx.git_repo, removed_by=principal.name,
        )
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

    Gate: the caller must be an authenticated principal in one of the
    configured ADMZ_REVEAL_GROUPS (default ``Administrators`` +
    ``ADMZ-Admins``). Anonymous callers are always denied — the
    ``tool_get_credentials_enabled`` fallback that used to let
    ``ADMZ_AUTH_BACKEND=none`` installs through was removed (#151): its
    documented purpose (the deleted ``get_credentials`` MCP tool) no
    longer existed, and what it actually granted was unauthenticated
    access to plaintext secrets.

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
    if not allowed:
        if reason == "anonymous":
            detail = (
                "Reveal denied: fleet-setting plaintext requires an "
                "authenticated identity in one of the reveal groups "
                f"({', '.join(reveal_groups())}). Configure "
                "ADMZ_AUTH_BACKEND (e.g. windows-local or api-key) so "
                "callers carry a real identity — anonymous access to "
                "plaintext secrets is not supported."
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
        details={"decision": reason},
    )
    return {"key": key, "value": value}


# --------------------------------------------------------------------------
# Recovery of factory-defaulted devices (deferred actions, Slice 3)
# --------------------------------------------------------------------------

class RecoveryRequest(BaseModel):
    # Only 'reprovision' is queued (runs when the device returns factory-default);
    # 'remove' is immediate via DELETE /devices/{id}, so it isn't queued here.
    intent: str = "reprovision"
    username: str = "root"


@router.post("/devices/{device_id}/recovery")
async def queue_recovery(
    request: Request,
    device_id: str,
    req: RecoveryRequest,
    registry: DeviceRegistry = Depends(get_registry),
):
    """Queue a pre-authorized recovery for a factory-defaulted device: when it
    next reports needsetup (now, or after a future factory reset) the health
    sweep re-provisions it (creates the admin account from the fleet default
    password). Authenticated + audited."""
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal
    from admz.fleet.pending_actions import TRIGGER_NEEDS_SETUP, pending_actions

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    if not registry.device_exists(device_id):
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")
    if req.intent != "reprovision":
        raise HTTPException(
            status_code=400,
            detail="Only 'reprovision' is queueable here; remove a device via DELETE.",
        )

    # Non-interactive callers take the confirmation widget — same policy as
    # /api/tasks (the console's Recovery card is exempt: a human clicked it).
    from admz.tasks.gated import describe_create, gate_task_write, is_interactive
    if not is_interactive(principal):
        spec = {
            "trigger_kind": "detection", "action_type": "reprovision",
            "device_id": device_id, "event": "on_needs_setup",
            "action_params": {"username": req.username},
            "description": (
                f"Re-provision {device_id} when it returns factory-defaulted"
            ),
        }
        return gate_task_write("create_task", device_id, spec,
                               describe_create(spec))

    pid = pending_actions.create(
        device_id=device_id,
        action={"action": "reprovision", "username": req.username},
        trigger=TRIGGER_NEEDS_SETUP,
        approved_by=str(principal),
        description=f"Re-provision {device_id} when it returns factory-defaulted",
    )
    record_event(principal, "device.queue_recovery", resource=f"device:{device_id}",
                 details={"intent": "reprovision", "pending_id": pid})
    return {
        "success": True, "queued": True, "pending_id": pid,
        "message": ("Re-provision queued — runs on the next health check, or "
                    "after a future factory reset."),
    }


@router.get("/devices/{device_id}/pending")
async def list_pending(
    device_id: str, registry: DeviceRegistry = Depends(get_registry),
):
    """Active pending (deferred) actions for a device."""
    from admz.fleet.pending_actions import pending_actions
    return {
        "device_id": device_id,
        "pending": pending_actions.list_active_for(device_id),
    }


@router.post("/devices/{device_id}/pending/{pid}/cancel")
async def cancel_pending(
    request: Request,
    device_id: str,
    pid: str,
    registry: DeviceRegistry = Depends(get_registry),
):
    """Cancel a still-pending deferred action."""
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal
    from admz.fleet.pending_actions import pending_actions

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    if not pending_actions.cancel(pid):
        raise HTTPException(
            status_code=404, detail="No cancellable pending action with that id.",
        )
    record_event(principal, "device.cancel_pending", resource=f"device:{device_id}",
                 details={"pending_id": pid})
    return {"success": True, "cancelled": pid}
