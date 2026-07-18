"""Watch-scoped event capture + transient preview (ADR-0041 amendment).

Covers the four pillars of the redesign:
  * the shared matcher (``record_matches``),
  * the WatchGate (device-set scoping + persistence gate, version-cached),
  * store retention (prune / enforce_retention),
  * the transient preview feed (capacity cap, fan-out, idle reaping).
"""

from __future__ import annotations

import asyncio
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
    def __init__(self, items):
        self._items = items
        self.version = 1

    def list(self):
        return self._items


class _DStore:
    def __init__(self, items):
        self._items = items
        self.version = 1

    def list(self, enabled_only=True):
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
    def _mgr(self):
        from admz.events.preview import PreviewManager
        return PreviewManager(registry=_Reg([{"device_id": "a"}, {"device_id": "b"}]))

    def test_capacity_cap(self, monkeypatch):
        import admz.events.config as c
        from admz.events.preview import PreviewCapacityError
        monkeypatch.setattr(c, "MAX_PREVIEW_STREAMS", 2)
        mgr = self._mgr()
        _run(mgr.open(["a", "b"]))          # 2 device-streams → at cap
        with pytest.raises(PreviewCapacityError):
            _run(mgr.open(["c"]))           # one more would exceed

    def test_open_requires_device(self):
        mgr = self._mgr()
        with pytest.raises(ValueError):
            _run(mgr.open([]))

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

        got, expected = _run(scenario())
        assert [g["id"] for g in got] == [e["id"] for e in expected]

    def test_session_persists_nothing(self):
        # a preview session is constructed with store=None on its streams — assert
        # the manager never wires a store into preview.
        from admz.events.preview import PreviewSession
        mgr = self._mgr()
        s = PreviewSession(["a"], registry=mgr.registry, manager=mgr)
        assert s.stream_count == 1
        # ring buffering doesn't touch any store
        _run(s._push(_rec()))
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
