"""Tests for the MCP deferred-recovery tools (queue / list / cancel).

These exercise the real ADMZMCPServer handlers against an isolated pending-
actions store, covering the cross-process pattern the chatbot uses to arm a
trigger-based re-provision.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")

    # Bind the pending-actions singleton to the isolated DB.
    import admz.fleet.pending_actions as pa
    monkeypatch.setattr(
        pa, "pending_actions", pa.PendingActionStore(str(tmp_path / "admz.db"))
    )

    from admz.mcp.server import ADMZMCPServer

    srv = ADMZMCPServer()
    # Authenticated, non-anonymous operator by default.
    srv.principal = SimpleNamespace(
        name="tester", source="api-key", is_anonymous=False
    )
    # Only 'cam-1' is a known device.
    monkeypatch.setattr(srv.registry, "device_exists", lambda d: d == "cam-1")
    return srv


class TestQueueDeviceRecovery:
    def test_queue_creates_pending(self, server):
        res = server._queue_device_recovery({"device_id": "cam-1"})
        assert res["success"] is True
        assert res["queued"] is True
        assert res["pending_id"]
        assert res["trigger"] == "on_needs_setup"

        # It is visible to the (shared) store the health loop reads.
        listing = server._list_device_recovery({"device_id": "cam-1"})
        assert listing["count"] == 1
        item = listing["pending"][0]
        assert item["action"] == "reprovision"
        assert item["approved_by"] == "tester"
        assert item["pending_id"] == res["pending_id"]

    def test_queue_anonymous_refused(self, server):
        server.principal = SimpleNamespace(
            name="anonymous", source="none", is_anonymous=True
        )
        res = server._queue_device_recovery({"device_id": "cam-1"})
        assert res["success"] is False
        assert res["error"] == "PermissionDenied"
        # nothing armed
        assert server._list_device_recovery({})["count"] == 0

    def test_queue_unknown_device_raises(self, server):
        from admz.mcp.server import DeviceNotFoundError

        with pytest.raises(DeviceNotFoundError):
            server._queue_device_recovery({"device_id": "nope"})

    def test_queue_unsupported_intent(self, server):
        res = server._queue_device_recovery(
            {"device_id": "cam-1", "intent": "remove"}
        )
        assert res["success"] is False
        assert "remove" in res["error"]

    def test_queue_missing_device_id(self, server):
        res = server._queue_device_recovery({})
        assert res["success"] is False


class TestListAndCancel:
    def test_list_all_vs_scoped(self, server, monkeypatch):
        monkeypatch.setattr(
            server.registry, "device_exists", lambda d: d in ("cam-1", "cam-2")
        )
        server._queue_device_recovery({"device_id": "cam-1"})
        server._queue_device_recovery({"device_id": "cam-2"})
        assert server._list_device_recovery({})["count"] == 2
        assert server._list_device_recovery({"device_id": "cam-1"})["count"] == 1

    def test_cancel_removes_it(self, server):
        pid = server._queue_device_recovery({"device_id": "cam-1"})["pending_id"]
        res = server._cancel_device_recovery({"pending_id": pid})
        assert res["success"] is True
        assert res["cancelled"] == pid
        assert server._list_device_recovery({})["count"] == 0

    def test_cancel_unknown_id(self, server):
        res = server._cancel_device_recovery({"pending_id": "does-not-exist"})
        assert res["success"] is False

    def test_cancel_missing_id(self, server):
        res = server._cancel_device_recovery({})
        assert res["success"] is False
