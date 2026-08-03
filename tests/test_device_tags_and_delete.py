"""MCP update_device_tags tool + the UI Delete-device affordance.

The delete_device MCP tool's widget gate is pinned in
test_mcp_destructive_gate.py; here we cover the new tag-edit tool and
that the device page surfaces a Delete control wired to the (authenticated,
audited) DELETE endpoint.
"""

from __future__ import annotations

import json

import pytest
from tests import mcp_harness


# ---------------------------------------------------------------------------
# MCP update_device_tags — reuses the destructive-gate test harness
# ---------------------------------------------------------------------------


def _make_server(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    monkeypatch.setenv("ADMZ_PRINCIPAL_NAME", "HOMELAB\\alice")
    monkeypatch.setenv("ADMZ_PRINCIPAL_SOURCE", "windows-local")
    monkeypatch.setenv("ADMZ_PRINCIPAL_GROUPS", "Administrators")
    from admz.mcp.server import ADMZMCPServer
    return ADMZMCPServer()


async def _call_tool(server, name: str, arguments: dict):
    return await mcp_harness.call_tool(server, name, arguments)


@pytest.fixture
def server(tmp_path, monkeypatch):
    return _make_server(tmp_path, monkeypatch)


class TestUpdateDeviceTags:
    @pytest.mark.asyncio
    async def test_tool_is_registered(self, server):
        names = set(await mcp_harness.tool_names(server))
        assert "update_device_tags" in names
        assert "delete_device" in names  # the widget-gated one already exists

    @pytest.mark.asyncio
    async def test_add_and_remove(self, server):
        server.registry.add_device("cam", {"host": "192.0.2.1", "tags": ["lab", "indoor"]})
        out = await _call_tool(
            server, "update_device_tags",
            {"device_id": "cam", "add": ["camera"], "remove": ["indoor"]},
        )
        assert out["success"] is True
        assert out["tags"] == ["lab", "camera"]
        assert out["added"] == ["camera"]
        assert out["removed"] == ["indoor"]
        # Persisted.
        assert server.registry.get_device_info("cam")["tags"] == ["lab", "camera"]

    @pytest.mark.asyncio
    async def test_add_is_deduped(self, server):
        server.registry.add_device("cam", {"host": "192.0.2.1", "tags": ["lab"]})
        out = await _call_tool(
            server, "update_device_tags", {"device_id": "cam", "add": ["lab", "lab"]},
        )
        assert out["tags"] == ["lab"]
        assert out["added"] == []

    @pytest.mark.asyncio
    async def test_remove_absent_is_noop(self, server):
        server.registry.add_device("cam", {"host": "192.0.2.1", "tags": ["lab"]})
        out = await _call_tool(
            server, "update_device_tags", {"device_id": "cam", "remove": ["nope"]},
        )
        assert out["tags"] == ["lab"]
        assert out["removed"] == []

    @pytest.mark.asyncio
    async def test_unknown_device_errors(self, server):
        out = await _call_tool(
            server, "update_device_tags", {"device_id": "ghost", "add": ["x"]},
        )
        assert out.get("success") is not True
        assert "not found" in str(out).lower() or out.get("error")


# ---------------------------------------------------------------------------
# UI: Delete-device control on the device page → DELETE endpoint
# ---------------------------------------------------------------------------


@pytest.fixture
def web(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from admz.auth import AuthBackend, NoAuth, Principal, set_active_backend

    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    import admz.api.main as main_module
    from admz.backends.sqlite_backend import SQLiteDeviceRegistry
    reg = SQLiteDeviceRegistry(
        db_path=str(tmp_path / "admz.db"), key_path=str(tmp_path / "admz.key"),
    )
    monkeypatch.setattr(main_module, "registry", reg)
    import admz.api.templating as templating
    monkeypatch.setattr(templating, "_registry", lambda: reg)
    from admz import audit as audit_module
    monkeypatch.setattr(
        audit_module, "audit_log",
        audit_module.AuditLog(db_path=str(tmp_path / "admz.db")),
    )
    reg.add_device("cam-x", {"host": "192.0.2.9", "nickname": "CamX"})

    class _Stub(AuthBackend):
        async def authenticate(self, request):
            return Principal(name="AXIS\\admin", display_name="admin",
                             source="windows", groups=["Administrators"],
                             is_anonymous=False)
    set_active_backend(_Stub())
    try:
        with TestClient(main_module.app) as c:
            yield c, reg
    finally:
        set_active_backend(NoAuth())


class TestDeleteUi:
    def test_device_page_has_delete_control(self, web):
        c, _ = web
        body = c.get("/device/cam-x").text
        assert "Danger zone" in body
        assert "Delete device" in body
        # Wired to the authenticated DELETE endpoint.
        assert "method: 'DELETE'" in body

    def test_delete_endpoint_removes_device(self, web):
        c, reg = web
        r = c.delete("/api/devices/cam-x")
        assert r.status_code == 204
        assert not reg.device_exists("cam-x")

    def test_delete_audited(self, web):
        c, _ = web
        c.delete("/api/devices/cam-x")
        from admz import audit as audit_module
        rows = audit_module.audit_log.list_recent(action="device.delete", limit=5)
        assert any(e.success for e in rows)
