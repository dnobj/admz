"""REST surface for the live device-event store (ADR-0041 layer 2).

- ``GET  /api/events``          — query the activity timeline (filters + paging)
- ``GET  /api/events/status``   — ingest supervisor status (per-device streams)
- ``POST /api/events/control``  — turn the ingest subsystem on/off at runtime
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from admz.api.context import get_context
from admz.events.preview import PreviewCapacityError

router = APIRouter()


@router.get("/api/events")
async def list_events(request: Request):
    """The unified activity timeline, newest-first.

    Query params: ``source`` (device|acs), ``type`` (topic substring),
    ``device_id`` (exact), ``device`` (name substring), ``q`` (general text
    search across summary/type/device/data), ``since_ms``, ``limit``.
    """
    q = request.query_params
    ctx = get_context()

    def _int(name, default):
        try:
            return int(q.get(name)) if q.get(name) else default
        except (TypeError, ValueError):
            return default

    # Off the event loop: substring filters (device/q/type) can't use an index,
    # and at millions of rows a single scan takes seconds — run inline it
    # blocks EVERY request while the Activity page auto-polls (live-observed:
    # a 5s scan per poll wedged the whole server at 1.7M rows).
    import asyncio

    events = await asyncio.to_thread(
        ctx.event_store.query,
        source=q.get("source") or None,
        type_filter=q.get("type") or None,
        device_id=q.get("device_id") or None,
        device_filter=q.get("device") or None,
        q=q.get("q") or None,
        since_ms=_int("since_ms", None),
        limit=_int("limit", 500),
    )
    return {
        "success": True,
        "count": len(events),
        "events": events,
        "ingest": ctx.event_supervisor.status(),
        "acs_ingest": ctx.acs_event_poller.status(),
        "acs_firebird": ctx.acs_firebird_poller.status(),
    }


@router.get("/api/events/preview")
async def preview_events(request: Request):
    """Live, **non-persisting** preview of the selected device(s) for the
    watched-event picker (SSE). Opens ephemeral WS streams to just those devices
    and streams normalized events straight to the browser — nothing is written to
    the event store. The stream tears down when this connection closes, after an
    idle period, or at a hard max-duration cap.

    Query: ``device_id`` (repeatable, or comma-separated). Independent of the
    steady-state ``event_ingest_enabled`` flag — picking must work with the
    firehose off.
    """
    q = request.query_params
    ids = []
    for key in ("device_id", "device_ids"):
        for v in q.getlist(key):
            ids.extend(x.strip() for x in str(v).split(",") if x.strip())
    if not ids:
        return JSONResponse({"success": False, "error": "device_id is required"}, status_code=400)

    ctx = get_context()
    try:
        session = await ctx.preview_manager.open(ids)
    except PreviewCapacityError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=429)
    except ValueError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)
    await session.start()

    async def gen():
        try:
            yield f"event: open\ndata: {json.dumps({'device_ids': session.device_ids})}\n\n"
            async for rec in session.subscribe():
                if await request.is_disconnected():
                    break
                if rec.get("_keepalive"):
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(rec, default=str)}\n\n"
        finally:
            await session.stop()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/events/status")
async def events_status():
    ctx = get_context()
    return {
        **ctx.event_supervisor.status(),
        "preview": ctx.preview_manager.status(),
        "acs": ctx.acs_event_poller.status(),
        "acs_firebird": ctx.acs_firebird_poller.status(),
    }


@router.post("/api/events/control")
async def events_control(request: Request):
    """Enable/disable live ingest at runtime (persists the fleet flag + (re)starts
    or stops the per-device WS streams without a server restart).

    Pass ``{"enabled": bool}`` for the device WS ingest, and/or
    ``{"acs_enabled": bool}`` for the ACS Pro action-rule poller (independent)."""
    body = await request.json()
    from admz.fleet_settings import fleet_settings

    ctx = get_context()
    if "enabled" in body:
        enabled = bool(body.get("enabled"))
        fleet_settings.set("event_ingest_enabled", "true" if enabled else "false")
        if enabled:
            await ctx.event_supervisor.start()
            await ctx.event_supervisor.reconcile()
        else:
            await ctx.event_supervisor.stop()
    if "acs_enabled" in body:
        acs_on = bool(body.get("acs_enabled"))
        fleet_settings.set("acs_event_ingest_enabled", "true" if acs_on else "false")
        if acs_on:
            await ctx.acs_event_poller.stop()   # reset high-water + restart cleanly
            await ctx.acs_event_poller.start()
        else:
            await ctx.acs_event_poller.stop()
    if "firebird_enabled" in body:
        fb_on = bool(body.get("firebird_enabled"))
        fleet_settings.set("acs_firebird_enabled", "true" if fb_on else "false")
        if fb_on:
            await ctx.acs_firebird_poller.stop()   # reset high-water + restart cleanly
            await ctx.acs_firebird_poller.start()
        else:
            await ctx.acs_firebird_poller.stop()
    return {
        "success": True,
        "status": ctx.event_supervisor.status(),
        "acs": ctx.acs_event_poller.status(),
        "acs_firebird": ctx.acs_firebird_poller.status(),
    }
