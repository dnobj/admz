"""
Web routes for out-of-band credential capture.

GET  /capture/{token}   → render the credential entry form
POST /capture/{token}   → save credentials and show confirmation
GET  /api/capture        → create a new capture session (JSON)
GET  /api/capture/{token}/status → poll session status (JSON)
"""

import asyncio
import logging

from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from admz import entry_credentials
from admz.api.capture import (
    KIND_ACCOUNT,
    KIND_ROOT_ADOPT,
    capture_store,
    CaptureStatus,
)

#: Ceiling on the whole authenticate-then-adopt sequence (FR-CRED-014).
#:
#: Bounded so ADMZ chooses the ceiling rather than having a reverse proxy
#: truncate it mid-write: ``docs/DEPLOYMENT_WINDOWS.md`` documents no proxy
#: timeout, so the real limit today is whatever nginx (60 s) or IIS ARR (120 s)
#: defaults to. Typical cost is 1-3 s (a TCP preflight, one strict credential
#: confirm, one add-user); the pathological case is ~25-45 s.
#:
#: On expiry the outcome is genuinely INDETERMINATE — the add-user may have
#: landed — so it is reported as ``unconfirmed``, never as success, and nothing
#: is stored.
_ADOPT_DEADLINE_SECONDS = 45.0
from admz.audit import record_event
from admz.device_registry import DeviceRegistry
from admz.exceptions import DeviceNotFoundError, BackendError
from admz.fleet_settings import fleet_settings
from admz.csrf import check_same_origin
from admz.rate_limit import rate_limiter, client_key_from_request
from admz.setting_policy import is_llm_writable


router = APIRouter()

template_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(template_dir))
from admz.api.templating import configure as _configure_templates  # noqa: E402
_configure_templates(templates)


def get_registry() -> DeviceRegistry:
    from admz.api.main import registry
    if registry is None:
        raise HTTPException(status_code=503, detail="Registry not initialized")
    return registry


# ── JSON API endpoints (used by MCP tool) ─────────────────────────────────

@router.post("/api/capture", tags=["capture"])
async def create_capture_session(
    device_id: str,
    account_id: str = "default",
    account_type: str = "service",
    purpose: str = "",
    registry: DeviceRegistry = Depends(get_registry),
):
    """
    Create a credential capture session and return its URL.

    The URL can be given to a user to enter credentials out of band.
    """
    # Verify the device exists
    if not registry.device_exists(device_id):
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")

    session = capture_store.create_session(
        device_id=device_id,
        account_id=account_id,
        account_type=account_type,
        purpose=purpose,
    )

    return {
        "token": session.token,
        "url": f"/capture/{session.token}",
        "device_id": device_id,
        "account_id": account_id,
        "expires_in_seconds": int(session.ttl),
    }


@router.get("/api/capture/{token}/status", tags=["capture"])
async def capture_status(token: str):
    """
    Check the status of a capture session.

    Returns status only — never returns credentials.
    """
    session = capture_store.get_session(token)
    if session is None:
        return {"status": "expired_or_not_found"}

    # `kind` and `outcome` (FR-CRED-014) because this endpoint is polled after
    # the POST has gone, and for a root-adopt session "completed" alone would be
    # read as "the credential was saved" — which is exactly what did not happen.
    return {
        "status": session.effective_status.value,
        "device_id": session.device_id,
        "account_id": session.account_id,
        "kind": session.kind,
        "outcome": session.outcome,
    }


# ── Web form endpoints (opened in user's browser) ─────────────────────────

@router.get("/capture/{token}", response_class=HTMLResponse, tags=["capture"])
async def capture_form(
    request: Request,
    token: str,
    registry: DeviceRegistry = Depends(get_registry),
):
    """Render the credential capture form for a valid token."""
    session = capture_store.get_session(token)

    if session is None:
        return templates.TemplateResponse(
            request,
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    if session.effective_status == CaptureStatus.COMPLETED:
        # FR-CRED-014: a spent ROOT-ADOPT token must not render "Credentials
        # Saved" — nothing about the typed password was saved. The persisted
        # `outcome` is what makes an honest answer possible here, long after the
        # POST that did the work has gone.
        if session.kind == KIND_ROOT_ADOPT:
            done = {
                "adopted": "ADMZ now has its own account",
                "adopt_failed": "ADMZ got in, but could not create its account",
                "unconfirmed": "ADMZ could not confirm the result",
                "orphaned": "ADMZ could not finish safely",
            }
            outcome = session.outcome or "unconfirmed"
            try:
                device_info = registry.get_device_info(session.device_id)
            except DeviceNotFoundError:
                device_info = {"device_id": session.device_id}
            return _adopt_done(
                request, outcome=outcome,
                heading=done.get(outcome, "This link has already been used"),
                device_label=device_info.get("nickname") or session.device_id,
                entry_username="",
                reason="This link has already been used and cannot be reused.")

        ctx = {
            "request": request,
            "title": "Credentials Saved",
            "device_id": session.device_id,
            "account_id": session.account_id,
        }
        if session.is_batch:
            ctx["device_ids"] = session.all_device_ids
            ctx["is_batch"] = True
        return templates.TemplateResponse(request, "capture_done.html", ctx)

    if session.effective_status == CaptureStatus.EXPIRED:
        return templates.TemplateResponse(
            request,
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    # Build device info for display
    is_batch = session.is_batch
    devices: List[Dict] = []
    for did in session.all_device_ids:
        try:
            info = registry.get_device_info(did)
            info["device_id"] = did
        except DeviceNotFoundError:
            info = {"device_id": did}
        devices.append(info)

    # FR-CRED-014: a root-adopt session gets its OWN form. `capture_form.html`
    # must never render for this kind — its note band says "These credentials
    # are stored encrypted", which is false when the typed password is used once
    # and then discarded, and it is the most misleading sentence this flow could
    # show an operator about to type a break-glass credential.
    if session.kind == KIND_ROOT_ADOPT:
        return _root_form(request, token, session,
                          devices[0] if devices else {"device_id": session.device_id})

    return templates.TemplateResponse(
        request,
        "capture_form.html",
        {
            "request": request,
            "title": "Enter Credentials",
            "token": token,
            "session": session,
            "device": devices[0] if devices else {},
            "devices": devices,
            "is_batch": is_batch,
        },
    )


def _note_capture_to_chat(
    token: str, saved: List[str], promotion: Optional[Dict[str, str]] = None
) -> None:
    """Tell the originating chat conversation (if any) that credentials
    were stored — the model otherwise keeps asking the user to "let me
    know once you've set the password". Device ids only; NEVER the
    password or username. Best-effort: a note failure must not affect
    the capture. ``promotion`` (FR-CRED-012) adds what happened to the
    entry list, so the model knows the fleet's list changed — or did not."""
    try:
        from admz.chatbot.sessions import chat_sessions

        link = chat_sessions.pop_action_link(token)
        if link is not None:
            chat_sessions.append_event(
                link["principal"], link["conversation_id"],
                "[console] The user submitted credentials for device(s) "
                f"{', '.join(saved)} via the secure capture form; they were "
                "stored server-side. (The password is not available in this "
                "conversation.)" + _promotion_sentence(promotion),
            )
    except Exception:  # noqa: BLE001 - never break a capture on a note
        logger.debug("chat capture note failed for %s", token, exc_info=True)


def _promotion_sentence(promotion: Optional[Dict[str, str]]) -> str:
    """One sentence for the chat note; no username, no password."""
    if not promotion:
        return ""
    if promotion.get("result") == "promoted":
        return " The user also promoted it to the fleet's entry list (FR-CRED-012)."
    if promotion.get("result") == "duplicate":
        return " It was already on the fleet's entry list."
    return f" Promotion to the entry list was refused: {promotion.get('reason', '')}."


def _promote_if_asked(
    requested: bool, username: str, password: str, saved: List[str], *,
    principal: object = None,
) -> Optional[Dict[str, str]]:
    """Promote the captured credential to the fleet's entry list (FR-CRED-012).

    A **scope promotion**: the secret becomes something ADMZ will offer to
    every device it onboards from now on. So it is opt-in per submission,
    audited as its own event — with the username and the device ids only,
    never the password — and a refusal (the cap, the prompt-always posture)
    leaves the capture that just succeeded exactly as it was.

    Nothing raised here reaches the operator: the capture has already
    succeeded and consumed its token, so an internal failure is logged and
    reported as a refusal with a fixed reason, never a 500. A duplicate is
    reported on the done page and not audited — nothing changed, and the
    capture's own trail already names the device. ``principal`` is the
    signed-in operator when the request carried one, so a fleet-wide scope
    change is attributed to whoever made it.
    """
    if not requested:
        return None
    label = f"promoted from {saved[0]}" if saved else "promoted"
    if len(saved) > 1:
        label += f" (+{len(saved) - 1})"
    try:
        added = entry_credentials.add_entry_credential(username, password, label=label)
    except ValueError as exc:
        return _promotion_refused(principal, username, saved, str(exc))
    except Exception:  # noqa: BLE001 - the capture already succeeded; never 500 it
        logger.warning("entry-credential promotion failed for %s", username, exc_info=True)
        return _promotion_refused(principal, username, saved, "internal error; see the server log")
    if not added:
        return {"result": "duplicate", "username": username, "reason": "already on the list"}
    try:
        record_event(
            principal, "entry_credential.promoted",
            resource="fleet_settings:entry_credentials",
            details={"username": username, "device_ids": list(saved), "label": label},
        )
    except Exception:  # noqa: BLE001 - an audit failure is logged, not surfaced
        logger.warning("entry-credential promotion audit failed for %s", username, exc_info=True)
    return {"result": "promoted", "username": username, "reason": ""}


def _promotion_refused(principal: object, username: str, saved: List[str], reason: str) -> Dict[str, str]:
    try:
        record_event(
            principal, "entry_credential.promotion_refused",
            resource="fleet_settings:entry_credentials",
            details={"username": username, "device_ids": list(saved), "reason": reason},
            success=False, error_message=reason,
        )
    except Exception:  # noqa: BLE001 - an audit failure is logged, not surfaced
        logger.warning("entry-credential refusal audit failed for %s", username, exc_info=True)
    return {"result": "refused", "username": username, "reason": reason}


@router.post("/capture/{token}", response_class=HTMLResponse, tags=["capture"])
async def capture_submit(
    request: Request,
    token: str,
    username: str = Form(...),
    password: str = Form(...),
    promote: bool = Form(False),
    entry_action: str = Form(""),
    registry: DeviceRegistry = Depends(get_registry),
):
    """Process the submitted credentials, by session **kind**.

    Two genuinely different operations share this route because they share the
    token, the TTL, the single-use completion and the chat-note chain — see
    ``admz/api/capture.py``'s ``KIND_*`` for why a column beat a second table.
    They do NOT share a body: ``account`` stores what was typed, and
    ``root_adopt`` (FR-CRED-014) uses it once and stores something else. Keeping
    today's body verbatim in :func:`_submit_account_capture` is what lets its
    contract — including "stored nothing is a 500" — stay exactly as it was.

    ``promote`` is the FR-CRED-012 checkbox — a browser sends ``on`` only when
    the human ticked it, and the bool form field reads ``off``/``false``/``0``
    as no. A session's ``propose_promote`` is never read here: the flag
    reaching the store requires the form submission, not the tool argument.
    ``entry_action`` is the root-adopt form's required radio group and is
    ignored by the account path.
    """
    # CSRF (#3). Must precede every side effect, including the rate-limit
    # counter — a cross-site POST should not be able to consume an operator's
    # capture budget either.
    check_same_origin(request)
    # Phase 4 stretch: per-IP rate limit. The token is 256-bit and
    # single-use, so brute force isn't the threat — overwrite races
    # and accidental double-submits are. 10 attempts then 10/minute.
    if not rate_limiter.check("capture", client_key_from_request(request)):
        raise HTTPException(
            status_code=429,
            detail="Too many capture attempts from this address. Try again in a few minutes.",
        )

    session = capture_store.get_session(token)

    if session is None or session.effective_status != CaptureStatus.PENDING:
        # A session whose `kind` this build does not recognise reads as None
        # (capture.py fails closed), so it lands here as "expired" rather than
        # falling through to the path that STORES the password.
        return templates.TemplateResponse(
            request,
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    if session.kind == KIND_ROOT_ADOPT:
        return await _submit_root_adopt(
            request, token, session, username, password, entry_action, registry,
        )
    return await _submit_account_capture(
        request, token, session, username, password, promote, registry,
    )


async def _submit_account_capture(
    request: Request,
    token: str,
    session: Any,
    username: str,
    password: str,
    promote: bool,
    registry: DeviceRegistry,
):
    """Store the typed credential as the device's own account — UNCHANGED.

    Moved verbatim out of ``capture_submit`` so the root-adopt path could be
    added beside it rather than branched into it. Its contract is deliberately
    untouched, including the one that would otherwise collide with FR-CRED-014:
    here, storing nothing IS an error (a 500), because storing is the whole
    point. For a root-adopt session storing nothing for the device is the NORMAL
    outcome, which is why these are separate functions and not one with a flag.
    """
    account_data = {
        "username": username,
        "password": password,
        "account_type": session.account_type,
        "purpose": session.purpose,
    }

    # Store credentials for all target devices (batch or single).
    # Use update_account when the account exists — atomic, no window
    # during which the account is observably missing. Fall back to
    # add_account for fresh ones.
    saved: List[str] = []
    errors: List[Dict] = []

    for did in session.all_device_ids:
        try:
            if registry.account_exists(did, session.account_id):
                registry.update_account(did, session.account_id, account_data)
            else:
                registry.add_account(did, session.account_id, account_data)
            saved.append(did)
        except DeviceNotFoundError:
            errors.append({"device_id": did, "error": "Device not found"})
        except BackendError as e:
            errors.append({"device_id": did, "error": str(e)})

    if not saved:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "request": request,
                "error": "Storage Error",
                "message": "Failed to save credentials for any device.",
                "title": "Error",
            },
            status_code=500,
        )

    # Mark session as completed (token is now single-use)
    capture_store.complete_session(token)

    # FR-CRED-012: promotion happens AFTER the device credential is stored
    # and never undoes or blocks it — a refused promotion is a note, not an
    # error, and so is a failure inside the promotion itself.
    promotion = _promote_if_asked(
        promote, username, password, saved,
        principal=getattr(request.state, "principal", None),
    )

    _note_capture_to_chat(token, saved, promotion)

    ctx = {
        "request": request,
        "title": "Credentials Saved",
        "device_id": session.device_id,
        "account_id": session.account_id,
        "promotion": promotion,
    }

    if session.is_batch:
        ctx["is_batch"] = True
        ctx["device_ids"] = session.all_device_ids
        ctx["saved"] = saved
        ctx["errors"] = errors

    return templates.TemplateResponse(request, "capture_done.html", ctx)


def _root_form(request, token, session, device, *, error=""):
    """Re-render the root-adopt form, optionally with a reason it came back."""
    return templates.TemplateResponse(
        request,
        "capture_root_form.html",
        {
            "request": request,
            "title": "Let ADMZ in",
            "token": token,
            "session": session,
            "device": device,
            "error": error,
            "prompt_always": entry_credentials.prompt_always(),
        },
    )


def _adopt_done(request, *, outcome, heading, device_label, entry_username,
                reason="", promotion=None, status_code=200):
    return templates.TemplateResponse(
        request,
        "capture_adopt_done.html",
        {
            "request": request,
            "outcome": outcome,
            "heading": heading,
            "device_label": device_label,
            "entry_username": entry_username,
            "reason": reason,
            "promotion": promotion,
        },
        status_code=status_code,
    )


async def _submit_root_adopt(
    request: Request,
    token: str,
    session: Any,
    username: str,
    password: str,
    entry_action: str,
    registry: DeviceRegistry,
):
    """Use the typed password ONCE to create ADMZ's own account (FR-CRED-014).

    The typed password is never stored as this device's credential. What reaches
    the registry is ``admz`` with a generated password, via
    ``provisioning.adopt_with_admz_account`` — the same two calls
    ``onboarding.py`` makes (confirm strict, then adopt), in the same order.

    **This is the first capture path that performs device I/O.** Everything
    before it only wrote to the registry, which is why the account path can
    treat "stored nothing" as a 500 and this one cannot:

        200 means ADMZ finished and the page says what happened.
        500 means ADMZ left an account behind that it cannot use.

    Storing nothing for the device is never, by itself, an error here.

    The token stays LIVE for every failure that did not touch the device — a
    corrected password is the same decision with better input — and is consumed
    the moment the ``admz`` write is attempted, because device state may have
    changed and a retry is a new decision.

    ADR-0059's gate is the submit button, not a confirmation card (ADR-0068 §9):
    ``POST /confirm/{token}`` — the mechanism the gate resolves to — is
    authorised by token possession alone with no CSRF check at all
    (KL-CRED-003), while this form adds ``check_same_origin``, a human typing
    that device's own administrator password, and a button naming the write.
    """
    from admz.api.context import get_context
    from admz.fleet.health import (
        _confirm_credentials,
        _persist_probe_marker,
        _tcp_probe,
    )
    from admz.provisioning import adopt_with_admz_account

    device_id = session.device_id
    try:
        device_info = registry.get_device_info(device_id)
    except Exception as exc:  # noqa: BLE001 — unknown or unreadable device
        logger.warning("root-adopt: device %s not readable: %s", device_id, exc)
        return _root_form(request, token, session, {"device_id": device_id},
                          error=f"ADMZ could not read this device's record: {exc}")

    device_label = device_info.get("nickname") or device_id
    host = device_info.get("host") or device_info.get("ip_address") or ""
    pair = {"username": username, "password": password}
    probe_info = {**device_info, "device_id": device_id}
    ctx = get_context()
    # Resolved ONCE, into a local named `principal`. `record_event`'s first
    # argument must be a principal (or an explicit None), and
    # tests/test_audit_principal_guard.py lints every call site statically for
    # exactly that — #283 found a `request` object passed where a principal
    # belonged, and an audit row that names the wrong actor is worse than one
    # that names none. Inlining `getattr(request.state, ...)` at each call is
    # the shape that lint rejects, correctly.
    principal = getattr(request.state, "principal", None)

    async def _run():
        """Preflight, prove the credential, then adopt.

        Returns ``(outcome, reason, promotion)``. Raises nothing the caller does
        not handle; the deadline is applied by the caller.
        """
        if host:
            up = await _tcp_probe(host, 80, 1.5)
            if up is None:
                up = await _tcp_probe(host, 443, 1.5)
            if up is None:
                return "unreachable", f"{host} did not answer.", None

        # strict: only an authenticated 2xx proves the pair. A lenient "not
        # rejected" once stored a bad password (P3408, 2026-07-02), and here it
        # would send an unproven credential into a `pwdgrp.cgi:add-user`.
        ok, _facts, learned = await _confirm_credentials(
            catalog=ctx.catalog, executor=ctx.executors.get("vapix"),
            device_info=probe_info, device_id=device_id, credentials=pair,
            timeout_seconds=10.0, strict=True,
        )
        if ok is False:
            return "auth_failed", "The device refused that username and password.", None
        if ok is None:
            return ("unconfirmed_auth",
                    "ADMZ could not confirm that password — the device answered "
                    "in a way that proves nothing either way.", None)

        # Persist what was learned about REACHING the device before anything
        # else; the health monitor reads it, and a device whose profile is
        # missing reports auth_failed while a working credential sits in store.
        if learned:
            _persist_probe_marker(registry, device_id, device_info, learned)
        reach = dict(device_info)
        if learned:
            reach.update(learned)

        # The two-way choice, taken NOW — gated on the credential being proven,
        # not on the adopt succeeding. A refused password promotes nothing
        # (spending two failed authentications against every future device for a
        # credential that does not work); a proven one whose admz write then
        # fails DOES promote if asked, because it demonstrably authenticates and
        # the entry list is the route to retry.
        promotion = _promote_if_asked(
            entry_action == "add_to_fleet_list", username, password, [device_id],
            principal=principal,
        )

        result = await adopt_with_admz_account(
            ctx.catalog, ctx.executors, registry,
            device_id=device_id, host=host, entry=pair, device_info=reach,
        )
        if not result.get("success"):
            return "adopt_failed", result.get("error") or "unknown error", promotion
        return "adopted", "", promotion

    try:
        outcome, reason, promotion = await asyncio.wait_for(
            _run(), timeout=_ADOPT_DEADLINE_SECONDS)
    except asyncio.TimeoutError:
        capture_store.complete_session(token, outcome="unconfirmed")
        _note_root_adopt_to_chat(token, device_id, "unconfirmed", None)
        logger.error("root-adopt for %s exceeded %.0fs; outcome indeterminate, "
                     "nothing stored", device_id, _ADOPT_DEADLINE_SECONDS)
        return _adopt_done(
            request, outcome="unconfirmed",
            heading="ADMZ could not confirm the result",
            device_label=device_label, entry_username=username)
    except Exception:  # noqa: BLE001 — the store may have failed after the write
        capture_store.complete_session(token, outcome="orphaned")
        logger.error(
            "root-adopt for %s: the device write may have succeeded but ADMZ "
            "could not keep the result. If an 'admz' account now exists on %s "
            "it must be removed or re-onboarded by hand.",
            device_id, host, exc_info=True)
        return _adopt_done(
            request, outcome="orphaned",
            heading="ADMZ could not finish safely",
            device_label=device_label, entry_username=username,
            reason=("ADMZ may have created its account on the device but could "
                    "not keep the password. Nothing was stored. Recover with "
                    "the fleet break-glass root password and re-onboard."),
            status_code=500)

    # --- outcomes that never touched the device: the token stays LIVE --------
    if outcome in ("unreachable", "auth_failed", "unconfirmed_auth"):
        record_event(
            principal,
            f"credential_prompt.{outcome}",
            resource=f"device:{device_id}",
            details={"username": username, "host": host},
            success=False, error_message=reason,
        )
        return _root_form(request, token, session, device_info, error=reason)

    # --- terminal outcomes: consume the token, write ONE chat note -----------
    capture_store.complete_session(token, outcome=outcome)
    record_event(
        principal,
        f"credential_prompt.{outcome}",
        resource=f"device:{device_id}",
        details={"username": username, "host": host,
                 "promotion": (promotion or {}).get("result", "none")},
        success=(outcome == "adopted"),
        error_message=reason,
    )
    _note_root_adopt_to_chat(token, device_id, outcome, promotion)

    if outcome == "adopted":
        return _adopt_done(
            request, outcome="adopted",
            heading="ADMZ now has its own account",
            device_label=device_label, entry_username=username,
            promotion=promotion)
    return _adopt_done(
        request, outcome="adopt_failed",
        heading="ADMZ got in, but could not create its account",
        device_label=device_label, entry_username=username,
        reason=reason, promotion=promotion)


def _note_root_adopt_to_chat(token, device_id, outcome, promotion):
    """One note, on a TERMINAL outcome only.

    ``pop_action_link`` is fetch-and-delete and there is one note per session
    (``sessions.py``), so a note on a mistyped password would consume the link
    and the REAL outcome would produce none — and under ADR-0066 that note is
    what fires the continuation turn. Says nothing about storage: for this kind
    there is no device credential to have stored.
    """
    said = {
        "adopted": ("ADMZ used the submitted password to create its own 'admz' "
                    "account on device {d} and now uses that. The submitted "
                    "password was NOT stored for the device."),
        "adopt_failed": ("The submitted password authenticated to device {d}, but "
                         "ADMZ could not create its own 'admz' account. Nothing "
                         "was stored, so the device still has no usable "
                         "credential."),
        "unconfirmed": ("ADMZ could not confirm the result for device {d}: the "
                        "device stopped answering partway through. Nothing was "
                        "stored."),
        "orphaned": ("ADMZ may have created an account on device {d} but could "
                     "not keep the password. Nothing was stored; this needs a "
                     "human."),
    }.get(outcome)
    if not said:
        return
    try:
        from admz.chatbot.sessions import chat_sessions

        link = chat_sessions.pop_action_link(token)
        if link is not None:
            chat_sessions.append_event(
                link["principal"], link["conversation_id"],
                "[console] " + said.format(d=device_id)
                + _promotion_sentence(promotion),
            )
    except Exception:  # noqa: BLE001 — never break a submit on a note
        logger.debug("root-adopt chat note failed for %s", token, exc_info=True)


# ── Fleet setting capture (password never touches LLM) ─────────────────

@router.get("/capture/fleet/{token}", response_class=HTMLResponse, tags=["capture"])
async def fleet_capture_form(request: Request, token: str):
    """Render the fleet setting capture form."""
    session = capture_store.get_fleet_session(token)

    if session is None:
        return templates.TemplateResponse(
            request,
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    if session.effective_status == CaptureStatus.COMPLETED:
        return templates.TemplateResponse(
            request,
            "capture_fleet_done.html",
            {
                "request": request,
                "title": "Setting Saved",
                "setting_key": session.setting_key,
                "label": session.label,
            },
        )

    if session.effective_status == CaptureStatus.EXPIRED:
        return templates.TemplateResponse(
            request,
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    return templates.TemplateResponse(
        request,
        "capture_fleet_form.html",
        {
            "request": request,
            "title": "Set Fleet Password",
            "token": token,
            "session": session,
        },
    )


@router.post("/capture/fleet/{token}", response_class=HTMLResponse, tags=["capture"])
async def fleet_capture_submit(
    request: Request,
    token: str,
    password: str = Form(...),
    username: str = Form("admin"),
):
    """Process the submitted fleet credentials (username + password)."""
    check_same_origin(request)  # CSRF (#3)
    session = capture_store.get_fleet_session(token)

    if session is None or session.effective_status != CaptureStatus.PENDING:
        return templates.TemplateResponse(
            request,
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    # ADR-0053: this route is reached with a one-time token minted by the MCP
    # tool, so the key travelled through a session row rather than through the
    # gate at ``mcp/server.py::_set_fleet_setting``. Re-check it here: a stale
    # session created before the allow-set narrowed, or a session row edited
    # out from under us, must not become a write path for a protected key.
    # Defence in depth — the mint side is gated too.
    if not is_llm_writable(session.setting_key):
        logger.warning(
            "fleet capture refused: %r is not LLM-writable", session.setting_key
        )
        return templates.TemplateResponse(
            request,
            "capture_expired.html",
            {"request": request, "title": "Link Expired"},
            status_code=410,
        )

    fleet_settings.set(session.setting_key, password)
    fleet_settings.set("default_username", username.strip() or "admin")
    capture_store.complete_fleet_session(token)

    return templates.TemplateResponse(
        request,
        "capture_fleet_done.html",
        {
            "request": request,
            "title": "Setting Saved",
            "setting_key": session.setting_key,
            "label": session.label,
        },
    )
