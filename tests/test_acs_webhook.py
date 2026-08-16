"""ACS rule-firing webhook — normalize, token auth, route ingest (ADR-0041)."""

from __future__ import annotations

import asyncio
import base64
from types import SimpleNamespace

import pytest


def _run(coro):
    return asyncio.run(coro)


def _patch_fs(monkeypatch, initial=None):
    import admz.fleet_settings as fs
    store = {"acs_webhook_token": initial} if initial else {}
    monkeypatch.setattr(fs.fleet_settings, "get", lambda k: store.get(k))
    monkeypatch.setattr(fs.fleet_settings, "set", lambda k, v: store.__setitem__(k, v))
    return store


class _Req:
    def __init__(self, headers=None, query=None, body=None, raise_json=False):
        self.headers = headers or {}
        self.query_params = query or {}
        self._body = body
        self._raise_json = raise_json

    async def json(self):
        if self._raise_json:
            raise ValueError("not json")
        return self._body

    async def form(self):
        return {}


# ── normalize ────────────────────────────────────────────────────────────────
def test_normalize_extracts_fields():
    from admz.modules.acs_pro.webhook import normalize_webhook
    r = normalize_webhook({"rule": "Front door", "camera": "Cam 1", "message": "hi"})
    assert r["source"] == "acs" and r["type"] == "ACS/ActionRule"
    assert r["data"]["category"] == "action_rule"
    assert r["data"]["rule_name"] == "Front door"
    assert r["data"]["data"]["rule"] == "Front door"     # so a detection condition can match
    assert r["device_name"] == "Cam 1"
    assert "Front door" in r["summary"]
    assert r["ts_ms"] > 0 and r["id"]


def test_normalize_key_spellings_unique_ids_and_default():
    from admz.modules.acs_pro.webhook import normalize_webhook
    a = normalize_webhook({"ruleName": "X"})
    b = normalize_webhook({"name": "X"})
    assert a["data"]["rule_name"] == "X" and b["data"]["rule_name"] == "X"
    assert a["id"] != b["id"]                              # each firing is distinct (no dedup)
    c = normalize_webhook({})
    assert c["data"]["rule_name"] == "ACS action rule"     # graceful default


# ── token ────────────────────────────────────────────────────────────────────
def test_get_token_generates_and_is_stable(monkeypatch):
    from admz.modules.acs_pro.webhook import get_token
    _patch_fs(monkeypatch)
    t = get_token()
    assert t and len(t) > 10
    assert get_token() == t


def test_token_ok_accepts_every_channel(monkeypatch):
    from admz.modules.acs_pro.webhook import token_ok
    _patch_fs(monkeypatch, "SECRET")
    assert token_ok(_Req(headers={"authorization": "Bearer SECRET"}))
    assert token_ok(_Req(headers={"x-acs-token": "SECRET"}))
    assert token_ok(_Req(query={"token": "SECRET"}))
    basic = "Basic " + base64.b64encode(b"acs:SECRET").decode()
    assert token_ok(_Req(headers={"authorization": basic}))
    assert token_ok(_Req(), body={"token": "SECRET"})
    assert not token_ok(_Req(headers={"x-acs-token": "WRONG"}))
    assert not token_ok(_Req())


def test_token_ok_fails_closed_when_unset(monkeypatch):
    from admz.modules.acs_pro.webhook import token_ok
    _patch_fs(monkeypatch)   # no token configured
    assert not token_ok(_Req(headers={"x-acs-token": "anything"}))


# ── route ────────────────────────────────────────────────────────────────────
class _Store:
    def __init__(self):
        self.rows = []

    def append(self, rec):
        self.rows.append(rec)
        return True


def _fake_ctx_and_fires():
    fired = []

    async def evaluate(rec):
        fired.append(rec)

    ctx = SimpleNamespace(event_store=_Store(),
                          detection_evaluator=SimpleNamespace(evaluate=evaluate))
    return ctx, fired


def test_route_rejects_without_token(monkeypatch):
    import admz.api.context as apictx
    from admz.modules.acs_pro import routes
    _patch_fs(monkeypatch, "SECRET")
    ctx, _ = _fake_ctx_and_fires()
    monkeypatch.setattr(apictx, "get_context", lambda: ctx)
    req = _Req(body={"rule": "X"})            # no token anywhere
    resp = _run(routes.acs_rule_fired(req))
    assert getattr(resp, "status_code", None) == 401
    assert ctx.event_store.rows == []         # nothing ingested


def test_route_accepts_and_feeds_store_and_evaluator(monkeypatch):
    import admz.api.context as apictx
    import admz.audit as audit
    from admz.modules.acs_pro import routes
    _patch_fs(monkeypatch, "SECRET")
    monkeypatch.setattr(audit, "record_event", lambda *a, **k: None)
    ctx, fired = _fake_ctx_and_fires()
    monkeypatch.setattr(apictx, "get_context", lambda: ctx)
    req = _Req(headers={"x-acs-token": "SECRET"}, body={"rule": "Lobby door", "camera": "Cam 2"})
    out = _run(routes.acs_rule_fired(req))
    assert out["success"] is True and out["rule"] == "Lobby door"
    assert len(ctx.event_store.rows) == 1
    assert ctx.event_store.rows[0]["data"]["rule_name"] == "Lobby door"
    assert len(fired) == 1 and fired[0]["source"] == "acs"   # detection evaluator ran
