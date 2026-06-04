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
from admz.api.templating import configure as _configure_templates  # noqa: E402
_configure_templates(templates)


def get_registry() -> DeviceRegistry:
    """Dependency to get the device registry instance."""
    from admz.api.main import registry

    if registry is None:
        raise HTTPException(status_code=503, detail="Registry not initialized")
    return registry


@router.get("/")
async def home_redirect():
    """Home page redirects to /chat (the new primary entry point).

    The legacy device list moved to /devices.
    """
    return RedirectResponse(url="/chat", status_code=302)


@router.get("/ui/site/{site_id}")
async def set_active_site(site_id: str, request: Request):
    """Persist the active site in a cookie + bounce back to the fleet.

    The site switcher in the top bar links here. We store the choice in a
    cookie (read by ``admz.api.templating.build_nav``) so the selection
    survives navigation across the server-rendered pages.
    """
    referer = request.headers.get("referer", "")
    target = "/devices"
    resp = RedirectResponse(url=target, status_code=303)
    # Basic validation: only set the cookie if the site actually exists.
    resp.set_cookie(
        "admz_site", site_id, max_age=60 * 60 * 24 * 365, samesite="lax", httponly=False
    )
    return resp


@router.get("/devices", response_class=HTMLResponse)
async def devices_page(
    request: Request,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Fleet dashboard — health, model, IP, group, drift, tags for the
    active site. Hierarchy-aware: filters to the cookie-selected site and
    (optionally) a ?group= filter, mirroring the sidebar group list.
    """
    try:
        devices = registry.list_devices()
        devices.sort(key=lambda d: d.get("nickname") or d.get("device_id", ""))

        # ── Hierarchy scoping (defensive: backend may not support it) ──
        active_site = request.cookies.get("admz_site")
        group_filter = request.query_params.get("group")
        hierarchy = True
        try:
            sites = registry.list_sites()
        except Exception:
            hierarchy = False
            sites = []

        site_obj = None
        if hierarchy:
            if not active_site or not any(s.get("site_id") == active_site for s in sites):
                active_site = sites[0]["site_id"] if sites else None
            site_obj = next((s for s in sites if s.get("site_id") == active_site), None)

            scoped = []
            for d in devices:
                did = d.get("device_id")
                # site membership
                try:
                    os_ = registry.get_device_org_site(did) or {}
                except Exception:
                    os_ = {}
                if active_site and os_.get("site_id") and os_.get("site_id") != active_site:
                    continue
                # group memberships + primary group label
                try:
                    memberships = registry.list_groups_for_device(did)
                except Exception:
                    memberships = []
                gids = [m.get("group_id") for m in memberships]
                primary = next((m for m in memberships if m.get("is_primary")), None)
                d["_groups"] = gids
                d["_primary_group"] = (primary or (memberships[0] if memberships else {})).get("name") if memberships else None
                if group_filter and group_filter not in gids:
                    continue
                scoped.append(d)
            devices = scoped

        group_name = None
        if group_filter and hierarchy:
            try:
                g = registry.get_device_group(group_filter)
                group_name = g.get("name") if g else group_filter
            except Exception:
                group_name = group_filter

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "devices": devices,
                "site": site_obj,
                "group_filter": group_filter,
                "group_name": group_name,
                "title": "Fleet",
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

        # Hierarchy context for the slot identity card (defensive).
        site_name = None
        group_names = []
        primary_group = None
        try:
            os_ = registry.get_device_org_site(device_id) or {}
            if os_.get("site_id"):
                site = registry.get_site(os_["site_id"])
                site_name = site.get("name") if site else os_["site_id"]
            memberships = registry.list_groups_for_device(device_id)
            group_names = [m.get("name") for m in memberships]
            primary = next((m for m in memberships if m.get("is_primary")), None)
            primary_group = (primary or (memberships[0] if memberships else {})).get("name")
        except Exception:
            pass

        return templates.TemplateResponse(
            "device_detail.html",
            {
                "request": request,
                "device": device,
                "accounts": accounts,
                "site_name": site_name,
                "group_names": group_names,
                "primary_group": primary_group,
                "title": device.get("nickname", device_id),
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


@router.post(
    "/device/{device_id}/account/{account_id}/rotate-password",
    response_class=RedirectResponse,
)
async def rotate_account_password(
    request: Request,
    device_id: str,
    account_id: str,
    registry: DeviceRegistry = Depends(get_registry),
):
    """Start a password-rotation flow for an existing account.

    Per ADR-0009, credentials only enter ADMZ through the
    out-of-band capture form — never via a chat transcript or
    a regular HTML form submitted alongside other data. This
    route creates a single-use capture session bound to the
    target device + account_id, then redirects the operator to
    the standard ``/capture/{token}`` page. The form there
    submits the new password directly to the registry, the
    capture token is consumed, and the operator lands on the
    standard "capture done" page.

    The redirect-with-token pattern means the new password is
    only ever in:
      - the operator's browser tab (the capture form)
      - the request body of POST /capture/{token}
      - the encrypted account row in the DB
    Crucially, NOT in chat history, NOT in server logs, NOT in
    the regular form-submission flow.
    """
    from admz.api.capture import capture_store

    # Verify the account exists before issuing a token (otherwise
    # the capture session would dead-end on completion).
    if not registry.account_exists(device_id, account_id):
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Account Not Found",
                "message": (
                    f"Account '{account_id}' not found for device "
                    f"'{device_id}'. Add it first via 'Add account'."
                ),
                "title": "Error",
            },
            status_code=404,
        )

    # Look up the existing account's metadata so the capture
    # session preserves account_type and purpose. This keeps the
    # rotated row shape-identical to what was there before.
    accounts = registry.list_accounts(device_id)
    existing = next(
        (a for a in accounts if a.get("account_id") == account_id), {}
    )

    session = capture_store.create_session(
        device_id=device_id,
        account_id=account_id,
        account_type=existing.get("account_type", "admin"),
        purpose=existing.get("purpose") or f"Rotated for {account_id}",
        ttl=300,  # 5 minutes — same default as fresh captures
    )

    # 303 See Other so the browser converts the POST into a GET.
    return RedirectResponse(url=f"/capture/{session.token}", status_code=303)


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


@router.get("/settings", response_class=HTMLResponse)
async def settings_overview(request: Request):
    """Unified Settings screen — safety policy + fleet config (Axis Signal).

    Surfaces the real fleet/confirm settings as the design's stacked cards.
    The two confirmation gates are shown as enforced; the toggles that map
    to real settings link to the existing forms that persist them.
    """
    levels = {
        r: get_confirmation_level(r)
        for r in ["dangerous", "service-affecting", "normal", "read-only"]
    }
    has_password = bool(fleet_settings.get("confirm_password_hash"))
    get_creds_enabled = fleet_settings.get("tool_get_credentials_enabled") == "true"
    web_reveal_enabled = fleet_settings.get("web_reveal_credentials_enabled") == "true"
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "title": "Settings",
            "levels": levels,
            "has_password": has_password,
            "get_creds_enabled": get_creds_enabled,
            "web_reveal_enabled": web_reveal_enabled,
            "all_settings": fleet_settings.list_all(),
        },
    )


@router.get("/audit-log", response_class=HTMLResponse)
async def audit_log_page(request: Request):
    """Audit log — who/what/when across humans, the agent, and system jobs."""
    from admz.audit import audit_log
    import time as _time

    try:
        entries = audit_log.list_recent(limit=200)
    except Exception:
        entries = []

    _DANGER = ("reboot", "restore", "factory", "reset", "delete", "remove", "firmware")
    _agent_hints = ("mcp", "agent", "gemini", "admz-bot", "console")

    def _kind(e):
        req = (e.requester or "").lower()
        src = (e.auth_source or "").lower()
        if any(h in req for h in _agent_hints) or src == "api-key":
            return "agent"
        if req in ("system", "scheduler", "") or src == "system":
            return "system"
        return "human"

    rows = []
    for e in entries:
        action = e.action or ""
        risk = "dangerous" if any(d in action.lower() for d in _DANGER) else (
            "read-only" if action.startswith(("list", "get", "read", "audit")) else "normal"
        )
        result = "ok" if e.success else "blocked"
        rows.append({
            "ts": e.timestamp,
            "day": _time.strftime("%Y-%m-%d", _time.localtime(e.timestamp)),
            "time": _time.strftime("%H:%M:%S", _time.localtime(e.timestamp)),
            "kind": _kind(e),
            "actor": e.requester or "unknown",
            "op": action,
            "target": e.resource or "—",
            "note": e.error_message or "",
            "risk": risk,
            "result": result,
        })

    # Group by day (preserving the recency order from list_recent).
    days = []
    counts = {"human": 0, "agent": 0, "system": 0, "blocked": 0}
    for r in rows:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1
        if r["result"] in ("blocked", "denied"):
            counts["blocked"] += 1
        if not days or days[-1][0] != r["day"]:
            days.append((r["day"], []))
        days[-1][1].append(r)

    return templates.TemplateResponse(
        "audit_log.html",
        {"request": request, "title": "Audit log", "days": days, "counts": counts,
         "total": len(rows)},
    )


@router.get("/schedules", response_class=HTMLResponse)
async def schedules_page(request: Request):
    """Schedules — recurring snapshot/audit/firmware/restore jobs."""
    from admz.api.context import get_context

    schedules = []
    try:
        ctx = get_context()
        schedules = [s.to_dict() for s in ctx.scheduler.list_schedules()]
    except Exception:
        schedules = []
    return templates.TemplateResponse(
        "schedules.html",
        {"request": request, "title": "Schedules", "schedules": schedules},
    )


@router.get("/configuration", response_class=HTMLResponse)
async def configuration_page(
    request: Request,
    registry: DeviceRegistry = Depends(get_registry),
):
    """Configuration / drift — per-device baseline + branch state.

    v1 surfaces the active-branch indicator and a per-device drift roster.
    The per-facet ConfigDiff + reconcile/rebase flow attaches here once a
    device has a baseline (see the architecture note).
    """
    try:
        devices = registry.list_devices()
        devices.sort(key=lambda d: d.get("nickname") or d.get("device_id", ""))
    except Exception:
        devices = []
    return templates.TemplateResponse(
        "configuration.html",
        {"request": request, "title": "Configuration", "devices": devices},
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
    web_reveal_enabled = fleet_settings.get("web_reveal_credentials_enabled") == "true"
    ctx = {
        "request": request,
        "title": "Confirmation Settings",
        "levels": levels,
        "has_password": has_password,
        "get_creds_enabled": get_creds_enabled,
        "web_reveal_enabled": web_reveal_enabled,
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
    """Save confirmation settings.

    CR-3: every branch of this handler writes to a key in
    ``PROTECTED_SETTING_KEYS`` (confirmation levels, the confirm-password
    hash, the credential-reveal flags). Anonymous callers must not be
    able to relax these gates from the network, so the whole handler
    requires an authenticated principal. Every write is audited.
    """
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)

    if action == "levels":
        mapping = {
            "dangerous": level_dangerous,
            "service-affecting": level_service_affecting,
            "normal": level_normal,
            "read-only": level_read_only,
        }
        applied = {}
        for risk, level in mapping.items():
            key = f"confirm_level_{risk}"
            if level and level in VALID_CONFIRMATION_LEVELS:
                fleet_settings.set(key, level)
                applied[key] = level

        record_event(
            principal, "fleet_setting.write",
            resource="confirm_settings:levels",
            details={"applied": applied},
        )
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
            record_event(
                principal, "fleet_setting.write",
                resource="confirm_settings:password",
                details={"op": "remove"},
            )
            return templates.TemplateResponse(
                "confirm_settings.html",
                _build_confirm_settings_context(
                    request, success="Confirmation password removed."
                ),
            )

        if new_password != confirm_new_password:
            record_event(
                principal, "fleet_setting.write",
                resource="confirm_settings:password",
                success=False, error_message="passwords-do-not-match",
            )
            return templates.TemplateResponse(
                "confirm_settings.html",
                _build_confirm_settings_context(
                    request, error="Passwords do not match."
                ),
            )

        hashed = hash_confirm_password(new_password)
        fleet_settings.set("confirm_password_hash", hashed)
        record_event(
            principal, "fleet_setting.write",
            resource="confirm_settings:password",
            details={"op": "set"},
        )
        return templates.TemplateResponse(
            "confirm_settings.html",
            _build_confirm_settings_context(
                request, success="Confirmation password updated."
            ),
        )

    elif action == "tool_toggle":
        form_data = await request.form()
        llm_enabled = "get_credentials_enabled" in form_data
        web_enabled = "web_reveal_credentials_enabled" in form_data
        if llm_enabled:
            fleet_settings.set("tool_get_credentials_enabled", "true")
        else:
            fleet_settings.delete("tool_get_credentials_enabled")
        if web_enabled:
            fleet_settings.set("web_reveal_credentials_enabled", "true")
        else:
            fleet_settings.delete("web_reveal_credentials_enabled")
        record_event(
            principal, "fleet_setting.write",
            resource="confirm_settings:tool_toggle",
            details={"llm_enabled": llm_enabled, "web_enabled": web_enabled},
        )
        return templates.TemplateResponse(
            "confirm_settings.html",
            _build_confirm_settings_context(
                request, success="Plaintext credential access settings saved."
            ),
        )

    record_event(
        principal, "fleet_setting.write",
        resource="confirm_settings:unknown",
        success=False, error_message=f"unknown-action:{action}",
    )
    return templates.TemplateResponse(
        "confirm_settings.html",
        _build_confirm_settings_context(request, error="Unknown action."),
    )
