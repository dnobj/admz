"""Tests for the detection-task path (was the pending_device_actions engine).

After ADR-0037 the store is the unified ``tasks`` table; this file pins the
back-compat ``PendingActionStore`` adapter (the REST/MCP recovery surface still
uses it), the handler dispatch, and HealthMonitor._run_pending (execute + mark +
audit) — now Task-native.
"""

from __future__ import annotations

import pytest

import admz.tasks.store as store_mod
from admz.fleet import pending_actions as pa_module
from admz.fleet.pending_actions import (
    PendingActionStore,
    TRIGGER_NEEDS_SETUP,
    TRIGGER_ONLINE,
    execute_pending_action,
    register_pending_handler,
)
from admz.tasks.store import TaskStore


@pytest.fixture
def ts(tmp_path, monkeypatch):
    """An isolated unified store, wired in as the global singleton so the health
    monitor + the pending adapter both see it."""
    db = str(tmp_path / "t.db")
    monkeypatch.setenv("ADMZ_DB_PATH", db)        # audit + store share the temp db
    s = TaskStore(db)
    monkeypatch.setattr(store_mod, "tasks_store", s)
    monkeypatch.setattr(pa_module, "pending_actions", PendingActionStore(store=s))
    return s


@pytest.fixture
def store(ts):
    """The legacy-API adapter over the isolated store."""
    return pa_module.pending_actions


# --------------------------------------------------------------------------
# store adapter (old API, old dict shape)
# --------------------------------------------------------------------------

class TestPendingActionStore:
    def test_create_and_list_active(self, store):
        pid = store.create(
            device_id="cam-1", action={"action": "reprovision"},
            trigger=TRIGGER_NEEDS_SETUP, approved_by="dnich", description="x",
        )
        active = store.list_active_for("cam-1")
        assert len(active) == 1
        assert active[0]["id"] == pid
        assert active[0]["action"] == {"action": "reprovision"}
        assert active[0]["status"] == "pending"
        assert active[0]["approved_by"] == "dnich"

    def test_claim_fires_once(self, store):
        store.create(device_id="cam-1", action={"action": "x"},
                     trigger=TRIGGER_NEEDS_SETUP)
        first = store.claim_for_trigger("cam-1", TRIGGER_NEEDS_SETUP)
        assert len(first) == 1
        assert store.claim_for_trigger("cam-1", TRIGGER_NEEDS_SETUP) == []
        assert store.list_active_for("cam-1") == []

    def test_claim_only_matching_trigger(self, store):
        store.create(device_id="cam-1", action={"action": "x"},
                     trigger=TRIGGER_ONLINE)
        assert store.claim_for_trigger("cam-1", TRIGGER_NEEDS_SETUP) == []
        assert len(store.claim_for_trigger("cam-1", TRIGGER_ONLINE)) == 1

    def test_expire_stale(self, store):
        pid = store.create(device_id="cam-1", action={"action": "x"},
                           trigger=TRIGGER_NEEDS_SETUP, ttl_seconds=-1)
        assert store.list_active_for("cam-1") == []
        assert store.expire_stale() == 1
        assert store.get(pid)["status"] == "expired"
        assert store.claim_for_trigger("cam-1", TRIGGER_NEEDS_SETUP) == []

    def test_cancel(self, store):
        pid = store.create(device_id="cam-1", action={"action": "x"},
                           trigger=TRIGGER_NEEDS_SETUP)
        assert store.cancel(pid) is True
        assert store.cancel(pid) is False
        assert store.list_active_for("cam-1") == []

    def test_unknown_trigger_rejected(self, store):
        with pytest.raises(ValueError):
            store.create(device_id="cam-1", action={}, trigger="on_whatever")


# --------------------------------------------------------------------------
# handler dispatch (old (action, device_id) signature over the unified registry)
# --------------------------------------------------------------------------

class TestDispatch:
    @pytest.mark.asyncio
    async def test_registered_handler_runs(self, store):
        calls = []

        async def handler(action, did):
            calls.append((action, did))

        register_pending_handler("test_act", handler)
        await execute_pending_action({"action": "test_act", "x": 1}, "cam-1")
        assert calls == [({"action": "test_act", "x": 1}, "cam-1")]

    @pytest.mark.asyncio
    async def test_unregistered_raises(self, store):
        with pytest.raises(ValueError):
            await execute_pending_action({"action": "nope-xyz"}, "cam-1")


# --------------------------------------------------------------------------
# HealthMonitor firing (claim -> execute -> mark), now Task-native
# --------------------------------------------------------------------------

class TestMonitorRunPending:
    @pytest.mark.asyncio
    async def test_run_pending_marks_done(self, ts):
        from admz.fleet.health import HealthMonitor

        ran = []

        async def handler(action, did):
            ran.append(did)

        register_pending_handler("recover", handler)
        pid = ts.create_detection(device_id="cam-1", event=TRIGGER_NEEDS_SETUP,
                                  action_type="recover", approved_by="dnich")
        claimed = ts.claim_for_event("cam-1", TRIGGER_NEEDS_SETUP)
        assert len(claimed) == 1

        mon = HealthMonitor(registry=None)
        await mon._run_pending(claimed[0])

        assert ran == ["cam-1"]
        assert ts.get(pid).status == "done"

    @pytest.mark.asyncio
    async def test_run_pending_marks_failed(self, ts):
        from admz.fleet.health import HealthMonitor

        async def boom(action, did):
            raise RuntimeError("provision failed")

        register_pending_handler("boom", boom)
        pid = ts.create_detection(device_id="cam-1", event=TRIGGER_NEEDS_SETUP,
                                  action_type="boom")
        claimed = ts.claim_for_event("cam-1", TRIGGER_NEEDS_SETUP)

        mon = HealthMonitor(registry=None)
        await mon._run_pending(claimed[0])

        rec = ts.get(pid)
        assert rec.status == "failed"
        assert "provision failed" in rec.last_error
