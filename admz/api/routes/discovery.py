"""REST routes for network discovery."""

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from admz.api.context import AppContext, get_context
from admz.discovery import discover_devices as run_network_discovery
from admz.validators import validate_scan_subnet

logger = logging.getLogger(__name__)

router = APIRouter()


class DiscoverRequest(BaseModel):
    timeout: float = 5.0
    axis_only: bool = False
    subnet: Optional[str] = None
    enable_mdns: bool = True
    enable_ssdp: bool = True
    enable_onvif: bool = True
    enable_arp: bool = True
    enable_ping: bool = False
    enable_http_probe: bool = True
    enable_snmp: bool = True
    snmp_community: str = "public"


class RegisterDiscoveredRequest(BaseModel):
    device_id: str
    ip_address: str
    mac_address: Optional[str] = None
    model: Optional[str] = None
    hostname: Optional[str] = None
    device_type: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


@router.post("/discovery/scan")
async def scan_network(
    request: Request,
    req: DiscoverRequest,
    ctx: AppContext = Depends(get_context),
):
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    # A bad subnet is a 400, not a 500 (#199). The authoritative check lives in
    # `discover_devices`; this only chooses the status code and surfaces the
    # reason, so the two cannot disagree about what is valid.
    try:
        validate_scan_subnet(req.subnet)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    devices = await run_network_discovery(
        timeout=req.timeout,
        axis_only=req.axis_only,
        subnet=req.subnet,
        enable_mdns=req.enable_mdns,
        enable_ssdp=req.enable_ssdp,
        enable_onvif=req.enable_onvif,
        enable_arp=req.enable_arp,
        enable_ping=req.enable_ping,
        enable_http_probe=req.enable_http_probe,
        enable_snmp=req.enable_snmp,
        snmp_community=req.snmp_community,
    )
    record_event(principal, "discovery.scan",
                 details={"subnet": req.subnet, "axis_only": req.axis_only,
                          "count": len(devices)})
    return {
        "count": len(devices),
        "devices": [d.to_registry_dict() for d in devices],
    }


@router.post("/discovery/register")
async def register_discovered(
    request: Request,
    req: RegisterDiscoveredRequest,
    ctx: AppContext = Depends(get_context),
):
    """Register a discovered device — **registry add only, no onboarding**.

    This is the separated half of the pair #366 asked about. The MCP tool of
    almost the same name (``register_discovered_device``) registers *and*
    onboards in one call, which suits an agent; this route suits a UI that will
    show the capture widget next, which is what the response says to do.

    The difference is deliberate. It is written down here because it was not
    written down anywhere for a long time, and the MCP tool's description
    actually described *this* route's behaviour while its handler did the other
    thing (#366).
    """
    from admz.audit import record_event
    from admz.auth import get_current_principal

    principal = await get_current_principal(request)
    resource = f"device:{req.device_id}"
    device_info = {
        "host": req.ip_address,
        "ip_address": req.ip_address,
        "mac_address": req.mac_address or "",
        "model": req.model or "",
        "hostname": req.hostname or "",
        "nickname": req.hostname or "",
        "device_type": req.device_type or "unknown",
        "tags": req.tags,
    }
    try:
        ctx.registry.add_device(req.device_id, device_info)
    except Exception as e:
        record_event(principal, "discovery.register", resource=resource,
                     success=False, error_message=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    record_event(principal, "discovery.register", resource=resource,
                 details={"ip": req.ip_address, "model": req.model})
    return {
        "message": (
            f"Device '{req.device_id}' registered. Use the capture flow "
            "to set credentials."
        ),
        "device_id": req.device_id,
    }


# ── The console's discovery widget (ADR-0072) ────────────────────────────


class AddDiscoveredRequest(BaseModel):
    device_ids: List[str] = Field(default_factory=list)


def _owned_scan(scan_id: str, principal: Any):
    """The scan, only for the principal that ran it. Another principal's scan
    and an unknown one look the same: 404."""
    from admz.discovery.scan_store import discovery_scans

    scan = discovery_scans.get_scan(scan_id)
    if scan is None or scan.principal != getattr(principal, "name", None):
        raise HTTPException(status_code=404, detail="scan not found")
    return scan


def _add_policy(principal: Any, scan: Any) -> dict:
    """What the widget needs to know before the operator clicks Add.

    The level is the one ``gate_scan_write`` will resolve, and ``may_approve``
    is the decision the approval gate will make — both read from the same
    functions, so the widget cannot promise what the gate then refuses.
    """
    from admz import operations
    from admz.api.routes.confirm import approval_decision
    from admz.discovery.candidates import MAX_ADD_BATCH, MAX_SCAN_AGE_SECONDS
    from admz.discovery.gated import add_consequence
    from admz.fleet_settings import fleet_settings

    level = operations.resolve_confirmation("service-affecting")
    # Same fallback as the approval card: with no confirmation password set,
    # a url_and_password session is approved without one.
    needs_password = (level == "url_and_password"
                      and bool(fleet_settings.get("confirm_password_hash")))
    may_approve, reason = approval_decision(principal)
    age = scan.age_seconds()
    return {
        "confirmation_level": level,
        "needs_password": needs_password,
        "may_approve": may_approve,
        "not_approver_reason": "" if may_approve else reason,
        "consequence": add_consequence(),
        "age_s": int(age),
        "max_age_s": MAX_SCAN_AGE_SECONDS,
        "stale": age > MAX_SCAN_AGE_SECONDS,
        "max_batch": MAX_ADD_BATCH,
    }


@router.get("/discovery/scans/{scan_id}")
async def get_discovery_scan(
    request: Request,
    scan_id: str,
    ctx: AppContext = Depends(get_context),
):
    """A recorded scan with live registration state (FR-DISC-010)."""
    from admz.auth import get_current_principal
    from admz.discovery import candidates

    principal = await get_current_principal(request)
    scan = _owned_scan(scan_id, principal)
    views = candidates.annotate(
        scan.devices, candidates.registered_index(ctx.registry))
    return {
        "scan_id": scan.scan_id,
        "subnet": scan.subnet,
        "axis_only": scan.axis_only,
        "created_at": scan.created_at,
        "count": len(views),
        **candidates.summary_counts(views),
        "devices": views,
        "add_policy": _add_policy(principal, scan),
    }


@router.post("/discovery/scans/{scan_id}/add")
async def add_discovered_devices(
    request: Request,
    scan_id: str,
    req: AddDiscoveredRequest,
    ctx: AppContext = Depends(get_context),
):
    """Open ONE approval for the selected devices (FR-DISC-011).

    Never approves: the widget sends the returned token straight to
    ``POST /api/chat/confirm/{token}``, so the approver check, the password,
    the per-token lockout, the audit row and the console note are the
    approval gate's own. A retry reuses this token.
    """
    from admz.audit import record_event
    from admz.auth import get_current_principal
    from admz.csrf import check_same_origin
    from admz.discovery import candidates
    from admz.discovery.gated import (
        ACTION_ADD_DISCOVERED, add_reason, gate_scan_write,
    )

    # CSRF first, before any side effect: the scan id has been in the model's
    # context and the event stream, so it is not a secret.
    check_same_origin(request)
    principal = await get_current_principal(request)
    scan = _owned_scan(scan_id, principal)

    if scan.age_seconds() > candidates.MAX_SCAN_AGE_SECONDS:
        raise HTTPException(status_code=409, detail=(
            "This scan is more than an hour old — addresses may have changed. "
            "Ask for a new scan and add from that one."))

    ids: List[str] = []
    for raw in req.device_ids:
        device_id = candidates.device_identity(raw)
        if not device_id:
            raise HTTPException(status_code=400, detail=(
                "Every selected id must be a device id from this scan."))
        if device_id not in ids:
            ids.append(device_id)
    if not ids:
        raise HTTPException(status_code=400, detail="Select at least one device.")
    if len(ids) > candidates.MAX_ADD_BATCH:
        raise HTTPException(status_code=400, detail=(
            f"At most {candidates.MAX_ADD_BATCH} devices can be added at once."))

    # All-or-nothing, as for a batch removal (ADR-0069): one device that
    # cannot be added rejects the request and nothing is created.
    index = candidates.registered_index(ctx.registry)
    rejected = []
    devices = []
    for device_id in ids:
        record = candidates.find_record(scan.devices, device_id)
        if record is None:
            rejected.append({"device_id": device_id, "reason": "not in this scan"})
            continue
        blocker = candidates.add_blocker(record, index.get(device_id, ""))
        if blocker:
            rejected.append({"device_id": device_id, "reason": blocker})
            continue
        # From the scan row, never from the request body.
        info = dict(record.get("registry_info") or {})
        devices.append({
            "device_id": device_id,
            "host": info.get("host") or record.get("ip_address") or "",
            "model": record.get("model") or "",
            "registry_info": info,
        })
    if rejected:
        raise HTTPException(status_code=400, detail={
            "error": "Nothing was added: some selected devices cannot be added.",
            "rejected": rejected,
        })

    from admz.api.confirm_store import ConfirmStatus, confirm_store
    from admz.discovery.scan_store import discovery_scans

    # The same selection again reuses its pending session: the password
    # lockout counts failures per token, so a fresh token per attempt would
    # reset it.
    add_key = ",".join(sorted(ids))
    if scan.add_token and scan.add_key == add_key:
        pending = confirm_store.get_session(scan.add_token)
        if pending is not None and pending.effective_status == ConfirmStatus.PENDING:
            return _pending_response(pending)

    target = ids[0] if len(ids) == 1 else "multiple"
    env = gate_scan_write(
        ACTION_ADD_DISCOVERED, target,
        {"device_ids": ids, "scan_id": scan.scan_id, "devices": devices},
        add_reason(devices),
    )
    token = env["confirm_token"]
    discovery_scans.remember_add(scan.scan_id, principal.name, add_key, token)
    try:
        from admz.chatbot.sessions import chat_sessions

        if scan.add_token and scan.add_token != token:
            # A new selection supersedes the old session. Unlinked, it stays
            # out of the conversation — no re-pinned card after a reload, no
            # note — and expires on its own; the widget never showed its URL.
            chat_sessions.pop_action_link(scan.add_token)
        if scan.conversation_id:
            # So the approval writes its [console] note into the conversation
            # the scan came from, and a reload re-pins a still-pending card.
            chat_sessions.link_action(
                token, principal.name, scan.conversation_id, "confirm",
                label=ACTION_ADD_DISCOVERED)
    except Exception:  # noqa: BLE001 — a missing note never blocks an add
        logger.warning("could not link the add approval to its conversation",
                       exc_info=True)
    record_event(principal, "discovery.add_requested",
                 resource=f"discovery_scan:{scan.scan_id[:8]}",
                 details={"count": len(ids), "device_ids": ",".join(ids)})
    return _pending_response(confirm_store.get_session(token))


def _pending_response(session: Any) -> dict:
    return {
        "status": "pending",
        "token": session.token,
        "confirm_url": f"/confirm/{session.token}",
        "confirmation_level": session.confirmation_level,
        "danger_description": session.danger_description,
    }
