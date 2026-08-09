"""Watch-scoped event capture + transient preview (ADR-0041 amendment).

Covers the four pillars of the redesign:
  * the shared matcher (``record_matches``),
  * the WatchGate (device-set scoping + persistence gate, version-cached),
  * store retention (prune / enforce_retention),
  * the transient preview feed (capacity cap, fan-out, idle reaping).
"""

from __future__ import annotations

import asyncio
import sqlite3
import time
from types import SimpleNamespace

import pytest


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _rec(*, device_id="a", source="device", topic="tns1:Device/tnsaxis:IO/Port",
         category="io", data=None):
    return {
        "id": f"{device_id}-{topic}-{time.time_ns()}",
        "ts": "2026-07-18T00:00:00.000Z", "ts_ms": 1, "source": source,
        "type": topic, "device_id": device_id, "device_name": device_id,
        "summary": "x", "data": {"topic": topic, "category": category, "data": data or {}},
    }


# ---------------------------------------------------------------------------
# Shared matcher
# ---------------------------------------------------------------------------


class TestRecordMatches:
    def _m(self, **kw):
        from admz.events.matching import record_matches
        return record_matches(**kw)

    def test_source_must_match(self):
        assert self._m(rec=_rec(source="device"), source="device") is True
        assert self._m(rec=_rec(source="acs"), source="device") is False

    def test_device_id_scope(self):
        assert self._m(rec=_rec(device_id="a"), device_id="a") is True
        assert self._m(rec=_rec(device_id="b"), device_id="a") is False

    def test_tag_scope(self):
        assert self._m(rec=_rec(device_id="a"), tag="lab", device_tags=["lab"]) is True
        assert self._m(rec=_rec(device_id="a"), tag="lab", device_tags=["prod"]) is False

    def test_category_and_topic(self):
        r = _rec(topic="tns1:VideoSource/tnsaxis:MotionAlarm", category="motion")
        assert self._m(rec=r, match={"category": "motion"}) is True
        assert self._m(rec=r, match={"category": "io"}) is False
        assert self._m(rec=r, match={"topic": "motionalarm"}) is True   # case-insensitive substring
        assert self._m(rec=r, match={"topic": "IO/Port"}) is False

    def test_condition_eq_ne_exists(self):
        r = _rec(data={"state": "1"})
        assert self._m(rec=r, match={"condition": {"key": "state", "value": "1"}}) is True
        assert self._m(rec=r, match={"condition": {"key": "state", "value": "0"}}) is False
        assert self._m(rec=r, match={"condition": {"key": "state", "op": "ne", "value": "0"}}) is True
        assert self._m(rec=r, match={"condition": {"key": "state", "op": "exists"}}) is True
        assert self._m(rec=r, match={"condition": {"key": "missing", "op": "exists"}}) is False


# ---------------------------------------------------------------------------
# WatchGate
# ---------------------------------------------------------------------------


def _wev(**kw):
    return SimpleNamespace(source=kw.get("source", "device"), device_id=kw.get("device_id"),
                           tag=kw.get("tag"), match=kw.get("match") or {})


class _WStore:
    """``fail_times`` makes the first N ``list()`` calls raise the way a real
    ``WatchedEventStore.list`` does — it wraps in try/*finally* with no except, so
    a locked/erroring sqlite propagates straight to the caller."""

    def __init__(self, items, fail_times=0):
        self._items = items
        self.version = 1
        self.fail_times = fail_times
        self.calls = 0

    def list(self):
        self.calls += 1
        if self.fail_times > 0:
            self.fail_times -= 1
            raise sqlite3.OperationalError("database is locked")
        return self._items


class _DStore:
    def __init__(self, items, fail_times=0):
        self._items = items
        self.version = 1
        self.fail_times = fail_times
        self.calls = 0

    def list(self, enabled_only=True):
        self.calls += 1
        if self.fail_times > 0:
            self.fail_times -= 1
            raise sqlite3.OperationalError("database is locked")
        return self._items


class _Reg:
    def __init__(self, devices):
        self._d = devices

    def list_devices(self):
        return self._d

    def get_device_info(self, did):
        for d in self._d:
            if d.get("device_id") == did:
                return d
        return {}


def _gate(watched, detections, roster):
    from admz.events.subscriptions import WatchGate
    return WatchGate(registry=_Reg(roster), watched_store=_WStore(watched),
                     detection_store=_DStore(detections))


class TestWatchGate:
    def test_device_ids_explicit_and_tag_expansion(self):
        roster = [{"device_id": "a"}, {"device_id": "b", "tags": ["lab"]},
                  {"device_id": "c", "tags": ["prod"]}]
        gate = _gate([_wev(device_id="a")], [_wev(tag="lab")], roster)
        assert gate.device_ids() == ["a", "b"]     # a explicit + b via tag; c excluded

    def test_device_ids_empty_when_nothing_watched(self):
        gate = _gate([], [], [{"device_id": "a"}, {"device_id": "b"}])
        assert gate.device_ids() == []

    def test_only_extant_devices(self):
        # a watch for a device no longer in the roster is ignored
        gate = _gate([_wev(device_id="ghost")], [], [{"device_id": "a"}])
        assert gate.device_ids() == []

    def test_matches_gate(self):
        gate = _gate([_wev(device_id="a", match={"category": "io"})], [],
                     [{"device_id": "a"}, {"device_id": "b"}])
        assert gate.matches(_rec(device_id="a", category="io")) is True
        assert gate.matches(_rec(device_id="a", category="motion")) is False   # wrong category
        assert gate.matches(_rec(device_id="b", category="io")) is False       # wrong device

    def test_matches_false_when_no_specs(self):
        gate = _gate([], [], [{"device_id": "a"}])
        assert gate.matches(_rec(device_id="a")) is False

    def test_version_cache_refreshes(self):
        from admz.events.subscriptions import WatchGate
        ws = _WStore([_wev(device_id="a")])
        gate = WatchGate(registry=_Reg([{"device_id": "a"}, {"device_id": "z"}]),
                         watched_store=ws, detection_store=_DStore([]))
        assert gate.device_ids() == ["a"]
        ws._items.append(_wev(device_id="z"))
        ws.version = 2                                   # bump → gate must re-read
        assert gate.device_ids() == ["a", "z"]


class TestWatchGateRefreshFailure:
    """GH #209 — a swallowed store-read failure must not advance the version cursor.

    ``_refresh`` early-returns when its cursor equals the store version, so a
    cursor advanced past a *failed* read is permanent for the life of the process:
    the gate never re-reads, ``device_ids()`` opens no stream and ``matches()``
    drops every event, while the watched event still shows in the UI and
    ``/api/events/status`` reports ``streams: 0`` — indistinguishable from a quiet
    camera. Recovery would need an unrelated config mutation or a service restart.
    """

    def test_failed_read_is_retried_on_the_next_call(self):
        from admz.events.subscriptions import WatchGate
        ws = _WStore([_wev(device_id="a")], fail_times=1)
        gate = WatchGate(registry=_Reg([{"device_id": "a"}]),
                         watched_store=ws, detection_store=_DStore([]))

        # First call: the store raises. It is swallowed by design (see below) —
        # so no exception escapes, and the gate simply has nothing yet.
        assert gate.device_ids() == []
        assert ws.calls == 1

        # ...but the cursor must NOT have advanced, so this call re-reads and
        # recovers. Against the pre-fix code this returns [] forever.
        assert gate.device_ids() == ["a"]
        assert ws.calls == 2                     # proves the store was retried

    def test_partial_failure_advances_neither_cursor(self):
        from admz.events.subscriptions import WatchGate
        ws = _WStore([_wev(device_id="a")])                   # succeeds
        ds = _DStore([_wev(device_id="b")], fail_times=1)     # raises first time
        gate = WatchGate(registry=_Reg([{"device_id": "a"}, {"device_id": "b"}]),
                         watched_store=ws, detection_store=ds)

        # The watched half read cleanly, the detection half did not. Publish
        # NOTHING and move NEITHER cursor: a half-advanced pair is worse than a
        # fully stale one, because the next refresh would then skip the half that
        # just succeeded and the watched specs would be lost permanently instead.
        assert gate.device_ids() == []
        assert gate._w_version != ws.version     # watched cursor did not move
        assert gate._d_version != ds.version     # detection cursor did not move

        # Next call re-reads BOTH halves — the successful one was not skipped.
        assert gate.device_ids() == ["a", "b"]
        assert ws.calls == 2 and ds.calls == 2
        assert gate._w_version == ws.version and gate._d_version == ds.version

    def test_matches_still_swallows_rather_than_raising(self):
        """The swallow itself is load-bearing and must survive the fix.

        ``matches`` is the stream's ``event_filter``, and ``wsstream._handle``
        calls it UNGUARDED (``if self.event_filter is not None and not
        self.event_filter(rec)``), so a raise out of ``_refresh`` would break the
        WS read loop. The bug was never the swallow — only the cursor advance.
        """
        from admz.events.subscriptions import WatchGate
        ws = _WStore([_wev(device_id="a", match={"category": "io"})], fail_times=1)
        gate = WatchGate(registry=_Reg([{"device_id": "a"}]),
                         watched_store=ws, detection_store=_DStore([]))

        rec = _rec(device_id="a", category="io")
        assert gate.matches(rec) is False        # swallowed, not raised
        assert gate.matches(rec) is True         # retried and recovered


# ---------------------------------------------------------------------------
# Store retention
# ---------------------------------------------------------------------------


class TestRetention:
    def _store(self, tmp_path):
        from admz.events.store import EventStore
        return EventStore(str(tmp_path / "e.db"))

    def _append(self, store, n, base_ms):
        for i in range(n):
            r = _rec(device_id="a")
            r["id"] = f"e{i}-{base_ms}"
            r["ts_ms"] = base_ms + i
            store.append(r)

    def test_prune_older_than(self, tmp_path):
        store = self._store(tmp_path)
        self._append(store, 5, base_ms=1_000)          # old
        self._append(store, 5, base_ms=10_000)         # new
        assert store.prune(older_than_ms=9_000) == 5
        assert store.count() == 5

    def test_prune_keep_max(self, tmp_path):
        store = self._store(tmp_path)
        self._append(store, 10, base_ms=1_000)
        assert store.prune(keep_max=3) == 7
        assert store.count() == 3

    def test_enforce_retention_uses_config(self, tmp_path, monkeypatch):
        import admz.events.config as c
        store = self._store(tmp_path)
        self._append(store, 20, base_ms=1_000)
        monkeypatch.setattr(c, "events_retention_days", lambda: 0)     # disable day-cutoff
        monkeypatch.setattr(c, "events_max_rows", lambda: 8)
        store.enforce_retention()
        assert store.count() == 8


# ---------------------------------------------------------------------------
# Transient preview
# ---------------------------------------------------------------------------


class TestPreview:
    @pytest.fixture(autouse=True)
    def _one_loop(self):
        """See `TestPreviewReaper._one_loop`: since GH #172 a `PreviewManager`
        owns a reaper task, so opening under one loop and discarding it leaves
        the task destroyed-pending. These tests predate the reaper and acquired
        one implicitly."""
        self._mgrs = []
        self._lp = asyncio.new_event_loop()
        try:
            yield
            for m in self._mgrs:
                self._lp.run_until_complete(m.aclose())
        finally:
            self._lp.close()

    def _go(self, coro):
        return self._lp.run_until_complete(coro)

    def _mgr(self):
        from admz.events.preview import PreviewManager
        m = PreviewManager(registry=_Reg([{"device_id": "a"}, {"device_id": "b"}]))
        self._mgrs.append(m)
        return m

    def test_capacity_cap(self, monkeypatch):
        import admz.events.config as c
        from admz.events.preview import PreviewCapacityError
        monkeypatch.setattr(c, "MAX_PREVIEW_STREAMS", 2)
        mgr = self._mgr()
        self._go(mgr.open(["a", "b"]))          # 2 device-streams → at cap
        with pytest.raises(PreviewCapacityError):
            self._go(mgr.open(["c"]))           # one more would exceed

    def test_open_requires_device(self):
        mgr = self._mgr()
        with pytest.raises(ValueError):
            self._go(mgr.open([]))

    def test_session_fanout_replays_ring_then_live(self):
        from admz.events.preview import PreviewSession
        mgr = self._mgr()
        s = PreviewSession(["a"], registry=mgr.registry, manager=mgr)

        s._started_at = time.time()   # normally set by start(); no real streams here

        async def scenario():
            r1, r2, r3 = _rec(), _rec(), _rec()
            await s._push(r1)
            await s._push(r2)               # buffered in the ring (no subscribers yet)
            agen = s.subscribe()
            got = [await agen.__anext__(), await agen.__anext__()]   # ring replay
            await s._push(r3)               # live event → subscriber queue
            got.append(await agen.__anext__())
            await agen.aclose()
            return got, [r1, r2, r3]

        got, expected = self._go(scenario())
        assert [g["id"] for g in got] == [e["id"] for e in expected]

    def test_session_persists_nothing(self):
        # a preview session is constructed with store=None on its streams — assert
        # the manager never wires a store into preview.
        from admz.events.preview import PreviewSession
        mgr = self._mgr()
        s = PreviewSession(["a"], registry=mgr.registry, manager=mgr)
        assert s.stream_count == 1
        # ring buffering doesn't touch any store
        self._go(s._push(_rec()))
        assert len(s.ring_snapshot()) == 1

    def test_idle_expired(self, monkeypatch):
        import admz.events.config as c
        from admz.events.preview import PreviewSession
        monkeypatch.setattr(c, "PREVIEW_IDLE_TIMEOUT", 10.0)
        mgr = self._mgr()
        s = PreviewSession(["a"], registry=mgr.registry, manager=mgr)
        s._last_subscriber_at = time.time() - 1000      # long ago, no subscribers
        assert s.idle_expired() is True
        s._queues.append(object())                       # a live subscriber
        assert s.idle_expired() is False


class TestPreviewReaper:
    """GH #172. The module docstring, the `/api/events/preview` route docstring
    and `PREVIEW_IDLE_TIMEOUT` all promised idle teardown; `idle_expired()`
    existed and **nothing called it**. Sessions left `_sessions` only via
    `_release` ← `stop()` ← the SSE generator's `finally`, so a generator that
    is never finalised — a killed browser, a proxy dropping the connection
    without closing it — held its device WebSocket streams open forever and
    permanently consumed part of `MAX_PREVIEW_STREAMS`.
    """

    def _mgr(self):
        from admz.events.preview import PreviewManager
        return PreviewManager(registry=_Reg([{"device_id": "a"}, {"device_id": "b"}]))

    @pytest.fixture(autouse=True)
    def _one_loop(self):
        """One event loop for the whole test, and every manager closed on it.

        The module's `_run` builds a fresh loop per call and discards it. That
        is fine for plain coroutines, but `PreviewManager` now owns a task: a
        manager opened under one loop and closed under another leaves the
        reaper "cancelling" forever and destroyed pending. Cancelling a task
        from a different loop is not a thing you can do.
        """
        self._mgrs = []
        self._lp = asyncio.new_event_loop()
        try:
            yield
            for m in self._mgrs:
                self._lp.run_until_complete(m.aclose())
        finally:
            self._lp.close()

    def _go(self, coro):
        return self._lp.run_until_complete(coro)

    def _open_mgr(self):
        m = self._mgr()
        self._mgrs.append(m)
        return m

    def test_a_fresh_session_is_not_expired(self, monkeypatch):
        """The open()->start() race. `_last_subscriber_at` used to initialise to
        0.0, and `open()` registers a session *before* the route calls
        `start()`; a sweep landing in that window would judge it idle since the
        epoch and stop a session about to be used."""
        from admz.events.preview import PreviewSession
        mgr = self._open_mgr()
        s = PreviewSession(["a"], registry=mgr.registry, manager=mgr)
        assert s.idle_expired() is False
        assert s.expired() is False

    def test_reap_stops_an_abandoned_session_and_frees_the_budget(self, monkeypatch):
        import admz.events.config as c
        monkeypatch.setattr(c, "MAX_PREVIEW_STREAMS", 2)
        monkeypatch.setattr(c, "PREVIEW_IDLE_TIMEOUT", 10.0)
        mgr = self._open_mgr()
        s = self._go(mgr.open(["a", "b"]))              # at cap
        s._last_subscriber_at = time.time() - 1000  # tab died; generator never finalised
        assert self._go(mgr.reap()) == 1
        assert mgr._sessions == []
        self._go(mgr.open(["a"]))                       # the budget is usable again

    def test_a_subscribed_session_is_never_reaped(self):
        """The guard must not close a preview someone is watching."""
        mgr = self._open_mgr()
        s = self._go(mgr.open(["a"]))
        s._last_subscriber_at = time.time() - 10_000
        s._queues.append(object())                  # a live subscriber
        assert self._go(mgr.reap()) == 0
        assert mgr._sessions == [s]

    def test_max_duration_is_enforced_without_an_iterating_subscriber(self, monkeypatch):
        """`subscribe()` checks `PREVIEW_MAX_SECONDS` too — but only between
        yields, so it bounds sessions whose subscriber is still iterating, which
        were never the ones at risk. A generator parked forever is."""
        import admz.events.config as c
        monkeypatch.setattr(c, "PREVIEW_MAX_SECONDS", 60.0)
        mgr = self._open_mgr()
        s = self._go(mgr.open(["a"]))
        s._queues.append(object())                  # "subscribed", but parked
        s._started_at = time.time() - 10_000
        assert s.idle_expired() is False            # not idle — a queue is present
        assert s.duration_expired() is True
        assert self._go(mgr.reap()) == 1

    def test_open_reaps_before_measuring_the_cap(self, monkeypatch):
        """Otherwise an abandoned session refuses a legitimate preview for up to
        a whole sweep interval."""
        import admz.events.config as c
        monkeypatch.setattr(c, "MAX_PREVIEW_STREAMS", 2)
        monkeypatch.setattr(c, "PREVIEW_IDLE_TIMEOUT", 10.0)
        mgr = self._open_mgr()
        dead = self._go(mgr.open(["a", "b"]))
        dead._last_subscriber_at = time.time() - 1000
        self._go(mgr.open(["c", "d"]))                  # would raise without the reap
        assert len(mgr._sessions) == 1

    def test_a_session_that_fails_to_stop_is_still_released(self, monkeypatch):
        """Otherwise one wedged session holds part of the cap permanently — the
        exact failure being fixed, reintroduced through the error path."""
        import admz.events.config as c
        monkeypatch.setattr(c, "PREVIEW_IDLE_TIMEOUT", 10.0)
        mgr = self._open_mgr()
        s = self._go(mgr.open(["a"]))
        s._last_subscriber_at = time.time() - 1000

        async def boom():
            raise RuntimeError("stop failed")
        s.stop = boom
        assert self._go(mgr.reap()) == 1
        assert mgr._sessions == []

    def test_the_reaper_loop_starts_on_open_and_stops_when_idle(self, monkeypatch):
        """Lazy and self-terminating: no previews open, no task. It cannot live
        in the ingest reconcile loop, which no-ops unless `event_ingest_enabled`
        while preview is deliberately independent of that flag."""
        import admz.events.config as c
        from admz.events.preview import PreviewManager
        # monkeypatch, not a hand-rolled save/restore: it puts back the *prior*
        # value rather than a hard-coded default, and survives a hard failure.
        monkeypatch.setattr(c, "PREVIEW_REAP_INTERVAL", 0.01)

        async def scenario():
            mgr = PreviewManager(registry=_Reg([{"device_id": "a"}]))
            assert mgr._reaper is None                 # nothing open → no task
            try:
                s = await mgr.open(["a"])
                assert mgr._reaper is not None and not mgr._reaper.done()
                await s.stop()                         # last session gone
                await asyncio.sleep(0.05)              # loop notices and exits
                assert mgr._sessions == []
                assert mgr._reaper is None
            finally:
                await mgr.aclose()
        self._go(scenario())

    def test_a_cancelled_stop_still_deregisters(self):
        """Review finding on #372. `stop()`'s `_stopped` guard means a second
        caller returns immediately — so if the first is cancelled before
        `_release`, the session stays in `_sessions` forever holding part of the
        cap. That is this PR's own bug, arriving through cancellation.
        """
        async def scenario():
            mgr = self._mgr()
            s = await mgr.open(["a"])
            started = asyncio.Event()

            async def hang():
                started.set()
                await asyncio.sleep(3600)
            s._stop_streams = hang

            task = asyncio.create_task(s.stop())
            await started.wait()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            assert mgr._sessions == []          # released despite the cancel
            await mgr.aclose()
        self._go(scenario())

    def test_a_slow_start_cannot_resurrect_a_reaped_session(self):
        """Review finding on #372. `start()` awaits each device in turn, so a
        hung connect can outlast the threshold; the reaper then stops and
        releases the session while `start()` is suspended. Without a `_stopped`
        check it resumes and keeps opening streams onto a session no longer in
        `_sessions` — untracked, unreapable, held for the life of the process.
        """
        from admz.events import preview as pv

        async def scenario():
            mgr = self._mgr()
            session = await mgr.open(["a", "b"])
            opened, stopped = [], []

            class _Stream:
                def __init__(self, did, **kw):
                    self.device_id, self.connected = did, False

                async def start(self):
                    opened.append(self.device_id)
                    if len(opened) == 1:
                        await session.stop()      # the reaper lands mid-start

                async def stop(self):
                    stopped.append(self.device_id)

            monkey = pv.DeviceEventStream
            pv.DeviceEventStream = _Stream
            try:
                await session.start()
            finally:
                pv.DeviceEventStream = monkey
            assert opened == ["a"]               # bailed out; "b" never opened
            assert stopped == ["a"]              # and the one it had was closed
            assert session._streams == []
            assert mgr._sessions == []
            await mgr.aclose()
        self._go(scenario())


# ---------------------------------------------------------------------------
# The retired category allow-list (GH #172)
# ---------------------------------------------------------------------------


class TestNoCategoryAllowList:
    """ADR-0048 replaced the ingest category allow-list with the watch gate, but
    only the *caller* was deleted at the time: `store_categories()`, its default
    set and the `event_store_categories` fleet key survived, reading like an
    operator control that silently did nothing. GH #172 removed the remainder.

    These tests exist because the obvious reading of #172 — "an unwired
    mechanism, so wire it" — is wrong, and would be a regression. They pin the
    reason, not just the deletion.
    """

    def test_the_mechanism_is_gone(self):
        from admz.events import config as cfg
        assert not hasattr(cfg, "store_categories")
        assert not hasattr(cfg, "DEFAULT_STORE_CATEGORIES")

    def test_the_fleet_key_is_undeclared(self):
        """Declaration and code reference must come out together — `tests/
        test_setting_policy.py::test_inventory_has_no_dead_entries` fails on a
        declared key with no reference, which is what catches half a removal."""
        from admz.setting_policy import KNOWN_SETTING_KEYS
        assert "event_store_categories" not in KNOWN_SETTING_KEYS

    def test_the_gate_admits_a_watched_other_category_event(self):
        """**The regression the allow-list would reintroduce**, at the gate.

        `other` was excluded from `DEFAULT_STORE_CATEGORIES`. So had the filter
        been wired as #172 first proposed, an operator who explicitly watched an
        `other`-category topic would get nothing stored, with no error anywhere
        — the silent-drop failure the gate exists to prevent.

        This asserts only that the gate says yes; that the event then actually
        reaches the store is
        `test_events_wsstream.py::test_a_watched_other_category_event_reaches_the_store`.
        """
        gate = _gate([_wev(device_id="a", match={"topic": "unclassified"})], [],
                     [{"device_id": "a"}])
        rec = _rec(device_id="a", topic="tns1:Vendor/Unclassified",
                   category="other")
        assert gate.matches(rec) is True

    def test_an_unwatched_event_is_dropped_whatever_its_category(self):
        """Why deleting the filter loses nothing: the gate is strictly narrower.

        A category allow-list could only ever drop a subset of what the gate
        already drops — including every `motion`/`io`/`tamper` event the
        allow-list would have *admitted*.
        """
        gate = _gate([_wev(device_id="a", match={"category": "io"})], [],
                     [{"device_id": "a"}])
        for category in ("other", "motion", "tamper", "system"):
            assert gate.matches(_rec(device_id="a", category=category)) is False


class TestRetiredSettingPurge:
    """GH #172. Deleting the code does not delete the row, and every settings
    surface enumerates `list_all()` — so without this an operator who once set
    `event_store_categories` keeps seeing a live-looking control that does
    nothing, which is the trap the removal exists to close.
    """

    def _cfg(self, monkeypatch):
        from admz.events import config as cfg

        class _S:
            def __init__(self):
                self.rows = {"event_store_categories": '["motion"]',
                             "event_topic_filters": '["//."]'}
                self.raised = False

            def delete(self, key):
                if self.raised:
                    raise RuntimeError("database is locked")
                return self.rows.pop(key, None) is not None

        store = _S()
        monkeypatch.setattr(cfg, "_settings", lambda: store)
        return cfg, store

    def test_removes_the_row_and_counts_it(self, monkeypatch):
        cfg, store = self._cfg(monkeypatch)
        assert cfg.purge_retired_settings() == 1
        assert "event_store_categories" not in store.rows

    def test_leaves_live_settings_alone(self, monkeypatch):
        """It sweeps a named list, not everything with an `event_` prefix."""
        cfg, store = self._cfg(monkeypatch)
        cfg.purge_retired_settings()
        assert store.rows["event_topic_filters"] == '["//."]'

    def test_is_idempotent(self, monkeypatch):
        cfg, store = self._cfg(monkeypatch)
        cfg.purge_retired_settings()
        assert cfg.purge_retired_settings() == 0

    def test_never_raises_when_the_store_fails(self, monkeypatch):
        """It runs in the API lifespan; a cleanup must not stop startup."""
        cfg, store = self._cfg(monkeypatch)
        store.raised = True
        assert cfg.purge_retired_settings() == 0
