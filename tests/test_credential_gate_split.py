"""Tests for the split plaintext-credential gates.

Background: a single ``tool_get_credentials_enabled`` flag used to
gate both the MCP ``get_credentials`` tool AND the REST endpoint
the web Reveal button hits. Operators who wanted to use Reveal had
to also expose plaintext to LLMs. Now there are two flags:

  - ``tool_get_credentials_enabled`` — LLM-facing MCP tool
  - ``web_reveal_credentials_enabled`` — web Reveal button + REST
    endpoint (for authenticated humans / API-key clients)

The REST endpoint accepts EITHER flag being true (since a strict
operator who turned on the LLM flag implicitly also wants the
endpoint reachable). The MCP tool only checks the LLM flag.

This file pins:
  - Both flags off → REST 403 with the new helpful message
  - Web flag on → REST 200, returns creds (LLM tool still blocked)
  - LLM flag on → REST 200 (kept-working for operators who relied
    on the legacy single-flag behavior)
  - Both flags are in PROTECTED_SETTING_KEYS
"""

import pytest
from fastapi.testclient import TestClient


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
# Gate matrix
# ---------------------------------------------------------------------------


class TestRestCredentialsGate:
    def test_both_flags_off_returns_403(self, client):
        from admz.fleet_settings import fleet_settings
        fleet_settings.delete("tool_get_credentials_enabled")
        fleet_settings.delete("web_reveal_credentials_enabled")

        r = client.get("/api/devices/cam-gate-test/credentials?account_id=default")
        assert r.status_code == 403
        # The helpful message should name BOTH flags so the operator
        # sees which one to flip.
        detail = r.json().get("detail", "").lower()
        assert "reveal" in detail
        assert "/confirm-settings" in detail

    def test_web_flag_on_returns_creds(self, client):
        """The new path: enable Reveal without giving LLMs the password."""
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("web_reveal_credentials_enabled", "true")
        fleet_settings.delete("tool_get_credentials_enabled")

        r = client.get("/api/devices/cam-gate-test/credentials?account_id=default")
        assert r.status_code == 200
        body = r.json()
        assert body["password"] == "topsecret"
        assert body["username"] == "root"

    def test_llm_flag_on_still_works_for_compat(self, client):
        """Operators who had only the legacy flag set must still see
        the endpoint work."""
        from admz.fleet_settings import fleet_settings
        fleet_settings.delete("web_reveal_credentials_enabled")
        fleet_settings.set("tool_get_credentials_enabled", "true")

        r = client.get("/api/devices/cam-gate-test/credentials?account_id=default")
        assert r.status_code == 200
        assert r.json()["password"] == "topsecret"

    def test_both_flags_on_still_works(self, client):
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("web_reveal_credentials_enabled", "true")
        fleet_settings.set("tool_get_credentials_enabled", "true")
        r = client.get("/api/devices/cam-gate-test/credentials?account_id=default")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# MCP get_credentials tool gate is NOT affected by the web flag
# ---------------------------------------------------------------------------


class TestMcpToolGateIsolated:
    def test_web_flag_does_not_enable_mcp_tool(self, client):
        """The whole point of the split: turning on Reveal must NOT
        also expose get_credentials to LLMs."""
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("web_reveal_credentials_enabled", "true")
        fleet_settings.delete("tool_get_credentials_enabled")

        # The MCP server's list_tools filters out get_credentials when
        # the LLM flag is off. We import and check directly.
        from admz.mcp.server import ADMZMCPServer
        server = ADMZMCPServer.__new__(ADMZMCPServer)
        # _is_get_credentials_enabled is the gate the MCP server uses.
        assert server._is_get_credentials_enabled() is False


# ---------------------------------------------------------------------------
# Settings page round-trip
# ---------------------------------------------------------------------------


class TestSettingsPageRoundtrip:
    def test_save_web_flag_only(self, client):
        # First confirm both are off
        from admz.fleet_settings import fleet_settings
        fleet_settings.delete("tool_get_credentials_enabled")
        fleet_settings.delete("web_reveal_credentials_enabled")

        # POST with only the web checkbox ticked
        r = client.post(
            "/confirm-settings",
            data={
                "action": "tool_toggle",
                "web_reveal_credentials_enabled": "1",
                # get_credentials_enabled not sent → unchecked
            },
        )
        assert r.status_code == 200
        assert fleet_settings.get("web_reveal_credentials_enabled") == "true"
        assert fleet_settings.get("tool_get_credentials_enabled") is None

    def test_save_both_flags(self, client):
        from admz.fleet_settings import fleet_settings
        r = client.post(
            "/confirm-settings",
            data={
                "action": "tool_toggle",
                "web_reveal_credentials_enabled": "1",
                "get_credentials_enabled": "1",
            },
        )
        assert r.status_code == 200
        assert fleet_settings.get("web_reveal_credentials_enabled") == "true"
        assert fleet_settings.get("tool_get_credentials_enabled") == "true"

    def test_save_unchecked_clears(self, client):
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("web_reveal_credentials_enabled", "true")
        fleet_settings.set("tool_get_credentials_enabled", "true")

        # Submit with neither checkbox ticked
        r = client.post(
            "/confirm-settings",
            data={"action": "tool_toggle"},
        )
        assert r.status_code == 200
        assert fleet_settings.get("web_reveal_credentials_enabled") is None
        assert fleet_settings.get("tool_get_credentials_enabled") is None

    def test_settings_page_renders_both_checkboxes(self, client):
        r = client.get("/confirm-settings")
        assert r.status_code == 200
        body = r.text
        # Both checkbox names must appear in the rendered form.
        assert 'name="web_reveal_credentials_enabled"' in body
        assert 'name="get_credentials_enabled"' in body
        # And the labels distinguish them clearly.
        assert "Reveal" in body
        assert "LLM" in body


# ---------------------------------------------------------------------------
# Protected from MCP writes
# ---------------------------------------------------------------------------


class TestBothFlagsProtected:
    def test_both_flags_in_protected_set(self):
        from admz.api.confirm_store import PROTECTED_SETTING_KEYS
        assert "tool_get_credentials_enabled" in PROTECTED_SETTING_KEYS
        assert "web_reveal_credentials_enabled" in PROTECTED_SETTING_KEYS
