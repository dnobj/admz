"""ACS Pro MCP tools (read-only v1, ADR-0040).

Each tool is a free ``(ctx, args)`` handler (the module-contract shape). They go
out through :class:`AcsProExecutor` via :func:`acs_call`; the MCP ``call_tool``
wrapper audits every call. The headline tool is ``acs_find_camera_for_device``,
which joins an ADMZ device to its ACS camera by MAC.

The whole list is contributed only when ACS Pro is enabled (see the module's
``mcp_tools()``), so the chatbot never sees these tools until a server is
connected.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.types import Tool

from admz.modules.contract import ToolSpec

# A wide default range so list ops return the whole set (override via args).
_DEFAULT_RANGE = {"range": {"StartIndex": 0, "NumberOfElements": 10000}}


async def acs_call(ctx: Any, op_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Resolve + execute one ACS op through the acs-pro executor (gated)."""
    from admz.modules.acs_pro.client import run_acs_op

    return await run_acs_op(ctx.server.catalog, ctx.server.executors, op_id, params)


# --- handlers ---------------------------------------------------------------
async def _acs_get_api_version(ctx, a):
    return await acs_call(ctx, "VersionFacade:GetApiVersion", {})


async def _acs_get_system(ctx, a):
    return await acs_call(ctx, "SystemFacade:GetSystem", {})


async def _acs_list_devices(ctx, a):
    return await acs_call(ctx, "DeviceListFacade:GetDeviceList", a or _DEFAULT_RANGE)


async def _acs_list_cameras(ctx, a):
    return await acs_call(ctx, "CameraListFacade:GetCameraList", a or _DEFAULT_RANGE)


async def _acs_get_recording_status(ctx, a):
    return await acs_call(ctx, "RecordingControlFacade:GetRecordingStatus", a or {})


async def _acs_search_events(ctx, a):
    from admz.modules.acs_pro.events import search_events

    return await search_events(
        ctx.server.catalog, ctx.server.executors,
        hours_back=float(a.get("hours", 24)),
        count=int(a.get("count", 200)),
        type_filter=a.get("type"),
        device_filter=a.get("device"),
    )


async def _acs_find_camera_for_device(ctx, a):
    """Join an ADMZ device to its ACS camera(s) by MAC (serial fallback)."""
    from admz.modules.acs_pro.correlate import correlate_device_to_cameras

    device_id = a["device_id"]
    if not ctx.server.registry.device_exists(device_id):
        return {"success": False, "error": "DeviceNotFound",
                "message": f"ADMZ device '{device_id}' not found."}
    admz_device = ctx.server.registry.get_device_info(device_id)
    admz_device.setdefault("device_id", device_id)

    devs = await acs_call(ctx, "DeviceListFacade:GetDeviceList", _DEFAULT_RANGE)
    if not devs.get("success"):
        return devs
    cams = await acs_call(ctx, "CameraListFacade:GetCameraList", _DEFAULT_RANGE)
    if not cams.get("success"):
        return cams

    acs_devices = (devs.get("data") or {}).get("Devices") or []
    acs_cameras = (cams.get("data") or {}).get("Cameras") or []
    match = correlate_device_to_cameras(admz_device, acs_devices, acs_cameras)
    return {"success": True, "device_id": device_id, **match}


# --- schemas ----------------------------------------------------------------
def _range_props() -> Dict[str, Any]:
    return {
        "range": {
            "type": "object",
            "description": "Optional paging window {StartIndex, NumberOfElements}.",
        }
    }


def tool_specs() -> List[ToolSpec]:
    """The ACS Pro tool specs (only registered when the module is enabled)."""
    return [
        ToolSpec(
            Tool(
                name="acs_get_api_version",
                description=(
                    "Probe the connected Axis Camera Station Pro server's API "
                    "version (connectivity check). Read-only."
                ),
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            _acs_get_api_version,
        ),
        ToolSpec(
            Tool(
                name="acs_get_system",
                description="Get the ACS Pro server's system information. Read-only.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            _acs_get_system,
        ),
        ToolSpec(
            Tool(
                name="acs_list_devices",
                description=(
                    "List the devices known to ACS Pro (name, model, MAC, "
                    "address). Read-only."
                ),
                inputSchema={"type": "object", "properties": _range_props(), "required": []},
            ),
            _acs_list_devices,
        ),
        ToolSpec(
            Tool(
                name="acs_list_cameras",
                description="List the cameras configured in ACS Pro. Read-only.",
                inputSchema={"type": "object", "properties": _range_props(), "required": []},
            ),
            _acs_list_cameras,
        ),
        ToolSpec(
            Tool(
                name="acs_get_recording_status",
                description=(
                    "Get recording status from ACS Pro. Read-only. Pass camera "
                    "identifiers per the RecordingControlFacade schema."
                ),
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            _acs_get_recording_status,
        ),
        ToolSpec(
            Tool(
                name="acs_search_events",
                description=(
                    "Search the ACS Pro event log over a recent time window. "
                    "Returns normalized events (recordings started/stopped, "
                    "etc.) newest-first. Read-only. Use to answer 'what "
                    "happened in ACS in the last N hours' or 'when was <camera> "
                    "last recording'."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "hours": {"type": "number", "description": "Look-back window in hours (default 24)."},
                        "count": {"type": "integer", "description": "Max events to return (default 200)."},
                        "type": {"type": "string", "description": "Substring filter on EventLogType (e.g. 'Recording'), case-insensitive."},
                        "device": {"type": "string", "description": "Substring filter on the camera/device name, case-insensitive."},
                    },
                    "required": [],
                },
            ),
            _acs_search_events,
        ),
        ToolSpec(
            Tool(
                name="acs_find_camera_for_device",
                description=(
                    "Correlate an ADMZ device to its Axis Camera Station Pro "
                    "camera(s) by MAC address (serial fallback). Returns the "
                    "matched ACS device + its cameras. Use this to answer "
                    "questions like 'is the lobby camera in ACS?'."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "device_id": {
                            "type": "string",
                            "description": "The ADMZ device_id (MAC/slot id).",
                        }
                    },
                    "required": ["device_id"],
                },
            ),
            _acs_find_camera_for_device,
        ),
    ]
