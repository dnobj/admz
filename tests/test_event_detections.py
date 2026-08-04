"""Event-pattern detections — store, evaluator, handlers, route auth (ADR-0041 layer 3)."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from types import SimpleNamespace

import pytest


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ── store fixtures ──────────────────────────────────────────────────────────
def _store(tmp_path):
    from admz.events.detections import DetectionStore
    return DetectionStore(str(tmp_path / "det.db"))


def _det(**kw):
    from admz.events.detections import EventDetection
    base = dict(id="", name="rule", source="device", action_type="notify")
    base.update(kw)
    return EventDetection(**base)


def _rec(**kw):
    """A normalized device-event record (the shape the evaluator sees)."""
    base = {
        "id": "e1", "ts": "2026-06-20T13:00:00.000Z", "source": "device",
        "type": "tns1:Device/tnsaxis:IO/Port", "device_id": "d1", "device_name": "Cam A",
        "summary": "Port · state=1",
        "data": {"topic": "tns1:Device/tnsaxis:IO/Port", "category": "io",
                 "leaf": "Port", "data": {"state": "1"}},
    }
    base.update(kw)
    return base


# ── store CRUD + version ─────────────────────────────────────────────────────
def test_store_crud_and_version_bump(tmp_path):
    s = _store(tmp_path)
    v0 = s.version
    rid = s.create(_det(name="motion", match={"category": "motion"}, cooldown_seconds=30))
    assert rid and s.version == v0 + 1
    got = s.get(rid)
    assert got.name == "motion" and got.match == {"category": "motion"} and got.cooldown_seconds == 30
    assert got.enabled is True and got.source == "device"
    # update bumps version + round-trips JSON
    assert s.update(rid, enabled=False, match={"category": "io"}) is True
    assert s.version == v0 + 2
    assert s.get(rid).enabled is False and s.get(rid).match == {"category": "io"}
    # list / enabled_only
    assert len(s.list()) == 1 and len(s.list(enabled_only=True)) == 0
    assert s.delete(rid) is True and s.version == v0 + 3
    assert s.get(rid) is None


def test_store_record_fire_does_not_bump_version(tmp_path):
    s = _store(tmp_path)
    rid = s.create(_det())
    v = s.version
    s.record_fire(rid, 1700000000000, "")
    assert s.version == v  # firing is not a structural change
    got = s.get(rid)
    assert got.fire_count == 1 and got.last_fired_ms == 1700000000000


# ── evaluator: a fake registry that returns tags ─────────────────────────────
class _Reg:
    def __init__(self, tags):
        self._tags = tags

    def get_device_info(self, device_id):
        return {"tags": self._tags.get(device_id, [])}


def _evaluator(tmp_path, tags=None):
    from admz.events.evaluator import DetectionEvaluator
    s = _store(tmp_path)
    ev = DetectionEvaluator(registry=_Reg(tags or {}), store=s)
    return ev, s


def test_match_category_and_source(tmp_path):
    ev, _ = _evaluator(tmp_path)
    assert ev._matches(_det(match={"category": "io"}), _rec()) is True
    assert ev._matches(_det(match={"category": "motion"}), _rec()) is False
    # source mismatch never matches
    assert ev._matches(_det(source="acs", match={"category": "io"}), _rec()) is False


def test_match_topic_substring(tmp_path):
    ev, _ = _evaluator(tmp_path)
    assert ev._matches(_det(match={"topic": "IO/Port"}), _rec()) is True
    assert ev._matches(_det(match={"topic": "PTZController"}), _rec()) is False


def test_match_condition_eq_ne_exists(tmp_path):
    ev, _ = _evaluator(tmp_path)
    assert ev._matches(_det(match={"condition": {"key": "state", "op": "eq", "value": "1"}}), _rec()) is True
    assert ev._matches(_det(match={"condition": {"key": "state", "op": "eq", "value": "0"}}), _rec()) is False
    assert ev._matches(_det(match={"condition": {"key": "state", "op": "ne", "value": "0"}}), _rec()) is True
    assert ev._matches(_det(match={"condition": {"key": "state", "op": "exists"}}), _rec()) is True
    assert ev._matches(_det(match={"condition": {"key": "nope", "op": "exists"}}), _rec()) is False


def test_scope_device_tag_all(tmp_path):
    ev, _ = _evaluator(tmp_path, tags={"d1": ["lab"]})
    # exact device
    assert ev._matches(_det(device_id="d1"), _rec()) is True
    assert ev._matches(_det(device_id="other"), _rec()) is False
    # tag (d1 is tagged "lab")
    assert ev._matches(_det(tag="lab"), _rec()) is True
    assert ev._matches(_det(tag="prod"), _rec()) is False
    # no scope = all
    assert ev._matches(_det(), _rec()) is True


def test_evaluate_fires_and_records(tmp_path, monkeypatch):
    """A matching notify rule fires execute_task_action + records the firing."""
    import admz.audit as audit
    audited = []
    monkeypatch.setattr(audit, "record_event", lambda *a, **k: audited.append((a, k)))

    ev, s = _evaluator(tmp_path)
    rid = s.create(_det(name="io-flag", action_type="notify",
                        match={"category": "io"}, action_params={"message": "port fired"}))
    _run(ev.evaluate(_rec()))
    # the fire is scheduled on the loop; evaluate's loop already ran it to completion
    # because _run drives the same loop until the coroutine + its child task settle.
    _run(asyncio.sleep(0))  # let the create_task fire drain
    got = s.get(rid)
    assert got.fire_count == 1
    assert audited and audited[0][0][1] == "detection.fired"


def test_evaluate_refuses_service_action_without_preauth(tmp_path):
    ev, s = _evaluator(tmp_path)
    rid = s.create(_det(name="rec", action_type="acs_action", match={"category": "io"},
                        action_params={"acs_op": "start_recording", "camera_id": "5"},
                        pre_authorized=False))
    _run(ev.evaluate(_rec()))
    # skipped before the optimistic _last_fired stamp → never marked fired
    assert rid not in ev._last_fired
    assert s.get(rid).fire_count == 0


def test_evaluate_allows_service_action_with_preauth(tmp_path, monkeypatch):
    """pre_authorized=True lets the ACS action fire (run_acs_op is stubbed)."""
    import admz.audit as audit
    monkeypatch.setattr(audit, "record_event", lambda *a, **k: None)
    import admz.modules.acs_pro.client as acs_client

    async def _fake_run_acs_op(catalog, executors, op_id, params):
        return {"success": True, "status_code": 200}

    monkeypatch.setattr(acs_client, "run_acs_op", _fake_run_acs_op)

    ev, s = _evaluator(tmp_path)
    rid = s.create(_det(name="rec", action_type="acs_action", match={"category": "io"},
                        action_params={"acs_op": "start_recording", "camera_id": "5"},
                        pre_authorized=True))
    _run(ev.evaluate(_rec()))
    _run(asyncio.sleep(0))
    assert s.get(rid).fire_count == 1


def test_cooldown_debounces(tmp_path, monkeypatch):
    import admz.audit as audit
    monkeypatch.setattr(audit, "record_event", lambda *a, **k: None)
    ev, s = _evaluator(tmp_path)
    rid = s.create(_det(action_type="notify", match={"category": "io"}, cooldown_seconds=3600))
    _run(ev.evaluate(_rec()))
    _run(asyncio.sleep(0))
    first = ev._last_fired.get(rid)
    assert first is not None
    # immediate second event is within cooldown → no new fire (stamp unchanged)
    _run(ev.evaluate(_rec(id="e2")))
    assert ev._last_fired.get(rid) == first


# ── the evaluator degrades, never drops (GH #255 / ADR-0058) ─────────────────
class _FlakyRuleStore:
    """A ``DetectionStore`` stand-in whose ``list()`` raises the way the real one
    does: it wraps in ``try``/*``finally``* with no ``except``, so a sqlite error
    propagates straight to the caller (``detections.py:180-192``)."""

    def __init__(self, rules, fail_times=0):
        self._rules = list(rules)
        self.version = 1
        self.fail_times = fail_times
        self.calls = 0

    def list(self, enabled_only=False):
        self.calls += 1
        if self.fail_times > 0:
            self.fail_times -= 1
            raise sqlite3.OperationalError("database is locked")
        return list(self._rules)

    def record_fire(self, det_id, ts_ms, error=""):   # pragma: no cover — _fire only
        pass


def _flaky_evaluator(rules, fail_times=0):
    from admz.events.evaluator import DetectionEvaluator
    s = _FlakyRuleStore(rules, fail_times=fail_times)
    return DetectionEvaluator(registry=_Reg({}), store=s), s


# `_last_fired[rule_id]` is stamped synchronously at evaluator.py:78, BEFORE the
# detached `create_task(self._fire(...))` — so it is the deterministic "this rule
# fired" signal, with no task draining and no second event loop involved.
def _fired(ev):
    return set(ev._last_fired)


class TestEvaluatorDegradesNeverDrops:
    """`evaluate` is `on_event` for five call paths and used to have exactly one
    raise path — the unguarded `_refresh()`. It raised *before any rule was
    evaluated*, so one unreadable rule cache dropped the whole firing, and four of
    the five paths can never re-deliver it."""

    def test_evaluate_does_not_raise_when_the_rule_store_does(self):
        ev, _ = _flaky_evaluator([_det(id="r1", match={"category": "io"})], fail_times=1)
        _run(ev.evaluate(_rec()))            # must not propagate — this IS the fix

    def test_evaluates_against_the_last_good_rules_during_an_outage(self):
        ev, s = _flaky_evaluator([_det(id="r1", match={"category": "io"})])
        _run(ev.evaluate(_rec()))
        assert _fired(ev) == {"r1"}          # loaded and fired normally
        ev._last_fired.clear()

        s.version = 2                        # a bump forces a refresh...
        s.fail_times = 1                     # ...and that refresh fails
        _run(ev.evaluate(_rec(id="e2")))
        assert _fired(ev) == {"r1"}          # still evaluated, against the stale list

    def test_a_failed_read_does_not_advance_the_version_cursor(self):
        r1 = _det(id="r1", match={"category": "io"})
        r2 = _det(id="r2", match={"category": "io"})
        ev, s = _flaky_evaluator([r1])
        _run(ev.evaluate(_rec()))
        ev._last_fired.clear()

        s._rules, s.version, s.fail_times = [r1, r2], 2, 1
        _run(ev.evaluate(_rec(id="e2")))
        assert _fired(ev) == {"r1"}          # r2 was added but the read failed
        ev._last_fired.clear()

        # Cursor untouched ⇒ the next call re-reads and picks r2 up.
        _run(ev.evaluate(_rec(id="e3")))
        assert _fired(ev) == {"r1", "r2"}
        assert s.calls == 3
        assert ev._rules_version == s.version    # structural check last (#207)

    def test_first_ever_failure_fires_nothing_but_still_does_not_raise(self):
        ev, _ = _flaky_evaluator([_det(id="r1", match={"category": "io"})], fail_times=1)
        _run(ev.evaluate(_rec()))            # no previous list to fall back on
        assert _fired(ev) == set()
        _run(ev.evaluate(_rec(id="e2")))     # ...and it recovers on the next call
        assert _fired(ev) == {"r1"}

    def test_a_rule_disabled_during_an_outage_still_fires_once(self, caplog):
        """DELIBERATE, per ADR-0058 — do not "fix" this.

        Evaluating one refresh cycle stale can fire a rule disabled moments ago.
        The alternative it replaces is dropping the event and firing *nothing*,
        including every rule still enabled. `pre_authorized` still gates every
        service-affecting action, and the staleness is bounded to one cycle —
        which the last two asserts pin.
        """
        r1 = _det(id="r1", match={"category": "io"})
        ev, s = _flaky_evaluator([r1])
        _run(ev.evaluate(_rec()))
        ev._last_fired.clear()

        s._rules, s.version, s.fail_times = [], 2, 1   # disabled, but the read fails
        _run(ev.evaluate(_rec(id="e2")))
        assert _fired(ev) == {"r1"}          # fires once more — accepted trade
        ev._last_fired.clear()

        _run(ev.evaluate(_rec(id="e3")))     # next refresh succeeds → it stops
        assert _fired(ev) == set()

    def test_warns_once_per_streak_and_once_on_recovery(self, caplog):
        ev, s = _flaky_evaluator([_det(id="r1", match={"category": "io"})])
        _run(ev.evaluate(_rec()))
        s.version, s.fail_times = 2, 3

        with caplog.at_level(logging.WARNING, logger="admz.events.evaluator"):
            for i in range(3):
                _run(ev.evaluate(_rec(id=f"e{i}")))      # three failing refreshes
            failed = [r for r in caplog.records if "refresh failed" in r.getMessage()]
            assert len(failed) == 1                      # not one per event
            _run(ev.evaluate(_rec(id="ok")))             # recovers
            recovered = [r for r in caplog.records if "refresh recovered" in r.getMessage()]
            assert len(recovered) == 1


# ── handlers ─────────────────────────────────────────────────────────────────
def test_notify_handler():
    from admz.tasks.handlers import _run_notify
    from admz.tasks.store import Task
    t = Task(id="x", action_type="notify", action_params={"message": "hi"})
    r = _run(_run_notify(t, None))
    assert r["success"] is True and "hi" in r["summary"]


def test_acs_action_handler_missing_camera():
    from admz.tasks.handlers import _run_acs_action, TaskContext
    from admz.tasks.store import Task
    t = Task(id="x", action_type="acs_action", action_params={"acs_op": "start_recording"})
    r = _run(_run_acs_action(t, TaskContext()))
    assert r["success"] is False and "camera_id" in r["summary"]


def test_acs_action_handler_calls_run_acs_op(monkeypatch):
    import admz.modules.acs_pro.client as acs_client
    seen = {}

    async def _fake(catalog, executors, op_id, params):
        seen["op_id"] = op_id
        seen["params"] = params
        return {"success": True, "status_code": 200}

    monkeypatch.setattr(acs_client, "run_acs_op", _fake)
    from admz.tasks.handlers import _run_acs_action, TaskContext
    from admz.tasks.store import Task
    t = Task(id="x", action_type="acs_action",
             action_params={"acs_op": "start_recording", "camera_id": "7"})
    r = _run(_run_acs_action(t, TaskContext()))
    assert r["success"] is True
    assert seen["op_id"] == "RecordingControlFacade:StartRecording"
    assert seen["params"] == {"cameraId": {"Id": "7"}}


# ── route: auth gating + service-affecting refusal ───────────────────────────
class _FakeSupervisor:
    async def start(self):
        return None

    async def reconcile(self):
        return None


def _ctx(tmp_path):
    store = _store(tmp_path)
    return SimpleNamespace(detection_store=store, event_supervisor=_FakeSupervisor())


def _patch_settings(monkeypatch):
    import admz.fleet_settings as fs
    monkeypatch.setattr(fs.fleet_settings, "set", lambda *a, **k: None)


def test_route_create_requires_authenticated_principal(tmp_path, monkeypatch):
    from fastapi import HTTPException
    import admz.auth as auth
    from admz.api.routes import detections as route

    async def _anon(req):
        return None  # anonymous

    monkeypatch.setattr(auth, "get_current_principal", _anon)
    _patch_settings(monkeypatch)
    req = route.CreateDetectionRequest(action_type="notify")
    with pytest.raises(HTTPException) as ei:
        _run(route.create_detection(req, SimpleNamespace(), _ctx(tmp_path)))
    assert ei.value.status_code == 403


def test_route_rejects_service_affecting_without_preauth(tmp_path, monkeypatch):
    from fastapi import HTTPException
    import admz.auth as auth
    import admz.authz as authz
    from admz.api.routes import detections as route

    async def _user(req):
        return SimpleNamespace(name="alice", is_anonymous=False)

    monkeypatch.setattr(auth, "get_current_principal", _user)
    monkeypatch.setattr(authz, "require_authenticated_principal", lambda p: None)
    _patch_settings(monkeypatch)
    req = route.CreateDetectionRequest(action_type="acs_action", pre_authorized=False,
                                       action_params={"camera_id": "5"})
    with pytest.raises(HTTPException) as ei:
        _run(route.create_detection(req, SimpleNamespace(), _ctx(tmp_path)))
    assert ei.value.status_code == 400


def test_route_create_ok_with_principal(tmp_path, monkeypatch):
    import admz.auth as auth
    import admz.authz as authz
    import admz.audit as audit
    from admz.api.routes import detections as route

    async def _user(req):
        return SimpleNamespace(name="alice", is_anonymous=False)

    monkeypatch.setattr(auth, "get_current_principal", _user)
    monkeypatch.setattr(authz, "require_authenticated_principal", lambda p: None)
    monkeypatch.setattr(audit, "record_event", lambda *a, **k: None)
    _patch_settings(monkeypatch)
    ctx = _ctx(tmp_path)
    req = route.CreateDetectionRequest(name="io-flag", action_type="notify",
                                       match={"category": "io"}, cooldown_seconds=60)
    out = _run(route.create_detection(req, SimpleNamespace(), ctx))
    assert out["success"] is True
    assert out["detection"]["name"] == "io-flag"
    assert len(ctx.detection_store.list()) == 1
