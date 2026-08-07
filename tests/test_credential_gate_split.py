"""Tests for the plaintext-credential gate.

NOTE (CR-3): POST /confirm-settings now requires an authenticated
principal — the handler writes to keys in PROTECTED_SETTING_KEYS.
The helper ``_with_admin`` below installs a Windows-IWA-like
principal for the duration of a test so the gate is satisfied.

Background: device-account passwords are never displayed through any
web/REST surface — the device-credential reveal endpoint and its
``web_reveal_credentials_enabled`` flag were removed entirely. The MCP
``get_credentials`` tool is gone too (CR-1), and #151 finished the job:
``tool_get_credentials_enabled`` — which once gated that tool and had
silently become an anonymous bypass of the fleet-setting reveal gate —
was removed along with its /confirm-settings checkbox.

This file pins:
  - The MCP get_credentials tool is gone (CR-1) and stays gone.
  - The /confirm-settings page no longer renders the LLM checkbox, and
    a legacy ``tool_toggle`` POST cannot write the flag.
  - The retired flag left the key inventory but — like any unknown
    key — still refuses LLM writes under ADR-0053's deny-by-default.
"""

import pytest
from contextlib import contextmanager
from fastapi.testclient import TestClient


@contextmanager
def _with_admin():
    """Install a Windows-IWA-like authenticated principal for the
    duration of the ``with`` block. Restores NoAuth on exit.

    Used by tests that POST to /confirm-settings — that handler
    now requires an authenticated principal because every branch
    writes to a key in PROTECTED_SETTING_KEYS (CR-3).
    """
    from admz.auth import (
        AuthBackend, NoAuth, Principal, set_active_backend,
    )

    class _StubBackend(AuthBackend):
        def __init__(self, p):
            self.p = p

        async def authenticate(self, request):
            return self.p

    admin = Principal(
        name="AXIS\\admin",
        display_name="admin",
        source="windows",
        groups=["Administrators"],
        is_anonymous=False,
    )
    set_active_backend(_StubBackend(admin))
    try:
        yield admin
    finally:
        set_active_backend(NoAuth())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")

    # Repoint singletons that captured the prior path at module import.
    # Several route modules did `from admz.fleet_settings import fleet_settings`
    # and need their local reference updated too.
    from admz import fleet_settings as fs_module
    from admz.api.routes import devices as devices_route
    from admz.api.routes import web as web_route
    db_path = str(tmp_path / "admz.db")
    _orig_fs = fs_module.fleet_settings
    _orig_devices_fs = devices_route.fleet_settings
    _orig_web_fs = web_route.fleet_settings
    fresh_fs = fs_module.FleetSettings(db_path)
    fs_module.fleet_settings = fresh_fs
    devices_route.fleet_settings = fresh_fs
    web_route.fleet_settings = fresh_fs

    from admz.api.main import app
    try:
        with TestClient(app, follow_redirects=False) as c:
            # Seed a device + account so the credentials endpoint
            # has something to return.
            from admz.api.main import registry
            registry.add_device(
                "cam-gate-test", {"host": "192.0.2.42", "model": "M"}
            )
            registry.add_account(
                "cam-gate-test",
                "default",
                {
                    "username": "root",
                    "password": "topsecret",
                    "account_type": "admin",
                    "purpose": "primary",
                },
            )
            yield c
    finally:
        fs_module.fleet_settings = _orig_fs
        devices_route.fleet_settings = _orig_devices_fs
        web_route.fleet_settings = _orig_web_fs


# ---------------------------------------------------------------------------
# Device-credential reveal endpoint is gone
# ---------------------------------------------------------------------------


class TestDeviceCredentialRevealRemoved:
    def test_endpoint_not_mounted(self):
        # assert_not_mounted refuses to pass against an empty/blind route table.
        # Before #223 this was `{r.path for r in app.routes if hasattr(r, "path")}`,
        # which under FastAPI >= 0.130 saw almost nothing and made this negative
        # assertion vacuous. See tests/route_inventory.py.
        from admz.api.main import app
        from tests.route_inventory import assert_not_mounted
        assert_not_mounted(app, "/api/devices/{device_id}/credentials")

    def test_endpoint_404(self, client):
        r = client.get(
            "/api/devices/cam-gate-test/credentials?account_id=default"
        )
        assert r.status_code == 404
        assert "topsecret" not in r.text


# ---------------------------------------------------------------------------
# MCP get_credentials tool has been removed entirely (CR-1)
# ---------------------------------------------------------------------------


class TestMcpGetCredentialsRemoved:
    """CR-1 removed the MCP ``get_credentials`` tool — the LLM uses
    ``create_temp_credentials`` when it needs to act on behalf of the
    user. The internal callers that still need the admin password
    (executor, plan engine) go through ``registry.get_credentials``
    directly; those values never cross the MCP wire format."""

    def test_get_credentials_tool_not_registered(self):
        from admz.mcp import server as mcp_server_module

        assert not hasattr(
            mcp_server_module.ADMZMCPServer, "_get_credentials"
        ), "MCP _get_credentials handler should have been removed (CR-1)"
        assert not hasattr(
            mcp_server_module.ADMZMCPServer, "_is_get_credentials_enabled"
        ), "MCP _is_get_credentials_enabled gate should have been removed (CR-1)"

    def test_get_credentials_tool_name_absent_from_source(self):
        import inspect
        from admz.mcp import server as mcp_server_module

        source = inspect.getsource(mcp_server_module)
        assert 'name="get_credentials"' not in source


# ---------------------------------------------------------------------------
# Settings page — the LLM checkbox is gone (#151)
# ---------------------------------------------------------------------------


class TestSettingsPageCheckboxRemoved:
    def test_page_renders_without_the_checkbox(self, client):
        r = client.get("/confirm-settings")
        assert r.status_code == 200
        body = r.text
        assert 'name="get_credentials_enabled"' not in body
        assert 'name="web_reveal_credentials_enabled"' not in body
        assert 'value="tool_toggle"' not in body

    def test_legacy_tool_toggle_post_cannot_write_the_flag(self, client):
        # A stale browser tab (or script) replaying the old form must not
        # recreate the flag row — the branch that wrote it is gone.
        from admz.fleet_settings import fleet_settings

        with _with_admin():
            r = client.post(
                "/confirm-settings",
                data={"action": "tool_toggle", "get_credentials_enabled": "1"},
            )
        assert r.status_code == 200
        assert "Unknown action" in r.text
        assert fleet_settings.get("tool_get_credentials_enabled") is None


# ---------------------------------------------------------------------------
# The retired flag stays un-writable by the LLM
# ---------------------------------------------------------------------------


class TestLegacyFlagRetired:
    def test_flag_left_the_key_inventory(self):
        from admz.api.confirm_store import PROTECTED_SETTING_KEYS
        # Retired keys leave the inventory entirely (the dead-entry guard
        # in test_setting_policy.py enforces this direction too).
        assert "tool_get_credentials_enabled" not in PROTECTED_SETTING_KEYS
        assert "web_reveal_credentials_enabled" not in PROTECTED_SETTING_KEYS

    def test_flag_still_refuses_llm_writes(self):
        # ADR-0053 deny-by-default: an unknown/retired key is protected,
        # so even on an upgraded install the model cannot recreate the row.
        from admz.fleet_settings import is_protected_setting
        assert is_protected_setting("tool_get_credentials_enabled") is True
