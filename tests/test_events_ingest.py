"""Event-ingest supervisor reconcile — WATCH-SCOPED (ADR-0041 amendment).

Steady-state ingest now opens a stream only for devices the WatchGate returns
(devices a watched event / enabled detection targets), never the whole roster,
and hands each stream the gate's ``matches`` as the persistence filter.
"""

from __future__ import annotations

import asyncio


def _run(coro):
    return asyncio.run(coro)


class _FakeStream:
    def __init__(self, device_id, **kw):
        self.device_id = device_id
        self.kw = kw                      # capture event_filter/store/on_event
        self.connected = False
        self.started = self.stopped = False
        self.last_event_at = 0.0
        self.last_error = ""

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True


class _FakeReg:
    def __init__(self, devices):
        self._devices = devices

    def list_devices(self):
        return self._devices

    def get_device_info(self, did):
        for d in self._devices:
            if (d.get("device_id") or d.get("id")) == did:
                return d
        return {}


class _FakeGate:
    """Stands in for WatchGate: configurable device set + match predicate."""

    def __init__(self, device_ids, *, registry=None, matches=None):
        self._ids = list(device_ids)
        self.registry = registry
        self._matches = matches or (lambda rec: True)

    def device_ids(self):
        return list(self._ids)

    def matches(self, rec):
        return self._matches(rec)

    def _device_tags(self, did):
        info = self.registry.get_device_info(did) if self.registry else {}
        return info.get("tags") or []


class _FakeStore:
    def __init__(self):
        self.retention_calls = 0

    def enforce_retention(self):
        self.retention_calls += 1
        return 0


def _sup(monkeypatch, *, watched_ids, roster=None, enabled=True, tag=None, matches=None):
    import admz.events.config as c
    import admz.events.ingest as ing
    monkeypatch.setattr(ing, "DeviceEventStream", _FakeStream)
    monkeypatch.setattr(c, "event_ingest_enabled", lambda: enabled)
    monkeypatch.setattr(c, "tag_filter", lambda: tag)
    reg = _FakeReg(roster if roster is not None else [{"device_id": d} for d in watched_ids])
    gate = _FakeGate(watched_ids, registry=reg, matches=matches)
    return ing.EventIngestSupervisor(registry=reg, store=_FakeStore(), gate=gate)


def test_reconcile_opens_only_watched_devices(monkeypatch):
    # roster has a,b,c but only a,c are watched → b never gets a stream.
    sup = _sup(monkeypatch,
               watched_ids=["a", "c"],
               roster=[{"device_id": "a"}, {"device_id": "b"}, {"device_id": "c"}])
    r = _run(sup.reconcile())
    assert r == {"added": 2, "removed": 0, "active": 2}
    assert set(sup._streams) == {"a", "c"}
    assert "b" not in sup._streams


def test_no_watched_events_means_no_streams(monkeypatch):
    """Enabling ingest with zero watched events opens ZERO streams — the whole
    point of the redesign (no firehose)."""
    sup = _sup(monkeypatch, watched_ids=[],
               roster=[{"device_id": "a"}, {"device_id": "b"}])
    r = _run(sup.reconcile())
    assert r == {"added": 0, "removed": 0, "active": 0}
    assert sup._streams == {}


def test_reconcile_drops_when_unwatched(monkeypatch):
    sup = _sup(monkeypatch, watched_ids=["a", "b"])
    _run(sup.reconcile())
    assert set(sup._streams) == {"a", "b"}
    dropped = sup._streams["b"]
    sup.gate._ids = ["a"]                 # b's watch removed
    r = _run(sup.reconcile())
    assert r["removed"] == 1 and set(sup._streams) == {"a"}
    assert dropped.stopped is True


def test_stream_receives_the_match_gate(monkeypatch):
    sup = _sup(monkeypatch, watched_ids=["a"])
    _run(sup.reconcile())
    stream = sup._streams["a"]
    assert stream.kw.get("event_filter") == sup.gate.matches   # gated persistence
    assert stream.kw.get("store") is sup.store


def test_retention_runs_each_reconcile(monkeypatch):
    sup = _sup(monkeypatch, watched_ids=["a"])
    _run(sup.reconcile())
    _run(sup.reconcile())
    assert sup.store.retention_calls == 2


def test_disabled_means_no_streams(monkeypatch):
    sup = _sup(monkeypatch, watched_ids=["a"], enabled=False)
    r = _run(sup.reconcile())
    assert r == {"added": 0, "removed": 0, "active": 0}
    assert sup._streams == {}


def test_runtime_disable_tears_down(monkeypatch):
    import admz.events.config as c
    sup = _sup(monkeypatch, watched_ids=["a"], enabled=True)
    _run(sup.reconcile())
    assert set(sup._streams) == {"a"}
    monkeypatch.setattr(c, "event_ingest_enabled", lambda: False)
    r = _run(sup.reconcile())
    assert r["active"] == 0 and sup._streams == {}


def test_tag_narrows_watched_set(monkeypatch):
    # both a,b are watched, but the global ingest tag narrows to 'lab'.
    roster = [{"device_id": "a", "tags": ["lab"]}, {"device_id": "b", "tags": ["prod"]}]
    sup = _sup(monkeypatch, watched_ids=["a", "b"], roster=roster, tag="lab")
    _run(sup.reconcile())
    assert set(sup._streams) == {"a"}


def test_status_shape(monkeypatch):
    sup = _sup(monkeypatch, watched_ids=["a"])
    _run(sup.reconcile())
    st = sup.status()
    assert st["streams"] == 1 and st["devices"][0]["device_id"] == "a"
