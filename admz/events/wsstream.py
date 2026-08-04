"""Per-device VAPIX WebSocket event-stream consumer (ADR-0041 layer 2).

One ``DeviceEventStream`` per subscribed device holds a persistent connection to
``ws(s)://<device>/vapix/ws-data-stream?sources=events``: it mints a short-lived
session token (digest GET to ``wssession.cgi``), opens the WebSocket, sends a
JSON-RPC ``events:configure`` subscribe message with the configured topic
filters, then drains ``events:notify`` messages — normalizing each and appending
it to the :class:`EventStore`. Reconnects with exponential backoff on drop.

The device password is fetched from the registry at connect time and **never
logged** (consistent with the executor's posture).
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

import httpx

from admz.events import config as cfg
from admz.events.normalize import normalize_vapix_event

logger = logging.getLogger(__name__)

EventCallback = Callable[[Dict[str, Any]], Awaitable[None]]

_INSECURE_SSL = ssl.create_default_context()
_INSECURE_SSL.check_hostname = False
_INSECURE_SSL.verify_mode = ssl.CERT_NONE


def _resolve_endpoint(device_info: Dict[str, Any], creds: Dict[str, Any]) -> Dict[str, Any]:
    """Host + scheme + http/ws base URLs for a device (mirrors the executor)."""
    host = (creds.get("host") or device_info.get("host") or "").strip()
    auth = device_info.get("auth") if isinstance(device_info.get("auth"), dict) else {}
    scheme = (auth.get("scheme") or "https").lower()
    method = (auth.get(scheme) or auth.get("auth_method") or device_info.get("auth_method") or "digest").lower()
    http_base = f"{scheme}://{host}"
    ws_scheme = "wss" if scheme == "https" else "ws"
    return {"host": host, "scheme": scheme, "method": method,
            "http_base": http_base, "ws_scheme": ws_scheme}


def _auth_for(method: str, username: str, password: str):
    return httpx.BasicAuth(username, password) if method == "basic" else httpx.DigestAuth(username, password)


async def mint_session_token(http_base: str, username: str, password: str, method: str) -> Optional[str]:
    """GET wssession.cgi → a short-lived plain-text token.

    Auth-method resilient: tries the device's known method first, then falls
    back to the other on a 401 (Axis speakers, for instance, answer with
    ``WWW-Authenticate: Basic`` while cameras use Digest). Mirrors the
    executor's self-healing auth so a stale stored method never blocks ingest.
    """
    url = f"{http_base}/axis-cgi/wssession.cgi"
    methods = [method] + [m for m in ("digest", "basic") if m != method]
    last = "?"
    async with httpx.AsyncClient(verify=False, timeout=cfg.WSSESSION_TIMEOUT) as client:
        for m in methods:
            r = await client.get(url, auth=_auth_for(m, username, password))
            last = r.status_code
            if r.status_code == 200:
                token = (r.text or "").strip()
                if token.startswith("{"):  # tolerate a JSON wrapper
                    try:
                        j = json.loads(token)
                        token = j.get("wssession") or j.get("token") or ""
                    except (TypeError, ValueError):
                        pass
                return token or None
            if r.status_code != 401:
                break  # a non-auth error won't be fixed by another scheme
    raise RuntimeError(f"wssession.cgi {last}")


class DeviceEventStream:
    """Supervised, reconnecting WS event consumer for one device."""

    def __init__(
        self,
        device_id: str,
        *,
        registry: Any,
        store: Any = None,
        on_event: Optional[EventCallback] = None,
        topic_filters: Optional[List[str]] = None,
        event_filter: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ):
        self.device_id = device_id
        self.registry = registry
        # store=None → don't persist (transient preview mode). event_filter, when
        # set, gates which events are kept (ingest passes the WatchGate here so
        # only watched hits are stored; preview passes None to see everything).
        self.store = store
        self.on_event = on_event
        self.event_filter = event_filter
        self.topic_filters = topic_filters or cfg.topic_filters()
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self.last_event_at: float = 0.0
        self.connected: bool = False
        self.last_error: str = ""
        self._warned_on_event = False        # log-once-per-failure-streak latch

    # ----- lifecycle -----
    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        self.connected = False

    # ----- loop -----
    async def _loop(self) -> None:
        delay = cfg.RECONNECT_BASE_DELAY
        while self._running:
            try:
                await self._connect_and_ingest()
                delay = cfg.RECONNECT_BASE_DELAY  # clean exit → reset backoff
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                self.connected = False
                self.last_error = f"{type(exc).__name__}: {exc}"
                logger.info("event stream %s reconnecting in %.0fs (%s)",
                            self.device_id, delay, self.last_error)
                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    break
                delay = min(delay * 2, cfg.RECONNECT_MAX_DELAY)

    async def _connect_and_ingest(self) -> None:
        import websockets  # local import: optional-at-rest transport dep

        info = self.registry.get_device_info(self.device_id) or {}
        creds = self.registry.get_credentials(self.device_id) or {}
        ep = _resolve_endpoint(info, creds)
        if not ep["host"]:
            raise RuntimeError("no host")
        username, password = creds.get("username") or "", creds.get("password") or ""
        device_name = info.get("nickname") or info.get("model") or self.device_id

        token = await mint_session_token(ep["http_base"], username, password, ep["method"])
        qs = f"wssession={token}&sources=events" if token else "sources=events"
        uri = f"{ep['ws_scheme']}://{ep['host']}/vapix/ws-data-stream?{qs}"
        ssl_ctx = _INSECURE_SSL if ep["ws_scheme"] == "wss" else None

        async with websockets.connect(uri, ssl=ssl_ctx, open_timeout=cfg.WS_OPEN_TIMEOUT,
                                      max_size=2 ** 21) as ws:
            await ws.send(json.dumps({
                "apiVersion": "1.0", "context": f"admz-{self.device_id}",
                "method": "events:configure",
                "params": {"eventFilterList": [{"topicFilter": t} for t in self.topic_filters]},
            }))
            self.connected = True
            self.last_error = ""
            logger.info("event stream connected: %s (%s)", self.device_id, device_name)
            async for raw in ws:
                if not self._running:
                    break
                try:
                    msg = json.loads(raw)
                except (TypeError, ValueError):
                    continue
                if msg.get("method") != "events:notify":
                    continue
                rec = normalize_vapix_event(msg, device_id=self.device_id, device_name=device_name)
                if rec is None:
                    continue
                await self._handle(rec)
        self.connected = False

    async def _handle(self, rec: Dict[str, Any]) -> bool:
        """Gate, (maybe) persist, and fan one normalized event to ``on_event``.

        The gate is what stops the firehose: ingest passes the WatchGate as
        ``event_filter``, so only events matching a watched event / detection are
        kept. An event that matches nothing can't fire any detection either, so
        it's dropped outright — never stored, no ``on_event``. Preview mode passes
        no filter and ``store=None``, so it sees everything live and persists
        nothing. Returns True if the event was kept.
        """
        if self.event_filter is not None and not self.event_filter(rec):
            return False
        rec["created_at"] = time.time()
        self.last_event_at = rec["created_at"]
        if self.store is not None:
            self.store.append(rec)
        if self.on_event is not None:
            try:
                await self.on_event(rec)
            except Exception:  # noqa: BLE001 — a handler error must not wedge the stream
                # A WS event is delivered ONCE — there is no window to re-poll — so
                # a handler failure here loses the detection outright. ADR-0058
                # removes the only raise path in the wired evaluator, which is why
                # this should now be unreachable; if it fires, an injected callback
                # is failing and that must be visible, not a debug line. Once per
                # streak: this runs per event.
                if not self._warned_on_event:
                    self._warned_on_event = True
                    logger.warning("on_event handler failed for %s; this event's detections "
                                   "will not be retried", self.device_id, exc_info=True)
                else:
                    logger.debug("on_event handler still failing for %s",
                                 self.device_id, exc_info=True)
            else:
                self._warned_on_event = False
        return True
