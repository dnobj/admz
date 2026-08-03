"""
Web UI routes for device management.
"""

from fastapi import APIRouter, Request, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from pathlib import Path
from typing import Optional

from admz.exceptions import (
    DeviceNotFoundError,
    AccountNotFoundError,
    PermissionDeniedError,
    BackendError,
)
from admz.device_registry import DeviceRegistry
from admz.api.context import AppContext, get_context
from admz.fleet_settings import fleet_settings
from admz.api.confirm_store import (
    get_confirmation_level,
    hash_confirm_password,
    VALID_CONFIRMATION_LEVELS,
    _DEFAULT_CONFIRMATION_LEVELS,
    confirm_level_key,
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


@router.get("/activity", response_class=HTMLResponse)
async def activity_page(request: Request, ctx: AppContext = Depends(get_context)):
    """Live activity feed (ADR-0041 layer 2) — the device-event timeline."""
    # The "From" picker: each registered device by name, plus software sources.
    # Operators mostly watch one device or one system at a time and narrow
    # from there, so the picker is explicit rather than a name-substring box.
    try:
        sources = sorted(
            ({"device_id": d.get("device_id"),
              "name": d.get("nickname") or d.get("model") or d.get("device_id")}
             for d in ctx.registry.list_devices() if d.get("device_id")),
            key=lambda d: d["name"],
        )
    except Exception:  # noqa: BLE001 — the feed must render without a registry
        sources = []
    return templates.TemplateResponse(
        request,
        "activity.html",
        {"request": request, "title": "Activity",
         "status": ctx.event_supervisor.status(),
         "acs_status": ctx.acs_event_poller.status(),
         "device_sources": sources},
    )


@router.get("/devices", response_class=HTMLResponse)
async def devices_page(
    request: Request,
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Devices — the unified roster: health, model, IP, drift, tags for the
    active site, with the drift diff + accept/revert actions inline (the
    old Configuration page folded in here). ``?filter=drifted`` switches
    into the bulk drift-review mode. Filters to the cookie-selected site
    and (optionally) a ?tag= filter, mirroring the sidebar tag list
    (ADR-0032: tags are the device-grouping primitive; `untagged` is the
    reserved value for devices with no tags).
    """
    try:
        devices = registry.list_devices()
        devices.sort(key=lambda d: d.get("nickname") or d.get("device_id", ""))

        # ── Site scoping (defensive: backend may not support it) ──
        active_site = request.cookies.get("admz_site")
        tag_filter = request.query_params.get("tag")
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
                scoped.append(d)
            devices = scoped

        # ── Tag filter (exact membership, same semantics as tag_filter
        # in scheduling/drift/snapshot) ──
        if tag_filter:
            if tag_filter == "untagged":
                devices = [d for d in devices if not d.get("tags")]
            else:
                devices = [
                    d for d in devices if tag_filter in (d.get("tags") or [])
                ]

        # ── Drift state, rendered server-side so the roster can show the
        # diff/accept/revert inline (cache-only; same source the Fleet
        # glance + the old Configuration page read). ──
        from admz.snapshot.drift_alerts import drift_alerts as _drift_store
        from admz.snapshot.drift_status import drift_status_for
        for d in devices:
            did = d.get("device_id", "")
            try:
                sig = _drift_store.get_last_signature(did)
            except Exception:
                sig = None
            drift = drift_status_for(d, sig)
            d["drift"] = drift
            d["drift_age"] = _time_ago(drift.get("checked_at"))

        filter_drift = request.query_params.get("filter") == "drifted"

        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "devices": devices,
                "site": site_obj,
                "tag_filter": tag_filter,
                "filter_drift": filter_drift,
                "title": "Devices",
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            request,
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

        # Site context for the slot identity card (defensive). Tags come
        # straight off the device dict (ADR-0032: no Group level).
        site_name = None
        try:
            os_ = registry.get_device_org_site(device_id) or {}
            if os_.get("site_id"):
                site = registry.get_site(os_["site_id"])
                site_name = site.get("name") if site else os_["site_id"]
        except Exception:
            pass

        # Last-known drift (same shared, cache-only source the Fleet glance
        # and Configuration workbench read — never a live probe on load).
        from admz.snapshot.drift_alerts import drift_alerts as _drift_store
        from admz.snapshot.drift_status import drift_status_for
        try:
            sig = _drift_store.get_last_signature(device_id)
        except Exception:
            sig = None
        drift = drift_status_for(device, sig)

        return templates.TemplateResponse(
            request,
            "device_detail.html",
            {
                "request": request,
                "device": device,
                "accounts": accounts,
                "site_name": site_name,
                "drift": drift,
                "drift_age": _time_ago(drift.get("checked_at")),
                "title": device.get("nickname", device_id),
            },
        )

    except DeviceNotFoundError:
        return templates.TemplateResponse(
            request,
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
            request,
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
            request,
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
            request,
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
            request,
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
            request,
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
            request,
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
        request,
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

        # Sites the device can be moved to (ADR-0032: a device belongs to
        # exactly one Site). Defensive — backends may not support sites.
        try:
            sites = registry.list_sites()
        except Exception:
            sites = []
        try:
            current_site_id = (registry.get_device_org_site(device_id) or {}).get("site_id")
        except Exception:
            current_site_id = None

        return templates.TemplateResponse(
            request,
            "edit_device.html",
            {
                "request": request,
                "device": device,
                "sites": sites,
                "current_site_id": current_site_id,
                "title": f"Edit Device: {device.get('nickname', device_id)}",
            },
        )

    except DeviceNotFoundError:
        return templates.TemplateResponse(
            request,
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
            request,
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
            request,
            "add_account.html",
            {
                "request": request,
                "device": device,
                "title": f"Add Account - {device.get('nickname', device_id)}",
            },
        )

    except DeviceNotFoundError:
        return templates.TemplateResponse(
            request,
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
            request,
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
            request,
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
            request,
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
        r: get_confirmation_level(r) for r in _DEFAULT_CONFIRMATION_LEVELS
    }
    has_password = bool(fleet_settings.get("confirm_password_hash"))
    get_creds_enabled = fleet_settings.get("tool_get_credentials_enabled") == "true"
    from admz.snapshot.ignore import (
        USER_SETTING_KEY, _GLOBAL_IGNORE_PATTERNS, _scoped_rules,
    )
    from admz.modules.acs_pro.config import acs_config
    try:
        from admz.github_app import secrets as _gh_secrets
        github_status = _gh_secrets.status()
    except Exception:  # noqa: BLE001 - the card just shows "not connected"
        github_status = {"connected": False}
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "request": request,
            "title": "Settings",
            "levels": levels,
            "has_password": has_password,
            "get_creds_enabled": get_creds_enabled,
            "acs": acs_config(),
            "github": github_status,
            "github_connected_flash": request.query_params.get("github_connected") == "1",
            "github_error_flash": request.query_params.get("github_error"),
            "all_settings": fleet_settings.list_all(),
            "ignore_patterns_text": fleet_settings.get(USER_SETTING_KEY) or "",
            "ignore_globals": list(_GLOBAL_IGNORE_PATTERNS),
            # Scoped rules only (the legacy textarea covers the global flat list).
            "ignore_rules": _scoped_rules(),
            "ignore_saved": request.query_params.get("ignore_saved") == "1",
        },
    )


@router.post("/settings/ignored-fields", response_class=RedirectResponse)
async def save_ignored_fields(request: Request, patterns: str = Form("")):
    """Persist the operator's config-tracking ignore list (one glob per line).

    Params matching these are dropped at snapshot CAPTURE, so they never enter
    a baseline, drift report, or the git config repo — for noisy keys or config
    an app stores badly (e.g. a plaintext credential a custom ACAP writes into
    param.cgi). Changes apply on the next snapshot/drift check."""
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal
    from admz.snapshot.ignore import USER_SETTING_KEY

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)

    # Normalize: trim each line, drop blanks; store newline-separated.
    lines = [ln.strip() for ln in (patterns or "").replace(",", "\n").splitlines()]
    cleaned = [ln for ln in lines if ln]
    fleet_settings.set(USER_SETTING_KEY, "\n".join(cleaned))
    record_event(
        principal, "settings.config_ignore", resource="fleet",
        details={"pattern_count": len(cleaned)},
    )
    return RedirectResponse(url="/settings?ignore_saved=1#config-tracking",
                            status_code=303)


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
        request,
        "audit_log.html",
        {"request": request, "title": "Audit log", "days": days, "counts": counts,
         "total": len(rows)},
    )


@router.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request):
    """Tasks — unified scheduled (recurring) + triggered (detection) work.
    The page fetches /api/tasks client-side."""
    return templates.TemplateResponse(
        request,
        "tasks.html", {"request": request, "title": "Tasks"},
    )


@router.get("/schedules")
async def schedules_redirect():
    """Back-compat: Schedules merged into Tasks (ADR-0037)."""
    return RedirectResponse(url="/tasks", status_code=307)


def _fmt_snapshot_date(iso: Optional[str]) -> Optional[str]:
    """Render a git ISO commit date as a compact 'YYYY-MM-DD HH:MM'."""
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return iso[:16].replace("T", " ")


def _time_ago(epoch: Optional[float]) -> Optional[str]:
    """Compact 'as of' stamp for a drift check — matches the Fleet
    view's JS timeAgo() so the two surfaces read the same."""
    if not epoch:
        return None
    import time as _t
    s = max(0, int(_t.time() - epoch))
    if s < 60:
        return "just now"
    m = s // 60
    if m < 60:
        return f"{m}m ago"
    h = m // 60
    if h < 24:
        return f"{h}h ago"
    d = h // 24
    if d < 30:
        return f"{d}d ago"
    mo = d // 30
    if mo < 12:
        return f"{mo}mo ago"
    return f"{mo // 12}y ago"


@router.get("/configuration")
async def configuration_redirect(request: Request):
    """The Configuration page was merged into the unified Devices roster
    (drift diff + accept/revert now live inline on /devices). Preserve any
    query string — e.g. ?filter=drifted lands on the bulk drift-review
    mode — so old links and bookmarks keep working."""
    qs = request.url.query
    target = "/devices" + (f"?{qs}" if qs else "")
    return RedirectResponse(url=target, status_code=307)


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
        request,
        "fleet_settings.html",
        {
            "request": request,
            "settings": display,
            "title": "Fleet Settings",
        },
    )


# ── Confirmation settings ────────────────────────────────────────────────

def _build_confirm_settings_context(request: Request, **extra):
    """Build the template context for the confirm-settings page.

    Every risk class in the policy table gets a row — derived, not listed.
    While this page rendered only the four vapix risks, an operator auditing
    gate policy could not see that ``confirm_level_action`` had been altered,
    which is half the severity of GH #152.
    """
    levels = {r: get_confirmation_level(r) for r in _DEFAULT_CONFIRMATION_LEVELS}
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
        request,
        "confirm_settings.html",
        _build_confirm_settings_context(request),
    )


@router.post("/confirm-settings", response_class=HTMLResponse)
async def confirm_settings_save(
    request: Request,
    action: str = Form(...),
    # Level fields (only present when action=levels) are read from the raw
    # form below, one per risk class in the policy table, rather than declared
    # here — a declared parameter per risk is exactly the hardcoded list that
    # let confirm_level_action go unwritable-but-unprotected (GH #152).
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
        form = await request.form()
        applied = {}
        for risk in _DEFAULT_CONFIRMATION_LEVELS:
            level = form.get(f"level_{risk}")
            key = confirm_level_key(risk)
            if level and level in VALID_CONFIRMATION_LEVELS:
                fleet_settings.set(key, level)
                applied[key] = level

        record_event(
            principal, "fleet_setting.write",
            resource="confirm_settings:levels",
            details={"applied": applied},
        )
        return templates.TemplateResponse(
            request,
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
                request,
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
                request,
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
            request,
            "confirm_settings.html",
            _build_confirm_settings_context(
                request, success="Confirmation password updated."
            ),
        )

    elif action == "tool_toggle":
        form_data = await request.form()
        llm_enabled = "get_credentials_enabled" in form_data
        if llm_enabled:
            fleet_settings.set("tool_get_credentials_enabled", "true")
        else:
            fleet_settings.delete("tool_get_credentials_enabled")
        record_event(
            principal, "fleet_setting.write",
            resource="confirm_settings:tool_toggle",
            details={"llm_enabled": llm_enabled},
        )
        return templates.TemplateResponse(
            request,
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
        request,
        "confirm_settings.html",
        _build_confirm_settings_context(request, error="Unknown action."),
    )
