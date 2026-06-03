"""Tests for Task #41 — MCP-side gate on destructive tools.

CR-3 added ``require_authenticated_principal`` to five REST endpoints
(mint API key, /confirm-settings, delete device, restore, plan
execute). The MCP equivalents of the destructive subset
(delete_device, restore_device, execute_plan) had no such gate —
anyone using an anonymous-principal chat session could call them
and actually wipe / restore / execute against real devices.

This file pins the new behavior:
  * Anonymous principals get a PermissionDenied envelope from
    delete_device / restore_device / execute_plan, with no side
    effects on the registry.
  * Authenticated principals (Windows IWA, API key, even the
    synthetic 'mcp-standalone' principal for CLI invocations of
    ``python -m admz mcp``) pass through to the handler as before.
  * Non-destructive tools (list_devices, get_device, snapshot_device,
    query_catalog, etc.) are not affected by the new gate — anonymous
    is fine for those.
  * Successful denials are still audit-logged with success=False.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from admz.mcp.server import _DESTRUCTIVE_MCP_TOOLS


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestDestructiveToolSet:
    """The list is the single source of truth — pin it so the set
    doesn't accidentally grow / shrink without a deliberate change."""

    def test_expected_tools_are_in_the_set(self):
        # Parity with CR-3's REST destructive list:
        #   DELETE /api/devices/{id}        → delete_device
        #   POST /api/snapshot/restore      → restore_device
        #   POST /api/plans/{id}/execute    → execute_plan
        assert "delete_device" in _DESTRUCTIVE_MCP_TOOLS
        assert "restore_device" in _DESTRUCTIVE_MCP_TOOLS
        assert "execute_plan" in _DESTRUCTIVE_MCP_TOOLS

    def test_non_destructive_tools_are_not_in_the_set(self):
        # Common read-only + low-risk-write tools must NOT be gated.
        not_gated = {
            "list_devices", "get_device", "get_device_health",
            "get_fleet_health", "search_devices",
            "snapshot_device", "snapshot_fleet",
            "register_device", "add_account", "delete_account",
            "query_catalog", "query_knowledge",
            "test_device_credentials", "discover_network_devices",
            "create_temp_credentials", "cleanup_temp_credentials",
            "execute_operation",  # dangerous ops gate themselves
                                  # separately via the confirmation flow
        }
        overlap = not_gated & _DESTRUCTIVE_MCP_TOOLS
        assert not overlap, (
            f"these tools should NOT be in _DESTRUCTIVE_MCP_TOOLS: {overlap}"
        )


# ---------------------------------------------------------------------------
# Live dispatcher behavior
# ---------------------------------------------------------------------------


@pytest.fixture
def anon_mcp_server(tmp_path, monkeypatch):
    """MCP server initialized as the anonymous principal — the default
    ADMZ_AUTH_BACKEND=none mapping."""
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")

    # Anonymous principal — name="anonymous", source="none"
    monkeypatch.setenv("ADMZ_PRINCIPAL_NAME", "anonymous")
    monkeypatch.setenv("ADMZ_PRINCIPAL_SOURCE", "none")
    monkeypatch.delenv("ADMZ_PRINCIPAL_GROUPS", raising=False)

    # Repoint the audit-log singleton for readback isolation.
    from admz import audit as audit_module
    fresh_audit = audit_module.AuditLog(db_path=str(tmp_path / "admz.db"))
    monkeypatch.setattr(audit_module, "audit_log", fresh_audit)

    from admz.mcp.server import ADMZMCPServer
    server = ADMZMCPServer()
    # Sanity: the principal we built really IS marked anonymous.
    assert server.principal.is_anonymous is True
    return server


@pytest.fixture
def auth_mcp_server(tmp_path, monkeypatch):
    """MCP server initialized as a real authenticated principal —
    the Windows-IWA-style identity the pool spawns when a logged-in
    user drives the chatbot."""
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")

    monkeypatch.setenv("ADMZ_PRINCIPAL_NAME", "AXIS\\alice")
    monkeypatch.setenv("ADMZ_PRINCIPAL_SOURCE", "windows")
    monkeypatch.setenv("ADMZ_PRINCIPAL_GROUPS", "Administrators")

    from admz import audit as audit_module
    fresh_audit = audit_module.AuditLog(db_path=str(tmp_path / "admz.db"))
    monkeypatch.setattr(audit_module, "audit_log", fresh_audit)

    from admz.mcp.server import ADMZMCPServer
    server = ADMZMCPServer()
    assert server.principal.is_anonymous is False
    return server


async def _call_tool(server, name: str, arguments: dict):
    """Dispatch through the registered call_tool handler. Returns
    the parsed JSON result."""
    from mcp.types import CallToolRequest, CallToolRequestParams

    handler = None
    for req_type, h in server.server.request_handlers.items():
        if req_type.__name__ == "CallToolRequest":
            handler = h
            break
    assert handler is not None

    req = CallToolRequest(
        method="tools/call",
        params=CallToolRequestParams(name=name, arguments=arguments),
    )
    result = await handler(req)
    text = result.root.content[0].text
    return json.loads(text)


class TestAnonymousBlockedFromDestructive:
    """The headline case: an anonymous principal gets PermissionDenied
    from each destructive tool, with no side effect on the registry."""

    @pytest.mark.asyncio
    async def test_anonymous_delete_device_refused(self, anon_mcp_server):
        # Seed a real device so any tool-side delete attempt would
        # actually have something to drop. If the gate works, the
        # device survives.
        anon_mcp_server.registry.add_device(
            "test-cam", {"host": "192.0.2.10"},
        )
        result = await _call_tool(
            anon_mcp_server, "delete_device", {"device_id": "test-cam"},
        )
        assert result.get("error") == "PermissionDenied"
        assert "authenticated principal" in result.get("message", "").lower()
        # Device still exists — gate stopped the call before the handler.
        assert anon_mcp_server.registry.device_exists("test-cam")

    @pytest.mark.asyncio
    async def test_anonymous_restore_device_refused(self, anon_mcp_server):
        anon_mcp_server.registry.add_device(
            "test-cam", {"host": "192.0.2.10"},
        )
        result = await _call_tool(
            anon_mcp_server, "restore_device",
            {"device_id": "test-cam", "ref": "HEAD"},
        )
        assert result.get("error") == "PermissionDenied"

    @pytest.mark.asyncio
    async def test_anonymous_execute_plan_refused(self, anon_mcp_server):
        result = await _call_tool(
            anon_mcp_server, "execute_plan",
            {"plan_id": "plan-deadbeef"},
        )
        assert result.get("error") == "PermissionDenied"

    @pytest.mark.asyncio
    async def test_denial_is_audited(self, anon_mcp_server):
        anon_mcp_server.registry.add_device(
            "test-cam", {"host": "192.0.2.10"},
        )
        await _call_tool(
            anon_mcp_server, "delete_device", {"device_id": "test-cam"},
        )
        from admz import audit as audit_module
        entries = audit_module.audit_log.list_recent(
            action="mcp.delete_device", limit=5,
        )
        assert entries
        assert entries[0].success is False
        assert "PermissionDenied" in entries[0].error_message
        assert entries[0].requester == "anonymous"


class TestAuthenticatedPassesThrough:
    """Real principals — Windows IWA, API key, or the standalone
    mcp-standalone identity used by ``python -m admz mcp`` — bypass
    the new gate. (Whether the underlying op then succeeds is the
    handler's problem; the gate just shouldn't be in the way.)"""

    @pytest.mark.asyncio
    async def test_admin_delete_device_reaches_handler(self, auth_mcp_server):
        # Add a device, then have the authenticated principal delete it.
        # No gate refusal — the device actually goes away.
        auth_mcp_server.registry.add_device(
            "test-cam", {"host": "192.0.2.10"},
        )
        result = await _call_tool(
            auth_mcp_server, "delete_device", {"device_id": "test-cam"},
        )
        # The handler succeeded — error envelope absent or non-permission.
        assert result.get("error") != "PermissionDenied", (
            f"authenticated principal was blocked: {result!r}"
        )
        assert not auth_mcp_server.registry.device_exists("test-cam")

    @pytest.mark.asyncio
    async def test_admin_execute_plan_reaches_handler(self, auth_mcp_server):
        # Plan doesn't exist; handler should respond with a "not found"
        # style error rather than the permission-denied gate.
        result = await _call_tool(
            auth_mcp_server, "execute_plan",
            {"plan_id": "plan-deadbeef"},
        )
        assert result.get("error") != "PermissionDenied", (
            f"authenticated principal was blocked: {result!r}"
        )

    @pytest.mark.asyncio
    async def test_mcp_standalone_treated_as_authenticated(
        self, tmp_path, monkeypatch,
    ):
        """``python -m admz mcp`` (no chatbot context) doesn't get
        ADMZ_PRINCIPAL_* env vars; the server falls back to the
        synthetic 'mcp-standalone' identity. That identity has
        source='mcp-standalone' so is_anonymous=False — destructive
        tools work because the operator has shell access."""
        monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
        monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
        monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
        for k in (
            "ADMZ_PRINCIPAL_NAME", "ADMZ_PRINCIPAL_SOURCE",
            "ADMZ_PRINCIPAL_GROUPS", "ADMZ_PRINCIPAL_DOMAIN",
            "ADMZ_PRINCIPAL_DISPLAY_NAME",
        ):
            monkeypatch.delenv(k, raising=False)

        from admz import audit as audit_module
        fresh_audit = audit_module.AuditLog(db_path=str(tmp_path / "admz.db"))
        monkeypatch.setattr(audit_module, "audit_log", fresh_audit)

        from admz.mcp.server import ADMZMCPServer
        server = ADMZMCPServer()
        assert server.principal.name == "mcp-standalone"
        assert server.principal.is_anonymous is False  # ← key

        server.registry.add_device("test-cam", {"host": "192.0.2.10"})
        result = await _call_tool(
            server, "delete_device", {"device_id": "test-cam"},
        )
        # Not blocked.
        assert result.get("error") != "PermissionDenied"


class TestNonDestructiveToolsUnaffected:
    """Sanity: tools NOT in _DESTRUCTIVE_MCP_TOOLS still work for
    anonymous principals. The gate is narrow on purpose."""

    @pytest.mark.asyncio
    async def test_anonymous_list_devices(self, anon_mcp_server):
        result = await _call_tool(anon_mcp_server, "list_devices", {})
        assert result.get("success") is True
        assert "devices" in result

    @pytest.mark.asyncio
    async def test_anonymous_get_device(self, anon_mcp_server):
        anon_mcp_server.registry.add_device(
            "test-cam", {"host": "192.0.2.10", "model": "M"},
        )
        result = await _call_tool(
            anon_mcp_server, "get_device", {"device_id": "test-cam"},
        )
        assert result.get("error") != "PermissionDenied"
        assert result.get("success") is True

    @pytest.mark.asyncio
    async def test_anonymous_snapshot_device_not_gated(self, anon_mcp_server):
        # snapshot_device is intentionally NOT in the destructive set —
        # it's reads from the device + commits a yaml snapshot, no
        # device-side mutation. Confirms the gate is narrowly scoped.
        # (Note: this will fail later because the test device isn't real
        # to probe, but it must get past the gate first.)
        anon_mcp_server.registry.add_device(
            "test-cam", {"host": "192.0.2.10"},
        )
        result = await _call_tool(
            anon_mcp_server, "snapshot_device", {"device_id": "test-cam"},
        )
        # The handler will report some other error (network failure,
        # facet failure) — but NOT PermissionDenied from our new gate.
        assert result.get("error") != "PermissionDenied"
