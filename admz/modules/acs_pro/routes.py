"""ACS Pro REST + page routes (ADR-0040).

- ``GET/POST /api/acs/config`` — load/save the connection (no password; Negotiate).
- ``POST /api/acs/test`` — probe a server (api-version) *before* saving, so the
  Settings → Modules "Test connection" button works pre-enable.
- ``GET /acs`` — the read-only module page (server status + cameras). Redirects
  to Settings when ACS isn't connected, so the page never dead-ends.

The config endpoints always exist (you need them to turn the module on); only
the *visible* surface (nav item, tools, prompt) gates on ``acs_enabled()``.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from admz.modules.acs_pro.client import run_acs_op, run_acs_op_direct
from admz.modules.acs_pro.config import DEFAULT_PORT, acs_config, save_acs_config

router = APIRouter()

template_dir = Path(__file__).parent.parent.parent / "api" / "templates"
templates = Jinja2Templates(directory=str(template_dir))
from admz.api.templating import configure as _configure_templates  # noqa: E402

_configure_templates(templates)

_LIST_RANGE = {"range": {"StartIndex": 0, "NumberOfElements": 10000}}


def _base_from_body(body: dict) -> str:
    host = (body.get("server_url") or "").strip()
    if not host:
        return ""
    if host.startswith(("http://", "https://")):
        return host.rstrip("/")
    try:
        port = int(body.get("port") or DEFAULT_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    return f"https://{host}:{port}"


@router.get("/api/acs/config")
async def acs_get_config():
    return acs_config()


@router.post("/api/acs/config")
async def acs_save_config(request: Request):
    body = await request.json()
    cfg = save_acs_config(
        enabled=bool(body.get("enabled")),
        server_url=body.get("server_url", ""),
        port=body.get("port", DEFAULT_PORT),
        verify_tls=bool(body.get("verify_tls")),
        client_machine_name=body.get("client_machine_name", ""),
    )
    return {"success": True, "config": cfg}


@router.post("/api/acs/test")
async def acs_test(request: Request):
    """Probe the posted server with a read-only api-version call."""
    from admz.api.context import get_context

    body = await request.json()
    base = _base_from_body(body)
    if not base:
        return JSONResponse(
            {"success": False, "error": "NoServer", "message": "Enter a server address."},
            status_code=400,
        )
    server = {"device_id": "acs-server", "host": base, "verify_tls": bool(body.get("verify_tls"))}
    ctx = get_context()
    res = await run_acs_op_direct(
        ctx.catalog, ctx.executors, "VersionFacade:GetApiVersion", {}, server
    )
    return res


@router.get("/api/acs/events")
async def acs_events(request: Request):
    """Search the ACS event log (lazy-loaded by the /acs Events panel + agents).

    Query params: hours (window), count, type (EventLogType substring), device
    (camera-name substring).
    """
    from admz.api.context import get_context

    from admz.modules.acs_pro.events import search_events

    q = request.query_params

    def _num(name, default):
        try:
            return float(q.get(name)) if q.get(name) else default
        except (TypeError, ValueError):
            return default

    ctx = get_context()
    return await search_events(
        ctx.catalog, ctx.executors,
        hours_back=_num("hours", 24),
        count=int(_num("count", 200)),
        type_filter=q.get("type") or None,
        device_filter=q.get("device") or None,
    )


@router.get("/api/acs/detections")
async def acs_detections(request: Request):
    """Search the ACS detection/analytics log (Motion, Object detection, …).

    Lazy-loaded by the /acs Detections panel + agents. Query params: hours
    (window), count, type (detection-type substring), device (camera-name
    substring).
    """
    from admz.api.context import get_context

    from admz.modules.acs_pro.events import search_detections

    q = request.query_params

    def _num(name, default):
        try:
            return float(q.get(name)) if q.get(name) else default
        except (TypeError, ValueError):
            return default

    ctx = get_context()
    return await search_detections(
        ctx.catalog, ctx.executors,
        hours_back=_num("hours", 24),
        count=int(_num("count", 2000)),
        type_filter=q.get("type") or None,
        device_filter=q.get("device") or None,
    )


@router.post("/api/acs/action")
async def acs_action(request: Request):
    """Gated ACS action from the /acs buttons (recording, live view, preset).

    Routes through the confirmation gate (risk_level: action → url_only), so the
    response is the blocked/confirm envelope; the UI then opens /confirm/{token}.
    A short allowlist keeps the buttons declarative; richer control is chat/MCP.
    """
    from admz.api.context import get_context

    from admz.operations import execute_gated_operation
    from admz.modules.acs_pro.config import client_machine_name
    from admz.modules.acs_pro.registry_view import ACS_DEVICE_ID, AcsRegistryView

    body = await request.json()
    op = (body.get("op") or "").lower()
    camera_id = body.get("camera_id")

    if op in ("start", "stop"):
        if not camera_id:
            return JSONResponse({"success": False, "error": "BadRequest", "message": "camera_id required."}, status_code=400)
        op_id = "RecordingControlFacade:StartRecording" if op == "start" else "RecordingControlFacade:StopRecording"
        params = {"cameraId": {"Id": camera_id}}
    elif op == "goto-preset":
        token = body.get("preset_token")
        if not camera_id or not token:
            return JSONResponse({"success": False, "error": "BadRequest", "message": "camera_id and preset_token required."}, status_code=400)
        op_id = "PtzFacade:GotoPresetToken"
        params = {"cameraId": {"Id": camera_id}, "presetToken": str(token)}
    elif op == "live-view":
        op_id = "ClientCommandsFacade:GoToLiveView"
        params = {"machineName": (body.get("machine_name") or "").strip() or client_machine_name()}
        if camera_id:
            op_id = "ClientCommandsFacade:GoToCameras"
            params["cameraIds"] = [{"Id": camera_id}]
    else:
        return JSONResponse(
            {"success": False, "error": "BadRequest", "message": "op must be start|stop|goto-preset|live-view."},
            status_code=400,
        )

    ctx = get_context()
    return await execute_gated_operation(
        device_id=ACS_DEVICE_ID, operation_id=op_id, family="acs-pro", params=params,
        catalog=ctx.catalog, registry=AcsRegistryView(ctx.registry), executors=ctx.executors,
    )


@router.get("/acs", response_class=HTMLResponse)
async def acs_page(request: Request):
    from admz.api.context import get_context

    cfg = acs_config()
    if not cfg["enabled"]:
        # Not connected → send the operator to the Modules card, no dead-end.
        return RedirectResponse("/settings", status_code=302)

    ctx = get_context()
    version = await run_acs_op(ctx.catalog, ctx.executors, "VersionFacade:GetApiVersion", {})
    reachable = bool(version.get("success"))
    cameras = []
    if reachable:
        cams = await run_acs_op(
            ctx.catalog, ctx.executors, "CameraListFacade:GetCameraList", _LIST_RANGE
        )
        if cams.get("success"):
            cameras = (cams.get("data") or {}).get("Cameras") or []

    return templates.TemplateResponse(
        "acs.html",
        {
            "request": request,
            "title": "ACS Pro",
            "cfg": cfg,
            "reachable": reachable,
            "version": version.get("data") if reachable else None,
            "error": None if reachable else version.get("message"),
            "cameras": cameras,
        },
    )
