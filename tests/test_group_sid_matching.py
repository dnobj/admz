"""GH #274: group membership must match by SID, not by localised name.

``NetUserGetLocalGroups`` reports display names. On a German install the
built-in group is ``Administratoren``, so the English ``Administrators``
default matched nobody — the reveal gate silently denied ``/settings/advanced``
and plaintext credentials, and the approver gate refused every approval.

**What these tests can and cannot prove.** This machine and both CI legs are
English, so the localised path cannot be exercised natively anywhere available.
It is *simulated* by substituting the one Win32 call
(``win_acl.lookup_account_sid``) with a fake that answers as a German machine
would: the localised name resolves, the English name does not. That is a real
test of ADMZ's logic and an honest stand-in for the OS, but it is not evidence
that ``LookupAccountNameW`` behaves as assumed on a genuinely localised
install. The assumption being made is stated at ``test_german_install_*``.

The unsimulated half — that ``lookup_account_sid`` resolves real names to real
SIDs — is covered against the live API in ``test_live_*`` (Windows only).
"""

import sys

import pytest

from admz import authz
from admz.auth import Principal
from admz.win_acl import SID_ADMINISTRATORS, SID_USERS, WinAclError


# --- fixtures --------------------------------------------------------------


def _principal(groups, *, name="tester"):
    return Principal(name=name, display_name=name, groups=list(groups))


@pytest.fixture(autouse=True)
def _clear_sid_cache():
    """The resolver memoises successes process-wide; isolate every test."""
    authz._SID_CACHE.clear()
    yield
    authz._SID_CACHE.clear()


class _FakeMachine:
    """Substitutes for ``win_acl.lookup_account_sid``.

    ``table`` maps the names this machine KNOWS to SIDs. Anything else raises
    ``WinAclError``, mirroring ERROR_NONE_MAPPED (1332) — which is what the
    real API returns, verified live in ``test_live_unknown_name_raises``.
    """

    def __init__(self, table, *, explode=False):
        self.table = table
        self.explode = explode
        self.calls = []

    def __call__(self, name):
        self.calls.append(name)
        if self.explode:
            raise WinAclError("simulated Win32 failure")
        try:
            return self.table[name]
        except KeyError:
            raise WinAclError(f"LookupAccountNameW({name!r}) failed: 1332")


GERMAN = {"Administratoren": SID_ADMINISTRATORS, "Benutzer": SID_USERS}


@pytest.fixture
def german(monkeypatch):
    """A German Windows: the localised name resolves, the English one does not."""
    fake = _FakeMachine(GERMAN)
    import admz.win_acl as win_acl
    monkeypatch.setattr(win_acl, "lookup_account_sid", fake)
    return fake


# --- the defect itself -----------------------------------------------------


@pytest.mark.parametrize("gate", ["reveal", "approve"])
def test_german_install_matches_the_english_default(german, gate):
    """The #274 defect, on BOTH gates.

    Assumption this rests on (untestable here): on a localised Windows,
    ``LookupAccountNameW`` resolves the LOCALISED name and does NOT resolve the
    English one. That asymmetry is why the configured side needs the
    well-known-SID table rather than another Win32 call — resolving both sides
    through the API alone would still fail to match.
    """
    p = _principal(["Administratoren"])
    fn = authz.principal_can_reveal if gate == "reveal" else authz.principal_can_approve

    allowed, reason = fn(p, configured_groups=["Administrators", "ADMZ-Admins"])

    assert allowed, f"{gate} gate still denies a localised Administrators group"
    assert reason == f"sid:{SID_ADMINISTRATORS}", (
        "a cross-locale match must be distinguishable in the audit trail")


@pytest.mark.parametrize("gate", ["reveal", "approve"])
def test_german_install_still_denies_an_unrelated_group(german, gate):
    """Anti-vacuity for the pair above.

    If the SID pass simply allowed everything, the test above would pass just
    as happily. A localised group that is NOT the configured one must still be
    refused.
    """
    p = _principal(["Benutzer"])          # resolves fine — to Users, not Admins
    fn = authz.principal_can_reveal if gate == "reveal" else authz.principal_can_approve

    allowed, reason = fn(p, configured_groups=["Administrators"])

    assert not allowed
    assert reason in ("not-in-reveal-groups", "not-in-approver-groups")


# --- the safety property: the SID pass is purely additive ------------------


def test_sid_pass_never_downgrades_an_existing_name_match(monkeypatch):
    """A name match must survive total failure of the SID machinery.

    This is the #272 hazard: a gate that fails closed on an unresolvable SID
    could lock an operator out of the very approval needed to fix it.
    """
    boom = _FakeMachine({}, explode=True)
    import admz.win_acl as win_acl
    monkeypatch.setattr(win_acl, "lookup_account_sid", boom)

    p = _principal(["Administrators"])
    allowed, reason = authz.principal_can_reveal(
        p, configured_groups=["Administrators"])

    assert allowed
    assert reason == "group:administrators", "the legacy reason tag changed"


def test_no_win32_call_when_names_already_match(monkeypatch):
    """The common (English) path must not pay a syscall per group per request.

    Also the reason the change is cheap: the SID pass only runs when the names
    genuinely disagree, which is precisely the localised case.
    """
    fake = _FakeMachine({"Administrators": SID_ADMINISTRATORS})
    import admz.win_acl as win_acl
    monkeypatch.setattr(win_acl, "lookup_account_sid", fake)

    allowed, _ = authz.principal_can_reveal(
        _principal(["Administrators"]), configured_groups=["Administrators"])

    assert allowed
    assert fake.calls == [], f"expected no Win32 lookups, got {fake.calls!r}"


def test_unresolvable_names_degrade_to_todays_behaviour(monkeypatch):
    """Off-Windows, or with a group nobody can resolve, behaviour is unchanged."""
    fake = _FakeMachine({})   # nothing resolves
    import admz.win_acl as win_acl
    monkeypatch.setattr(win_acl, "lookup_account_sid", fake)

    # Non-match stays a non-match...
    allowed, reason = authz.principal_can_reveal(
        _principal(["Marketing"]), configured_groups=["ADMZ-Admins"])
    assert not allowed and reason == "not-in-reveal-groups"

    # ...and a match stays a match.
    allowed, _ = authz.principal_can_reveal(
        _principal(["ADMZ-Admins"]), configured_groups=["ADMZ-Admins"])
    assert allowed


# --- resolution details ----------------------------------------------------


def test_well_known_table_agrees_with_win_acl_constants():
    """The table must not drift from the constants #252 already established."""
    assert authz._WELL_KNOWN_GROUP_SIDS["administrators"] == SID_ADMINISTRATORS
    assert authz._WELL_KNOWN_GROUP_SIDS["users"] == SID_USERS


def test_well_known_sids_are_resolved_without_calling_win32(german):
    """The English side comes from the table, not the API — which is the whole
    reason the fix works on a machine where the English name does not resolve."""
    assert authz._resolve_group_sid("Administrators") == SID_ADMINISTRATORS
    assert german.calls == [], f"table entry should not hit Win32: {german.calls!r}"


def test_domain_qualified_name_is_not_folded_into_the_builtin_sid(german):
    """``DOMAIN\\Administrators`` is not ``BUILTIN\\Administrators``.

    The legacy name pass domain-strips and so conflates them; that behaviour is
    preserved deliberately (it is what installs rely on today), but the SID pass
    must not entrench it — it resolves the qualified name as given.
    """
    german.table["ACME\\Administrators"] = "S-1-5-21-1-2-3-512"
    assert authz._resolve_group_sid("ACME\\Administrators") == "S-1-5-21-1-2-3-512"

    # And the legacy conflation still works, via the NAME pass.
    allowed, reason = authz.principal_can_reveal(
        _principal(["ACME\\Administrators"]), configured_groups=["Administrators"])
    assert allowed and reason == "group:administrators"


def test_cache_stores_successes_and_not_failures(german):
    """Caching a failure would turn one transient DC hiccup into a permanent one."""
    assert authz._resolve_group_sid("Administratoren") == SID_ADMINISTRATORS
    assert authz._resolve_group_sid("Nonexistent") is None

    assert "Administratoren" in authz._SID_CACHE
    assert "Nonexistent" not in authz._SID_CACHE

    # A second lookup of the failure retries; the success does not.
    german.calls.clear()
    authz._resolve_group_sid("Administratoren")
    authz._resolve_group_sid("Nonexistent")
    assert german.calls == ["Nonexistent"]


def test_empty_and_none_group_names_are_ignored():
    assert authz._resolve_group_sid("") is None
    assert authz._resolve_group_sid(None) is None
    assert authz._resolve_group_sid("   ") is None


# --- one matcher, both gates (the #255 lesson) -----------------------------


@pytest.mark.parametrize("gate", ["reveal", "approve"])
def test_both_gates_route_through_the_single_matcher(monkeypatch, gate):
    """Structural guard: neither gate may grow its own membership logic.

    #272 left this bug unfixed rather than fix one gate and create a second
    convention. If a future change reimplements matching inside either gate,
    this goes red.
    """
    seen = []

    def _spy(principal_groups, configured_groups):
        seen.append((list(principal_groups), list(configured_groups)))
        return "group:sentinel"

    monkeypatch.setattr(authz, "_match_groups", _spy)
    fn = authz.principal_can_reveal if gate == "reveal" else authz.principal_can_approve

    allowed, reason = fn(_principal(["Whatever"]), configured_groups=["Cfg"])

    assert allowed and reason == "group:sentinel", (
        f"the {gate} gate did not use _match_groups for its decision")
    assert seen == [(["Whatever"], ["Cfg"])]


# --- live Win32, Windows only ----------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_live_resolves_builtin_administrators():
    """The unsimulated half: the real API against the real machine.

    Locale-safe as written — this box is English, and the assertion is that the
    English name maps to the invariant SID, which is exactly what an English
    machine should do.
    """
    from admz.win_acl import lookup_account_sid
    assert lookup_account_sid("Administrators") == SID_ADMINISTRATORS
    assert lookup_account_sid("BUILTIN\\Administrators") == SID_ADMINISTRATORS
    assert lookup_account_sid("SYSTEM") == "S-1-5-18"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_live_unknown_name_raises():
    """ERROR_NONE_MAPPED (1332) must surface as WinAclError, not a bare False.

    This is what the fake in these tests is imitating; if the real API stopped
    raising here, the fakes above would be modelling something that no longer
    happens.
    """
    from admz.win_acl import lookup_account_sid
    with pytest.raises(WinAclError):
        lookup_account_sid("NoSuchGroup-c2f4b1a0")


@pytest.mark.skipif(sys.platform == "win32", reason="non-Windows only")
def test_off_windows_resolution_is_none_not_an_error():
    """The ubuntu CI leg imports and exercises this too — it must degrade, not raise."""
    assert authz._resolve_group_sid("Administrators") == SID_ADMINISTRATORS  # table
    assert authz._resolve_group_sid("ADMZ-Admins") is None                   # needs Win32

    allowed, _ = authz.principal_can_reveal(
        _principal(["ADMZ-Admins"]), configured_groups=["ADMZ-Admins"])
    assert allowed, "name matching must still work with no Win32 available"
