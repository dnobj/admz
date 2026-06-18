"""Tests for audit-log search (AuditLog.search + the search_audit_log MCP tool)."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from admz.audit import AuditLog


@pytest.fixture
def log(tmp_path):
    return AuditLog(str(tmp_path / "admz.db"))


def _seed(log, **kw):
    log.record(
        requester=kw.get("requester", "dnich"),
        auth_source=kw.get("auth_source", "windows-local"),
        action=kw["action"],
        resource=kw.get("resource", ""),
        details=kw.get("details"),
        success=kw.get("success", True),
        error_message=kw.get("error_message", ""),
    )


class TestAuditSearch:
    def test_device_matches_resource_and_details(self, log):
        _seed(log, action="mcp.execute_operation",
              resource="mcp:execute_operation/device:CAM-1/op:factorydefault.cgi:factory-reset",
              details={"args": {"device_id": "CAM-1", "operation_id": "factorydefault.cgi:factory-reset"}})
        _seed(log, action="mcp.get_device", resource="mcp:get_device/device:CAM-2")
        got = log.search(device="CAM-1")
        assert len(got) == 1 and got[0].resource.endswith("factory-reset")
        # device id buried only in details is still found
        _seed(log, action="device.create", resource="device:CAM-3",
              details={"device_id": "CAM-3"})
        assert len(log.search(device="CAM-3")) == 1

    def test_action_substring(self, log):
        _seed(log, action="device.queue_recovery", resource="device:X")
        _seed(log, action="mcp.list_device_recovery")
        _seed(log, action="mcp.get_device")
        assert len(log.search(action="recovery")) == 2

    def test_requester_substring(self, log):
        _seed(log, action="a", requester="AXIS\\alice")
        _seed(log, action="b", requester="scheduler")
        assert len(log.search(requester="alice")) == 1

    def test_time_range(self, log):
        _seed(log, action="old")
        # backdate by writing directly is awkward; use start in the future to
        # exclude, and start in the past to include.
        now = time.time()
        assert len(log.search(start=now - 3600)) == 1   # within the last hour
        assert len(log.search(start=now + 3600)) == 0   # nothing in the future

    def test_free_text(self, log):
        _seed(log, action="mcp.execute_operation",
              resource="mcp:execute_operation/device:X",
              details={"args": {"operation_id": "factorydefault.cgi:factory-reset"}})
        assert len(log.search(text="factorydefault")) == 1
        assert len(log.search(text="reboot")) == 0

    def test_success_filter(self, log):
        _seed(log, action="ok", success=True)
        _seed(log, action="bad", success=False, error_message="boom")
        assert len(log.search(success=False)) == 1
        assert log.search(success=False)[0].error_message == "boom"

    def test_who_defaulted_device_x(self, log):
        # The definitive "who" — the confirm.approve row.
        _seed(log, action="confirm.approve",
              resource="device:CAM-9/op:factorydefault.cgi:factory-reset",
              details={"confirmed_by": "AXIS\\bob", "risk_level": "dangerous"})
        hits = log.search(device="CAM-9", action="confirm.approve")
        assert len(hits) == 1
        assert hits[0].details["confirmed_by"] == "AXIS\\bob"

    def test_limit(self, log):
        for i in range(10):
            _seed(log, action="x", resource=f"r{i}")
        assert len(log.search(limit=3)) == 3


class TestToolResourceEnrichment:
    def test_operation_id_in_resource(self):
        from admz.mcp.server import _tool_resource
        r = _tool_resource("execute_operation",
                           {"device_id": "CAM-1", "operation_id": "factorydefault.cgi:factory-reset"})
        assert r == "mcp:execute_operation/device:CAM-1/op:factorydefault.cgi:factory-reset"

    def test_no_op_no_suffix(self):
        from admz.mcp.server import _tool_resource
        assert _tool_resource("get_device", {"device_id": "CAM-1"}) == "mcp:get_device/device:CAM-1"


class TestSearchAuditLogHelpers:
    def test_window_parsing(self):
        from admz.mcp.server import ADMZMCPServer
        assert ADMZMCPServer._parse_audit_window("7d") == 7 * 86400
        assert ADMZMCPServer._parse_audit_window("24h") == 24 * 3600
        assert ADMZMCPServer._parse_audit_window("30m") == 30 * 60
        assert ADMZMCPServer._parse_audit_window("1w") == 604800
        assert ADMZMCPServer._parse_audit_window("nonsense") is None

    def test_ts_parsing(self):
        from admz.mcp.server import ADMZMCPServer
        assert ADMZMCPServer._parse_audit_ts("1781781084") == 1781781084.0
        iso = ADMZMCPServer._parse_audit_ts("2026-06-18T00:00:00Z")
        assert iso and iso > 1_700_000_000


class TestSearchAuditLogTool:
    @pytest.fixture
    def server(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
        monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
        monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
        from admz.mcp.server import ADMZMCPServer
        srv = ADMZMCPServer()
        # seed audit rows on the same isolated db
        lg = AuditLog(str(tmp_path / "admz.db"))
        _seed(lg, action="confirm.approve",
              resource="device:CAM-9/op:factorydefault.cgi:factory-reset",
              details={"confirmed_by": "AXIS\\bob", "risk_level": "dangerous"})
        _seed(lg, action="mcp.get_device", resource="mcp:get_device/device:CAM-2")
        return srv

    def test_search_returns_formatted_entries(self, server):
        res = server._search_audit_log({"device_id": "CAM-9", "within": "7d"})
        assert res["success"] and res["count"] == 1
        e = res["entries"][0]
        assert e["actor"] == "AXIS\\bob" or e["action"] == "confirm.approve"
        assert "approved_by=AXIS\\bob" in (e["summary"] or "")
        assert e["time"].startswith("20")  # ISO
        assert res["window"] and res["window"]["since"]

    def test_search_action_filter(self, server):
        assert server._search_audit_log({"action": "confirm"})["count"] == 1
        assert server._search_audit_log({"action": "get_device"})["count"] == 1

    def test_search_no_match(self, server):
        assert server._search_audit_log({"device_id": "NOPE"})["count"] == 0
