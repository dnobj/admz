"""Authorization predicates for the ADMZ web/REST surface.

Sits one layer above :mod:`admz.auth`: ``auth.py`` answers "who is
this caller?" by building a :class:`Principal`; this module answers
"is this principal allowed to do X?" by inspecting that Principal.

Phase-4 design intent: real authentication (Windows IWA via reverse
proxy, or API keys) populates ``Principal.groups``; sensitive
operations then check group membership rather than relying solely on
fleet-wide on/off flags. Anonymous principals (``ADMZ_AUTH_BACKEND=none``)
are simply denied by these predicates — the last flag that softened
that for reveal (``tool_get_credentials_enabled``) was removed in #151.

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

                         If the names do not match, both sides are
                         resolved to SIDs and compared again (#274),
                         so the English ``Administrators`` default
                         still matches ``Administratoren`` on a
                         German install. See :func:`_match_groups`.
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
# Group matching (GH #274) — names first, SIDs as a widening fallback
# ---------------------------------------------------------------------------
#
# ``NetUserGetLocalGroups`` reports localised display names, so a German
# install returns ``Administratoren`` and the ``Administrators`` default here
# matches nobody. The SID is invariant; the name is not. ``win_acl`` has
# compared SIDs rather than names since #252 for exactly this reason.
#
# There is ONE matcher, :func:`_match_groups`, used by both the reveal gate and
# the approver gate. Two implementations of one membership predicate is how the
# ``_refresh`` drift in #209/#255 happened, and it is why #272 deliberately left
# this alone rather than fixing only its own half.

#: English built-in group names -> their locale-invariant SIDs (winnt.h).
#:
#: This table is what makes the fix work, and the reason is easy to miss:
#: ``LookupAccountNameW`` on a localised install resolves the LOCALISED name,
#: so looking up the literal ``"Administrators"`` FAILS on a German box. But the
#: configured side is always English — ADMZ's own defaults are English literals
#: and so is anything copied from the docs. Resolving both sides through Win32
#: alone would therefore still not match; the configured side needs this table
#: and the principal side needs the API.
#:
#: Only ``BUILTIN\`` aliases belong here: their SIDs are identical on every
#: machine. Domain groups (``Domain Admins`` = ``S-1-5-21-<domain>-512``) are
#: domain-relative and cannot be tabled — they resolve via ``LookupAccountNameW``
#: or fall through to name comparison.
_WELL_KNOWN_GROUP_SIDS = {
    "administrators": "S-1-5-32-544",
    "users": "S-1-5-32-545",
    "guests": "S-1-5-32-546",
    "power users": "S-1-5-32-547",
    "account operators": "S-1-5-32-548",
    "server operators": "S-1-5-32-549",
    "print operators": "S-1-5-32-550",
    "backup operators": "S-1-5-32-551",
    "replicator": "S-1-5-32-552",
    "remote desktop users": "S-1-5-32-555",
    "network configuration operators": "S-1-5-32-556",
    "performance monitor users": "S-1-5-32-558",
    "performance log users": "S-1-5-32-559",
    "distributed com users": "S-1-5-32-562",
    "iis_iusrs": "S-1-5-32-568",
    "event log readers": "S-1-5-32-573",
    "hyper-v administrators": "S-1-5-32-578",
    "access control assistance operators": "S-1-5-32-579",
    "remote management users": "S-1-5-32-580",
}

#: Successful resolutions only. A name->SID mapping is stable for the life of a
#: process (renaming a local group is rare and needs a restart to take effect
#: here); caching FAILURES would turn one transient domain-controller hiccup
#: into a permanent one, which is the opposite of the fail-soft behaviour below.
_SID_CACHE: dict = {}


def _resolve_group_sid(name: str) -> Optional[str]:
    """Best-effort group name -> SID string. ``None`` if it cannot be resolved.

    Never raises: off-Windows, for a nonexistent group, or on any Win32 failure
    this returns ``None`` and the caller falls back to comparing names.
    """
    raw = (name or "").strip()
    if not raw:
        return None
    # A domain-qualified name is resolved AS GIVEN. ``DOMAIN\Administrators`` is
    # not ``BUILTIN\Administrators`` and must not be folded into it here — the
    # legacy name comparison already conflates the two (it domain-strips before
    # comparing), and that behaviour is preserved by the name pass, but there is
    # no reason to entrench it in the SID pass as well.
    if "\\" in raw or "/" in raw:
        return _lookup_sid_cached(raw)
    key = _normalize(raw)
    well_known = _WELL_KNOWN_GROUP_SIDS.get(key)
    if well_known:
        return well_known
    return _lookup_sid_cached(raw)


def _lookup_sid_cached(raw: str) -> Optional[str]:
    if raw in _SID_CACHE:
        return _SID_CACHE[raw]
    try:
        from admz import win_acl
        sid = win_acl.lookup_account_sid(raw)
    except Exception:  # noqa: BLE001 — off-Windows, ERROR_NONE_MAPPED, anything
        sid = None
    # Deliberately NOT `return None` above: the failure has to reach this one
    # cache-write so the guard below is the thing that actually enforces
    # "successes only". With an early return the guard is unreachable for the
    # only case it exists for, and a mutation removing it changes nothing —
    # which is exactly what happened before this was restructured.
    if sid:
        _SID_CACHE[raw] = sid
    return sid


def _sid_set(groups: Iterable[str]) -> set:
    return {s for s in (_resolve_group_sid(g) for g in groups if g) if s}


def _match_groups(
    principal_groups: Iterable[str], configured_groups: Iterable[str]
) -> Optional[str]:
    """The single membership predicate behind both gates.

    Returns a reason tag naming *why* access was granted, or ``None``.

    Names are compared first, SIDs only if that fails. Two consequences, both
    deliberate:

    * **The SID pass is purely additive.** It can turn a "no" into a "yes"; it
      can never turn a "yes" into a "no". So an unresolvable SID — off-Windows,
      a group that does not exist locally, a domain controller that did not
      answer — degrades to exactly today's behaviour rather than locking an
      operator out of the gate they need in order to fix it (the hazard #272
      navigated, and the same argument :func:`approver_groups` makes for its
      own fallback: it is safe *because* it cannot be weaker).
    * **No Win32 call happens on the common path.** An English install matches
      by name on the first pass, so the syscalls only occur when the names
      genuinely disagree — which is the localised case this exists for.

    The widening it permits is narrow: a SID match requires the operator to have
    configured *that group*. It cannot admit a group nobody listed.
    """
    p_names = _group_set_normalized(principal_groups)
    if not p_names:
        return None
    by_name = p_names & _group_set_normalized(configured_groups)
    if by_name:
        # Deterministic (alphabetical) for readable audit logs.
        return f"group:{sorted(by_name)[0]}"

    by_sid = _sid_set(principal_groups) & _sid_set(configured_groups)
    if by_sid:
        # Distinct prefix so the audit trail shows the match was cross-locale.
        return f"sid:{sorted(by_sid)[0]}"
    return None


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
      * ``"anonymous"`` — no real identity (the synthetic principal from
        ``ADMZ_AUTH_BACKEND=none``, or no principal at all). Always
        denied; the ``tool_get_credentials_enabled`` fallback that used
        to soften this for single-user installs was removed (#151).
        Same tag :func:`principal_can_approve` uses for the same case.
      * ``"no-groups"`` — authenticated principal has no group
        memberships
      * ``"not-in-reveal-groups"`` — authenticated principal has groups
        but none of them are in the configured reveal-groups list
    """
    if principal is None or getattr(principal, "is_anonymous", False):
        return False, "anonymous"

    if not (principal.groups or []):
        return False, "no-groups"

    configured = configured_groups if configured_groups is not None else reveal_groups()
    # One matcher, shared with principal_can_approve (#274). Matches by name,
    # then by SID so a localised built-in group name still resolves.
    reason = _match_groups(principal.groups or [], configured)
    if reason:
        return True, reason

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
#: the stricter gate already works.
#:
#: Still written as English NAMES rather than SIDs, and that is now safe: since
#: #274 :func:`_match_groups` resolves both sides, so ``Administrators`` here
#: matches a principal whose group ``NetUserGetLocalGroups`` reports as
#: ``Administratoren``. Names are kept because they are what an operator reads,
#: types and sees in the 403 message; the SID equivalence is machinery, not
#: configuration.
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
    if not (principal.groups or []):
        return False, "no-groups"
    configured = configured_groups if configured_groups is not None else approver_groups()
    reason = _match_groups(principal.groups or [], configured)
    if reason:
        return True, reason
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

    Anonymous principals are denied like any other non-member; the
    distinct ``"anonymous"`` tag exists so audit rows and error
    messages can say *why* (no identity vs. wrong groups), not to
    signal a softer path — the flag fallback it used to signal was
    removed (#151).
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
