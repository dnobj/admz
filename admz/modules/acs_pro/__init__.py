"""ACS Pro module (#2): Axis Camera Station Pro (read-only v1, ADR-0040).

A pluggable platform module (ADR-0039). Its **entire footprint** — nav item,
MCP tools, and chatbot prompt section — is gated on :func:`acs_enabled`, so
until the operator connects a server from Settings → Modules, ACS Pro adds
nothing to the UI or the tool surface.

Auth is Negotiate as the ADMZ process identity (no stored password). v1 is
read-only; cameras correlate to ADMZ devices by MAC. The executor is always
registered (cheap, harmless) so the family resolves; only the *visible* surface
is gated.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from admz.modules.contract import Module, NavItem, NavSection, ToolSpec

_PROMPT_SECTION = """\
# Axis Camera Station Pro (ACS Pro) is connected

An ACS Pro video-management server is connected (read-only in this version). Its
cameras map to ADMZ devices by **MAC address** (serial number is a fallback).

- To answer "is <device> in ACS / recording in ACS?", call
  `acs_find_camera_for_device` with the ADMZ `device_id` — it returns the
  matched ACS camera(s). Then use `acs_get_recording_status` for recording state.
- `acs_list_cameras` / `acs_list_devices` enumerate what ACS knows;
  `acs_get_api_version` / `acs_get_system` report server status.
- Two event streams: `acs_search_events` is the **system** log (recordings,
  camera up/down, disk warnings); `acs_get_recorded_events` is the
  **detection/analytics** log (Motion, Object detection, Action rule) — use it
  for "was there motion on <camera>?" / "recent object detections".
  `acs_get_recorded_event_types` lists the detection categories.

## ACS control actions (service-affecting — gated)

These change ACS/camera state and are SERVICE-AFFECTING: each returns a
confirmation the operator must approve in a web widget before it runs. Never
claim an action happened until it's confirmed.
- Recording: `acs_start_recording` / `acs_stop_recording`; annotate with
  `acs_add_bookmark`.
- PTZ (camera-addressed by `camera_id` from `acs_list_cameras`): `acs_ptz_move`
  (left/right/up/down), `acs_ptz_zoom`, `acs_ptz_center`,
  `acs_goto_preset` / `acs_ptz_goto_preset_token`.
- Smart Client steering (by `machine_name`, defaults to this server's host):
  `acs_client_live_view`, `acs_client_go_to_cameras`,
  `acs_client_start_playback` / `acs_client_pause_playback`,
  `acs_client_set_playback_position`, `acs_client_set_playback_speed`. These only
  work if that Smart Client is running."""


def _executors() -> Dict[str, object]:
    from admz.modules.acs_pro.executor import AcsProExecutor

    return {"acs-pro": AcsProExecutor()}


def _mcp_tools() -> List[ToolSpec]:
    from admz.modules.acs_pro.config import acs_enabled

    if not acs_enabled():
        return []
    from admz.modules.acs_pro.tools import tool_specs

    return tool_specs()


def _nav_section(ctx: Any = None) -> Optional[NavSection]:
    from admz.modules.acs_pro.config import acs_enabled

    if not acs_enabled():
        return None
    return NavSection(
        id="acs_pro",
        title="ACS Pro",
        items=(NavItem(key="acs", label="Cameras", href="/acs", icon="cctv"),),
    )


def _prompt_section(ctx: Any = None) -> str:
    from admz.modules.acs_pro.config import acs_enabled

    return _PROMPT_SECTION if acs_enabled() else ""


def _routers():
    from admz.modules.acs_pro.routes import router

    return [(router, "")]


def _self_heals() -> bool:
    return False


def get_module() -> Module:
    return Module(
        id="acs_pro",
        family="acs-pro",
        title="Axis Camera Station Pro",
        catalog_family="acs-pro",
        executors=_executors,
        mcp_tools=_mcp_tools,
        routers=_routers,
        nav_section=_nav_section,
        build_prompt_section=_prompt_section,
        self_heals=_self_heals,
    )
