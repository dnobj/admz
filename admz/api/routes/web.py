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
from admz.hierarchy import device_is_in_site
from admz.api.context import AppContext, get_context
from admz.fleet_settings import fleet_settings, is_sensitive_setting_key
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
                # Site membership. A device with NO site counts as being in the
                # active one (GH #427): every device in the registry belongs to
                # a site, so a NULL is a gap in the data rather than a device
                # that lives somewhere else, and hiding it from the roster would
                # make it unmanageable rather than merely miscounted.
                #
                # `templating.py`'s nav count applies the SAME rule, via the
                # shared `device_is_in_site` predicate. They used to disagree —
                # this loop kept a NULL device and the nav's strict equality
                # dropped it — which is how one registry produced 5 in the nav
                # and 11 on this page.
                try:
                    os_ = registry.get_device_org_site(did) or {}
                except Exception:
                    os_ = {}
                if not device_is_in_site(os_.get("site_id"), active_site):
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


@router.post(
    "/device/{device_id}/credentials",
    response_class=RedirectResponse,
)
async def enter_device_credentials(
    request: Request,
    device_id: str,
    registry: DeviceRegistry = Depends(get_registry),
):
    """Open a capture session for a device ADMZ cannot authenticate to
    (ADR-0064 slice B, #443): the durable **Enter credentials** action.

    The rotate route above requires the account to exist; a `no_credentials`
    device has none, so this route binds the session to the `default`
    account as an **admin** (the session default is `service`, which the
    rotate route only avoids by copying an existing account's type). Same
    ADR-0009 shape otherwise: a single-use token, the standard capture form,
    the password never in chat, logs or this route. Browser-only, so the
    same-origin check `capture_submit` performs applies here too.
    """
    from admz.api.capture import capture_store
    from admz.csrf import check_same_origin

    check_same_origin(request)
    if not registry.device_exists(device_id):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "request": request,
                "error": "Device Not Found",
                "message": f"Device '{device_id}' is not registered.",
                "title": "Error",
            },
            status_code=404,
        )
    # `auth_failed` reaches this route too, and then the `default` row exists:
    # keep its shape exactly as the rotate route does (the capture submit
    # merges the session's type and purpose into the row). Only a device with
    # no row at all gets the admin default.
    existing = next(
        (a for a in registry.list_accounts(device_id) if a.get("account_id") == "default"),
        None,
    )
    session = capture_store.create_session(
        device_id=device_id,
        account_id="default",
        account_type=(existing or {}).get("account_type") or "admin",
        purpose=(existing or {}).get("purpose")
        or "Entered from the device page — ADMZ had no usable stored credential",
        ttl=300,
    )
    return RedirectResponse(url=f"/capture/{session.token}", status_code=303)


@router.post(
    "/device/{device_id}/adopt-credentials",
    response_class=RedirectResponse,
)
async def adopt_device_credentials(
    request: Request,
    device_id: str,
    registry: DeviceRegistry = Depends(get_registry),
):
    """Open a **root-adopt** capture session: let ADMZ in, once (FR-CRED-014).

    The sibling route above stores whatever the operator types as this device's
    credential — which is right for rotating a password or setting a stale one.
    This one is the opposite operation: the typed password is used **once** to
    authenticate so ADMZ can create its own ``admz`` account, and it is never
    stored for the device (ADR-0068).

    Deliberately a separate route rather than a flag on that one, because the
    device page offers both and the choice is the operator's: for a device in
    ``auth_failed`` nothing outside the device can tell whether its password
    changed (store a new one) or ADMZ's own account was removed (let ADMZ back
    in). Two routes with two labels keep that choice visible.

    No ``account_type``/``purpose`` is copied from an existing row, unlike the
    route above: nothing about the typed password becomes an account, so a row
    shape to preserve does not exist. Browser-only, so the same-origin check
    ``capture_submit`` performs applies here too.
    """
    from admz.api.capture import KIND_ROOT_ADOPT, capture_store
    from admz.csrf import check_same_origin

    check_same_origin(request)
    if not registry.device_exists(device_id):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "request": request,
                "error": "Device Not Found",
                "message": f"Device '{device_id}' is not registered.",
                "title": "Error",
            },
            status_code=404,
        )
    session = capture_store.create_session(
        device_id=device_id,
        kind=KIND_ROOT_ADOPT,
        purpose="Let ADMZ in — used once to create ADMZ's own account",
        ttl=300,
    )
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
    """Unified Settings screen — safety policy, fleet config, and the
    provisioning credentials the retired ``/fleet-settings`` page used to own.

    The two confirmation gates are shown as enforced; the toggles that map to
    real settings link to the existing forms that persist them. Everything the
    page renders is built by :func:`_settings_page_context`, which the three
    credential POSTs share so a refused write re-renders this same page.
    """
    return templates.TemplateResponse(
        request, "settings.html", _settings_page_context(request),
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


#: Below this length the Fleet Settings form WARNS about the break-glass root
#: password, and saves it only once the operator has said they accept the risk.
#:
#: A warning, not a floor, by the owner's decision (2026-09-14): a short root
#: password is a risk an operator may knowingly take. Nor is it a policy on
#: device password strength — Axis units enforce their own rules, and a value
#: one rejects fails at provisioning's root write, before anything is stored.
_ROOT_PASSWORD_RECOMMENDED_LENGTH = 8

#: The longest label the entry-credential form accepts. A label is free text
#: shown on the settings page and in audit rows; this only keeps both legible.
_ENTRY_LABEL_MAX_LENGTH = 80

#: The audit ``resource`` for every change to the entry list — the same one
#: the capture form's promotion records, so one filter finds both writers.
_ENTRY_CREDENTIALS_RESOURCE = "fleet_settings:entry_credentials"


def _settings_page_context(
    request: Request,
    *,
    success: Optional[str] = None,
    error: Optional[str] = None,
    warning: Optional[str] = None,
    short_password_pending: bool = False,
    open_form: str = "",
) -> dict:
    """Everything ``settings.html`` renders, shared by GET and the POSTs.

    One builder for ``GET /settings`` and for the three credential POSTs that
    used to render the standalone ``/fleet-settings`` page: a refused write then
    re-renders the page the operator was already on, with the flash row at the
    top and ``open_form`` keeping the form they submitted open ("break-glass" or
    "entry"). A successful write leaves both collapsed.

    Sensitive values (``is_sensitive_setting_key`` — the same predicate the
    JSON API and the MCP tool use, admz/redact.py's D-2 consolidation) are
    never put in the template context at all (#158): the initial render
    shows a placeholder, and the page's own JS fetches the real value on
    demand from the already-gated ``GET /api/fleet/settings/{key}/reveal``,
    same as before. What changed is *which* keys get that treatment — this
    used to be decided by a hand-rolled ``"password" in key.lower()`` test
    that missed anything not literally named "password"
    (``gemini_api_key``, ``acs_webhook_token``), so those rendered in
    plaintext directly in the HTML response with no gate at all.

    The break-glass root password follows the same rule: the context carries
    whether it is SET, never the value.
    """
    from admz import entry_credentials
    from admz.modules.acs_pro.config import acs_config
    from admz.provisioning import FLEET_ROOT_PASSWORD_KEY
    from admz.snapshot.ignore import (
        USER_SETTING_KEY, _GLOBAL_IGNORE_PATTERNS, _scoped_rules,
    )

    settings = fleet_settings.list_all()
    display = {}
    for k, v in settings.items():
        sensitive = is_sensitive_setting_key(k)
        display[k] = {"value": None if sensitive else v, "sensitive": sensitive}

    try:
        entry_view = _entry_credentials_view(entry_credentials.describe())
    except Exception as exc:  # noqa: BLE001 - the page must not fall with the list
        import logging

        logging.getLogger(__name__).warning(
            "entry credentials unavailable on the settings page", exc_info=True)
        entry_view = {"error": type(exc).__name__}

    try:
        from admz.github_app import secrets as _gh_secrets
        github_status = _gh_secrets.status()
    except Exception:  # noqa: BLE001 - the card just shows "not connected"
        github_status = {"connected": False}

    return {
        "request": request,
        "settings": display,
        "title": "Settings",
        # Safety policy card.
        "levels": {r: get_confirmation_level(r) for r in _DEFAULT_CONFIRMATION_LEVELS},
        "has_password": bool(fleet_settings.get("confirm_password_hash")),
        # Modules, GitHub backup and config-tracking cards.
        "acs": acs_config(),
        "github": github_status,
        "github_connected_flash": request.query_params.get("github_connected") == "1",
        "github_error_flash": request.query_params.get("github_error"),
        "all_settings": settings,
        "ignore_patterns_text": settings.get(USER_SETTING_KEY) or "",
        "ignore_globals": list(_GLOBAL_IGNORE_PATTERNS),
        # Scoped rules only (the legacy textarea covers the global flat list).
        "ignore_rules": _scoped_rules(),
        "ignore_saved": request.query_params.get("ignore_saved") == "1",
        # Which credential form renders open — see the docstring.
        "open_form": open_form,
        # FR-CRED-012 / ADR-0064 slice D: the first operator view of the
        # entry list — redacted (usernames and labels; never a password),
        # every stored entry marked tried or stored-never-tried.
        "entry_credentials": entry_view,
        # FR-CRED-014 / ADR-0068: a boolean, never the value. Read from the
        # `list_all()` above rather than a second query.
        "root_password_configured": bool(settings.get(FLEET_ROOT_PASSWORD_KEY)),
        "root_password_recommended_length": _ROOT_PASSWORD_RECOMMENDED_LENGTH,
        # Set when a short password arrived without the acceptance box ticked:
        # the box then renders visible, so accepting works without script too.
        "short_password_pending": short_password_pending,
        "entry_label_max_length": _ENTRY_LABEL_MAX_LENGTH,
        "success": success,
        "error": error,
        "warning": warning,
    }


@router.get("/fleet-settings", response_class=RedirectResponse)
async def fleet_settings_page(request: Request):
    """Retired page — its three controls now live on ``/settings``.

    Kept as a redirect rather than deleted: the POST endpoints below still carry
    the ``/fleet-settings`` prefix (the forms that submit to them moved, their
    URLs did not), operators have this URL in their history, and the old page's
    own links are still in older docs.
    """
    return RedirectResponse(url="/settings#provisioning-credentials", status_code=302)


async def _authorize_credential_write(request: Request, *, action: str, resource: str):
    """The gate every Fleet Settings credential form shares, in its order.

    **Same-origin first**, before any side effect — a cross-site POST must not
    even be able to write a refusal row. Then **reveal-group membership**, not
    merely an authenticated caller: whoever sets a credential knows it
    afterwards, so setting one must need at least the permission that revealing
    it needs, or the form is a back door to reveal. A refusal is audited under
    ``action`` and then raised as the canonical 403.

    Returns ``(principal, reason)``; ``reason`` names what granted access.
    """
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.authz import principal_can_reveal, require_reveal_permission
    from admz.csrf import check_same_origin

    # CSRF (#3) before every side effect — a cross-site POST must not even be
    # able to write a refusal row.
    check_same_origin(request)

    principal = await get_current_principal(request)
    allowed, reason = principal_can_reveal(principal)
    if not allowed:
        record_event(
            principal, action, resource=resource,
            success=False, error_message=f"reveal-denied:{reason}",
        )
        # Raises the canonical 403, outside any error handling so a refusal can
        # never be swallowed into a friendly rendered page.
        require_reveal_permission(principal)
    return principal, reason


@router.post("/fleet-settings/root-password", response_class=HTMLResponse)
async def set_fleet_root_password(
    request: Request,
    root_password: str = Form(""),
    confirm_root_password: str = Form(""),
    accept_short_password: str = Form(""),
):
    """Set or replace the break-glass root password (FR-CRED-014, ADR-0068).

    The web counterpart to ``python -m admz settings set fleet_root_password``,
    which takes the value as a command-line argument — so it lands in shell
    history and the process list. A form typed by a human in the browser has
    neither exposure.

    A per-key write handler, like ``POST /confirm-settings``, which is the
    precedent it follows. It departs from it in four places, deliberately (the
    first two live in :func:`_authorize_credential_write`, which the entry-list
    forms share):

    - **Gate: reveal-group membership, not merely an authenticated caller.**
      Whoever sets this value knows it afterwards, so setting it must require
      at least the permission needed to REVEAL it
      (``GET /api/fleet/settings/{key}/reveal``). A weaker gate would be a
      back door to reveal.
    - **Same-origin checked first**, before any side effect including the
      audit row for a refusal. ``/confirm-settings`` does not do this
      (KL-CRED-003 records the gap); the capture routes do.
    - **An empty submission is refused, never treated as "remove".**
      ``/confirm-settings`` clears its password on an empty submit. Here that
      would quietly turn off provisioning for the entire fleet, because an
      unset break-glass password makes ``provision_factory_default`` refuse.
    - **A refused attempt is audited**, as the reveal endpoint audits its
      denials. Someone trying to set the fleet's break-glass password without
      permission is worth a row.

    The value is never echoed, never logged, and never in an audit row.
    ``fleet_settings.set`` encrypts it at rest (``STORE_ENCRYPTED_SETTING_KEYS``).

    **A short password is a warning, not a refusal** (owner decision,
    2026-09-14). Below ``_ROOT_PASSWORD_RECOMMENDED_LENGTH`` nothing is saved
    until the operator ticks the acceptance box, and accepting waives nothing
    else: an empty, mismatched or space-padded submission is refused either way.
    **Nothing recorded says the password is short** — not its length, not the
    acceptance, not the unaccepted attempt before it. The audit log is readable
    by any signed-in user (``GET /api/audit``), and "the fleet's break-glass
    password is under eight characters" is a fact about the secret, so the save
    is recorded exactly as any other.

    ``accept_short_password`` is a string parsed after the gate: as a ``bool``
    form field, a malformed value would be rejected by request validation before
    the same-origin and reveal checks had run.
    """
    from admz.audit import record_event
    from admz.provisioning import FLEET_ROOT_PASSWORD_KEY

    principal, reason = await _authorize_credential_write(
        request, action="fleet_setting.write", resource=FLEET_ROOT_PASSWORD_KEY,
    )
    accepted = accept_short_password.strip().lower() in ("yes", "on", "true", "1")

    # Machine tag for the audit row, operator sentence for the page. Neither
    # ever contains the value.
    problem = None
    if not root_password:
        problem = ("empty",
                   "Enter a password. An empty value is not accepted here: "
                   "without a break-glass root password ADMZ will not provision "
                   "factory-defaulted devices at all.")
    elif root_password != confirm_root_password:
        problem = ("mismatch", "The two passwords do not match.")
    elif root_password != root_password.strip():
        # Refused rather than silently stripped: stripping would store a value
        # different from the one the operator believes they set, and they would
        # discover it at a camera's login prompt.
        problem = ("surrounding-whitespace",
                   "The password starts or ends with a space. That is almost "
                   "always a paste accident, so it is not accepted — remove it "
                   "and try again.")

    if problem:
        tag, sentence = problem
        record_event(
            principal, "fleet_setting.write",
            resource=FLEET_ROOT_PASSWORD_KEY,
            success=False, error_message=tag,
        )
        return templates.TemplateResponse(
            request, "settings.html",
            # The form reopens with the message above it: the operator was
            # mid-edit, and a collapsed form would hide what they must correct.
            _settings_page_context(request, error=sentence, open_form="break-glass"),
        )

    short = len(root_password) < _ROOT_PASSWORD_RECOMMENDED_LENGTH
    if short and not accepted:
        # A confirmation step, not a refusal, so it writes no audit row: a row
        # saying "short" would describe the password about to be saved.
        return templates.TemplateResponse(
            request, "settings.html",
            _settings_page_context(
                request,
                warning=(
                    "Nothing was saved yet: that password is shorter than "
                    f"{_ROOT_PASSWORD_RECOMMENDED_LENGTH} characters. A short "
                    "break-glass password is easier to guess, and it logs in to "
                    "every device ADMZ provisions. To use it anyway, enter it "
                    "twice again and tick the box to accept the risk."
                ),
                short_password_pending=True,
            ),
        )

    replaced = bool(fleet_settings.get(FLEET_ROOT_PASSWORD_KEY))
    fleet_settings.set(FLEET_ROOT_PASSWORD_KEY, root_password)
    # After the write, not before: an audit row must never claim a change that
    # did not land. Same ordering as `run_settings` and `capabilities.set_enabled`.
    # And the same row whatever the password's length — see the docstring.
    record_event(
        principal, "fleet_setting.write",
        resource=FLEET_ROOT_PASSWORD_KEY,
        details={"op": "replace" if replaced else "set", "granted_by": reason},
    )
    return templates.TemplateResponse(
        request, "settings.html",
        _settings_page_context(
            request,
            success=(
                "Break-glass root password "
                + ("replaced" if replaced else "set")
                + ". ADMZ writes it to factory-defaulted devices it provisions "
                "from now on. Devices it has already provisioned keep the root "
                "password they were given."
            ),
            warning=(
                f"It is shorter than {_ROOT_PASSWORD_RECOMMENDED_LENGTH} "
                "characters, as you accepted. You can replace it with a longer "
                "one here at any time."
            ) if short else None,
        ),
    )


def _entry_refusal_sentence(code: str, fallback: str = "") -> str:
    """What the page says when ``admz.entry_credentials`` refuses a write.

    Keyed on the refusal's code, never its message: the library's messages are
    written for a log, and they will be reworded.
    """
    from admz import entry_credentials

    return {
        entry_credentials.REFUSED_PROMPT_ALWAYS: (
            "This installation is set to store no entry credentials and to ask "
            "every time (the prompt-always posture), so nothing was added."),
        entry_credentials.REFUSED_CAP: (
            f"The list already holds the most it may ({entry_credentials.MAX_STORED}), "
            "so nothing was added. Remove one first — each credential is another "
            "failed login against every device ADMZ adopts."),
        entry_credentials.REFUSED_UNREADABLE: (
            "The stored entry list cannot be read in full, so nothing was "
            "changed: any change would lose part of it. It cannot be decrypted, "
            "or it is not a list of complete username/password pairs — restore "
            "the key file it was written with, or correct it with "
            "python -m admz settings set entry_credentials."),
        entry_credentials.REFUSED_STALE: (
            "The entry list has changed since this page was loaded, so nothing "
            "was removed. The list below is current."),
        entry_credentials.REFUSED_INCOMPLETE: "Enter both a username and a password.",
    }.get(code, fallback)


def _entry_write_refused(request: Request, principal, *, action: str, tag: str,
                         sentence: str, details: dict):
    """Audit a refused change to the entry list, then re-render the page saying why.

    The audit row carries the machine ``tag`` and the non-secret ``details``
    (username and label); the page carries the ``sentence``. Neither carries a
    password.
    """
    from admz.audit import record_event

    record_event(
        principal, action, resource=_ENTRY_CREDENTIALS_RESOURCE,
        details=details, success=False, error_message=tag,
    )
    return templates.TemplateResponse(
        request, "settings.html",
        # A refused ADD reopens the add form, with the message above it — the
        # operator was mid-edit. A refused removal has no form to reopen.
        _settings_page_context(
            request, error=sentence,
            open_form="entry" if action.endswith("add_refused") else "",
        ),
    )


@router.post("/fleet-settings/entry-credentials", response_class=HTMLResponse)
async def add_fleet_entry_credential(
    request: Request,
    entry_username: str = Form(""),
    entry_password: str = Form(""),
    confirm_entry_password: str = Form(""),
    entry_label: str = Form(""),
):
    """Add a pair to the entry list from the Fleet Settings page (FR-CRED-012).

    The list's other writers are the capture form's promote box, which only
    offers a password a device has just accepted, and
    ``python -m admz settings set entry_credentials``, which takes the whole
    list — passwords included — as a command-line argument. This form covers
    the case neither does: a password an operator knows was set by hand on
    devices ADMZ has not adopted yet.

    **It widens what ADMZ tries against every device it adopts**, so it carries
    the break-glass form's protections: :func:`_authorize_credential_write`
    (same-origin first, then reveal-group membership — which matters doubly
    here, because a duplicate is reported and so answers "is this password
    already on the list"), the password typed twice and never echoed, and every
    refusal audited. The audit row names the username and label, never the
    password. The storage cap and the prompt-always posture are
    ``admz.entry_credentials``' rules, surfaced here rather than restated.

    The username is trimmed, because it is shown back on the page where a
    change is visible; a password with surrounding spaces is refused instead,
    for the reason the break-glass form gives.
    """
    from admz import entry_credentials
    from admz.audit import record_event

    principal, reason = await _authorize_credential_write(
        request, action="entry_credential.add_refused",
        resource=_ENTRY_CREDENTIALS_RESOURCE,
    )
    username, label = entry_username.strip(), entry_label.strip()
    details = {"username": username, "label": label}

    problem = None
    if not username or not entry_password:
        problem = (entry_credentials.REFUSED_INCOMPLETE,
                   _entry_refusal_sentence(entry_credentials.REFUSED_INCOMPLETE))
    elif entry_password != confirm_entry_password:
        problem = ("mismatch", "The two passwords do not match.")
    elif entry_password != entry_password.strip():
        problem = ("surrounding-whitespace",
                   "The password starts or ends with a space. That is almost "
                   "always a paste accident, so it is not accepted — remove it "
                   "and try again.")
    elif len(label) > _ENTRY_LABEL_MAX_LENGTH:
        problem = ("label-too-long",
                   f"Keep the label to {_ENTRY_LABEL_MAX_LENGTH} characters or fewer.")
    if problem:
        tag, sentence = problem
        return _entry_write_refused(
            request, principal, action="entry_credential.add_refused",
            tag=tag, sentence=sentence, details=details,
        )

    try:
        added = entry_credentials.add_entry_credential(
            username, entry_password, label=label)
    except entry_credentials.EntryCredentialRefused as exc:
        return _entry_write_refused(
            request, principal, action="entry_credential.add_refused",
            tag=exc.code, sentence=_entry_refusal_sentence(exc.code, str(exc)),
            details=details,
        )
    if not added:
        # Nothing changed, so nothing is audited — as for a duplicate promotion.
        return templates.TemplateResponse(
            request, "settings.html",
            _settings_page_context(
                request,
                warning=(f"That password for {username} is already on the entry "
                         "list, so nothing was added."),
                open_form="entry",
            ),
        )

    # After the write, as for the break-glass password: an audit row must never
    # claim a change that did not land.
    record_event(
        principal, "entry_credential.added",
        resource=_ENTRY_CREDENTIALS_RESOURCE,
        details={**details, "granted_by": reason},
    )
    return templates.TemplateResponse(
        request, "settings.html",
        _settings_page_context(
            request,
            success=(f"Added {username} to the entry list. ADMZ tries it on "
                     "devices it does not yet manage, from the next onboarding "
                     "on; it is never stored as a device's credential."),
        ),
    )


@router.post("/fleet-settings/entry-credentials/remove", response_class=HTMLResponse)
async def remove_fleet_entry_credential(
    request: Request,
    position: str = Form(""),
    revision: str = Form(""),
):
    """Remove one pair from the entry list (FR-CRED-012).

    Gated exactly as adding is. Removing narrows what ADMZ tries rather than
    widening it, but it is still a fleet-wide credential change — it can take
    away the only credential that gets ADMZ into a batch of devices — and it
    cannot be undone from the page, which never shows the password.

    ``position`` is the row's place in the list the page showed and
    ``revision`` the list's revision when the page was rendered;
    ``entry_credentials.remove_entry_credential`` acts only while that revision
    still holds, so a stale tab, another writer, or this same form resubmitted
    by a reload removes nothing. The audit row names the removed row as read
    from storage. ``position`` arrives as a string and is parsed here, after
    the gate: as an ``int`` form field, a malformed value would be rejected by
    request validation before the gate had run.
    """
    from admz import entry_credentials
    from admz.audit import record_event

    principal, reason = await _authorize_credential_write(
        request, action="entry_credential.remove_refused",
        resource=_ENTRY_CREDENTIALS_RESOURCE,
    )
    # What was asked for, bounded: a refused request may be hand-made.
    details = {"position": position[:20]}
    try:
        index = int(position)
    except ValueError:
        # Not a position at all, which only a hand-made request sends.
        return _entry_write_refused(
            request, principal, action="entry_credential.remove_refused",
            tag=entry_credentials.REFUSED_STALE,
            sentence=_entry_refusal_sentence(entry_credentials.REFUSED_STALE),
            details=details,
        )
    try:
        removed = entry_credentials.remove_entry_credential(index, revision=revision)
    except entry_credentials.EntryCredentialRefused as exc:
        return _entry_write_refused(
            request, principal, action="entry_credential.remove_refused",
            tag=exc.code, sentence=_entry_refusal_sentence(exc.code, str(exc)),
            details=details,
        )

    record_event(
        principal, "entry_credential.removed",
        resource=_ENTRY_CREDENTIALS_RESOURCE,
        details={**removed, "granted_by": reason},
    )
    sentence = f"Removed {removed['username']} from the entry list."
    if removed["legacy_pair"]:
        sentence += (" It was the fleet default pair, so the default_username "
                     "and default_password settings were deleted.")
    return templates.TemplateResponse(
        request, "settings.html",
        _settings_page_context(request, success=sentence),
    )


def _entry_credentials_view(desc: dict) -> dict:
    """Pair each stored entry with whether a pass tries it, for the template.

    ``stored_tried`` comes from ``entry_credentials.describe``, which works it
    out from the credentials themselves — matching redacted usernames and
    labels here could mark the dead one of two identical entries tried and the
    live one "never tried". ``entries_tried`` counts the entry credentials a
    pass tries, leaving out ADMZ's break-glass attempt when ``in_use`` ends with
    one (``break_glass_last``), so the page names it after the count rather than
    reporting "4 (at most 3)". Redacted dicts in, redacted dicts out.
    """
    flags = desc.get("stored_tried") or []
    rows = [{**c, "tried": bool(flags[i]) if i < len(flags) else False}
            for i, c in enumerate(desc.get("stored", []))]
    entries_tried = len(desc.get("in_use", [])) - (1 if desc.get("break_glass_last") else 0)
    return {**desc, "rows": rows, "entries_tried": max(entries_tried, 0)}


# ── Confirmation settings ────────────────────────────────────────────────

def _build_confirm_settings_context(request: Request, **extra):
    """Build the template context for the confirm-settings page.

    Every risk class in the policy table gets a row — derived, not listed.
    While this page rendered only the four vapix risks, an operator auditing
    gate policy could not see that ``confirm_level_action`` had been altered,
    which is half the severity of GH #152.
    """
    from admz.authz import APPROVER_GROUPS_SETTING, approver_groups

    levels = {r: get_confirmation_level(r) for r in _DEFAULT_CONFIRMATION_LEVELS}
    has_password = bool(fleet_settings.get("confirm_password_hash"))
    # Show the EFFECTIVE list, not the raw setting: if the box is empty the
    # default applies, and the page must say what is actually in force (GH #152
    # is the same complaint about this page — it could not show what was really
    # in effect).
    ctx = {
        "request": request,
        "title": "Confirmation Settings",
        "levels": levels,
        "has_password": has_password,
        "approver_groups": ", ".join(approver_groups()),
        "approver_groups_configured": bool(
            (fleet_settings.get(APPROVER_GROUPS_SETTING) or "").strip()),
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

    elif action == "approver_groups":
        # GH #178. Blank clears the setting so the built-in default applies —
        # `authz.approver_groups()` treats unset AND empty as "use the floor"
        # and logs when it does, so an empty box can never mean "anyone".
        form_data = await request.form()
        raw = (form_data.get("approver_groups") or "").strip()
        from admz.authz import APPROVER_GROUPS_SETTING, approver_groups
        if raw:
            fleet_settings.set(APPROVER_GROUPS_SETTING, raw)
        else:
            fleet_settings.delete(APPROVER_GROUPS_SETTING)
        record_event(
            principal, "fleet_setting.write",
            resource="confirm_settings:approver_groups",
            details={"op": "set" if raw else "reset-to-default",
                     "effective": approver_groups()},
        )
        return templates.TemplateResponse(
            request,
            "confirm_settings.html",
            _build_confirm_settings_context(
                request,
                success=("Approver groups saved: " + ", ".join(approver_groups())
                         if raw else
                         "Approver groups reset to the default: "
                         + ", ".join(approver_groups())),
            ),
        )

    # NOTE: an ``action == "tool_toggle"`` branch used to live here, writing
    # ``tool_get_credentials_enabled``. Both the branch and the flag were
    # removed (#151): the flag's documented purpose (the deleted
    # ``get_credentials`` MCP tool) no longer existed, and its only live
    # effect had become an anonymous bypass of the fleet-setting reveal
    # gate. A legacy POST now falls through to the unknown-action error.

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
