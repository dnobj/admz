"""
Web UI routes for device management.
"""

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional

from admz.exceptions import (
    DeviceNotFoundError,
    AccountNotFoundError,
    PermissionDeniedError,
    BackendError,
)
from admz.device_registry import DeviceRegistry
from admz.fleet_settings import fleet_settings
from admz.api.confirm_store import (
    get_confirmation_level,
    hash_confirm_password,
    VALID_CONFIRMATION_LEVELS,
)


router = APIRouter()

# Setup templates
template_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))


def get_registry() -> DeviceRegistry:
    """Dependency to get the device registry instance."""
    from admz.api.main import registry

    if registry is None:
        raise HTTPException(status_code=503, detail="Registry not initialized")
    return registry


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Home page - Display list of all devices.
    """
    try:
        devices = registry.list_devices()

        # Sort devices by device_id
        devices.sort(key=lambda d: d.get("device_id", ""))

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "devices": devices,
                "title": "ADMZ - Device List",
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Failed to load devices",
                "message": str(e),
                "title": "Error",
            },
            status_code=500,
        )


@router.get("/device/{device_id}", response_class=HTMLResponse)
async def device_detail(
    request: Request,
    device_id: str,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Device detail page - Display device information and accounts.
    """
    try:
        # Get device info
        device = registry.get_device_info(device_id)

        # Get accounts (without passwords)
        try:
            accounts = registry.list_accounts(device_id)
        except Exception:
            accounts = []

        return templates.TemplateResponse(
            "device_detail.html",
            {
                "request": request,
                "device": device,
                "accounts": accounts,
                "title": f"Device: {device.get('nickname', device_id)}",
            },
        )

    except DeviceNotFoundError:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Device Not Found",
                "message": f"Device '{device_id}' not found",
                "title": "Error - Device Not Found",
            },
            status_code=404,
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Failed to load device",
                "message": str(e),
                "title": "Error",
            },
            status_code=500,
        )


@router.get("/device/{device_id}/account/{account_id}", response_class=HTMLResponse)
async def account_detail(
    request: Request,
    device_id: str,
    account_id: str,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Account detail page - Display account information without password.
    """
    try:
        # Get device info
        device = registry.get_device_info(device_id)

        # Get account info from the accounts list
        accounts = registry.list_accounts(device_id)
        account = None
        for acc in accounts:
            if acc.get("account_id") == account_id:
                account = acc
                break

        if not account:
            raise AccountNotFoundError(
                f"Account '{account_id}' not found for device '{device_id}'"
            )

        return templates.TemplateResponse(
            "account_detail.html",
            {
                "request": request,
                "device": device,
                "account": account,
                "title": f"Account: {account_id} - {device.get('nickname', device_id)}",
            },
        )

    except DeviceNotFoundError:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Device Not Found",
                "message": f"Device '{device_id}' not found",
                "title": "Error - Device Not Found",
            },
            status_code=404,
        )
    except AccountNotFoundError as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Account Not Found",
                "message": str(e),
                "title": "Error - Account Not Found",
            },
            status_code=404,
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Failed to load account",
                "message": str(e),
                "title": "Error",
            },
            status_code=500,
        )


@router.get("/add-device", response_class=HTMLResponse)
async def add_device_form(
    request: Request,
):
    """
    Add device form page.
    """
    return templates.TemplateResponse(
        "add_device.html",
        {
            "request": request,
            "title": "Add Device",
        },
    )


@router.get("/device/{device_id}/edit", response_class=HTMLResponse)
async def edit_device_form(
    request: Request,
    device_id: str,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Edit device form page.
    """
    try:
        device = registry.get_device_info(device_id)

        return templates.TemplateResponse(
            "edit_device.html",
            {
                "request": request,
                "device": device,
                "title": f"Edit Device: {device.get('nickname', device_id)}",
            },
        )

    except DeviceNotFoundError:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Device Not Found",
                "message": f"Device '{device_id}' not found",
                "title": "Error - Device Not Found",
            },
            status_code=404,
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Failed to load device",
                "message": str(e),
                "title": "Error",
            },
            status_code=500,
        )


@router.get("/device/{device_id}/add-account", response_class=HTMLResponse)
async def add_account_form(
    request: Request,
    device_id: str,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Add account form page.
    """
    try:
        device = registry.get_device_info(device_id)

        return templates.TemplateResponse(
            "add_account.html",
            {
                "request": request,
                "device": device,
                "title": f"Add Account - {device.get('nickname', device_id)}",
            },
        )

    except DeviceNotFoundError:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Device Not Found",
                "message": f"Device '{device_id}' not found",
                "title": "Error - Device Not Found",
            },
            status_code=404,
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Failed to load device",
                "message": str(e),
                "title": "Error",
            },
            status_code=500,
        )


@router.get("/search", response_class=HTMLResponse)
async def search_devices(
    request: Request,
    query: str = "",
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Search devices page.
    """
    try:
        devices = registry.list_devices()

        # Filter devices based on query
        if query:
            query_lower = query.lower()
            filtered_devices = []
            for device in devices:
                # Search in device_id, nickname, location, model, serial_number
                searchable_fields = [
                    str(device.get("device_id", "")),
                    str(device.get("nickname", "")),
                    str(device.get("location", "")),
                    str(device.get("model", "")),
                    str(device.get("serial_number", "")),
                    str(device.get("host", "")),
                ]

                # Also search in tags
                tags = device.get("tags", [])
                searchable_fields.extend([str(tag) for tag in tags])

                # Check if query matches any field
                if any(query_lower in field.lower() for field in searchable_fields):
                    filtered_devices.append(device)

            devices = filtered_devices

        # Sort devices by device_id
        devices.sort(key=lambda d: d.get("device_id", ""))

        return templates.TemplateResponse(
            "search.html",
            {
                "request": request,
                "devices": devices,
                "query": query,
                "title": f"Search Results: {query}" if query else "Search Devices",
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Search failed",
                "message": str(e),
                "title": "Error",
            },
            status_code=500,
        )


@router.get("/fleet-settings", response_class=HTMLResponse)
async def fleet_settings_page(request: Request):
    """Fleet settings page — view fleet-wide configuration."""
    settings = fleet_settings.list_all()
    # Mask password values for initial render (revealed client-side)
    display = {}
    for k, v in settings.items():
        if "password" in k.lower():
            display[k] = f"({'*' * min(len(v), 8)})"
        else:
            display[k] = v

    return templates.TemplateResponse(
        "fleet_settings.html",
        {
            "request": request,
            "settings": display,
            "title": "Fleet Settings",
        },
    )


# ── Confirmation settings ────────────────────────────────────────────────

def _build_confirm_settings_context(request: Request, **extra):
    """Build the template context for the confirm-settings page."""
    risk_levels = ["dangerous", "service-affecting", "normal", "read-only"]
    levels = {r: get_confirmation_level(r) for r in risk_levels}
    has_password = bool(fleet_settings.get("confirm_password_hash"))
    get_creds_enabled = fleet_settings.get("tool_get_credentials_enabled") == "true"
    ctx = {
        "request": request,
        "title": "Confirmation Settings",
        "levels": levels,
        "has_password": has_password,
        "get_creds_enabled": get_creds_enabled,
    }
    ctx.update(extra)
    return ctx


@router.get("/confirm-settings", response_class=HTMLResponse)
async def confirm_settings_page(request: Request):
    """Confirmation settings page — configure confirmation levels and password."""
    return templates.TemplateResponse(
        "confirm_settings.html",
        _build_confirm_settings_context(request),
    )


@router.post("/confirm-settings", response_class=HTMLResponse)
async def confirm_settings_save(
    request: Request,
    action: str = Form(...),
    # Level fields (only present when action=levels)
    level_dangerous: Optional[str] = Form(None),
    level_service_affecting: Optional[str] = Form(None, alias="level_service-affecting"),
    level_normal: Optional[str] = Form(None),
    level_read_only: Optional[str] = Form(None, alias="level_read-only"),
    # Password fields (only present when action=password)
    new_password: Optional[str] = Form(None),
    confirm_new_password: Optional[str] = Form(None),
):
    """Save confirmation settings."""
    if action == "levels":
        mapping = {
            "dangerous": level_dangerous,
            "service-affecting": level_service_affecting,
            "normal": level_normal,
            "read-only": level_read_only,
        }
        for risk, level in mapping.items():
            key = f"confirm_level_{risk}"
            if level and level in VALID_CONFIRMATION_LEVELS:
                fleet_settings.set(key, level)

        return templates.TemplateResponse(
            "confirm_settings.html",
            _build_confirm_settings_context(
                request, success="Confirmation levels saved."
            ),
        )

    elif action == "password":
        # Empty password → remove
        if not new_password:
            fleet_settings.delete("confirm_password_hash")
            return templates.TemplateResponse(
                "confirm_settings.html",
                _build_confirm_settings_context(
                    request, success="Confirmation password removed."
                ),
            )

        if new_password != confirm_new_password:
            return templates.TemplateResponse(
                "confirm_settings.html",
                _build_confirm_settings_context(
                    request, error="Passwords do not match."
                ),
            )

        hashed = hash_confirm_password(new_password)
        fleet_settings.set("confirm_password_hash", hashed)
        return templates.TemplateResponse(
            "confirm_settings.html",
            _build_confirm_settings_context(
                request, success="Confirmation password updated."
            ),
        )

    elif action == "tool_toggle":
        form_data = await request.form()
        enabled = "get_credentials_enabled" in form_data
        if enabled:
            fleet_settings.set("tool_get_credentials_enabled", "true")
        else:
            fleet_settings.delete("tool_get_credentials_enabled")
        return templates.TemplateResponse(
            "confirm_settings.html",
            _build_confirm_settings_context(
                request, success="MCP tool access settings saved."
            ),
        )

    return templates.TemplateResponse(
        "confirm_settings.html",
        _build_confirm_settings_context(request, error="Unknown action."),
    )
