"""ACS Pro actions-v2 — gated camera actions (ADR-0041)."""

from __future__ import annotations

import asyncio

import pytest


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture
def acs_on(monkeypatch):
    import admz.modules.acs_pro.config as cfg
    monkeypatch.setattr(cfg, "acs_enabled", lambda: True)
    monkeypatch.setattr(cfg, "base_url", lambda: "https://acs:29204")
    monkeypatch.setattr(cfg, "acs_config", lambda: {"verify_tls": False, "enabled": True, "port": 29204})


def test_action_risk_maps_to_url_only():
    from admz.api.confirm_store import get_confirmation_level

    # Without this, the .get(risk, "none") fallback would let actions through.
    assert get_confirmation_level("action") == "url_only"
    assert get_confirmation_level("read") == "none"


class _Inner:
    def device_exists(self, d):
        return d == "real-cam"

    def get_device_info(self, d):
        return {"device_id": d, "real": True}

    def get_credentials(self, d):
        return {"username": "u"}

    def list_devices(self):
        return ["real-cam"]


def test_registry_view_resolves_acs_and_delegates(acs_on):
    from admz.exceptions import AccountNotFoundError
    from admz.modules.acs_pro.registry_view import AcsRegistryView

    v = AcsRegistryView(_Inner())
    # acs-server resolves to the configured connection (no real row).
    assert v.device_exists("acs-server") is True
    info = v.get_device_info("acs-server")
    assert info["host"] == "https://acs:29204" and info["kind"] == "acs_server"
    with pytest.raises(AccountNotFoundError):
        v.get_credentials("acs-server")
    # everything else delegates, incl. via __getattr__.
    assert v.device_exists("real-cam") is True
    assert v.get_device_info("real-cam")["real"] is True
    assert v.list_devices() == ["real-cam"]


def _catalog():
    import axis_api_atlas
    from axis_api_atlas.catalog.loader import CatalogLoader

    return CatalogLoader(axis_api_atlas.default_data_path())


def test_gated_action_returns_blocked_not_fired(acs_on):
    from admz.api.confirm_store import ConfirmStore
    from admz.operations import execute_gated_operation
    from admz.modules.acs_pro.registry_view import ACS_DEVICE_ID, AcsRegistryView

    class _NeverExec:
        async def execute(self, *a, **k):
            raise AssertionError("a gated action must NOT fire before approval")

    out = _run(execute_gated_operation(
        device_id=ACS_DEVICE_ID,
        operation_id="RecordingControlFacade:StartRecording",
        family="acs-pro",
        params={"cameraId": {"Id": "x"}},
        catalog=_catalog(),
        registry=AcsRegistryView(object()),
        executors={"acs-pro": _NeverExec()},
        store=ConfirmStore(),
    ))
    assert out.get("blocked") is True
    assert out.get("confirmation_level") == "url_only"
    assert out.get("confirm_token")


def test_approval_fires_through_acs_registry(acs_on):
    from admz.api.confirm_store import ConfirmStore
    from admz.executor.models import StepResult
    from admz.operations import execute_approved_session
    from admz.modules.acs_pro.registry_view import ACS_DEVICE_ID, AcsRegistryView

    store = ConfirmStore()
    sess = store.create_session(
        device_id=ACS_DEVICE_ID,
        operation_id="RecordingControlFacade:StartRecording",
        family="acs-pro",
        params={"cameraId": {"Id": "x"}},
        risk_level="action",
        confirmation_level="url_only",
        danger_description="start recording",
        ttl=300,
    )
    store.complete_session(sess.token, confirmed_by="tester")

    fired = {}

    class _Exec:
        def self_heals(self):
            return False

        async def execute(self, operation, device, credentials, params):
            fired.update(host=device.get("host"), params=params, creds=credentials)
            return StepResult(operation_id="op", device_id="acs-server", success=True, status_code=200)

    out = _run(execute_approved_session(
        sess, catalog=_catalog(),
        registry=AcsRegistryView(object()),  # inner never touched for acs-server
        executors={"acs-pro": _Exec()},
    ))
    assert out.get("success") is True
    # AcsRegistryView resolved the synthetic server to the configured host,
    # and Negotiate means empty credentials.
    assert fired["host"] == "https://acs:29204"
    assert fired["creds"] == {"username": "", "password": ""}


def test_acs_action_tools_present_when_enabled(acs_on):
    from admz.modules.acs_pro.tools import tool_specs

    names = {s.tool.name for s in tool_specs()}
    assert {"acs_start_recording", "acs_stop_recording",
            "acs_add_bookmark", "acs_goto_preset"} <= names
