"""Tests for the deferred-action engine (pending_device_actions + firing).

Covers the store (create / list / atomic fire-once claim / expire / cancel),
the handler dispatch, and HealthMonitor._run_pending (execute + mark + audit).
"""

from __future__ import annotations

import pytest

from admz.fleet import pending_actions as pa_module
from admz.fleet.pending_actions import (
    PendingActionStore,
    TRIGGER_NEEDS_SETUP,
    TRIGGER_ONLINE,
    execute_pending_action,
    register_pending_handler,
)


@pytest.fixture
def store(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    monkeypatch.setenv("ADMZ_DB_PATH", db)        # audit + store share the temp db
    s = PendingActionStore(db_path=db)
    monkeypatch.setattr(pa_module, "pending_actions", s)
    monkeypatch.setattr(pa_module, "_HANDLERS", {})  # isolate the handler registry
    return s


# --------------------------------------------------------------------------
# store
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
        # second claim sees nothing — the first atomically marked it 'fired'
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
        assert store.list_active_for("cam-1") == []          # past-expiry excluded
        assert store.expire_stale() == 1
        assert store.get(pid)["status"] == "expired"
        assert store.claim_for_trigger("cam-1", TRIGGER_NEEDS_SETUP) == []

    def test_cancel(self, store):
        pid = store.create(device_id="cam-1", action={"action": "x"},
                           trigger=TRIGGER_NEEDS_SETUP)
        assert store.cancel(pid) is True
        assert store.cancel(pid) is False  # already cancelled, not pending
        assert store.list_active_for("cam-1") == []

    def test_unknown_trigger_rejected(self, store):
        with pytest.raises(ValueError):
            store.create(device_id="cam-1", action={}, trigger="on_whatever")


# --------------------------------------------------------------------------
# handler dispatch
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
            await execute_pending_action({"action": "nope"}, "cam-1")


# --------------------------------------------------------------------------
# HealthMonitor firing (claim -> execute -> mark)
# --------------------------------------------------------------------------

class TestMonitorRunPending:
    @pytest.mark.asyncio
    async def test_run_pending_marks_done(self, store):
        from admz.fleet.health import HealthMonitor

        ran = []

        async def handler(action, did):
            ran.append(did)

        register_pending_handler("recover", handler)
        pid = store.create(device_id="cam-1", action={"action": "recover"},
                           trigger=TRIGGER_NEEDS_SETUP, approved_by="dnich")
        claimed = store.claim_for_trigger("cam-1", TRIGGER_NEEDS_SETUP)

        mon = HealthMonitor(registry=None)
        await mon._run_pending(claimed[0])

        assert ran == ["cam-1"]
        assert store.get(pid)["status"] == "done"

    @pytest.mark.asyncio
    async def test_run_pending_marks_failed(self, store):
        from admz.fleet.health import HealthMonitor

        async def boom(action, did):
            raise RuntimeError("provision failed")

        register_pending_handler("boom", boom)
        pid = store.create(device_id="cam-1", action={"action": "boom"},
                           trigger=TRIGGER_NEEDS_SETUP)
        claimed = store.claim_for_trigger("cam-1", TRIGGER_NEEDS_SETUP)

        mon = HealthMonitor(registry=None)
        await mon._run_pending(claimed[0])

        rec = store.get(pid)
        assert rec["status"] == "failed"
        assert "provision failed" in rec["last_error"]
