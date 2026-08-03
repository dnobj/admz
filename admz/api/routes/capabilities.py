"""Advanced capability switches — the read API and the hidden surface (GH #132).

Three endpoints, and the interesting part is what gates each one:

* ``GET  /api/capabilities`` — the whole declaration table plus
  ``{enabled, source}``. ``require_authenticated_principal``: it is inventory,
  not secrets, but an anonymous caller has ``/api/health`` for the id list.
* ``POST /api/capabilities/{id}`` — the only write. ``require_reveal_permission``
  (the same ``Administrators`` bar that guards plaintext credentials), plus a
  typed-id acknowledgement and a free-text reason that lands in the audit row.
* ``GET/POST /settings/advanced`` — the hidden page. **Unlinked**: it is not on
  ``/settings`` and not in the sidebar, so you reach it by typing the URL or by
  clicking the topbar chip, which only exists once something is already on.

**Deliberately not the ADR-0034 ``url_*`` confirm gate.** That gate exists for
device-affecting operations; reusing it for a config toggle would muddy the
model the issue explicitly says not to replace. The reveal bar + typed
acknowledgement is the right shape for "an admin is changing what this
installation is allowed to do".

Under ``ADMZ_AUTH_BACKEND=none`` there is no identity to check, so the page
renders **read-only** (Master resolution 2): its diagnostic value is highest on
exactly the unauthenticated dev box where these switches get used, and a hard
403 would hide it there. It informs; it refuses to act.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from admz import capabilities
from admz.auth import Principal, get_current_principal
from admz.authz import principal_can_reveal, require_authenticated_principal, reveal_groups

logger = logging.getLogger(__name__)

router = APIRouter()

_template_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(_template_dir))
try:  # match the rest of the app's template config (filters, globals)
    from admz.api.templating import configure as _configure_templates

    _configure_templates(templates)
except Exception:  # noqa: BLE001
    pass


# ---------------------------------------------------------------------------
# Shaping
# ---------------------------------------------------------------------------

#: Danger class → badge colour on the page. Declared in the registry (slice 3)
#: so the MCP read and this one cannot disagree about what "red" means; kept
#: importable under the old name because the template renders ``row.severity``.
DANGER_SEVERITY: Dict[str, str] = capabilities.DANGER_SEVERITY


def _row(cap: capabilities.Capability) -> Dict[str, Any]:
    """One capability as the API and the page both see it.

    Shaped by :func:`admz.capabilities.describe` — slice 3 added a second
    reader (the ``get_advanced_capabilities`` MCP tool) and moved the shape
    into the registry rather than letting the two surfaces drift.
    """
    return capabilities.describe(cap)


def _auth_backend_context() -> Dict[str, Any]:
    """``ADMZ_AUTH_BACKEND`` as read-only *context*, not a registry row.

    Master resolution 5: it already emits its own startup WARNING, and
    registering it would leave every dev box permanently chipped — which trains
    operators to ignore the chip and defeats its purpose. An operator reading
    "what mode is this in?" still wants it in the same view, so it appears here
    as a line, with no chip, no ``/api/health`` entry and no toggle.

    The reveal groups are supplied from here because ``admz.authz`` imports
    FastAPI and the registry must stay importable in the MCP subprocess.
    """
    return capabilities.auth_backend_context(reveal_groups())


# ---------------------------------------------------------------------------
# Gating
# ---------------------------------------------------------------------------


def _reveal_decision(principal: Optional[Principal]) -> Tuple[bool, str]:
    """``(may_toggle, reason)`` — or raise 403.

    Three outcomes, and the middle one is the whole of Master resolution 2:

    * in a reveal group → ``(True, "group:…")``
    * anonymous (``ADMZ_AUTH_BACKEND=none``) → ``(False, "anonymous-fallback")``,
      i.e. the page still renders, read-only
    * authenticated but not in a reveal group → **403**. This is a real
      identity that has been checked and refused; degrading it to read-only
      would be a different answer to the same question.
    """
    allowed, reason = principal_can_reveal(principal)
    if allowed:
        return True, reason
    if reason == "anonymous-fallback":
        return False, reason
    raise HTTPException(
        status_code=403,
        detail=(
            "Advanced capabilities are gated: requires membership in one of "
            f"the configured reveal groups ({', '.join(reveal_groups())}). "
            f"Decision: {reason}."
        ),
    )


def _apply_toggle(
    principal: Optional[Principal],
    cap_id: str,
    *,
    enabled: bool,
    confirm_id: str,
    reason: str,
) -> Dict[str, Any]:
    """Validate and perform one toggle. Shared by the API and the page form.

    Order matters and is deliberate: authorization first (so an unauthorized
    caller learns nothing about which ids exist), then existence, then the
    env-only refusal, then the acknowledgement. ``set_enabled`` writes the
    audit row.
    """
    may_toggle, decision = _reveal_decision(principal)
    if not may_toggle:
        raise HTTPException(
            status_code=403,
            detail=(
                "Advanced capabilities are read-only on this installation: "
                "ADMZ_AUTH_BACKEND=none means there is no identity to check "
                "against the reveal groups, and a change this consequential "
                "must be attributable. Configure an auth backend, or set the "
                "capability's environment variable on the service."
            ),
        )

    cap = capabilities.get(cap_id)
    if cap is None:
        raise HTTPException(status_code=404, detail=f"Unknown capability: {cap_id}")

    if not capabilities.is_toggleable(cap_id):
        raise HTTPException(
            status_code=409,
            detail=(
                f"{cap.id} cannot be changed from a browser. It is class "
                f"'{cap.danger}' and is enabled by environment variable only: "
                f"set {cap.env_var}=1 on the ADMZ service and restart it. "
                "That is by design — enabling it should require service "
                "control on the box, not a click."
            ),
        )

    if (confirm_id or "").strip() != cap.id:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Type the capability id ({cap.id}) to confirm. This is the "
                "acknowledgement step: no stray click enables a capability."
            ),
        )

    if not (reason or "").strip():
        raise HTTPException(
            status_code=400,
            detail="A reason is required; it is recorded in the audit log.",
        )

    source = capabilities.set_enabled(
        cap.id, enabled, principal, reason=reason.strip()
    )
    return {
        "id": cap.id,
        "enabled": bool(source),
        "source": source,
        "decision": decision,
        # The one surprising outcome, said out loud rather than left to be
        # discovered: turning the setting off does not turn off a capability
        # the environment is forcing on.
        "note": (
            f"{cap.id} is still active because {cap.env_var} is set in the "
            "service environment; unset it and restart to turn it off."
            if source == "env" and not enabled
            else ""
        ),
    }


# ---------------------------------------------------------------------------
# REST
# ---------------------------------------------------------------------------


class ToggleRequest(BaseModel):
    enabled: bool
    reason: str = ""
    confirm_id: str = ""


@router.get("/api/capabilities", tags=["capabilities"])
async def list_capabilities(request: Request) -> Dict[str, Any]:
    """The full declaration table plus each capability's live state."""
    principal = await get_current_principal(request)
    require_authenticated_principal(principal)

    rows = [_row(cap) for cap in capabilities.all_capabilities()]
    return {
        "capabilities": rows,
        "active": [r["id"] for r in rows if r["enabled"]],
        "auth_backend": _auth_backend_context(),
    }


@router.post("/api/capabilities/{cap_id}", tags=["capabilities"])
async def set_capability(
    cap_id: str, body: ToggleRequest, request: Request
) -> Dict[str, Any]:
    """Enable/disable one settings-enablable capability. Reveal-gated, audited."""
    principal = await get_current_principal(request)
    return _apply_toggle(
        principal,
        cap_id,
        enabled=body.enabled,
        confirm_id=body.confirm_id,
        reason=body.reason,
    )


# ---------------------------------------------------------------------------
# The hidden page
# ---------------------------------------------------------------------------


def _page_context(
    request: Request,
    principal: Optional[Principal],
    *,
    may_toggle: bool,
    success: str = "",
    error: str = "",
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = [_row(cap) for cap in capabilities.all_capabilities()]
    active = [r for r in rows if r["enabled"]]
    return {
        "request": request,
        "title": "Advanced capabilities",
        "principal": principal,
        "rows": rows,
        "active_count": len(active),
        "loud_count": len([r for r in active if not r["production_appropriate"]]),
        "may_toggle": may_toggle,
        "auth": _auth_backend_context(),
        "success": success,
        "error": error,
    }


@router.get("/settings/advanced", response_class=HTMLResponse, tags=["capabilities"])
async def advanced_settings_page(
    request: Request,
    principal: Principal = Depends(get_current_principal),
):
    may_toggle, _reason = _reveal_decision(principal)
    return templates.TemplateResponse(
        request,
        "advanced_settings.html",
        _page_context(request, principal, may_toggle=may_toggle),
    )


@router.post("/settings/advanced", response_class=HTMLResponse, tags=["capabilities"])
async def advanced_settings_action(
    request: Request,
    cap_id: str = Form(...),
    enabled: str = Form(""),
    confirm_id: str = Form(""),
    reason: str = Form(""),
    principal: Principal = Depends(get_current_principal),
):
    """The page's own form post — same validation, rendered instead of raised."""
    may_toggle, _reason = _reveal_decision(principal)
    success = ""
    error = ""
    want_on = capabilities.truthy(enabled)
    try:
        result = _apply_toggle(
            principal, cap_id,
            enabled=want_on, confirm_id=confirm_id, reason=reason,
        )
        success = (
            f"{cap_id} {'enabled' if want_on else 'disabled'}. "
            + (result["note"] or "Recorded in the audit log.")
        )
    except HTTPException as exc:
        error = str(exc.detail)

    return templates.TemplateResponse(
        request,
        "advanced_settings.html",
        _page_context(
            request, principal,
            may_toggle=may_toggle, success=success, error=error,
        ),
    )
