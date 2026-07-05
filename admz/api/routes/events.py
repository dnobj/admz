"""REST surface for the live device-event store (ADR-0041 layer 2).

- ``GET  /api/events``          — query the activity timeline (filters + paging)
- ``GET  /api/events/status``   — ingest supervisor status (per-device streams)
- ``POST /api/events/control``  — turn the ingest subsystem on/off at runtime
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from admz.api.context import get_context

router = APIRouter()


@router.get("/api/events")
async def list_events(request: Request):
    """The unified activity timeline, newest-first.

    Query params: ``source`` (device|acs), ``type`` (topic substring),
    ``device_id`` (exact), ``device`` (name substring), ``since_ms``, ``limit``.
    """
    q = request.query_params
    ctx = get_context()

    def _int(name, default):
        try:
            return int(q.get(name)) if q.get(name) else default
        except (TypeError, ValueError):
            return default

    events = ctx.event_store.query(
        source=q.get("source") or None,
        type_filter=q.get("type") or None,
        device_id=q.get("device_id") or None,
        device_filter=q.get("device") or None,
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


@router.get("/api/events/status")
async def events_status():
    ctx = get_context()
    return {
        **ctx.event_supervisor.status(),
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
