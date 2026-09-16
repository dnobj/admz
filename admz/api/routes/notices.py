"""Console notices: list, review, dismiss, snooze (ADR-0071 §3–§7).

A **review** writes one metadata-only ``[console]`` note into the caller's
active conversation — or into a new one, titled from the notice and made
active, when there is none. The page's existing continuation check
(ADR-0066) then fires the one gated turn that answers it. Making a new
conversation active deviates from ADR-0066 §3 on purpose: here the operator
clicked the button in this console, so moving their pointer is their action.

Two refusals protect the conversation: a notice that is no longer live (409
``not_open``), and a continuation already answering this conversation (409
``continuation_in_flight``), so two turns never stream into one conversation.

**Dismiss** and **snooze** change no device or registry state and the next
transition re-raises, so they are audited, not gated. Anonymous callers may
list, review and dismiss, on ADR-0066 §6's reasoning: nothing here discloses a
token or mints anything. Every POST takes a JSON body, so a cross-site form
cannot reach it.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from admz.audit import record_event
from admz.auth import Principal, get_current_principal, principal_name
from admz.notices.notes import review_note
from admz.notices.store import KIND_DRIFT, KINDS, STATUSES, Notice
from admz.notices.views import notice_view
from admz.validators import sanitize_display_text, validate_identifier

logger = logging.getLogger(__name__)

router = APIRouter()

#: Most notices one review may open.
MAX_BATCH = 20
#: Longest snooze, in hours (30 days).
MAX_SNOOZE_HOURS = 720


class ReviewRequest(BaseModel):
    """Body of ``POST /api/notices/{id}/review`` — ``{}`` today."""


class BatchReviewRequest(BaseModel):
    """Body of ``POST /api/notices/review``."""

    ids: List[int] = Field(..., min_length=1, max_length=MAX_BATCH)


class DismissRequest(BaseModel):
    """Body of ``POST /api/notices/{id}/dismiss``."""

    note: Optional[str] = Field(None, max_length=200,
                                description="Why — kept in the audit row.")


class SnoozeRequest(BaseModel):
    """Body of ``POST /api/notices/{id}/snooze``."""

    hours: float = Field(4, ge=1, le=MAX_SNOOZE_HOURS)


def _store():
    from admz.notices import store as store_module
    return store_module.notices_store


def _sessions():
    import admz.chatbot.sessions as sessions_module
    return sessions_module.chat_sessions


def _registry() -> Any:
    try:
        from admz.api.context import get_context
        return get_context().registry
    except Exception:  # noqa: BLE001 — the list renders without device names
        return None


def _get_or_404(notice_id: int) -> Notice:
    notice = _store().get(notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="notice not found")
    return notice


@router.get("/notices", tags=["notices"])
async def list_notices(
    status: str = Query("open", description="open, snoozed, handled, expired, live or all"),
    kind: Optional[str] = Query(None, description="drift or event"),
    device_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    principal: Principal = Depends(get_current_principal),
):
    """The attention queue, most recently updated first."""
    if status not in (*STATUSES, "live", "all"):
        raise HTTPException(status_code=422, detail=f"unknown status: {status}")
    if kind is not None and kind not in KINDS:
        raise HTTPException(status_code=422, detail=f"unknown kind: {kind}")
    if device_id:
        try:
            validate_identifier(device_id, "device_id")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
    store = _store()
    rows = store.list(status=None if status == "all" else status, kind=kind,
                      device_id=device_id or None, limit=limit)
    registry = _registry()
    return {
        "notices": [notice_view(n, registry) for n in rows],
        "count": len(rows),
        "open_count": store.count_open(),
    }


def _conversation_title(notices: List[Notice]) -> str:
    if len(notices) > 1:
        return f"Review {len(notices)} notices"
    notice = notices[0]
    if notice.kind == KIND_DRIFT:
        return sanitize_display_text(f"Drift on {notice.device_id}", max_length=80)
    return f"Notice #{notice.id}"


def _open_for_review(notices: List[Notice], principal: Principal) -> Dict[str, Any]:
    sessions = _sessions()
    who = principal_name(principal)
    conversation_id = sessions.get_active_conversation(who)
    if conversation_id and sessions.has_live_resume_claim(who, conversation_id):
        raise HTTPException(status_code=409, detail="continuation_in_flight")
    note = review_note(notices)
    created = False
    if not conversation_id:
        conversation_id = sessions.create_conversation(
            who, title=_conversation_title(notices), title_source="snippet",
            make_active=True,
        )
        created = True
    if not sessions.append_event(who, conversation_id, note):
        raise HTTPException(status_code=500, detail="the review note was not written")
    store = _store()
    for notice in notices:
        store.mark_reviewed(notice.id, conversation_id)
    ids = [n.id for n in notices]
    record_event(
        principal, "notice.review",
        resource=f"notice:{ids[0]}" if len(ids) == 1 else "notices",
        details={
            "notice_ids": ",".join(str(i) for i in ids),
            "device_ids": ",".join(sorted({n.device_id for n in notices if n.device_id})),
            "conversation_id": conversation_id,
            "created_conversation": created,
        },
    )
    return {"conversation_id": conversation_id, "created": created,
            "note": note, "notice_ids": ids}


@router.post("/notices/{notice_id}/review", tags=["notices"])
async def review_notice(
    notice_id: int,
    body: ReviewRequest = Body(...),
    principal: Principal = Depends(get_current_principal),
):
    """Open one notice for review in the Console chat."""
    notice = _get_or_404(notice_id)
    if not notice.is_live:
        raise HTTPException(status_code=409, detail="not_open")
    return _open_for_review([notice], principal)


@router.post("/notices/review", tags=["notices"])
async def review_notices(
    body: BatchReviewRequest = Body(...),
    principal: Principal = Depends(get_current_principal),
):
    """Open several notices with one note. Notices that are gone or already
    closed are skipped and listed; with none left to review, 409."""
    store = _store()
    live: List[Notice] = []
    skipped: List[int] = []
    for notice_id in dict.fromkeys(body.ids):
        notice = store.get(notice_id)
        if notice is not None and notice.is_live:
            live.append(notice)
        else:
            skipped.append(notice_id)
    if not live:
        raise HTTPException(status_code=409, detail="not_open")
    result = _open_for_review(live, principal)
    result["skipped"] = skipped
    return result


@router.post("/notices/{notice_id}/dismiss", tags=["notices"])
async def dismiss_notice(
    notice_id: int,
    body: DismissRequest = Body(...),
    principal: Principal = Depends(get_current_principal),
):
    """Close a notice without acting on it. The next transition re-raises."""
    notice = _get_or_404(notice_id)
    closed = _store().handle(notice_id, "dismissed", by=principal_name(principal))
    if closed is None:
        raise HTTPException(status_code=409, detail="not_open")
    details: Dict[str, Any] = {"kind": notice.kind, "device_id": notice.device_id}
    if body.note and body.note.strip():
        details["note"] = sanitize_display_text(body.note, max_length=200)
    record_event(principal, "notice.dismiss", resource=f"notice:{notice_id}",
                 details=details)
    return {"notice": notice_view(closed, _registry())}


@router.post("/notices/{notice_id}/snooze", tags=["notices"])
async def snooze_notice(
    notice_id: int,
    body: SnoozeRequest = Body(...),
    principal: Principal = Depends(get_current_principal),
):
    """Hide a notice for ``hours`` (1–720). A new transition wakes it early."""
    notice = _get_or_404(notice_id)
    until = time.time() + body.hours * 3600
    snoozed = _store().snooze(notice_id, until)
    if snoozed is None:
        raise HTTPException(status_code=409, detail="not_open")
    record_event(principal, "notice.snooze", resource=f"notice:{notice_id}",
                 details={"kind": notice.kind, "device_id": notice.device_id,
                          "hours": body.hours})
    return {"notice": notice_view(snoozed, _registry())}
