"""Per-device WS event consumer (ADR-0041 layer 2)."""

from __future__ import annotations

import asyncio
import json

import websockets


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_resolve_endpoint():
    from admz.events.wsstream import _resolve_endpoint
    ep = _resolve_endpoint({"auth": {"scheme": "https", "https": "digest"}}, {"host": "1.2.3.4"})
    assert ep["ws_scheme"] == "wss" and ep["http_base"] == "https://1.2.3.4" and ep["method"] == "digest"
    ep2 = _resolve_endpoint({"auth": {"scheme": "http"}}, {"host": "h"})
    assert ep2["ws_scheme"] == "ws" and ep2["http_base"] == "http://h"


class _FakeWS:
    """Async-iterable fake WebSocket: records sends, yields canned frames."""

    def __init__(self, frames):
        self._frames = list(frames)
        self.sent = []

    async def send(self, m):
        self.sent.append(json.loads(m))

    def __aiter__(self):
        self._it = iter(self._frames)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class _FakeConnect:
    def __init__(self, ws):
        self._ws = ws

    async def __aenter__(self):
        return self._ws

    async def __aexit__(self, *a):
        return False


class _Store:
    def __init__(self):
        self.rows = []

    def append(self, rec):
        self.rows.append(rec)
        return True


class _Reg:
    def get_device_info(self, did):
        return {"host": "10.0.0.9", "nickname": "Lobby", "auth": {"scheme": "https", "https": "digest"}}

    def get_credentials(self, did):
        return {"username": "root", "password": "secret", "host": "10.0.0.9"}


IO_NOTIFY = {"method": "events:notify", "params": {"notification": {
    "topic": "tns1:Device/tnsaxis:IO/Port",
    "message": {"source": {"port": "1"}, "key": {}, "data": {"state": "1"}},
    "timestamp": 1781150388807}}}
OTHER_NOTIFY = {"method": "events:notify", "params": {"notification": {
    "topic": "tns1:VideoSource/tnsaxis:LiveStreamAccessed",
    "message": {"source": {}, "key": {}, "data": {"accessed": "1"}},
    "timestamp": 1781150388900}}}
CONFIGURE_ACK = {"apiVersion": "1.0", "method": "events:configure", "data": {}}


def test_mint_token_falls_back_digest_to_basic(monkeypatch):
    """Axis speakers answer Basic where cameras use Digest — the token mint
    must fall back rather than give up (the C-series 401 root cause)."""
    import httpx
    from admz.events import wsstream

    class _Resp:
        def __init__(self, status, text=""):
            self.status_code = status
            self.text = text
            self.headers = {}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, auth=None):
            return _Resp(200, "TOK123") if isinstance(auth, httpx.BasicAuth) else _Resp(401)

    monkeypatch.setattr(wsstream.httpx, "AsyncClient", _Client)
    token = _run(wsstream.mint_session_token("https://h", "u", "p", "digest"))
    assert token == "TOK123"


def _drive(monkeypatch, *, store, on_event=None, event_filter=None):
    """Run one _connect_and_ingest pass over two canned events (IO + 'other')."""
    from admz.events import wsstream

    fake_ws = _FakeWS([json.dumps(CONFIGURE_ACK), json.dumps(IO_NOTIFY), json.dumps(OTHER_NOTIFY)])
    monkeypatch.setattr(websockets, "connect", lambda *a, **k: _FakeConnect(fake_ws))

    async def fake_mint(http_base, u, p, method):
        return "tok123"
    monkeypatch.setattr(wsstream, "mint_session_token", fake_mint)

    stream = wsstream.DeviceEventStream("d1", registry=_Reg(), store=store, on_event=on_event,
                                        topic_filters=["//."], event_filter=event_filter)
    stream._running = True
    _run(stream._connect_and_ingest())
    return fake_ws


def test_consumer_subscribes_and_stores_all_without_filter(monkeypatch):
    """No event_filter (e.g. legacy/ungated) → every recognized event is stored.
    The category allow-list that used to drop 'other' events is gone; scoping is
    now the WatchGate's job, injected as event_filter."""
    store = _Store()
    fired = []

    async def on_event(rec):
        fired.append(rec)

    ws = _drive(monkeypatch, store=store, on_event=on_event)
    assert ws.sent and ws.sent[0]["method"] == "events:configure"
    assert ws.sent[0]["params"]["eventFilterList"] == [{"topicFilter": "//."}]
    assert len(store.rows) == 2                      # both IO and 'other' kept
    assert store.rows[0]["device_name"] == "Lobby"
    assert len(fired) == 2


def test_event_filter_gates_persistence(monkeypatch):
    """The ingest gate: only events the filter accepts are stored/fired — this is
    what stops the firehose (a non-matching event is dropped outright)."""
    store = _Store()
    fired = []

    async def on_event(rec):
        fired.append(rec)

    # keep only category 'io' (stands in for the WatchGate)
    _drive(monkeypatch, store=store, on_event=on_event,
           event_filter=lambda rec: (rec.get("data") or {}).get("category") == "io")
    assert len(store.rows) == 1
    assert store.rows[0]["type"] == "tns1:Device/tnsaxis:IO/Port"
    assert len(fired) == 1 and fired[0]["data"]["category"] == "io"


def test_preview_mode_persists_nothing(monkeypatch):
    """store=None (preview) → nothing is written, but on_event still fans every
    event out (the live picker feed)."""
    fired = []

    async def on_event(rec):
        fired.append(rec)

    _drive(monkeypatch, store=None, on_event=on_event, event_filter=None)
    assert len(fired) == 2   # both events fanned to the SSE broadcaster
    # (no store → nothing persisted; store=None must not raise)
