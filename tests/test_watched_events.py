"""Watched events — store CRUD + auth-gated, side-effect-free REST (ADR-0041)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest


def _run(coro):
    return asyncio.run(coro)


def _store(tmp_path):
    from admz.events.watched import WatchedEventStore
    return WatchedEventStore(str(tmp_path / "w.db"))


def _we(**kw):
    from admz.events.watched import WatchedEvent
    base = dict(id="", name="rule", source="device")
    base.update(kw)
    return WatchedEvent(**base)


# ── store ────────────────────────────────────────────────────────────────────
def test_store_crud_and_version_bump(tmp_path):
    s = _store(tmp_path)
    v0 = s.version
    wid = s.create(_we(name="lobby motion", device_id="d1",
                       match={"category": "motion", "condition": {"key": "state", "op": "eq", "value": "1"}},
                       notes="watch this"))
    assert wid and s.version == v0 + 1
    got = s.get(wid)
    assert got.name == "lobby motion" and got.device_id == "d1" and got.notes == "watch this"
    assert got.match == {"category": "motion", "condition": {"key": "state", "op": "eq", "value": "1"}}
    # update bumps version + round-trips JSON
    assert s.update(wid, name="renamed", match={"category": "io"}, notes="n2") is True
    assert s.version == v0 + 2
    g2 = s.get(wid)
    assert g2.name == "renamed" and g2.match == {"category": "io"} and g2.notes == "n2"
    assert len(s.list()) == 1
    assert s.delete(wid) is True and s.version == v0 + 3
    assert s.get(wid) is None


def test_store_update_rejects_unknown_fields(tmp_path):
    s = _store(tmp_path)
    wid = s.create(_we())
    v = s.version
    assert s.update(wid, bogus="x") is False     # nothing allowed → no-op
    assert s.version == v
    # mixed: only allowed fields applied
    assert s.update(wid, name="ok", bogus="x") is True
    assert s.get(wid).name == "ok"


def test_store_list_newest_first(tmp_path):
    s = _store(tmp_path)
    a = s.create(_we(name="a", created_at=100.0))
    b = s.create(_we(name="b", created_at=200.0))
    names = [w.name for w in s.list()]
    assert names == ["b", "a"]


# ── route (auth + no ingest side-effect) ─────────────────────────────────────
def _ctx(tmp_path):
    return SimpleNamespace(watched_event_store=_store(tmp_path))


async def _anon_principal(req):
    """Resolve to the synthetic anonymous principal that
    ``ADMZ_AUTH_BACKEND=none`` — the documented default — hands every
    request. This is the exact condition ``require_authenticated_principal``
    exists to refuse, so tests using it run the REAL gate (never the
    ``lambda p: None`` stand-in the happy-path tests below install).
    """
    from admz.auth import Principal
    return Principal(name="anonymous", display_name="anonymous",
                     source="none", is_anonymous=True)


def test_route_create_requires_authenticated_principal(tmp_path, monkeypatch):
    from fastapi import HTTPException
    import admz.auth as auth
    from admz.api.routes import watched_events as route

    async def _anon(req):
        return None
    monkeypatch.setattr(auth, "get_current_principal", _anon)
    req = route.CreateWatchedEventRequest(name="x", match={"category": "io"})
    with pytest.raises(HTTPException) as ei:
        _run(route.create_watched_event(req, SimpleNamespace(), _ctx(tmp_path)))
    assert ei.value.status_code == 403


def test_route_update_requires_authenticated_principal(tmp_path, monkeypatch):
    """PATCH refuses an anonymous caller with the real gate in place (#211).

    ``test_route_patch_delete_404_on_unknown`` neutralizes
    ``require_authenticated_principal`` so it can reach the store's 404 path;
    this is its paired guard. Asserting 403 on an id that does NOT exist is
    what makes it load-bearing: without the gate the same call returns 404,
    so the assertion can only pass if line 65 ran first.
    """
    from fastapi import HTTPException
    import admz.auth as auth
    from admz.api.routes import watched_events as route

    monkeypatch.setattr(auth, "get_current_principal", _anon_principal)

    class _Req:
        async def json(self):
            return {"name": "x"}

    with pytest.raises(HTTPException) as ei:
        _run(route.update_watched_event("nope", _Req(), _ctx(tmp_path)))
    assert ei.value.status_code == 403


def test_route_delete_requires_authenticated_principal(tmp_path, monkeypatch):
    """DELETE refuses an anonymous caller with the real gate in place (#211).

    Same shape as the PATCH guard above, and the id is deliberately real:
    without the gate the delete would succeed (200) and destroy the row, so
    the surviving row is second evidence that line 83 ran.
    """
    from fastapi import HTTPException
    import admz.auth as auth
    from admz.api.routes import watched_events as route

    ctx = _ctx(tmp_path)
    wid = ctx.watched_event_store.create(_we(name="keep me"))
    monkeypatch.setattr(auth, "get_current_principal", _anon_principal)

    with pytest.raises(HTTPException) as ei:
        _run(route.delete_watched_event(wid, SimpleNamespace(), ctx))
    assert ei.value.status_code == 403
    assert ctx.watched_event_store.get(wid) is not None  # not deleted


def test_route_create_does_not_enable_ingest(tmp_path, monkeypatch):
    """Bookmarking is cheap: POST must NOT flip event_ingest_enabled (unlike detections)."""
    import admz.auth as auth
    import admz.authz as authz
    import admz.audit as audit
    import admz.fleet_settings as fs
    from admz.api.routes import watched_events as route

    async def _user(req):
        return SimpleNamespace(name="alice", is_anonymous=False)
    monkeypatch.setattr(auth, "get_current_principal", _user)
    monkeypatch.setattr(authz, "require_authenticated_principal", lambda p: None)
    monkeypatch.setattr(audit, "record_event", lambda *a, **k: None)

    set_calls = []
    monkeypatch.setattr(fs.fleet_settings, "set", lambda *a, **k: set_calls.append(a))

    ctx = _ctx(tmp_path)
    req = route.CreateWatchedEventRequest(name="io watch", source="device",
                                          device_id="d1", match={"category": "io"})
    out = _run(route.create_watched_event(req, SimpleNamespace(), ctx))
    assert out["success"] is True
    assert out["watched"]["name"] == "io watch" and out["watched"]["match"] == {"category": "io"}
    assert len(ctx.watched_event_store.list()) == 1
    # the cheap-bookmark invariant: nothing touched fleet settings (no ingest flip)
    assert set_calls == []


def test_route_get_lists_created(tmp_path, monkeypatch):
    import admz.auth as auth
    import admz.authz as authz
    import admz.audit as audit
    from admz.api.routes import watched_events as route

    async def _user(req):
        return SimpleNamespace(name="alice", is_anonymous=False)
    monkeypatch.setattr(auth, "get_current_principal", _user)
    monkeypatch.setattr(authz, "require_authenticated_principal", lambda p: None)
    monkeypatch.setattr(audit, "record_event", lambda *a, **k: None)
    ctx = _ctx(tmp_path)
    _run(route.create_watched_event(
        route.CreateWatchedEventRequest(name="w1", match={"category": "motion"}),
        SimpleNamespace(), ctx))
    out = _run(route.list_watched_events(ctx))
    assert out["success"] and len(out["watched"]) == 1 and out["watched"][0]["name"] == "w1"


def test_route_patch_delete_404_on_unknown(tmp_path, monkeypatch):
    from fastapi import HTTPException
    import admz.auth as auth
    import admz.authz as authz
    import admz.audit as audit
    from admz.api.routes import watched_events as route

    async def _user(req):
        return SimpleNamespace(name="alice", is_anonymous=False)
    monkeypatch.setattr(auth, "get_current_principal", _user)
    monkeypatch.setattr(authz, "require_authenticated_principal", lambda p: None)
    monkeypatch.setattr(audit, "record_event", lambda *a, **k: None)
    ctx = _ctx(tmp_path)

    class _Req:
        async def json(self):
            return {"name": "x"}

    with pytest.raises(HTTPException) as ei:
        _run(route.update_watched_event("nope", _Req(), ctx))
    assert ei.value.status_code == 404
    with pytest.raises(HTTPException) as ei2:
        _run(route.delete_watched_event("nope", SimpleNamespace(), ctx))
    assert ei2.value.status_code == 404
