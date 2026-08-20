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
    def test_queue_gates_behind_the_widget(self, server):
        # Arming a detection task is standing behavior — the tool now
        # returns the confirmation card instead of writing directly.
        res = server._queue_device_recovery({"device_id": "cam-1"})
        assert res["success"] is False
        assert res["blocked"] is True
        assert res["confirm_url"].startswith("/confirm/")
        assert "on_needs_setup" in res["reason"]

        # Nothing armed until the card is approved.
        assert server._list_device_recovery({"device_id": "cam-1"})["count"] == 0

        # The held session is a create_task action with the reprovision spec.
        from admz.api.confirm_store import confirm_store
        session = confirm_store.get_session(res["confirm_token"])
        assert session.operation_id == "action:create_task"
        assert session.action["action_type"] == "reprovision"
        assert session.action["event"] == "on_needs_setup"

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
    def _arm(self, device_id):
        # Seed a pending action directly (the tool itself now gates; list
        # and cancel behavior is what's under test here).
        from admz.fleet.pending_actions import TRIGGER_NEEDS_SETUP, pending_actions
        return pending_actions.create(
            device_id=device_id,
            action={"action": "reprovision", "username": "root"},
            trigger=TRIGGER_NEEDS_SETUP,
            approved_by="tester",
            description=f"Re-provision {device_id}",
        )

    def test_list_all_vs_scoped(self, server, monkeypatch):
        monkeypatch.setattr(
            server.registry, "device_exists", lambda d: d in ("cam-1", "cam-2")
        )
        self._arm("cam-1")
        self._arm("cam-2")
        assert server._list_device_recovery({})["count"] == 2
        assert server._list_device_recovery({"device_id": "cam-1"})["count"] == 1

    def test_cancel_removes_it(self, server):
        pid = self._arm("cam-1")
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


class TestListTasks:
    def _isolated_store(self, tmp_path, monkeypatch):
        import admz.tasks.store as sm
        from admz.tasks.store import TaskStore
        ts = TaskStore(str(tmp_path / "admz.db"))
        monkeypatch.setattr(sm, "tasks_store", ts)
        return ts

    def test_list_unified(self, server, tmp_path, monkeypatch):
        from admz.tasks.store import EVENT_NEEDS_SETUP
        ts = self._isolated_store(tmp_path, monkeypatch)
        ts.create_schedule(description="nightly", interval_seconds=86400,
                           action_type="snapshot")
        ts.create_detection(device_id="cam-1", event=EVENT_NEEDS_SETUP,
                            action_type="reprovision")
        res = server._list_tasks({})
        # The two created here + the seeded capability-survey cadence
        # (ADR-0063 S2 — the app fixture seeds it into this same DB).
        assert res["success"] and res["count"] == 3
        kinds = {t["trigger_kind"] for t in res["tasks"]}
        assert kinds == {"schedule", "detection"}
        whens = {t["when"] for t in res["tasks"]}
        assert any(w.startswith("every") for w in whens)
        assert any(w.startswith("when") for w in whens)

    def test_list_filter_kind(self, server, tmp_path, monkeypatch):
        from admz.tasks.store import EVENT_NEEDS_SETUP
        ts = self._isolated_store(tmp_path, monkeypatch)
        ts.create_schedule(description="s", interval_seconds=60, action_type="snapshot")
        ts.create_detection(device_id="cam-1", event=EVENT_NEEDS_SETUP,
                            action_type="reprovision")
        assert server._list_tasks({"kind": "detection"})["count"] == 1
        # The one created here + the seeded capability-survey cadence.
        assert server._list_tasks({"kind": "schedule"})["count"] == 2
