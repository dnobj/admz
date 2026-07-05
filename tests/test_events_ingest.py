"""Event-ingest supervisor reconcile + gating (ADR-0041 layer 2)."""

from __future__ import annotations

import asyncio


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeStream:
    def __init__(self, device_id, **kw):
        self.device_id = device_id
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


def _sup(monkeypatch, devices, enabled=True, tag=None):
    import admz.events.ingest as ing
    import admz.events.config as c
    monkeypatch.setattr(ing, "DeviceEventStream", _FakeStream)
    monkeypatch.setattr(c, "event_ingest_enabled", lambda: enabled)
    monkeypatch.setattr(c, "tag_filter", lambda: tag)
    return ing.EventIngestSupervisor(registry=_FakeReg(devices), store=object())


def test_reconcile_adds_and_drops(monkeypatch):
    reg_devices = [{"device_id": "a"}, {"device_id": "b"}]
    sup = _sup(monkeypatch, reg_devices)
    r = _run(sup.reconcile())
    assert r == {"added": 2, "removed": 0, "active": 2}
    assert set(sup._streams) == {"a", "b"}

    # device b removed from the roster → its stream is dropped + stopped
    sup.registry._devices = [{"device_id": "a"}]
    dropped = sup._streams["b"]
    r = _run(sup.reconcile())
    assert r["removed"] == 1 and set(sup._streams) == {"a"}
    assert dropped.stopped is True


def test_disabled_means_no_streams(monkeypatch):
    sup = _sup(monkeypatch, [{"device_id": "a"}], enabled=False)
    r = _run(sup.reconcile())
    assert r == {"added": 0, "removed": 0, "active": 0}
    assert sup._streams == {}


def test_runtime_disable_tears_down(monkeypatch):
    import admz.events.config as c
    sup = _sup(monkeypatch, [{"device_id": "a"}], enabled=True)
    _run(sup.reconcile())
    assert set(sup._streams) == {"a"}
    monkeypatch.setattr(c, "event_ingest_enabled", lambda: False)
    r = _run(sup.reconcile())
    assert r["active"] == 0 and sup._streams == {}


def test_tag_scoping(monkeypatch):
    devices = [{"device_id": "a", "tags": ["lab"]}, {"device_id": "b", "tags": ["prod"]}]
    sup = _sup(monkeypatch, devices, tag="lab")
    _run(sup.reconcile())
    assert set(sup._streams) == {"a"}


def test_status_shape(monkeypatch):
    sup = _sup(monkeypatch, [{"device_id": "a"}])
    _run(sup.reconcile())
    st = sup.status()
    assert st["streams"] == 1 and "devices" in st and st["devices"][0]["device_id"] == "a"
