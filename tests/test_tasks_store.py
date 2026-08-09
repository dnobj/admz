"""Tests for the unified TaskStore (ADR-0037)."""

from __future__ import annotations

import time

import pytest

from admz.tasks.store import (
    EVENT_NEEDS_SETUP,
    TRIGGER_DETECTION,
    TRIGGER_SCHEDULE,
    Task,
    TaskStore,
    event_for_status,
)


@pytest.fixture
def store(tmp_path):
    return TaskStore(str(tmp_path / "admz.db"))


class TestScheduleTasks:
    def test_create_get_list(self, store):
        t = store.create_schedule(
            description="Nightly snapshot", interval_seconds=3600,
            action_type="snapshot", tag_filter="lab",
        )
        assert t.trigger_kind == TRIGGER_SCHEDULE
        assert t.next_run  # defaulted to now+interval
        got = store.get(t.id)
        assert got.description == "Nightly snapshot"
        assert got.interval_seconds == 3600
        assert got.tag_filter == "lab"
        assert got.enabled is True
        scheds = store.schedule_tasks()
        assert [s.id for s in scheds] == [t.id]

    def test_enabled_only_filter(self, store):
        a = store.create_schedule(description="on", interval_seconds=60)
        b = store.create_schedule(description="off", interval_seconds=60, enabled=False)
        ids = {s.id for s in store.schedule_tasks(enabled_only=True)}
        assert a.id in ids and b.id not in ids

    def test_update_and_run_result(self, store):
        t = store.create_schedule(description="x", interval_seconds=60)
        store.update(t.id, enabled=False, interval_seconds=120)
        assert store.get(t.id).enabled is False
        assert store.get(t.id).interval_seconds == 120
        store.set_run_result(t.id, last_run="2026-06-18T00:00:00+00:00",
                             last_result="3 succeeded", next_run="2026-06-18T01:00:00+00:00")
        g = store.get(t.id)
        assert g.last_result == "3 succeeded"
        assert g.next_run == "2026-06-18T01:00:00+00:00"

    def test_delete(self, store):
        t = store.create_schedule(description="x", interval_seconds=60)
        assert store.delete(t.id) is True
        assert store.get(t.id) is None
        assert store.delete(t.id) is False

    def test_device_ids_roundtrip(self, store):
        t = store.create_schedule(
            description="x", interval_seconds=60, device_ids=["AA", "BB"],
        )
        assert store.get(t.id).device_ids == ["AA", "BB"]


class TestDetectionTasks:
    def test_create_and_list_active_for(self, store):
        pid = store.create_detection(
            device_id="cam-1", event=EVENT_NEEDS_SETUP, action_type="reprovision",
            action_params={"username": "root"}, approved_by="tester",
            description="recover cam-1",
        )
        active = store.list_active_for("cam-1")
        assert len(active) == 1
        t = active[0]
        assert t.id == pid
        assert t.trigger_kind == TRIGGER_DETECTION
        assert t.action_type == "reprovision"
        assert t.action == {"action": "reprovision", "username": "root"}
        assert t.approved_by == "tester"
        # not visible for another device
        assert store.list_active_for("other") == []

    def test_unknown_event_rejected(self, store):
        with pytest.raises(ValueError):
            store.create_detection(device_id="x", event="on_whatever",
                                   action_type="reprovision")

    def test_claim_fires_once(self, store):
        store.create_detection(device_id="cam-1", event=EVENT_NEEDS_SETUP,
                               action_type="reprovision")
        first = store.claim_for_event("cam-1", EVENT_NEEDS_SETUP)
        assert len(first) == 1
        # a second concurrent claim gets nothing (already fired)
        second = store.claim_for_event("cam-1", EVENT_NEEDS_SETUP)
        assert second == []
        # it's no longer in the active list
        assert store.list_active_for("cam-1") == []

    def test_claim_event_mismatch(self, store):
        store.create_detection(device_id="cam-1", event=EVENT_NEEDS_SETUP,
                               action_type="reprovision")
        assert store.claim_for_event("cam-1", "on_online") == []

    def test_cancel(self, store):
        pid = store.create_detection(device_id="cam-1", event=EVENT_NEEDS_SETUP,
                                     action_type="reprovision")
        assert store.cancel(pid) is True
        assert store.list_active_for("cam-1") == []
        # cancel is a no-op once it's not pending
        assert store.cancel(pid) is False

    def test_expire_stale(self, store):
        pid = store.create_detection(device_id="cam-1", event=EVENT_NEEDS_SETUP,
                                     action_type="reprovision", ttl_seconds=-1)
        # already expired -> expire_stale flips it
        assert store.expire_stale() == 1
        assert store.list_active_for("cam-1") == []
        assert store.get(pid).status == "expired"

    def test_schedule_tasks_excludes_detections(self, store):
        store.create_detection(device_id="cam-1", event=EVENT_NEEDS_SETUP,
                               action_type="reprovision")
        store.create_schedule(description="s", interval_seconds=60)
        assert len(store.schedule_tasks()) == 1


class TestListFilters:
    def test_list_by_kind_and_device(self, store):
        store.create_schedule(description="s", interval_seconds=60, device_ids=["cam-1"])
        store.create_detection(device_id="cam-1", event=EVENT_NEEDS_SETUP,
                               action_type="reprovision")
        store.create_detection(device_id="cam-2", event=EVENT_NEEDS_SETUP,
                               action_type="reprovision")
        assert len(store.list(trigger_kind=TRIGGER_DETECTION)) == 2
        assert len(store.list(trigger_kind=TRIGGER_SCHEDULE)) == 1
        # device filter spans schedule scope (device_ids) + detection target
        for_cam1 = store.list(device_id="cam-1")
        assert {t.trigger_kind for t in for_cam1} == {TRIGGER_SCHEDULE, TRIGGER_DETECTION}
        assert len(for_cam1) == 2

    def test_active_only_drops_cancelled_detection(self, store):
        pid = store.create_detection(device_id="cam-1", event=EVENT_NEEDS_SETUP,
                                     action_type="reprovision")
        store.cancel(pid)
        assert store.list(trigger_kind=TRIGGER_DETECTION, active_only=True) == []
        assert len(store.list(trigger_kind=TRIGGER_DETECTION)) == 1  # still on record


def test_event_for_status():
    assert event_for_status("needs_setup") == EVENT_NEEDS_SETUP
    assert event_for_status("online") == "on_online"
    assert event_for_status("auth_failed") is None


def test_task_to_dict_shape():
    t = Task(id="x", description="hi", interval_seconds=3600, action_type="snapshot")
    d = t.to_dict()
    assert d["name"] == "hi" and d["interval_human"] == "1h"
    assert d["trigger_kind"] == "schedule"


class TestModuleTaskHandlerInstall:
    """GH #172 instance 4. `contract.py` lists `task_handlers()` among the seven
    factories "the platform calls and merges", present tense, and
    `ModuleRegistry.task_handlers_all` implements the merge — but nothing
    invoked it. Six of the seven merges were wired; this was the only orphan, so
    a module implementing the documented contract had its handlers silently
    dropped, surfacing later and far from the cause as `ValueError: no handler
    registered for action ...`.
    """

    def _clean(self, monkeypatch):
        """Work on a copy of the handler registry — it is module-global, and the
        built-ins register at import."""
        from admz.tasks import handlers as h
        monkeypatch.setattr(h, "_HANDLERS", dict(h._HANDLERS))
        return h

    class _Reg:
        def __init__(self, mapping):
            self._m = mapping

        def task_handlers_all(self):
            return self._m

    def test_module_handlers_are_installed(self, monkeypatch):
        h = self._clean(monkeypatch)

        async def handler(task, ctx):
            return {"success": True}

        assert h.install_module_task_handlers(self._Reg({"acs_sync": handler})) == 1
        assert h.get_task_handler("acs_sync") is handler
        assert "acs_sync" in h.list_action_types()

    def test_a_module_may_not_replace_a_builtin(self, monkeypatch):
        """A module quietly taking over `snapshot` for the whole fleet would be
        load-order-dependent and invisible. Refused; the built-in stands."""
        h = self._clean(monkeypatch)
        builtin = h.get_task_handler("snapshot")
        assert builtin is not None                      # guard: the premise

        async def usurper(task, ctx):
            return {"success": True}

        assert h.install_module_task_handlers(self._Reg({"snapshot": usurper})) == 0
        assert h.get_task_handler("snapshot") is builtin

    def test_one_refusal_does_not_block_the_others(self, monkeypatch):
        h = self._clean(monkeypatch)

        async def a(task, ctx):
            return {}

        async def b(task, ctx):
            return {}

        n = h.install_module_task_handlers(
            self._Reg({"snapshot": a, "acs_sync": b}))
        assert n == 1
        assert h.get_task_handler("acs_sync") is b

    def test_no_modules_is_not_an_error(self, monkeypatch):
        h = self._clean(monkeypatch)
        assert h.install_module_task_handlers(self._Reg({})) == 0
        assert h.install_module_task_handlers(self._Reg(None)) == 0

    def test_the_real_registry_is_accepted(self, monkeypatch):
        """Shape check against the actual ModuleRegistry, so a rename of
        `task_handlers_all` fails here rather than at startup. Neither shipped
        module supplies handlers today, so 0 is the expected count."""
        from admz.modules.registry import ModuleRegistry
        h = self._clean(monkeypatch)
        assert h.install_module_task_handlers(ModuleRegistry().discover()) == 0


class TestBaselineBootidIsGone:
    """GH #172 instance 5. A column plus four API fields that nothing wrote and
    nothing read: the only writer was the one-shot legacy migration, and neither
    firing path (`claim_for_event`, `HealthMonitor._fire_pending`) ever compared
    a device's bootid. It shipped as `null` in `GET /api/tasks`,
    `GET /api/tasks/{id}`, `GET /api/devices/{id}/pending` and the MCP
    `list_device_recovery` result.

    The confusable twin in `admz/recovery.py` (`await_device_recovery`) is
    genuinely live and is deliberately untouched — that resemblance is what made
    this one look like it worked.
    """

    def test_the_field_is_removed(self):
        from admz.tasks.store import Task
        assert not hasattr(Task(id="t1"), "baseline_bootid")

    def test_it_is_not_in_the_api_shape(self):
        from admz.tasks.store import Task
        assert "baseline_bootid" not in Task(id="t1").to_dict()

    def test_create_detection_rejects_it(self):
        """The kwarg is gone, so a caller cannot quietly reintroduce the field."""
        import inspect
        from admz.tasks.store import TaskStore
        assert "baseline_bootid" not in inspect.signature(
            TaskStore.create_detection).parameters

    def test_the_live_recovery_twin_is_untouched(self):
        """`await_device_recovery` really does use a baseline bootid. Deleting
        the dead one must not have taken the working one with it."""
        import inspect
        from admz import recovery
        assert "baseline_bootid" in inspect.signature(
            recovery.await_device_recovery).parameters


class TestModuleHandlerInstallEdgeCases:
    """Review findings on #373 — the cases the first pass missed."""

    def _clean(self, monkeypatch):
        from admz.tasks import handlers as h
        monkeypatch.setattr(h, "_HANDLERS", dict(h._HANDLERS))
        monkeypatch.setattr(h, "_MODULE_INSTALLED", set(h._MODULE_INSTALLED))
        return h

    class _Reg:
        def __init__(self, mapping):
            self._m = mapping

        def task_handlers_all(self):
            return self._m

    def test_a_second_lifespan_is_a_no_op(self, monkeypatch):
        h = self._clean(monkeypatch)

        async def handler(task, ctx):
            return {}

        reg = self._Reg({"acs_sync": handler})
        assert h.install_module_task_handlers(reg) == 1
        assert h.install_module_task_handlers(reg) == 0     # identical → no-op
        assert h.get_task_handler("acs_sync") is handler

    def test_a_changed_module_handler_refreshes(self, monkeypatch):
        """Not an override: refusing here would pin the stale callable and log
        it as a built-in clash, which it is not."""
        h = self._clean(monkeypatch)

        async def v1(task, ctx):
            return {}

        async def v2(task, ctx):
            return {}

        h.install_module_task_handlers(self._Reg({"acs_sync": v1}))
        assert h.install_module_task_handlers(self._Reg({"acs_sync": v2})) == 1
        assert h.get_task_handler("acs_sync") is v2

    def test_a_builtin_is_still_refused_after_a_module_install(self, monkeypatch):
        """The refresh path must not become a way in."""
        h = self._clean(monkeypatch)
        builtin = h.get_task_handler("snapshot")

        async def usurper(task, ctx):
            return {}

        h.install_module_task_handlers(self._Reg({"acs_sync": usurper}))
        assert h.install_module_task_handlers(self._Reg({"snapshot": usurper})) == 0
        assert h.get_task_handler("snapshot") is builtin


class TestModuleVsModuleCollision:
    """A plain `dict.update` in `task_handlers_all` hid module-vs-module
    clashes: the install step saw one handler and had nothing to refuse."""

    def test_the_merge_warns_when_two_modules_claim_one_action(self, caplog):
        import logging
        from admz.modules.registry import ModuleRegistry

        async def a(task, ctx):
            return {}

        async def b(task, ctx):
            return {}

        class _M:
            def __init__(self, mid, handlers):
                self.id, self._h = mid, handlers

            def task_handlers(self):
                return self._h

        reg = ModuleRegistry()
        reg._modules = [_M("alpha", {"sync": a}), _M("beta", {"sync": b})]
        with caplog.at_level(logging.WARNING):
            merged = reg.task_handlers_all()
        assert merged["sync"] is b                      # last wins, as before
        assert "alpha" in caplog.text and "beta" in caplog.text


class TestPendingActionShimCompat:
    def test_it_still_accepts_the_removed_kwarg(self):
        """It is a back-compat shim; removing a parameter it always took would
        TypeError on exactly the callers it exists to keep working."""
        import inspect
        from admz.fleet.pending_actions import PendingActionStore
        assert "baseline_bootid" in inspect.signature(
            PendingActionStore.create).parameters
