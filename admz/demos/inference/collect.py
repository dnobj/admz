"""Collection orchestration for demo inference (#124, slice 2).

This is the **only I/O module** in the inference package: it gathers what
:mod:`admz.demos.inference.graph` then turns into the evidence graph, in one of
two modes.

``fast`` (the default, and what the "Infer demos" button runs)
    Registry devices + the *latest existing* snapshot facets (``action_rules``,
    ``applications``) + one live ACS read. Seconds, and — crucially — it works
    with **the whole fleet offline**: nothing here probes a device. It also
    works with **no ACS at all**: an absent/disabled Firebird reader degrades to
    ``{available: false, reason}`` exactly as ``GET /api/acs/rules`` does
    (``modules/acs_pro/routes.py:145-167``), and the graph is still built from
    device-side rules.

``survey``
    discover → onboard → snapshot → then the fast path, for a genuinely fresh
    install where the registry is empty and nothing has been snapshotted. It is
    minutes-long, so it runs as a **background job** against the
    ``demo_inference_runs`` row (never blocking the HTTP request), following the
    house idiom: ``asyncio.create_task`` launching the work and writing terminal
    state back (``fleet/health.py:904-951``), with a ``"n/total"`` progress
    string in the same shape as the only existing progress contract
    (``plans/engine.py:508-536``). Each phase reuses an existing entry point —
    ``discovery.discover_devices``, ``onboarding.onboard_device_credentials``,
    ``SnapshotEngine.snapshot_fleet`` — so the survey introduces **no new
    device-touch path**.

The ACS join prefers the **supported** route: ``DeviceListFacade:GetDeviceList``
feeds ``rule_anatomy``'s resolver, which takes the live ``DeviceId``'s integer
key (slice 1 proved it *is* the Firebird primary key) and reads that row's
``MacAddress``; the Firebird ``DEVICE.MAC_ADDRESS`` is the free fallback.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from admz.demos.inference import graph as graph_mod
from admz.demos.inference.runs import (MODE_FAST, MODE_SURVEY, SURVEY_PHASES,
                                       InferenceRun, InferenceRunStore)

logger = logging.getLogger(__name__)

#: ACS list facades page their results; ask for the whole fleet in one call
#: (same range literal the ``/acs`` page uses).
_LIST_RANGE = {"range": {"StartIndex": 0, "NumberOfElements": 10000}}

ACS_DISABLED_REASON = (
    "ACS Pro isn't connected — inference ran on device-side rules alone, so it "
    "has no cross-device rule topology to work from."
)


class CollectionError(RuntimeError):
    """Something the run *must* read could not be read.

    Deliberately not a degradation. ACS is optional and an absent snapshot is
    information, so both degrade with a reason — but the registry **is** the
    node set, and an unreadable registry is indistinguishable from an empty
    fleet once it has been turned into a graph. A run that cannot read it fails
    loudly rather than presenting a clean, complete, empty result.
    """


# ═══════════════════════════════════════════════════════════════════════════
# Fast path
# ═══════════════════════════════════════════════════════════════════════════

def _registry_nodes(ctx: Any) -> List[Dict[str, Any]]:
    """Registry rows enriched with each device's installed ACAPs (cache-only).

    ``device_applications`` returns ``{}`` for a device with no snapshot; that
    is **unknown**, not "no apps", and the graph treats it as such.

    An unreadable registry raises :class:`CollectionError`: there is no honest
    graph to build without the node set, and an empty one would be a lie a
    caller cannot detect.
    """
    from admz.rules.capabilities import device_applications

    try:
        rows = ctx.registry.list_devices() or []
    except Exception as exc:  # noqa: BLE001 — fail the run; never fake an empty fleet
        logger.warning("demo inference: registry read failed", exc_info=True)
        raise CollectionError(
            f"the device registry could not be read ({exc}) — refusing to report "
            "an empty fleet, which is what an unreadable registry would look "
            "like.") from exc

    out: List[Dict[str, Any]] = []
    for row in rows:
        did = row.get("device_id") or row.get("id")
        if not did:
            continue
        entry = dict(row)
        entry["device_id"] = did
        try:
            entry["acaps"] = device_applications(ctx.git_repo, ctx.registry, did)
        except Exception:  # noqa: BLE001 — grounding is best-effort, never fatal
            entry["acaps"] = {}
        out.append(entry)
    return out


def _device_rule_facets(ctx: Any,
                        device_ids: List[str]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """``(facets, read_errors)``.

    ``facets`` maps ``device_id`` → its ``action_rules`` facet doc, or ``None``
    when there is **no snapshot to read**. ``read_errors`` maps ``device_id`` →
    why the read *failed*, and the two are kept apart on purpose: a permission,
    repository or parse failure is not the same fact as "this device has never
    been snapshotted", and folding one into the other tells the operator to fix
    the wrong thing. The graph reports each in its own terms.

    Reads exactly what ``wizard.py:30`` reads — the device's latest observation,
    falling back to its baseline. Never probes.
    """
    out: Dict[str, Any] = {}
    errors: Dict[str, str] = {}
    for did in device_ids:
        doc = None
        try:
            info = ctx.registry.get_device_info(did) or {}
            ref = info.get("latest_observed_sha") or info.get("baseline_sha")
            if ref:
                doc = ctx.git_repo.read_facet(did, "action_rules", ref)
        except Exception as exc:  # noqa: BLE001 — reported as a read error, not "no snapshot"
            logger.warning("demo inference: action_rules facet read failed for %s",
                           did, exc_info=True)
            errors[did] = f"{type(exc).__name__}: {exc}"
            continue
        out[did] = doc
    return out, errors


async def read_acs_rules(ctx: Any) -> Dict[str, Any]:
    """``{available, reason, rules}`` — the ACS rule anatomy, or why not.

    Degradation shape is identical to ``GET /api/acs/rules``: never an
    exception, always a reason. The live ``DeviceListFacade`` read is
    best-effort — losing it only costs the preferred ``api_device_id`` join
    path, and the Firebird ``DEVICE`` MAC still resolves every reference.
    """
    from admz.modules.acs_pro.config import acs_enabled
    from admz.modules.acs_pro.firebird import (firebird_available, firebird_enabled,
                                               rule_anatomy)

    if not acs_enabled():
        return {"available": False, "reason": ACS_DISABLED_REASON, "rules": []}
    if not firebird_enabled():
        return {"available": False, "reason": "Firebird reader disabled — ACS rule "
                                              "anatomy is unavailable.", "rules": []}
    ok, reason = firebird_available()
    if not ok:
        return {"available": False, "reason": reason, "rules": []}

    api_devices: List[Dict[str, Any]] = []
    join_note = ""
    try:
        from admz.modules.acs_pro.client import run_acs_op

        res = await run_acs_op(ctx.catalog, ctx.executors,
                               "DeviceListFacade:GetDeviceList", _LIST_RANGE)
        if res.get("success"):
            api_devices = (res.get("data") or {}).get("Devices") or []
        else:
            join_note = (f" (live device list unavailable: {res.get('message')} — "
                         "falling back to the Firebird DEVICE MAC)")
    except Exception as exc:  # noqa: BLE001 — the fallback join still works
        join_note = (f" (live device list unavailable: {exc} — falling back to the "
                     "Firebird DEVICE MAC)")

    try:
        rules = await asyncio.to_thread(rule_anatomy, None, api_devices)
    except Exception as exc:  # noqa: BLE001 — never crash a page on ACS internals
        logger.warning("demo inference: ACS rule anatomy read failed", exc_info=True)
        return {"available": False, "reason": f"ACS rule read failed: {exc}",
                "rules": []}
    return {"available": True, "reason": "ok" + join_note, "rules": rules,
            "api_device_count": len(api_devices)}


async def collect_graph(ctx: Any, *, include_acs: bool = True) -> Dict[str, Any]:
    """The fast path: registry + latest snapshots + one live ACS read → graph.

    Raises :class:`CollectionError` if the registry is unreadable. This is the
    layer that owns the clock, too: ``build_graph`` is pure and deterministic,
    so the wall-clock stamp is applied here.
    """
    devices = _registry_nodes(ctx)
    facets, facet_errors = _device_rule_facets(ctx, [d["device_id"] for d in devices])
    if include_acs:
        acs = await read_acs_rules(ctx)
    else:
        acs = {"available": False, "reason": "ACS read skipped by request",
               "rules": []}
    return graph_mod.build_graph(
        devices,
        device_rule_facets=facets,
        facet_read_errors=facet_errors,
        acs_rules=acs.get("rules") or [],
        acs={"available": acs["available"], "reason": acs["reason"]},
        generated_at=time.time(),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Runs
# ═══════════════════════════════════════════════════════════════════════════

async def run_fast(ctx: Any, store: InferenceRunStore, *, created_by: str = "",
                   include_acs: bool = True) -> InferenceRun:
    """Start, execute and finish a ``fast`` run inline — it takes seconds.

    A :class:`CollectionError` (today: an unreadable registry) lands here like
    any other failure: the run is recorded ``failed`` with the reason, which is
    what the button and the MCP tool render. It never becomes a ``complete``
    run over an empty fleet.
    """
    run = store.start(mode=MODE_FAST, created_by=created_by,
                      message="Reading the registry, the last snapshots and ACS…")
    try:
        graph = await collect_graph(ctx, include_acs=include_acs)
    except Exception as exc:  # noqa: BLE001 — a failed run is recorded, not raised
        logger.exception("demo inference run %s failed", run.id)
        store.fail(run.id, str(exc))
        failed = store.get(run.id)
        return failed if failed is not None else run
    done = store.finish(run.id, graph, message=describe(graph))
    return done if done is not None else run


async def run_survey(ctx: Any, store: InferenceRunStore, run_id: str, *,
                     register_new: bool = True, timeout: float = 5.0,
                     subnet: Optional[str] = None, proposal_store: Any = None,
                     include_weak: bool = True, principal: Any = None) -> None:
    """The background body of a ``survey`` run: discover → onboard → snapshot →
    collect, writing progress and terminal state onto the run row.

    Every phase is best-effort and reports itself: a discovery that finds
    nothing, an onboarding that can't authenticate, a snapshot that fails on
    some devices — none of them abort the run, because the fast path underneath
    still produces a graph from whatever *is* known. Only an unexpected error
    marks the run ``failed``.
    """
    total = len(SURVEY_PHASES)
    notes: List[str] = []
    try:
        # 1 ── discover (read-only network scan, existing 7-protocol orchestrator)
        store.progress(run_id, phase="discover", step=0, total=total,
                       message="Scanning the network for devices…")
        discovered = await _discover(timeout=timeout, subnet=subnet)
        notes.append(f"discovered {len(discovered)} device(s)")

        # 2 ── onboard the ones ADMZ doesn't know yet (existing #101 path)
        store.progress(run_id, phase="onboard", step=1, total=total,
                       message=f"Found {len(discovered)} device(s); resolving "
                               "credentials for any that are new…")
        added, provisioned = (await _onboard(ctx, discovered) if register_new
                              else ([], []))
        notes.append(f"onboarded {len(added)} new device(s)"
                     if register_new else "onboarding skipped by request")
        # Record the device writes HERE, not at the end of the run: the onboard
        # phase is where credentials were provisioned onto devices, and a later
        # phase failing must not lose that record (#199).
        _record_survey_writes(principal, run_id=run_id, subnet=subnet,
                              register_new=register_new, registered=added,
                              provisioned=provisioned)

        # 3 ── snapshot, so action_rules / applications facets exist to read
        device_ids = _all_device_ids(ctx)
        store.progress(run_id, phase="snapshot", step=2, total=total,
                       message=f"Snapshotting {len(device_ids)} device(s) so their "
                               "rules and apps can be read…")
        ok, failed = await _snapshot(ctx, device_ids)
        notes.append(f"snapshotted {ok}/{ok + failed} device(s)")

        # 4 ── the fast path over the now-populated state
        store.progress(run_id, phase="collect", step=3, total=total,
                       message="Building the evidence graph…")
        graph = await collect_graph(ctx)
        graph["survey"] = {"discovered": len(discovered), "onboarded": len(added),
                           "snapshotted": ok, "snapshot_failed": failed,
                           # The run row is the survey's own record, so it
                           # carries the same scope + writes the audit row does
                           # — it used to hold counts only (#199).
                           "subnet": subnet, "registered": sorted(added),
                           "provisioned": sorted(provisioned),
                           "notes": notes}
        run = store.finish(run_id, graph,
                           message=describe(graph) + " · " + "; ".join(notes))
        # A deep survey exists to produce the inventory, so it clusters too —
        # best-effort: the graph is already safely on the record, and a
        # clustering failure must not turn a good survey into a failed run.
        if proposal_store is not None and run is not None:
            try:
                persist_proposals(ctx, run, proposal_store,
                                  include_weak=include_weak)
            except Exception:  # noqa: BLE001
                logger.warning("demo inference survey %s: clustering failed",
                               run_id, exc_info=True)
    except asyncio.CancelledError:
        store.fail(run_id, "run cancelled (server shutting down)")
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("demo inference survey %s failed", run_id)
        store.fail(run_id, str(exc))


#: Keys a survey may record about the devices it WROTE to (#199).
#:
#: An ALLOW-LIST, and it must stay one — the same discipline as
#: ``audit.OUTCOME_IDENTITY_KEYS`` (#246) and the approve-row fields (#276).
#: :func:`_survey_audit_fields` filters through it, so adding a key to that dict
#: without adding it here silently drops the key rather than leaking it, and a
#: test pins that.
#:
#: Identifiers and the requested scope ONLY. Never the discovered device dicts
#: (host / mac / model / firmware), and never anything out of onboarding's
#: result: ``provision_factory_default`` **writes a credential**, and an audit
#: log that is never pruned (there is no DELETE in ``audit.py``) is the last
#: place it should be echoed.
_SURVEY_AUDIT_KEYS = (
    "run", "subnet", "register_new",
    "registered_count", "provisioned_count",
    "registered", "provisioned",
)


def _survey_audit_fields(*, run_id: str, subnet: Optional[str],
                         register_new: bool, registered: List[str],
                         provisioned: List[str]) -> Dict[str, Any]:
    """What a survey wrote, for the audit row — allow-listed.

    ``subnet`` is recorded AS REQUESTED. ``None`` means the caller did not name
    one and the ARP scanner auto-detects the local ``/24``; recording that
    honestly is more useful than inventing the resolved CIDR here, which is
    derived several layers down and could differ from what was actually scanned.
    """
    fields = {
        "run": run_id,
        "subnet": subnet if subnet else "(none given — local /24 auto-detected)",
        "register_new": bool(register_new),
        "registered_count": len(registered),
        "provisioned_count": len(provisioned),
        "registered": sorted(registered),
        "provisioned": sorted(provisioned),
    }
    return {k: v for k, v in fields.items() if k in _SURVEY_AUDIT_KEYS}


def _record_survey_writes(principal: Any, **kw: Any) -> None:
    """One audit row naming the scope and the devices a survey wrote to.

    Called right after the onboard phase rather than at the end of the run, on
    purpose: a later phase failing (snapshot, collect, clustering) must not lose
    the record of writes that already reached devices. Same reasoning as #209 —
    never let the record of work depend on later work succeeding.

    Never raises: an audit failure must not turn a completed survey into a
    failed one (house convention, cf. ``routes/github_app.py::_audit``).
    """
    try:
        from admz.audit import record_event
        record_event(principal, "demo.survey_devices", resource="demos:inference",
                     details=_survey_audit_fields(**kw))
    except Exception:  # noqa: BLE001
        logger.warning("demo inference survey: could not record device writes",
                       exc_info=True)


async def _discover(*, timeout: float, subnet: Optional[str]) -> List[Any]:
    try:
        from admz.discovery import discover_devices

        return await discover_devices(timeout=timeout, axis_only=True, subnet=subnet)
    except Exception:  # noqa: BLE001 — a failed scan just means nothing new
        logger.warning("demo inference survey: discovery failed", exc_info=True)
        return []


async def _onboard(ctx: Any, discovered: List[Any]) -> tuple:
    """Register devices the fleet has but ADMZ doesn't, then run the standard
    credential onboarding on each (stored-verify → needsetup → fleet pair →
    capture widget). Reuses ``onboarding.onboard_device_credentials`` verbatim.

    Returns ``(registered, provisioned)`` — the ids added to the registry, and
    the subset that had an admin account **created on the device**. The second
    list is the whole point: this used to discard the onboarding result, so
    nothing in the system knew which devices a survey had written to (#199).
    """
    from admz.device_registry import canonical_mac
    from admz.onboarding import PROVISIONED, onboard_device_credentials

    try:
        known = {canonical_mac(d.get("mac_address") or d.get("device_id") or "")
                 for d in (ctx.registry.list_devices() or [])}
    except Exception:  # noqa: BLE001
        return [], []

    added: List[str] = []
    provisioned: List[str] = []
    for dev in discovered:
        try:
            info = dev.to_registry_dict() if hasattr(dev, "to_registry_dict") else dict(dev)
        except Exception:  # noqa: BLE001
            continue
        mac = canonical_mac(info.get("mac_address") or "")
        if not mac or mac in known:
            continue
        device_id = info.get("device_id") or mac
        try:
            ctx.registry.add_device(device_id, info)
            known.add(mac)
            added.append(device_id)
        except Exception:  # noqa: BLE001 — a device we can't register is skipped
            logger.info("demo inference survey: could not register %s", device_id,
                        exc_info=True)
            continue
        try:
            result = await onboard_device_credentials(
                device_id=device_id, registry=ctx.registry, catalog=ctx.catalog,
                executors=ctx.executors)
            # PROVISIONED is the one status that means a root admin account was
            # CREATED on the device (onboarding.py -> provision_factory_default).
            # The other statuses only read, or write to the registry.
            if (result or {}).get("status") == PROVISIONED:
                provisioned.append(device_id)
        except Exception:  # noqa: BLE001 — onboarding never fails a survey
            logger.info("demo inference survey: onboarding %s failed", device_id,
                        exc_info=True)
    return added, provisioned


def _all_device_ids(ctx: Any) -> List[str]:
    try:
        return [d.get("device_id") for d in (ctx.registry.list_devices() or [])
                if d.get("device_id")]
    except Exception:  # noqa: BLE001
        return []


async def _snapshot(ctx: Any, device_ids: List[str]) -> tuple:
    if not device_ids:
        return 0, 0
    try:
        results = await ctx.snapshot_engine.snapshot_fleet(
            device_ids=device_ids, message="demo inference deep survey")
    except Exception:  # noqa: BLE001 — a failed snapshot still leaves old facets
        logger.warning("demo inference survey: snapshot_fleet failed", exc_info=True)
        return 0, len(device_ids)
    # ``snapshot_fleet`` gathers with ``return_exceptions=True``, so a per-device
    # failure arrives as the exception object itself; a DeviceSnapshot reports
    # through ``status`` (SnapshotStatus.SUCCESS / PARTIAL / FAILED).
    ok = 0
    for res in results:
        if isinstance(res, BaseException):
            continue
        status = getattr(getattr(res, "status", None), "value", None)
        if status != "failed":
            ok += 1
    return ok, len(results) - ok


# ═══════════════════════════════════════════════════════════════════════════
# Proposals (#124 slice 3) — cluster the graph, persist the candidates
# ═══════════════════════════════════════════════════════════════════════════

#: How far back the best-effort firing history looks. Matches the score's stale
#: band — anything older contributes 0 either way, so reading it is wasted work.
FIRING_WINDOW_SECONDS = 30 * 86400.0


def collect_firings(ctx: Any, graph: Dict[str, Any]) -> Dict[str, float]:
    """``{rule_key: last-seen epoch}`` — **best effort**, from the event log.

    A rule "fired" is observed the same way the demo readiness panel observes a
    signal: its trigger topic appearing on its trigger device in ADMZ's own
    event log (``events/store.py:225``). That covers the ``device_event_direct``
    majority with zero ACS touch and zero device probe.

    Everything about this is optional. Event capture may be off, the store may
    be empty, a rule may have no topic — in every case the key is simply absent
    and :func:`admz.demos.inference.cluster.firing_recency` degrades the term to
    0 with a ``firing_unknown`` flag. A scoring term whose data source is the
    most fragile input in the system must never be able to fail the run.
    """
    store = getattr(ctx, "event_store", None)
    if store is None:
        return {}
    since_ms = int((time.time() - FIRING_WINDOW_SECONDS) * 1000)
    out: Dict[str, float] = {}
    for rule in graph.get("rules") or []:
        key = rule.get("rule_key")
        devices = rule.get("trigger_device_ids") or rule.get("device_ids") or []
        for topic in rule.get("topics") or []:
            for did in devices:
                try:
                    got = store.activity_since(since_ms=since_ms, device_id=did,
                                               type_filter=topic)
                except Exception:  # noqa: BLE001 — best effort, always
                    continue
                last = got.get("last_ms")
                if last and (key not in out or last / 1000.0 > out[key]):
                    out[key] = last / 1000.0
    return out


def persist_proposals(ctx: Any, run, proposal_store, *,
                      include_weak: bool = True) -> Dict[str, Any]:
    """Cluster a finished run's graph and write the proposals it yields.

    Respects two memories so a re-run is a *diff*, not a re-ask:

    * a member set the operator already **confirmed or dismissed** is not
      proposed again (it is counted and named in the report instead), and
    * a still-open proposal for a member set this run re-proposes is marked
      ``superseded`` — the newer evidence replaces it without erasing it.
    """
    from admz.demos.inference import cluster
    from admz.demos.inference.proposals import DemoProposal

    graph = run.graph or {}
    firings = {}
    try:
        firings = collect_firings(ctx, graph)
    except Exception:  # noqa: BLE001 — see collect_firings' docstring
        logger.warning("demo inference: firing history unavailable", exc_info=True)

    result = cluster.propose(graph, run_id=run.id, include_weak=include_weak,
                             firings=firings, now=time.time())

    decided = proposal_store.decided_content_keys()
    written: List[Any] = []
    already: List[Dict[str, Any]] = []
    for draft in result["proposals"]:
        prior = decided.get(draft["content_key"])
        if prior is not None:
            already.append({"content_key": draft["content_key"],
                            "name": prior.name, "status": prior.status,
                            "demo_id": prior.demo_id,
                            "device_ids": draft["members"],
                            "reason": (f"these devices were already "
                                       f"{prior.status} as '{prior.name}'")})
            continue
        proposal = DemoProposal(
            id=draft["id"], run_id=run.id, content_key=draft["content_key"],
            name=draft["name"], proposed_name=draft["name"], purpose="",
            device_ids=draft["members"],
            roles=draft["roles"], rules=draft["rules"],
            evidence=draft["evidence"],
            suggested_owned_keys=draft["suggested_owned_keys"],
            score=draft["score"], confidence=draft["confidence"],
            flags=draft["flags"], overlaps=draft["overlaps"],
            score_breakdown=draft["score_breakdown"], devices=draft["devices"],
        )
        proposal_store.supersede_open(proposal.content_key, except_id=proposal.id)
        written.append(proposal_store.upsert(proposal))

    report = dict(result["report"])
    report["already_decided"] = already
    report["written"] = len(written)
    report["cluster_params"] = result["params"]
    return {"proposals": written, "report": report}


async def infer_demos(ctx: Any, run_store: InferenceRunStore, proposal_store, *,
                      created_by: str = "", include_acs: bool = True,
                      include_weak: bool = True) -> Dict[str, Any]:
    """The whole slice-3 move: collect → cluster → persist, in one fast call.

    A failed collection is a failed *run*, recorded with its reason, never an
    exception thrown at the caller — the same contract slice 2 established.
    """
    run = await run_fast(ctx, run_store, created_by=created_by,
                         include_acs=include_acs)
    if run.status == "failed":
        return {"run": run, "proposals": [], "report": {"error": run.error}}
    out = persist_proposals(ctx, run, proposal_store, include_weak=include_weak)
    out["run"] = run
    return out


def describe(graph: Dict[str, Any]) -> str:
    """One line for the run header / the button's result banner."""
    s = (graph or {}).get("summary") or {}
    by_source = s.get("rules_by_source") or {}
    parts = [
        f"{s.get('device_count', 0)} device(s)",
        f"{by_source.get('acs', 0)} ACS rule(s)",
        f"{by_source.get('device', 0)} device rule(s)",
        f"{s.get('edge_count', 0)} edge(s)",
    ]
    if s.get("unresolved_count"):
        parts.append(f"{s['unresolved_count']} unresolved reference(s)")
    if not ((s.get("acs") or {}).get("available")):
        parts.append("ACS unavailable")
    return " · ".join(parts)


def summary_only(graph: Dict[str, Any]) -> Dict[str, Any]:
    """The agent-facing digest: the summary plus one line per rule and edge —
    everything needed to reason about the fleet without the full node dump."""
    s = (graph or {}).get("summary") or {}
    return {
        "summary": s,
        "acs": (graph or {}).get("acs"),
        "devices": [
            {"device_id": n["device_id"], "name": n["name"], "model": n["model"],
             "tags": n["tags"],
             "apps": [a["name"] for a in n["acaps"]],
             "distinctive_apps": [a["name"] for a in n["acaps"] if a["distinctive"]]}
            for n in (graph or {}).get("nodes") or []
        ],
        "rules": [
            {"source": r["source"], "rule_id": r["rule_id"], "name": r["name"],
             "enabled": r["enabled"], "device_ids": r["device_ids"],
             "topics": r["topics"], "actions": r["action_kinds"],
             "names_only": r["names_only"],
             "observability": (r.get("observability") or {}).get("verdict"),
             "app_grounding": [g["detail"] for g in (r.get("app_grounding") or [])]}
            for r in (graph or {}).get("rules") or []
        ],
        "edges": [
            {"id": e["id"], "a": e["a"], "b": e["b"], "weight": e["weight"],
             "class": e["class"], "corroborating": e["corroborating"],
             "why": [i["detail"] for i in e["evidence"]]}
            for e in (graph or {}).get("edges") or []
        ],
        "unresolved": (graph or {}).get("unresolved") or [],
        "unattached_rules": (graph or {}).get("unattached_rules") or [],
    }


__all__ = ["collect_graph", "read_acs_rules", "run_fast", "run_survey",
           "describe", "summary_only", "CollectionError", "MODE_FAST",
           "MODE_SURVEY", "collect_firings", "persist_proposals", "infer_demos"]
