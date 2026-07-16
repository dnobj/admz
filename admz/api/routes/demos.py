"""REST + web surface for demos (ADR-0046).

A demo is inert metadata — it never fires anything on its own, so CRUD needs only
an authenticated principal (same bar as detections). The one action that *touches*
devices, Prepare, delegates to the existing gated scenario push, so it inherits the
approval widget rather than inventing a second gate.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from admz.api.context import AppContext, get_context
from admz.demos import service
from admz.demos.store import Demo

logger = logging.getLogger(__name__)

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


class FragmentField(BaseModel):
    device_id: str
    facet: str
    path: str


class FragmentAssignRequest(BaseModel):
    """Assign drifted fields to a demo's fragment (ADR-0047 capture)."""

    fields: List[FragmentField]
    role: Optional[str] = None   # default: the device's role in the demo
    mode: str = "set"


class FragmentEntry(BaseModel):
    facet: str
    path: str


class FragmentRemoveRequest(BaseModel):
    role: str
    entries: List[FragmentEntry]


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
    demo = _get(ctx, demo_id)
    view = service.demo_view(demo, ctx.registry, ctx.event_store)
    view["fragments"] = _fragments_view(ctx, demo)
    return {"success": True, "demo": view}


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
    try:
        from admz.demos import fragments as fr

        fr.delete_demo_fragments(ctx.git_repo, demo_id, demo.name)
    except Exception:  # noqa: BLE001 — orphan fragments are harmless; history keeps them
        logger.warning("demo %s: fragment cleanup failed", demo_id, exc_info=True)
    record_event(principal, "demo.delete", resource=f"demo:{demo_id}",
                 details={"name": demo.name})
    return {"success": True}


# ── Fragments (ADR-0047 capture) ─────────────────────────────────────────────


def _fragments_view(ctx: AppContext, demo: Demo) -> Dict[str, Any]:
    """``{role: {facets, counts}}`` for the demo's owned config, or {}."""
    from admz.demos import fragments as fr

    out: Dict[str, Any] = {}
    for role, facets in fr.load_all_fragments(ctx.git_repo, demo.id).items():
        out[role] = {"facets": facets, "counts": fr.fragment_entry_count(facets)}
    return out


@router.post("/api/demos/{demo_id}/fragment")
async def assign_fragment(demo_id: str, req: FragmentAssignRequest, request: Request,
                          ctx: AppContext = Depends(get_context)):
    """Assign selected drift-diff rows to the demo's fragment (capture).

    The server re-checks drift per device (same pattern as ``/snapshot/revert``)
    so values come from the REAL diff, not the client: the captured value is the
    device's **actual live value** — the operator configured the device the way
    the demo needs it, so the live side IS the demo's config. Writes only; no
    device is touched.
    """
    from admz.audit import record_event
    from admz.demos import fragments as fr
    from admz.snapshot.facets import get_facets_for_device

    principal = await _principal(request)
    demo = _get(ctx, demo_id)
    if not req.fields:
        raise HTTPException(400, "no fields selected")
    if req.mode not in fr.MODES:
        raise HTTPException(400, f"mode must be one of {fr.MODES}")

    selected: Dict[str, set] = {}
    for f in req.fields:
        selected.setdefault(f.device_id, set()).add((f.facet, f.path))

    added: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    warnings: List[str] = []
    entries_by_role: Dict[str, List[Dict[str, str]]] = {}
    roles_learned: Dict[str, str] = {}

    for did, chosen in selected.items():
        if not ctx.registry.device_exists(did):
            skipped.append({"device_id": did, "facet": "", "path": "",
                            "reason": "device not found"})
            continue
        device_info = ctx.registry.get_device_info(did)
        device_info["device_id"] = did
        facets_by_name = {f.name: f for f in get_facets_for_device(device_info)}
        role = fr.normalize_role(req.role or (demo.roles or {}).get(did))

        report = await ctx.drift_detector.check_drift(did)
        by_key = {(f.facet, f.path): f for f in report.fields}
        for facet_name, path in sorted(chosen):
            field = by_key.get((facet_name, path))
            if field is None:
                skipped.append({"device_id": did, "facet": facet_name,
                                "path": path, "reason": "not-drifted"})
                continue
            ok, reason, warns = fr.validate_assignment(
                field, facets_by_name.get(facet_name), req.mode, device_info)
            warnings.extend(warns)
            if not ok:
                skipped.append({"device_id": did, "facet": facet_name,
                                "path": path, "reason": reason})
                continue
            entries_by_role.setdefault(role, []).append(
                {"facet": facet_name, "path": path, "value": field.actual})
            added.append({"device_id": did, "role": role, "facet": facet_name,
                          "path": path, "value": field.actual,
                          "canonical_key": field.canonical_key})
            roles_learned[did] = role

    commit_sha = None
    for role, entries in entries_by_role.items():
        sha = fr.add_entries(ctx.git_repo, demo, role, entries, mode=req.mode)
        commit_sha = sha or commit_sha

    # Capturing from a device implicitly binds it: record the role, and put the
    # device in scope when the demo isn't tag-scoped.
    if roles_learned:
        demo.roles = {**(demo.roles or {}), **roles_learned}
        if not demo.tag:
            missing = [d for d in roles_learned if d not in (demo.device_ids or [])]
            demo.device_ids = list(demo.device_ids or []) + missing
        ctx.demo_store.update(demo)

    record_event(principal, "demo.fragment_assign", resource=f"demo:{demo_id}",
                 details={"added": len(added), "skipped": len(skipped),
                          "mode": req.mode, "commit": commit_sha})
    return {"success": True, "added": added, "skipped": skipped,
            "warnings": warnings, "commit_sha": commit_sha,
            "fragments": _fragments_view(ctx, demo)}


@router.post("/api/demos/{demo_id}/fragment/remove")
async def remove_fragment_entries(demo_id: str, req: FragmentRemoveRequest,
                                  request: Request,
                                  ctx: AppContext = Depends(get_context)):
    from admz.audit import record_event
    from admz.demos import fragments as fr

    principal = await _principal(request)
    demo = _get(ctx, demo_id)
    sha = fr.remove_entries(
        ctx.git_repo, demo, req.role,
        [{"facet": e.facet, "path": e.path} for e in req.entries])
    record_event(principal, "demo.fragment_remove", resource=f"demo:{demo_id}",
                 details={"role": req.role, "entries": len(req.entries),
                          "commit": sha})
    return {"success": True, "commit_sha": sha,
            "fragments": _fragments_view(ctx, demo)}


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
         "holders": holders, "all_devices": devices, "tags": tags,
         "fragments": _fragments_view(ctx, demo)},
    )
