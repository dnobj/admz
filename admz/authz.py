"""Authorization predicates for the ADMZ web/REST surface.

Sits one layer above :mod:`admz.auth`: ``auth.py`` answers "who is
this caller?" by building a :class:`Principal`; this module answers
"is this principal allowed to do X?" by inspecting that Principal.

Phase-4 design intent: real authentication (Windows IWA via reverse
proxy, or API keys) populates ``Principal.groups``; sensitive
operations then check group membership rather than relying solely on
fleet-wide on/off flags. The flags remain useful for local
zero-config installs where ``ADMZ_AUTH_BACKEND=none`` and there is no
real identity to attribute permissions to.

Currently this module covers one predicate — **credential reveal** —
because that's the operation a user explicitly asked us to gate
behind group membership. More predicates (provision, delete, rotate)
can land here as Phase 4 expands.

Configuration::

    ADMZ_REVEAL_GROUPS   Comma-separated list of group names that
                         grant the "reveal plaintext credentials"
                         permission. Defaults to:

                             Administrators,ADMZ-Admins

                         Matching is case-insensitive and trims
                         whitespace. Leading domain prefixes
                         (e.g. ``DOMAIN\\Administrators``) are
                         stripped before comparison so the same
                         config works whether LDAP enrichment
                         returns ``"Administrators"`` or
                         ``"AXIS\\Administrators"``.
"""

from __future__ import annotations

import logging
import os
from typing import Iterable, List, Optional, Sequence, Tuple

from fastapi import HTTPException, status

from admz.auth import Principal


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config — which groups grant Reveal
# ---------------------------------------------------------------------------


_DEFAULT_REVEAL_GROUPS = ("Administrators", "ADMZ-Admins")


def _strip_domain(name: str) -> str:
    """Strip a leading ``DOMAIN\\`` or ``DOMAIN/`` prefix from a group
    name so config can list bare names and still match LDAP-enriched
    qualified names.
    """
    if "\\" in name:
        name = name.rsplit("\\", 1)[-1]
    if "/" in name:
        name = name.rsplit("/", 1)[-1]
    return name


def _normalize(name: str) -> str:
    """Lower-case + domain-strip for case-insensitive comparison."""
    return _strip_domain(name).strip().lower()


def reveal_groups(env_value: Optional[str] = None) -> List[str]:
    """Return the configured list of group names that grant Reveal.

    ``env_value`` lets tests override without touching ``os.environ``;
    when None, reads ``ADMZ_REVEAL_GROUPS``. Empty or unset → defaults.
    """
    raw = env_value if env_value is not None else os.getenv("ADMZ_REVEAL_GROUPS")
    if raw is None or not raw.strip():
        return list(_DEFAULT_REVEAL_GROUPS)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts or list(_DEFAULT_REVEAL_GROUPS)


def _group_set_normalized(groups: Iterable[str]) -> set:
    return {_normalize(g) for g in groups if g}


# ---------------------------------------------------------------------------
# Permission predicate
# ---------------------------------------------------------------------------


def principal_can_reveal(
    principal: Optional[Principal],
    *,
    configured_groups: Optional[Sequence[str]] = None,
) -> Tuple[bool, str]:
    """Decide whether ``principal`` may retrieve plaintext credentials.

    Returns ``(allowed, reason)``. ``reason`` is a short machine-
    friendly tag suitable for audit logging:

      * ``"group:<groupname>"`` — granted via membership; ``<groupname>``
        is the matched group from the configured list (so the audit log
        shows *why* it was allowed)
      * ``"anonymous-fallback"`` — principal is the synthetic anonymous
        identity from ``ADMZ_AUTH_BACKEND=none``; caller should consult
        the fleet flag to decide. Returns ``allowed=False`` from this
        function so the flag check is explicit at the call site
      * ``"no-groups"`` — authenticated principal has no group
        memberships
      * ``"not-in-reveal-groups"`` — authenticated principal has groups
        but none of them are in the configured reveal-groups list
    """
    if principal is None or getattr(principal, "is_anonymous", False):
        return False, "anonymous-fallback"

    pgroups = _group_set_normalized(principal.groups or [])
    if not pgroups:
        return False, "no-groups"

    configured = configured_groups if configured_groups is not None else reveal_groups()
    wanted = _group_set_normalized(configured)

    matched = pgroups & wanted
    if matched:
        # Surface one matched group in the reason. Multiple matches are
        # fine; pick deterministically (alphabetical) for readable
        # audit logs.
        return True, f"group:{sorted(matched)[0]}"

    return False, "not-in-reveal-groups"


# ---------------------------------------------------------------------------
# Approve — who may approve a confirmation session (GH #178)
# ---------------------------------------------------------------------------

#: Fleet setting holding the comma-separated approver group list. Protected by
#: the inverted policy in ``setting_policy`` (ADR-0053): absent from the
#: LLM-writable allow-set, so the model can never widen who may approve.
APPROVER_GROUPS_SETTING = "confirm_approver_groups"

#: The floor. ``Administrators`` is the SAME name the reveal gate already
#: defaults to, deliberately: if an operator can reveal a credential today,
#: they can approve tomorrow, so shipping this cannot lock out an install where
#: the stricter gate already works. (Bare NAMES, not SIDs, because
#: ``NetUserGetLocalGroups`` returns ``lgrui0_name`` — see the localisation
#: caveat in ``win_acl``: the *name* is localised, the SID is not. That limit is
#: pre-existing and shared with reveal, not introduced here.)
_DEFAULT_APPROVER_GROUPS = ("Administrators", "ADMZ-Admins")


def approver_groups(configured: Optional[str] = None) -> List[str]:
    """Group names that may approve a confirmation session.

    Reads the ``confirm_approver_groups`` fleet setting; ``configured`` lets
    tests pass a value without touching the store.

    **Unset or empty falls back to the default, loudly.** An empty value is NOT
    read as "no restriction": that is precisely the fail-open shape #178 was
    filed for, where a missing ``confirm_password_hash`` silently turned
    ``url_and_password`` into ``url_only``. Nor does it fail closed — the
    fallback IS the documented floor and is itself a real restriction, so
    refusing every approval because a text box was cleared would lock the
    operator out of the very approval needed to fix it. Falling back is only
    safe because it cannot be *weaker* than the floor; it is logged so the
    divergence between configured and effective is never silent.
    """
    raw = configured
    if raw is None:
        try:
            from admz.fleet_settings import fleet_settings
            raw = fleet_settings.get(APPROVER_GROUPS_SETTING)
        except Exception:  # noqa: BLE001 — a settings outage must not lock out
            logger.warning("approver group lookup failed; using the default (%s)",
                           ", ".join(_DEFAULT_APPROVER_GROUPS), exc_info=True)
            return list(_DEFAULT_APPROVER_GROUPS)
    if raw is None:
        return list(_DEFAULT_APPROVER_GROUPS)          # never configured — the floor
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    if not parts:
        logger.warning(
            "%s is configured but empty; falling back to the default approver "
            "groups (%s). An empty value does NOT mean 'anyone may approve'.",
            APPROVER_GROUPS_SETTING, ", ".join(_DEFAULT_APPROVER_GROUPS))
        return list(_DEFAULT_APPROVER_GROUPS)
    return parts


def principal_can_approve(
    principal: Optional[Principal],
    *,
    configured_groups: Optional[Sequence[str]] = None,
) -> Tuple[bool, str]:
    """Decide whether ``principal`` may approve a confirmation session.

    Same membership rule as :func:`principal_can_reveal` — deliberately, and
    via the same normalisation helpers. Two mechanisms for "is this principal
    in a group" is how the ``_refresh`` sibling drift in #209/#255 happened.
    """
    if principal is None or getattr(principal, "is_anonymous", False):
        return False, "anonymous"
    pgroups = _group_set_normalized(principal.groups or [])
    if not pgroups:
        return False, "no-groups"
    configured = configured_groups if configured_groups is not None else approver_groups()
    matched = pgroups & _group_set_normalized(configured)
    if matched:
        return True, f"group:{sorted(matched)[0]}"
    return False, "not-in-approver-groups"


def require_approve_permission(principal: Optional[Principal]) -> str:
    """Raise 403 unless ``principal`` may approve. Returns the reason tag so the
    caller records *why* it was allowed in the audit row.

    Before #178 the approve path made no authorization decision at all: it
    resolved a principal solely to write audit rows, so any authenticated user
    could approve anything — while *reading* a credential required group
    membership. The gate guarding device writes was weaker than the one
    guarding credential reads.
    """
    allowed, reason = principal_can_approve(principal)
    if allowed:
        return reason
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Approval denied: approving a confirmation requires membership in "
            f"one of the approver groups ({', '.join(approver_groups())}). "
            f"Decision: {reason}."
        ),
    )


def require_reveal_permission(principal: Optional[Principal]) -> str:
    """FastAPI-friendly helper that raises 403 if the principal can't
    reveal. Returns the reason tag on success so the caller can record
    it in the audit log.

    NOTE: this helper alone does NOT handle the anonymous fallback —
    the call site is expected to first try this helper, catch the 403
    that comes back for anonymous, and only then consult the flag.
    Using a sentinel reason keeps the call-site logic explicit rather
    than burying it inside an authz helper.
    """
    allowed, reason = principal_can_reveal(principal)
    if allowed:
        return reason
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Reveal denied: requires membership in one of the configured "
            f"reveal groups ({', '.join(reveal_groups())}). "
            f"Decision: {reason}."
        ),
    )


def require_authenticated_principal(principal: Optional[Principal]) -> None:
    """Raise 403 unless ``principal`` is a real, non-anonymous identity.

    CR-3: used to gate the small set of endpoints that should refuse
    anonymous callers even when ``ADMZ_AUTH_BACKEND=none`` is in effect:

      * ``POST /api/api-keys`` — anonymous shouldn't mint long-lived
        credentials.
      * Writes to protected fleet settings — confirm levels,
        confirm-password hash, credential-access flags, scheduler /
        health-monitor toggles, the Gemini API key. Since ADR-0053 that
        is *every* key except the fleet credential pair, and the check
        is :func:`admz.fleet_settings.is_protected_setting`. Note there
        is no generic REST fleet-settings write route — the enforcement
        point is the MCP tool and the out-of-band capture path.
      * ``DELETE /api/devices/{id}``,
        ``POST /api/snapshot/restore``,
        ``POST /api/plans/{id}/execute`` — destructive / data-loss.

    Local-dev workflow (the common case for ``ADMZ_AUTH_BACKEND=none``
    with the localhost-only bind) keeps working for read + low-risk
    mutation; only the few above require a real identity. The
    operator can mint themselves an API key after switching the
    backend to ``api-key`` or ``composite``.

    Raises:
        HTTPException(403): if ``principal`` is None or
            ``principal.is_anonymous`` is True.
    """
    if principal is None or getattr(principal, "is_anonymous", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This endpoint requires an authenticated principal. "
                "The default ADMZ_AUTH_BACKEND=none maps every caller "
                "to the anonymous principal, which can read freely + "
                "mutate low-risk state but cannot perform destructive "
                "or credential-affecting actions. To unblock, mint an "
                "API key (ADMZ_AUTH_BACKEND=api-key) or stand up "
                "Windows IWA (ADMZ_AUTH_BACKEND=windows / composite)."
            ),
        )


__all__ = [
    "reveal_groups",
    "principal_can_reveal",
    "require_reveal_permission",
    "require_authenticated_principal",
]
