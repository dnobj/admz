"""REST + web surface for demos (ADR-0046).

A demo is inert metadata — it never fires anything on its own, so CRUD needs only
an authenticated principal (same bar as detections). The one action that *touches*
devices, Prepare, delegates to the existing gated scenario push, so it inherits the
approval widget rather than inventing a second gate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from admz.api.context import AppContext, get_context
from admz.demos import service
from admz.demos.store import Demo

router = APIRouter()

template_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))
from admz.api.templating import configure as _configure_templates  # noqa: E402
_configure_templates(templates)


class DemoRequest(BaseModel):
    name: str = ""
    narrative: str = ""
    tag: Optional[str] = None
    device_ids: List[str] = Field(default_factory=list)
    roles: Dict[str, str] = Field(default_factory=dict)
    config_source: str = "baseline"
    signals: List[Dict[str, Any]] = Field(default_factory=list)
    enabled: bool = True


async def _principal(request: Request):
    from admz.auth import get_current_principal
    from admz.authz import require_authenticated_principal

    principal = await get_current_principal(request)
    require_authenticated_principal(principal)
    return principal


def _get(ctx: AppContext, demo_id: str) -> Demo:
    demo = ctx.demo_store.get(demo_id)
    if demo is None:
        raise HTTPException(404, "demo not found")
    return demo


# ── REST ─────────────────────────────────────────────────────────────────────

@router.get("/api/demos")
async def list_demos(ctx: AppContext = Depends(get_context)):
    return {
        "success": True,
        "demos": service.demo_views(
            ctx.demo_store.list(), ctx.registry, ctx.event_store),
    }


@router.get("/api/demos/{demo_id}")
async def get_demo(demo_id: str, ctx: AppContext = Depends(get_context)):
    return {
        "success": True,
        "demo": service.demo_view(
            _get(ctx, demo_id), ctx.registry, ctx.event_store),
    }


@router.post("/api/demos")
async def create_demo(req: DemoRequest, request: Request,
                      ctx: AppContext = Depends(get_context)):
    from admz.audit import record_event

    principal = await _principal(request)
    if not (req.name or "").strip():
        raise HTTPException(400, "name is required")
    demo = ctx.demo_store.create(Demo(
        id="", name=req.name.strip(), narrative=req.narrative or "",
        tag=req.tag or None, device_ids=req.device_ids or [],
        roles=req.roles or {}, config_source=req.config_source or "baseline",
        signals=req.signals or [], enabled=bool(req.enabled),
        created_by=str(principal),
    ))
    record_event(principal, "demo.create", resource=f"demo:{demo.id}",
                 details={"name": demo.name,
                          "scope": demo.tag or f"{len(demo.device_ids)} device(s)",
                          "config_source": demo.config_source})
    return {"success": True,
            "demo": service.demo_view(demo, ctx.registry, ctx.event_store)}


@router.patch("/api/demos/{demo_id}")
async def update_demo(demo_id: str, request: Request,
                      ctx: AppContext = Depends(get_context)):
    from admz.audit import record_event

    principal = await _principal(request)
    demo = _get(ctx, demo_id)
    body = await request.json()
    for f in ("name", "narrative", "tag", "device_ids", "roles",
              "config_source", "signals", "enabled"):
        if f in body:
            setattr(demo, f, body[f])
    ctx.demo_store.update(demo)
    record_event(principal, "demo.update", resource=f"demo:{demo_id}",
                 details={"fields": [f for f in body]})
    return {"success": True,
            "demo": service.demo_view(demo, ctx.registry, ctx.event_store)}


@router.delete("/api/demos/{demo_id}")
async def delete_demo(demo_id: str, request: Request,
                      ctx: AppContext = Depends(get_context)):
    from admz.audit import record_event

    principal = await _principal(request)
    demo = _get(ctx, demo_id)
    ctx.demo_store.delete(demo_id)
    record_event(principal, "demo.delete", resource=f"demo:{demo_id}",
                 details={"name": demo.name})
    return {"success": True}


# ── Prepare / End ────────────────────────────────────────────────────────────
#
# Both delegate to the shared scenario core (ADR-0044), so a demo's config moves
# ride the SAME gated plan + approval widget as every other config push. A demo
# introduces no new way to touch a device — only a new reason to.

@router.post("/api/demos/{demo_id}/prepare")
async def prepare_demo(demo_id: str, request: Request,
                       ctx: AppContext = Depends(get_context)):
    """Load a sidelined demo's scenario onto its devices in one gated plan.

    A **baseline** demo has nothing to load — its config is already the device's
    normal state — so this refuses rather than inventing a push. Devices held by
    another demo's scenario are reported as blockers instead of being stolen:
    exclusivity is the point of a scenario.
    """
    from admz.demos import readiness as rd
    from admz.snapshot.scenarios import activate_scenario_core

    principal = await _principal(request)
    demo = _get(ctx, demo_id)
    name = rd.scenario_of(demo.config_source)
    if not name:
        raise HTTPException(
            400, "This demo runs on the baseline config — there's nothing to "
                 "load. Its devices are ready when they're in sync and online.")

    targets = service.resolve_devices(demo, ctx.registry)
    if not targets:
        raise HTTPException(400, "This demo has no devices.")

    held = [
        d.get("device_id") for d in targets
        if d.get("active_scenario") and d.get("active_scenario") != name
    ]
    if held:
        raise HTTPException(
            409, f"{', '.join(held)} currently held by another scenario "
                 f"({', '.join(sorted({d.get('active_scenario') for d in targets if d.get('active_scenario') and d.get('active_scenario') != name}))}). "
                 "End that demo first.")

    try:
        result = await activate_scenario_core(
            ctx, name, targets, principal,
            description=f"Prepare demo '{demo.name}' (scenario '{name}')")
    except ValueError as e:
        raise HTTPException(400, str(e))
    result["demo_id"] = demo.id
    return result


@router.post("/api/demos/{demo_id}/end")
async def end_demo(demo_id: str, request: Request,
                   ctx: AppContext = Depends(get_context)):
    """Snap a sidelined demo's devices back to baseline, handing them back."""
    from admz.demos import readiness as rd
    from admz.snapshot.scenarios import return_to_baseline_core

    principal = await _principal(request)
    demo = _get(ctx, demo_id)
    if not rd.scenario_of(demo.config_source):
        raise HTTPException(
            400, "This demo runs on the baseline config — there's nothing to "
                 "end. Its devices were never taken out of their normal state.")

    targets = service.resolve_devices(demo, ctx.registry)
    if not targets:
        raise HTTPException(400, "This demo has no devices.")
    try:
        result = await return_to_baseline_core(
            ctx, targets, principal,
            description=f"End demo '{demo.name}' — return to baseline")
    except ValueError as e:
        raise HTTPException(400, str(e))
    result["demo_id"] = demo.id
    return result


# ── Web ──────────────────────────────────────────────────────────────────────

@router.get("/demos", response_class=HTMLResponse)
async def demos_page(request: Request, ctx: AppContext = Depends(get_context)):
    """The job view above the inventory view: every demo + its one-glance verdict.

    Readiness is server-rendered from the drift/health caches (same split as the
    Devices page — see ``routes/web.py``); nothing here probes a device.
    """
    demos = service.demo_views(ctx.demo_store.list(), ctx.registry, ctx.event_store)
    try:
        tags = sorted({t for d in ctx.registry.list_devices() for t in (d.get("tags") or [])})
    except Exception:  # noqa: BLE001
        tags = []
    return templates.TemplateResponse(
        "demos.html",
        {"request": request, "title": "Demos", "demos": demos, "tags": tags},
    )


@router.get("/demos/{demo_id}", response_class=HTMLResponse)
async def demo_detail_page(demo_id: str, request: Request,
                           ctx: AppContext = Depends(get_context)):
    demo = _get(ctx, demo_id)
    view = service.demo_view(demo, ctx.registry, ctx.event_store)

    # "On loan" is only actionable if we can name who has it — resolve the
    # holding demo for every device a scenario has taken.
    all_demos = ctx.demo_store.list()
    holders: Dict[str, List[Dict[str, str]]] = {}
    for row in view["readiness"]["devices"]:
        if row["config"]["state"] not in ("on_loan", "conflict"):
            continue
        holders[row["device_id"]] = [
            {"id": h.id, "name": h.name}
            for h in service.holders_of(row["device_id"], all_demos, ctx.registry)
            if h.id != demo.id
        ]

    try:
        devices = ctx.registry.list_devices()
        tags = sorted({t for d in devices for t in (d.get("tags") or [])})
    except Exception:  # noqa: BLE001
        devices, tags = [], []

    return templates.TemplateResponse(
        "demo_detail.html",
        {"request": request, "title": view["name"] or "Demo", "demo": view,
         "holders": holders, "all_devices": devices, "tags": tags},
    )
