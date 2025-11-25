"""
Web UI routes for device management.
"""

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from admz.exceptions import (
    DeviceNotFoundError,
    AccountNotFoundError,
    PermissionDeniedError,
    BackendError,
)
from admz.device_registry import DeviceRegistry


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
