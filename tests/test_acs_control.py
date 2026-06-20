"""ACS Pro gated control actions — PTZ + ClientCommands (ADR-0041)."""

from __future__ import annotations

import asyncio

import pytest


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture
def captured_action(monkeypatch):
    """Replace the gated-action helper with a capturing stub.

    Lets us assert each handler builds the right op_id + params without going
    through the real confirmation gate.
    """
    import admz.modules.acs_pro.tools as tools

    seen = {}

    async def fake(ctx, op_id, params):
        seen["op_id"] = op_id
        seen["params"] = params
        return {"blocked": True, "confirmation_level": "url_only"}

    monkeypatch.setattr(tools, "acs_gated_action", fake)
    return seen


def test_ptz_move_maps_direction(captured_action):
    from admz.modules.acs_pro.tools import _acs_ptz_move

    _run(_acs_ptz_move(None, {"camera_id": "c1", "direction": "left"}))
    assert captured_action["op_id"] == "PtzFacade:Move"
    assert captured_action["params"] == {"cameraId": {"Id": "c1"}, "direction": 0}

    _run(_acs_ptz_move(None, {"camera_id": "c1", "direction": "down"}))
    assert captured_action["params"]["direction"] == 3


def test_ptz_zoom_and_preset_token(captured_action):
    from admz.modules.acs_pro.tools import _acs_ptz_zoom, _acs_ptz_goto_preset_token

    _run(_acs_ptz_zoom(None, {"camera_id": "c1", "steps": -2}))
    assert captured_action["op_id"] == "PtzFacade:Zoom"
    assert captured_action["params"] == {"cameraId": {"Id": "c1"}, "steps": -2}

    _run(_acs_ptz_goto_preset_token(None, {"camera_id": "c1", "preset_token": "tok9"}))
    assert captured_action["op_id"] == "PtzFacade:GotoPresetToken"
    assert captured_action["params"]["presetToken"] == "tok9"


def test_client_live_view_defaults_machine(monkeypatch, captured_action):
    import admz.modules.acs_pro.config as cfg
    monkeypatch.setattr(cfg, "client_machine_name", lambda: "BOX-1")
    from admz.modules.acs_pro.tools import _acs_client_live_view

    _run(_acs_client_live_view(None, {}))
    assert captured_action["op_id"] == "ClientCommandsFacade:GoToLiveView"
    assert captured_action["params"] == {"machineName": "BOX-1"}

    # explicit machine_name overrides the default
    _run(_acs_client_live_view(None, {"machine_name": "WALL-2"}))
    assert captured_action["params"]["machineName"] == "WALL-2"


def test_client_go_to_cameras_single_and_list(monkeypatch, captured_action):
    import admz.modules.acs_pro.config as cfg
    monkeypatch.setattr(cfg, "client_machine_name", lambda: "BOX-1")
    from admz.modules.acs_pro.tools import _acs_client_go_to_cameras

    _run(_acs_client_go_to_cameras(None, {"camera_id": "c1"}))
    assert captured_action["op_id"] == "ClientCommandsFacade:GoToCameras"
    assert captured_action["params"]["cameraIds"] == [{"Id": "c1"}]

    _run(_acs_client_go_to_cameras(None, {"camera_ids": ["a", "b"], "machine_name": "W"}))
    assert captured_action["params"]["cameraIds"] == [{"Id": "a"}, {"Id": "b"}]
    assert captured_action["params"]["machineName"] == "W"


def test_client_playback_position_and_speed(monkeypatch, captured_action):
    import admz.modules.acs_pro.config as cfg
    monkeypatch.setattr(cfg, "client_machine_name", lambda: "BOX-1")
    from admz.modules.acs_pro.tools import (
        _acs_client_set_playback_position, _acs_client_set_playback_speed,
    )

    _run(_acs_client_set_playback_position(None, {"position": "2026-06-20 10:30:00"}))
    assert captured_action["op_id"] == "ClientCommandsFacade:SetPlaybackPositionUtc"
    assert captured_action["params"]["position"] == "2026-06-20 10:30:00"

    _run(_acs_client_set_playback_speed(None, {"speed": 2}))
    assert captured_action["op_id"] == "ClientCommandsFacade:SetPlaybackSpeed"
    assert captured_action["params"]["speed"] == 2.0
    assert isinstance(captured_action["params"]["speed"], float)


def test_client_machine_name_defaults_to_hostname(monkeypatch):
    import socket
    import admz.modules.acs_pro.config as cfg

    # No configured override → falls back to the box hostname.
    monkeypatch.setattr(cfg, "acs_config", lambda: {"client_machine_name": ""})
    assert cfg.client_machine_name() == socket.gethostname()
    monkeypatch.setattr(cfg, "acs_config", lambda: {"client_machine_name": "WALL-9"})
    assert cfg.client_machine_name() == "WALL-9"


def _catalog():
    import axis_api_atlas
    from axis_api_atlas.catalog.loader import CatalogLoader

    return CatalogLoader(axis_api_atlas.default_data_path())


def test_gated_control_blocks_not_fired(monkeypatch):
    """A PTZ control action must gate (url_only) and NOT fire pre-approval."""
    import admz.modules.acs_pro.config as cfg
    monkeypatch.setattr(cfg, "acs_enabled", lambda: True)
    monkeypatch.setattr(cfg, "base_url", lambda: "https://acs:29204")
    monkeypatch.setattr(cfg, "acs_config", lambda: {"verify_tls": False, "enabled": True, "port": 29204})

    from admz.api.confirm_store import ConfirmStore
    from admz.operations import execute_gated_operation
    from admz.modules.acs_pro.registry_view import ACS_DEVICE_ID, AcsRegistryView

    class _NeverExec:
        async def execute(self, *a, **k):
            raise AssertionError("a gated control action must NOT fire before approval")

    out = _run(execute_gated_operation(
        device_id=ACS_DEVICE_ID,
        operation_id="PtzFacade:Move",
        family="acs-pro",
        params={"cameraId": {"Id": "x"}, "direction": 0},
        catalog=_catalog(),
        registry=AcsRegistryView(object()),
        executors={"acs-pro": _NeverExec()},
        store=ConfirmStore(),
    ))
    assert out.get("blocked") is True
    assert out.get("confirmation_level") == "url_only"
    assert out.get("confirm_token")


def test_control_tools_present_when_enabled(monkeypatch):
    import admz.modules.acs_pro.config as cfg
    monkeypatch.setattr(cfg, "acs_enabled", lambda: True)
    from admz.modules.acs_pro.tools import tool_specs

    names = {s.tool.name for s in tool_specs()}
    assert {
        "acs_ptz_move", "acs_ptz_zoom", "acs_ptz_center", "acs_ptz_goto_preset_token",
        "acs_client_live_view", "acs_client_go_to_cameras",
        "acs_client_start_playback", "acs_client_pause_playback",
        "acs_client_set_playback_position", "acs_client_set_playback_speed",
    } <= names
