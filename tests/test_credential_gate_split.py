"""Tests for the plaintext-credential gate.

NOTE (CR-3): POST /confirm-settings now requires an authenticated
principal — the handler writes to keys in PROTECTED_SETTING_KEYS.
The helper ``_with_admin`` below installs a Windows-IWA-like
principal for the duration of a test so the gate is satisfied.

Background: device-account passwords are never displayed through any
web/REST surface — the device-credential reveal endpoint and its
``web_reveal_credentials_enabled`` flag were removed entirely. A single
flag remains:

  - ``tool_get_credentials_enabled`` — LLM-facing MCP ``get_credentials``
    tool (off by default; toggled only via /confirm-settings).

This file pins:
  - The MCP get_credentials tool is gone (CR-1) and stays gone.
  - The /confirm-settings page renders exactly the one LLM checkbox and
    its toggle round-trips.
  - ``tool_get_credentials_enabled`` is protected; the removed
    ``web_reveal_credentials_enabled`` is not.
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

    def test_endpoint_404_even_with_llm_flag(self, client):
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("tool_get_credentials_enabled", "true")
        try:
            r = client.get(
                "/api/devices/cam-gate-test/credentials?account_id=default"
            )
            assert r.status_code == 404
            assert "topsecret" not in r.text
        finally:
            fleet_settings.delete("tool_get_credentials_enabled")


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
# Settings page round-trip — one LLM flag only
# ---------------------------------------------------------------------------


class TestSettingsPageRoundtrip:
    def test_save_llm_flag(self, client):
        from admz.fleet_settings import fleet_settings
        fleet_settings.delete("tool_get_credentials_enabled")

        with _with_admin():
            r = client.post(
                "/confirm-settings",
                data={"action": "tool_toggle", "get_credentials_enabled": "1"},
            )
        assert r.status_code == 200
        assert fleet_settings.get("tool_get_credentials_enabled") == "true"

    def test_save_unchecked_clears(self, client):
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("tool_get_credentials_enabled", "true")

        with _with_admin():
            r = client.post(
                "/confirm-settings",
                data={"action": "tool_toggle"},
            )
        assert r.status_code == 200
        assert fleet_settings.get("tool_get_credentials_enabled") is None

    def test_settings_page_renders_llm_checkbox_only(self, client):
        r = client.get("/confirm-settings")
        assert r.status_code == 200
        body = r.text
        # The LLM checkbox remains; the removed web-reveal one does not.
        assert 'name="get_credentials_enabled"' in body
        assert 'name="web_reveal_credentials_enabled"' not in body
        assert "LLM" in body


# ---------------------------------------------------------------------------
# Protected from MCP writes
# ---------------------------------------------------------------------------


class TestFlagProtected:
    def test_llm_flag_protected_web_flag_gone(self):
        from admz.api.confirm_store import PROTECTED_SETTING_KEYS
        assert "tool_get_credentials_enabled" in PROTECTED_SETTING_KEYS
        # The web-reveal flag was retired entirely.
        assert "web_reveal_credentials_enabled" not in PROTECTED_SETTING_KEYS
