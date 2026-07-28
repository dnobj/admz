"""REST + web surface for demos (ADR-0046/0047).

Thin HTTP layer over the shared cores in :mod:`admz.demos.actions` — MCP and
the confirm-widget executors call the SAME cores, so every surface runs one
implementation. Metadata CRUD is inert (authenticated principal only). The
drift-affecting writes (assign-fragment, adopt) gate behind the approval widget
for non-interactive principals (api keys, chat) — the signed-in console user
writes directly, mirroring the tasks policy. Prepare/End inherit the scenario
plan gate.
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
from admz.demos import actions, service
from admz.demos.actions import DemoActionError
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


class InferenceRunRequest(BaseModel):
    """Start a demo-inference run (#124) — collect, cluster and propose."""

    # "fast": registry + last snapshots + one live ACS read (seconds, works with
    # the fleet offline). "survey": discover → onboard → snapshot → infer, run
    # in the background because it takes minutes.
    mode: str = "fast"
    include_acs: bool = True
    # survey only — leave onboarding on for a genuinely fresh install; turn it
    # off for a strictly read-only sweep of what is already registered.
    register_new: bool = True
    subnet: Optional[str] = None
    timeout: float = 5.0
    # Defaults TRUE on purpose. On the reference fleet every ACS rule triggers
    # and acts on the SAME device, so there is no cross-device rule topology at
    # all and every cluster is corroborating-evidence-only; defaulting this
    # False would return an empty inventory on a site that demonstrably has
    # demos. Weak clusters are surfaced flagged `no_topology` and capped at
    # `low` confidence instead of being hidden — see cluster.py's module
    # docstring. Pass false for topology-backed proposals only.
    include_weak: bool = True


class ProposalConfirmRequest(BaseModel):
    """Everything a proposal guessed is overridable at the moment of confirming."""

    name: Optional[str] = None
    purpose: Optional[str] = None
    device_ids: Optional[List[str]] = None
    roles: Optional[Dict[str, str]] = None
    tag: Optional[str] = None


class ProposalDismissRequest(BaseModel):
    reason: str = ""


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


def _http(e: DemoActionError) -> HTTPException:
    return HTTPException(status_code=e.status, detail=str(e))


# ── REST ─────────────────────────────────────────────────────────────────────

@router.get("/api/demos")
async def list_demos(ctx: AppContext = Depends(get_context)):
    return {
        "success": True,
        "demos": service.demo_views(
            ctx.demo_store.list(), ctx.registry, ctx.event_store),
    }


# ── Proposals (#124 slice 3) ─────────────────────────────────────────────────
#
# Read/dismiss are inert. CONFIRM creates a demo and attaches rule membership —
# still inert by the ADR-0046 bar (metadata; `active` stays False, so drift
# attribution sees nothing new) because, per resolved DECISION b, it writes NO
# fragments. The gate in `demos/gated.py` exists for the drift-affecting writes
# (assign_demo_fragment, adopt_demo); confirm is neither, touches no device and
# issues no ACS write, and deleting a demo is free. Hence ungated, same bar as
# POST /api/demos.

def _proposal(ctx: AppContext, ref: str):
    from admz.demos.inference.confirm import resolve_proposal

    try:
        return resolve_proposal(ctx.proposal_store, ref)
    except DemoActionError as e:
        raise _http(e)


@router.get("/api/demos/proposals")
async def list_demo_proposals(status: Optional[str] = "proposed",
                              run_id: Optional[str] = None,
                              ctx: AppContext = Depends(get_context)):
    """Candidate demos, strongest first. ``status=all`` returns every status."""
    wanted = None if (status or "").lower() in ("", "all", "any") else status
    rows = ctx.proposal_store.list(status=wanted, run_id=run_id)
    return {"success": True, "count": len(rows),
            "proposals": [p.to_dict() for p in rows]}


@router.get("/api/demos/proposals/{proposal_id}")
async def get_demo_proposal(proposal_id: str,
                            ctx: AppContext = Depends(get_context)):
    """One proposal: full evidence, score breakdown, rules with observability,
    and the suggested owned keys."""
    return {"success": True, "proposal": _proposal(ctx, proposal_id).to_dict()}


@router.post("/api/demos/proposals/{proposal_id}/confirm")
async def confirm_demo_proposal(proposal_id: str, req: ProposalConfirmRequest,
                                request: Request,
                                ctx: AppContext = Depends(get_context)):
    """Create the real demo. Writes no fragments — the demo owns nothing yet."""
    from admz.demos.inference.confirm import confirm_proposal_core

    principal = await _principal(request)
    proposal = _proposal(ctx, proposal_id)
    try:
        return confirm_proposal_core(
            ctx, proposal, principal, name=req.name, purpose=req.purpose,
            device_ids=req.device_ids, roles=req.roles, tag=req.tag)
    except DemoActionError as e:
        raise _http(e)


@router.post("/api/demos/proposals/{proposal_id}/dismiss")
async def dismiss_demo_proposal(proposal_id: str, req: ProposalDismissRequest,
                                request: Request,
                                ctx: AppContext = Depends(get_context)):
    """Record that this is not a demo — remembered, so re-inference respects it."""
    from admz.demos.inference.confirm import dismiss_proposal_core

    principal = await _principal(request)
    proposal = _proposal(ctx, proposal_id)
    try:
        return dismiss_proposal_core(ctx, proposal, principal, reason=req.reason)
    except DemoActionError as e:
        raise _http(e)


@router.get("/api/demos/{demo_id}")
async def get_demo(demo_id: str, ctx: AppContext = Depends(get_context)):
    demo = _get(ctx, demo_id)
    view = service.demo_view(demo, ctx.registry, ctx.event_store)
    view["fragments"] = _fragments_view(ctx, demo)
    return {"success": True, "demo": view}


@router.post("/api/demos")
async def create_demo(req: DemoRequest, request: Request,
                      ctx: AppContext = Depends(get_context)):
    principal = await _principal(request)
    try:
        demo = actions.create_demo_core(ctx, req.model_dump(), principal)
    except DemoActionError as e:
        raise _http(e)
    return {"success": True,
            "demo": service.demo_view(demo, ctx.registry, ctx.event_store)}


@router.patch("/api/demos/{demo_id}")
async def update_demo(demo_id: str, request: Request,
                      ctx: AppContext = Depends(get_context)):
    principal = await _principal(request)
    demo = _get(ctx, demo_id)
    body = await request.json()
    try:
        demo = actions.update_demo_core(ctx, demo, body, principal)
    except DemoActionError as e:
        raise _http(e)
    return {"success": True,
            "demo": service.demo_view(demo, ctx.registry, ctx.event_store)}


@router.delete("/api/demos/{demo_id}")
async def delete_demo(demo_id: str, request: Request,
                      ctx: AppContext = Depends(get_context)):
    principal = await _principal(request)
    demo = _get(ctx, demo_id)
    actions.delete_demo_core(ctx, demo, principal)
    return {"success": True}


# ── Fragments (ADR-0047 capture) ─────────────────────────────────────────────


def _fragments_view(ctx: AppContext, demo: Demo) -> Dict[str, Any]:
    return actions.fragments_view(ctx, demo)


@router.post("/api/demos/{demo_id}/fragment")
async def assign_fragment(demo_id: str, req: FragmentAssignRequest, request: Request,
                          ctx: AppContext = Depends(get_context)):
    """Assign selected drift-diff rows to the demo's fragment (capture).

    Drift-affecting (ADR-0047 policy): api-key and other non-interactive
    principals get the approval widget; the signed-in console user writes
    directly. The core re-checks drift so captured values come from the REAL
    diff. Writes only; no device is touched.
    """
    from admz.demos.gated import gate_demo_write, is_interactive

    principal = await _principal(request)
    demo = _get(ctx, demo_id)
    fields = [{"device_id": f.device_id, "facet": f.facet, "path": f.path}
              for f in req.fields]
    if not is_interactive(principal):
        n = len(fields)
        return gate_demo_write(
            "assign_demo_fragment", demo.id,
            {"demo": demo.id, "fields": fields, "role": req.role,
             "mode": req.mode},
            f"Assign {n} config field{'s' if n != 1 else ''} to demo "
            f"'{demo.name}' — its keys become deliberate (not drift) once "
            "the demo is active.")
    try:
        return await actions.assign_fragment_core(
            ctx, demo, fields, req.role, req.mode, principal)
    except DemoActionError as e:
        raise _http(e)


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


# ── Adopt / deactivate (ADR-0047 activation state, no pushes) ────────────────


@router.post("/api/demos/{demo_id}/adopt")
async def adopt_demo(demo_id: str, request: Request,
                     ctx: AppContext = Depends(get_context)):
    """Mark a demo ACTIVE without pushing anything (drift-affecting →
    non-interactive principals get the approval widget; guards re-run at
    apply time). See :func:`admz.demos.actions.adopt_demo_core`."""
    from admz.demos.gated import gate_demo_write, is_interactive

    principal = await _principal(request)
    demo = _get(ctx, demo_id)
    if not is_interactive(principal):
        return gate_demo_write(
            "adopt_demo", demo.id, {"demo": demo.id},
            f"Adopt demo '{demo.name}' (mark active) — its owned keys stop "
            "counting as drift and join each device's expected state.")
    try:
        return actions.adopt_demo_core(ctx, demo, principal)
    except DemoActionError as e:
        raise _http(e)


@router.post("/api/demos/{demo_id}/deactivate")
async def deactivate_demo(demo_id: str, request: Request,
                          ctx: AppContext = Depends(get_context)):
    """Stop claiming the demo's keys (no push — only reveals drift again)."""
    principal = await _principal(request)
    demo = _get(ctx, demo_id)
    return actions.deactivate_demo_core(ctx, demo, principal)


# ── Prepare / End ────────────────────────────────────────────────────────────
#
# Both delegate to the shared scenario core (ADR-0044), so a demo's config moves
# ride the SAME gated plan + approval widget as every other config push. A demo
# introduces no new way to touch a device — only a new reason to.

@router.post("/api/demos/{demo_id}/prepare")
async def prepare_demo(demo_id: str, request: Request,
                       ctx: AppContext = Depends(get_context)):
    """Load a sidelined demo's scenario in one gated plan. See
    :func:`admz.demos.actions.prepare_demo_core` for the guards."""
    principal = await _principal(request)
    demo = _get(ctx, demo_id)
    try:
        return await actions.prepare_demo_core(ctx, demo, principal)
    except DemoActionError as e:
        raise _http(e)


@router.post("/api/demos/{demo_id}/end")
async def end_demo(demo_id: str, request: Request,
                   ctx: AppContext = Depends(get_context)):
    """Snap a sidelined demo's devices back to baseline, handing them back."""
    principal = await _principal(request)
    demo = _get(ctx, demo_id)
    try:
        return await actions.end_demo_core(ctx, demo, principal)
    except DemoActionError as e:
        raise _http(e)


# ── Inference (#124 slice 2 — the evidence graph) ────────────────────────────
#
# Read-only and inert: a run reads the registry, the last snapshots and ACS, and
# writes ONE row to `demo_inference_runs`. It touches no device, issues no ACS
# write, and never creates a demo — so no confirmation gate, same bar as demo
# metadata CRUD (0046-demos.md:126). `survey` mode's extra phases reuse the
# existing discovery/onboarding/snapshot entry points; it adds no new
# device-touch path.

#: Strong refs to in-flight survey tasks (the loop holds only weak ones).
_BACKGROUND_RUNS: set = set()


@router.post("/api/demos/inference/runs")
async def start_inference_run(req: InferenceRunRequest, request: Request,
                              ctx: AppContext = Depends(get_context)):
    """Start a run. ``fast`` completes inline; ``survey`` returns immediately
    with a ``running`` row and finishes in the background — poll
    ``GET /api/demos/inference/runs/{id}`` for progress."""
    import asyncio

    from admz.audit import record_event
    from admz.demos.inference import collect
    from admz.demos.inference.runs import (MODE_FAST, MODE_SURVEY,
                                           SURVEY_STALE_SECONDS)

    principal = await _principal(request)
    mode = (req.mode or MODE_FAST).strip().lower()
    if mode not in (MODE_FAST, MODE_SURVEY):
        raise HTTPException(400, "mode must be 'fast' or 'survey'")
    store = ctx.inference_run_store

    if mode == MODE_FAST:
        out = await collect.infer_demos(
            ctx, store, ctx.proposal_store, created_by=str(principal),
            include_acs=req.include_acs, include_weak=req.include_weak)
        run = out["run"]
        record_event(principal, "demo.inference_run", resource="demos:inference",
                     success=run.status != "failed",
                     details={"mode": mode, "run": run.id,
                              "devices": run.device_count, "rules": run.rule_count,
                              "proposals": len(out["proposals"])})
        return {"success": True, "run": run.to_dict(),
                "proposals": [p.to_dict() for p in out["proposals"]],
                "report": out["report"]}

    # A deep survey rewrites the registry and every snapshot — one at a time.
    # A row abandoned by a dead process ages out, so a crash can't wedge this.
    already = store.running(mode=MODE_SURVEY, max_age=SURVEY_STALE_SECONDS)
    if already:
        raise HTTPException(
            409, f"a deep survey is already running (run {already[0].id})")
    run = store.start(mode=MODE_SURVEY, created_by=str(principal),
                      message="Starting deep survey…")
    # Hold a strong reference: the event loop only keeps a weak one, so a
    # minutes-long task can otherwise be garbage-collected mid-run.
    task = asyncio.create_task(collect.run_survey(
        ctx, store, run.id, register_new=req.register_new,
        timeout=req.timeout, subnet=req.subnet,
        proposal_store=ctx.proposal_store, include_weak=req.include_weak))
    _BACKGROUND_RUNS.add(task)
    task.add_done_callback(_BACKGROUND_RUNS.discard)
    record_event(principal, "demo.inference_run", resource="demos:inference",
                 details={"mode": mode, "run": run.id,
                          "register_new": req.register_new})
    return {"success": True, "started": True, "run": run.header()}


@router.get("/api/demos/inference/runs")
async def list_inference_runs(limit: int = 25,
                              ctx: AppContext = Depends(get_context)):
    """Run headers, newest first — no graphs (they are the audit trail, fetched
    one at a time)."""
    runs = ctx.inference_run_store.list(limit=limit)
    return {"success": True, "count": len(runs),
            "runs": [r.header() for r in runs]}


@router.get("/api/demos/inference/runs/{run_id}")
async def get_inference_run(run_id: str, ctx: AppContext = Depends(get_context)):
    """One run: status/progress, the full evidence graph, and the proposals it
    produced (the audit trail and the verdict, together)."""
    run = ctx.inference_run_store.get(run_id)
    if run is None:
        raise HTTPException(404, "inference run not found")
    proposals = ctx.proposal_store.list(status=None, run_id=run_id)
    return {"success": True, "run": run.to_dict(),
            "proposals": [p.to_dict() for p in proposals]}


# ── Web ──────────────────────────────────────────────────────────────────────

@router.get("/demos", response_class=HTMLResponse)
async def demos_page(request: Request, ctx: AppContext = Depends(get_context)):
    """The job view above the inventory view: every demo + its one-glance verdict.

    Readiness is server-rendered from the drift/health caches (same split as the
    Devices page — see ``routes/web.py``); nothing here probes a device.
    """
    demos = service.demo_views(ctx.demo_store.list(), ctx.registry, ctx.event_store)
    try:
        devices = [
            {"device_id": d.get("device_id"),
             "name": d.get("nickname") or d.get("device_id"),
             "model": d.get("model") or ""}
            for d in ctx.registry.list_devices() if d.get("device_id")
        ]
        devices.sort(key=lambda d: d["name"])
        tags = sorted({t for d in ctx.registry.list_devices() for t in (d.get("tags") or [])})
    except Exception:  # noqa: BLE001
        devices, tags = [], []
    return templates.TemplateResponse(
        "demos.html",
        {"request": request, "title": "Demos", "demos": demos, "tags": tags,
         "all_devices": devices},
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

    # device_id → friendly name, for the signal picker + signals table (a
    # watched event carries its device; show it by name, not MAC).
    device_names = {
        d.get("device_id"): (d.get("nickname") or d.get("model")
                             or d.get("device_id"))
        for d in devices if d.get("device_id")
    }

    return templates.TemplateResponse(
        "demo_detail.html",
        {"request": request, "title": view["name"] or "Demo", "demo": view,
         "holders": holders, "all_devices": devices, "tags": tags,
         "device_names": device_names,
         "fragments": _fragments_view(ctx, demo)},
    )
