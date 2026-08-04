"""Tests for CR-4 — MCP subprocess gets a principal + audit on every call_tool.

Background: prior to CR-4 the MCP server received no principal info
from the spawning chat code, and ``call_tool`` never wrote an audit
row. Any action driven through the chatbot was unattributable. With
this change:

* The MCP pool passes ``ADMZ_PRINCIPAL_*`` env vars when spawning
  the subprocess.
* The MCP server reconstructs a :class:`Principal` in ``__init__``,
  falling back to a synthetic ``mcp-standalone`` identity when the
  env vars are absent.
* ``call_tool`` is wrapped with a single try/finally that records
  one audit row per dispatch, with password-shaped argument fields
  masked.

This file pins:
  - Principal reconstruction from env vars (full + partial + absent)
  - mcp_pool builds the env-var dict from a Principal
  - call_tool writes an audit row on success
  - call_tool writes an audit row on failure
  - Sensitive argument fields are masked in the audit details
"""

from __future__ import annotations

import asyncio
import json

import pytest

from admz.auth import Principal
from admz.chatbot.mcp_pool import _principal_to_env, _principal_key
from tests import mcp_harness


# ---------------------------------------------------------------------------
# Principal env-var helpers (mcp_pool side)
# ---------------------------------------------------------------------------


class TestPrincipalToEnv:
    def test_full_principal_round_trips(self):
        p = Principal(
            name="AXIS\\alice",
            display_name="alice",
            domain="AXIS",
            groups=["Administrators", "ADMZ-Admins"],
            source="windows",
            is_anonymous=False,
        )
        env = _principal_to_env(p)
        assert env["ADMZ_PRINCIPAL_NAME"] == "AXIS\\alice"
        assert env["ADMZ_PRINCIPAL_DISPLAY_NAME"] == "alice"
        assert env["ADMZ_PRINCIPAL_DOMAIN"] == "AXIS"
        assert env["ADMZ_PRINCIPAL_SOURCE"] == "windows"
        assert env["ADMZ_PRINCIPAL_GROUPS"] == "Administrators,ADMZ-Admins"

    def test_minimal_principal(self):
        # No groups, no domain → those env vars not emitted.
        p = Principal(
            name="anonymous", display_name="anonymous",
            source="none", is_anonymous=True,
        )
        env = _principal_to_env(p)
        assert env["ADMZ_PRINCIPAL_NAME"] == "anonymous"
        assert env["ADMZ_PRINCIPAL_SOURCE"] == "none"
        assert "ADMZ_PRINCIPAL_DOMAIN" not in env
        assert "ADMZ_PRINCIPAL_GROUPS" not in env

    def test_string_fallback(self):
        # Legacy callers passing just a name string still get the
        # name var so the subprocess has something to attribute to.
        env = _principal_to_env("just-a-string")
        assert env == {"ADMZ_PRINCIPAL_NAME": "just-a-string"}

    def test_none_returns_empty(self):
        assert _principal_to_env(None) == {}

    def test_unknown_object_returns_empty(self):
        class Foo:
            pass
        assert _principal_to_env(Foo()) == {}


class TestPrincipalKey:
    def test_principal_object_key(self):
        p = Principal(name="alice", display_name="alice", source="windows")
        assert _principal_key(p) == "alice"

    def test_string_key(self):
        assert _principal_key("alice") == "alice"

    def test_none_key(self):
        assert _principal_key(None) == "anonymous"


# ---------------------------------------------------------------------------
# Principal reconstruction (mcp/server side)
# ---------------------------------------------------------------------------


class TestPrincipalFromEnv:
    def test_full_round_trip(self, monkeypatch):
        monkeypatch.setenv("ADMZ_PRINCIPAL_NAME", "AXIS\\alice")
        monkeypatch.setenv("ADMZ_PRINCIPAL_DISPLAY_NAME", "alice")
        monkeypatch.setenv("ADMZ_PRINCIPAL_DOMAIN", "AXIS")
        monkeypatch.setenv("ADMZ_PRINCIPAL_SOURCE", "windows")
        monkeypatch.setenv(
            "ADMZ_PRINCIPAL_GROUPS", "Administrators,ADMZ-Admins"
        )

        from admz.mcp.server import ADMZMCPServer
        p = ADMZMCPServer._build_principal_from_env()
        assert p.name == "AXIS\\alice"
        assert p.display_name == "alice"
        assert p.domain == "AXIS"
        assert p.source == "windows"
        assert p.groups == ["Administrators", "ADMZ-Admins"]
        assert p.is_anonymous is False

    def test_missing_env_returns_mcp_standalone(self, monkeypatch):
        for k in (
            "ADMZ_PRINCIPAL_NAME",
            "ADMZ_PRINCIPAL_DISPLAY_NAME",
            "ADMZ_PRINCIPAL_DOMAIN",
            "ADMZ_PRINCIPAL_SOURCE",
            "ADMZ_PRINCIPAL_GROUPS",
        ):
            monkeypatch.delenv(k, raising=False)
        from admz.mcp.server import ADMZMCPServer
        p = ADMZMCPServer._build_principal_from_env()
        assert p.name == "mcp-standalone"
        assert p.source == "mcp-standalone"

    def test_anonymous_round_trip(self, monkeypatch):
        monkeypatch.setenv("ADMZ_PRINCIPAL_NAME", "anonymous")
        monkeypatch.setenv("ADMZ_PRINCIPAL_SOURCE", "none")
        monkeypatch.delenv("ADMZ_PRINCIPAL_DOMAIN", raising=False)
        monkeypatch.delenv("ADMZ_PRINCIPAL_GROUPS", raising=False)
        from admz.mcp.server import ADMZMCPServer
        p = ADMZMCPServer._build_principal_from_env()
        assert p.name == "anonymous"
        assert p.is_anonymous is True


# ---------------------------------------------------------------------------
# Sensitive-arg sanitizer
# ---------------------------------------------------------------------------


class TestSanitizeArgs:
    def test_masks_password_field(self):
        from admz.mcp.server import _sanitize_tool_args
        out = _sanitize_tool_args({"username": "u", "password": "topsecret"})
        assert out == {"username": "u", "password": "***"}

    def test_masks_nested(self):
        from admz.mcp.server import _sanitize_tool_args
        out = _sanitize_tool_args(
            {"creds": {"username": "u", "password": "x"}}
        )
        assert out == {"creds": {"username": "u", "password": "***"}}

    def test_masks_token_secret_apikey(self):
        from admz.mcp.server import _sanitize_tool_args
        out = _sanitize_tool_args({
            "token": "abc", "secret_value": "y",
            "api_key": "k", "ok": "z",
        })
        assert out == {
            "token": "***", "secret_value": "***",
            "api_key": "***", "ok": "z",
        }

    def test_non_dict_passes_through(self):
        from admz.mcp.server import _sanitize_tool_args
        assert _sanitize_tool_args("plain") == "plain"
        assert _sanitize_tool_args(None) is None


# ---------------------------------------------------------------------------
# End-to-end: call_tool writes audit row with the principal
# ---------------------------------------------------------------------------


@pytest.fixture
def mcp_server(tmp_path, monkeypatch):
    """Build an in-process MCP server with an isolated DB + a known
    principal in env.

    Repoints the module-level ``audit_log`` singleton to the test
    DB — the singleton was constructed at import time with the
    default ADMZ_DB_PATH, so monkeypatching the env var alone isn't
    enough to make it write to the tmp DB.
    """
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")

    monkeypatch.setenv("ADMZ_PRINCIPAL_NAME", "AXIS\\alice")
    monkeypatch.setenv("ADMZ_PRINCIPAL_SOURCE", "windows")
    monkeypatch.setenv("ADMZ_PRINCIPAL_GROUPS", "Administrators")

    # Repoint the module-level singleton so call_tool's audit writes
    # land in the test DB.
    from admz import audit as audit_module
    fresh = audit_module.AuditLog(db_path=str(tmp_path / "admz.db"))
    monkeypatch.setattr(audit_module, "audit_log", fresh)

    from admz.mcp.server import ADMZMCPServer
    return ADMZMCPServer()


async def _call_tool(server, name: str, arguments: dict):
    """Dispatch one tool call through the server's registered
    call_tool handler. Returns the parsed JSON result."""
    return await mcp_harness.call_tool(server, name, arguments)


class TestCallToolAuditing:
    @pytest.mark.asyncio
    async def test_successful_tool_call_audited(self, mcp_server):
        # list_devices is a safe, side-effect-free tool. Register one
        # device first so the result is meaningful.
        mcp_server.registry.add_device(
            "test-cam", {"host": "192.0.2.10"}
        )
        result = await _call_tool(mcp_server, "list_devices", {})
        assert result["success"] is True

        # Audit row should exist with the windows principal. Use the
        # monkeypatched singleton (which points at the test DB) for
        # the readback.
        from admz import audit as audit_module
        entries = audit_module.audit_log.list_recent(
            action="mcp.list_devices", limit=5
        )
        assert entries, "expected an audit entry for mcp.list_devices"
        assert entries[0].requester == "AXIS\\alice"
        assert entries[0].auth_source == "windows"
        assert entries[0].success is True

    @pytest.mark.asyncio
    async def test_failed_tool_call_audited(self, mcp_server):
        # get_device for a non-existent device → DeviceNotFoundError →
        # caught by the dispatcher's except clause → audited as failure.
        result = await _call_tool(
            mcp_server, "get_device", {"device_id": "nonexistent"}
        )
        assert result.get("error") == "DeviceNotFound"

        from admz import audit as audit_module
        entries = audit_module.audit_log.list_recent(
            action="mcp.get_device", limit=5
        )
        assert entries
        assert entries[0].success is False
        assert "DeviceNotFound" in entries[0].error_message

    @pytest.mark.asyncio
    async def test_resource_field_includes_device_id(self, mcp_server):
        mcp_server.registry.add_device(
            "test-cam-2", {"host": "192.0.2.11"}
        )
        await _call_tool(
            mcp_server, "get_device", {"device_id": "test-cam-2"}
        )

        from admz import audit as audit_module
        entries = audit_module.audit_log.list_recent(
            action="mcp.get_device", limit=5
        )
        assert entries
        # The resource string should mention the device_id so the
        # audit log groups by device.
        assert "test-cam-2" in entries[0].resource


# ---------------------------------------------------------------------------
# _fmt_audit_entry whitelists the fields it surfaces
#
# Capturing an identifier into the audit row is only half a fix if the MCP
# audit tool then drops it on the way out — the operator reading the log
# through the tool would never see it.
# ---------------------------------------------------------------------------


class TestFmtAuditEntrySurfacesIdentifiers:
    """_fmt_audit_entry reads nothing off ``self``, so it is exercised unbound.

    That keeps these independent of ``ADMZMCPServer()`` construction, which
    needs a live ``mcp`` Server to register handlers against.
    """

    def _fmt(self, details):
        from admz.audit import AuditEntry
        from admz.mcp.server import ADMZMCPServer

        entry = AuditEntry(
            id=1,
            timestamp=1750000000.0,
            requester="AXIS\\alice",
            auth_source="windows",
            action="confirm.approve",
            resource="device:cam-01/op:action:create_action_rule",
            details=details,
            success=True,
            error_message="",
        )
        return ADMZMCPServer._fmt_audit_entry(None, entry)

    def test_rule_id_appears_in_the_summary(self):
        out = self._fmt({
            "confirmed_by": "chat", "risk_level": "dangerous", "rule_id": "175",
            "config_id": "42",
        })
        assert "rule_id=175" in out["summary"]
        assert "config_id=42" in out["summary"]
        # The fields it already surfaced are still there.
        assert "approved_by=chat" in out["summary"]
        assert "risk=dangerous" in out["summary"]

    def test_every_allow_listed_key_is_surfaced(self):
        """Driven off the writer's allow-list, so extending one extends both."""
        from admz.audit import OUTCOME_IDENTITY_KEYS

        out = self._fmt({k: f"v-{k}" for k in OUTCOME_IDENTITY_KEYS})
        for key in OUTCOME_IDENTITY_KEYS:
            assert f"{key}=v-{key}" in out["summary"], f"{key} dropped"

    def test_row_without_identifiers_summarises_as_before(self):
        out = self._fmt({"confirmed_by": "web", "risk_level": "dangerous"})
        assert out["summary"] == "approved_by=web; risk=dangerous"
