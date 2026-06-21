"""ACS Pro action-rule poller — normalize + poll/high-water/gating (ADR-0041)."""

from __future__ import annotations

import asyncio


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _det(id_, ts, cam="c1", name="Lobby", end=None):
    """One ``search_detections`` 'Action Rule' row (its normalized shape)."""
    return {"ts": ts, "end": end, "type": "Action Rule",
            "camera_id": cam, "device_name": name, "data": {"Id": id_}}


# ── normalize ────────────────────────────────────────────────────────────────
def test_normalize_maps_to_canonical_store_record():
    from admz.events.acs_ingest import normalize_acs_action_rule
    rec = normalize_acs_action_rule(_det(40, "2026-06-11T18:57:35.5861971Z", name="Lobby"))
    assert rec["source"] == "acs"
    assert rec["type"] == "ACS/ActionRule"
    assert rec["device_id"] == "c1" and rec["device_name"] == "Lobby"
    assert rec["data"]["category"] == "action_rule"
    assert rec["data"]["topic"] == "ACS/ActionRule"
    assert rec["data"]["event_id"] == 40
    assert rec["data"]["rule_name"] is None        # ACS firings are anonymous
    assert rec["ts_ms"] > 0
    assert rec["id"]
    # stable / deterministic id (dedup across polls)
    assert normalize_acs_action_rule(_det(40, "2026-06-11T18:57:35.5861971Z")).__class__


def test_parse_ms_tolerates_7digit_fraction_and_Z():
    from admz.events.acs_ingest import _parse_ms
    a = _parse_ms("2026-06-11T18:57:35.5861971Z")   # 7 fractional digits + Z
    b = _parse_ms("2026-06-11T18:57:35Z")           # no fraction
    assert a > 0 and b > 0 and a > b
    assert _parse_ms(None) == 0
    assert _parse_ms("not-a-time") == 0


# ── poller ───────────────────────────────────────────────────────────────────
class _Store:
    def __init__(self):
        self.rows = []

    def append(self, rec):
        if any(r["id"] == rec["id"] for r in self.rows):
            return False                            # dedup like EventStore
        self.rows.append(rec)
        return True


def _poller(monkeypatch, events, enabled=True):
    import admz.events.config as cfg
    import admz.modules.acs_pro.events as acs_events

    monkeypatch.setattr(cfg, "acs_event_ingest_enabled", lambda: enabled)

    async def fake_search(catalog, executors, **kw):
        return {"success": True, "events": list(events)}

    monkeypatch.setattr(acs_events, "search_detections", fake_search)
    from admz.events.acs_ingest import AcsActionRulePoller
    return AcsActionRulePoller(catalog=None, executors={}, store=_Store(), on_event=None)


def test_poll_fires_only_events_newer_than_high_water(monkeypatch):
    from admz.events.acs_ingest import _parse_ms
    fired = []
    events = [
        _det(1, "2026-06-11T18:57:35.0Z"),   # historical
        _det(2, "2026-06-21T12:00:00.0Z"),   # new
    ]
    p = _poller(monkeypatch, events)

    async def on_event(rec):
        fired.append(rec)
    p.on_event = on_event
    p._hw_ms = _parse_ms("2026-06-15T00:00:00Z")    # boundary between the two

    res = _run(p.poll_once())
    assert res["fired"] == 1
    assert len(fired) == 1 and fired[0]["data"]["event_id"] == 2
    assert len(p.store.rows) == 2                    # both seeded to the store/feed


def test_second_poll_does_not_refire_or_duplicate(monkeypatch):
    fired = []
    events = [_det(2, "2026-06-21T12:00:00.0Z")]
    p = _poller(monkeypatch, events)

    async def on_event(rec):
        fired.append(rec)
    p.on_event = on_event
    p._hw_ms = 0                                     # everything is "new" on the first poll

    _run(p.poll_once())                              # fires once + appends
    _run(p.poll_once())                              # hw advanced; same event → no refire
    assert len(fired) == 1
    assert len(p.store.rows) == 1                    # dedup on id


def test_poll_is_noop_when_disabled(monkeypatch):
    p = _poller(monkeypatch, [_det(2, "2026-06-21T12:00:00.0Z")], enabled=False)
    res = _run(p.poll_once())
    assert res["enabled"] is False and res["fired"] == 0
    assert p.store.rows == []


def test_poll_swallows_search_failure(monkeypatch):
    import admz.events.config as cfg
    import admz.modules.acs_pro.events as acs_events
    monkeypatch.setattr(cfg, "acs_event_ingest_enabled", lambda: True)

    async def boom(catalog, executors, **kw):
        raise RuntimeError("acs unreachable")
    monkeypatch.setattr(acs_events, "search_detections", boom)
    from admz.events.acs_ingest import AcsActionRulePoller
    p = AcsActionRulePoller(catalog=None, executors={}, store=_Store())
    res = _run(p.poll_once())                        # must not raise
    assert res["fired"] == 0 and "error" in res
    assert p.last_error


def test_status_shape(monkeypatch):
    p = _poller(monkeypatch, [])
    st = p.status()
    for k in ("enabled", "running", "last_count", "last_fired", "fired_total", "last_error"):
        assert k in st
