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


__all__ = [
    "reveal_groups",
    "principal_can_reveal",
    "require_reveal_permission",
]
