"""Only a member of the approver group may approve a confirmation (GH #178).

Before this, `routes/confirm.py` contained **zero** calls to
`require_authenticated_principal` or `require_reveal_permission` — against eight
other route modules that use them. It resolved a principal solely to write audit
rows, so any authenticated user could approve anything, while *reading* a
credential required group membership: the gate guarding device writes was weaker
than the one guarding credential reads.

The vacuity trap in this shape is that "a non-member is refused" is trivially
green if principal resolution returns nothing for anybody. `test_member_is_allowed`
exists to prove the gate is not simply denying everything, and runs first.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace as NS

import pytest


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _principal(name="AXIS\\dnich", groups=("Administrators", "Users"),
               anonymous=False):
    return NS(name=name, groups=list(groups), is_anonymous=anonymous,
              auth_source="windows-local")


# ── the predicate ────────────────────────────────────────────────────────────
class TestPrincipalCanApprove:
    def test_member_is_allowed_and_the_reason_names_the_group(self):
        """FIRST: proves the gate is not just denying everyone."""
        from admz.authz import principal_can_approve
        ok, reason = principal_can_approve(_principal(),
                                           configured_groups=["Administrators"])
        assert ok is True
        assert reason == "group:administrators"

    def test_non_member_is_refused(self):
        from admz.authz import principal_can_approve
        ok, reason = principal_can_approve(_principal(groups=["Users"]),
                                           configured_groups=["ADMZ-Admins"])
        assert ok is False and reason == "not-in-approver-groups"

    def test_anonymous_and_groupless_are_refused_distinguishably(self):
        from admz.authz import principal_can_approve
        assert principal_can_approve(None, configured_groups=["x"]) == (False, "anonymous")
        assert principal_can_approve(_principal(anonymous=True),
                                     configured_groups=["x"]) == (False, "anonymous")
        assert principal_can_approve(_principal(groups=[]),
                                     configured_groups=["x"]) == (False, "no-groups")

    def test_matching_ignores_case_and_domain_prefix(self):
        """Same normalisation the reveal gate uses — one mechanism, not two."""
        from admz.authz import principal_can_approve
        p = _principal(groups=["AXIS\\ADMINISTRATORS"])
        ok, _ = principal_can_approve(p, configured_groups=["administrators"])
        assert ok is True


# ── the default, and the lockout constraint ──────────────────────────────────
class TestDefaultCannotLockTheOperatorOut:
    def test_unconfigured_resolves_to_administrators(self, monkeypatch):
        from admz import authz
        monkeypatch.setattr(authz, "approver_groups",
                            authz.approver_groups)          # keep the real one
        import admz.fleet_settings as fs
        monkeypatch.setattr(fs.fleet_settings, "get", lambda k, *a, **kw: None)
        assert authz.approver_groups() == ["Administrators", "ADMZ-Admins"]

    def test_a_local_administrator_passes_on_a_fresh_install(self, monkeypatch):
        """The operator is a local Administrator. With nothing configured they
        must still be able to approve — otherwise this change locks them out of
        the very approval needed to undo it."""
        from admz import authz
        import admz.fleet_settings as fs
        monkeypatch.setattr(fs.fleet_settings, "get", lambda k, *a, **kw: None)
        ok, reason = authz.principal_can_approve(_principal(groups=["Administrators"]))
        assert ok is True and reason == "group:administrators"

    def test_the_default_matches_the_reveal_gate(self):
        """If reveal works for a principal today, approve works tomorrow. That
        equivalence is the anti-lockout argument, so pin it."""
        from admz.authz import _DEFAULT_APPROVER_GROUPS, _DEFAULT_REVEAL_GROUPS
        assert _DEFAULT_APPROVER_GROUPS == _DEFAULT_REVEAL_GROUPS

    def test_empty_configured_value_does_not_silently_permit(self, monkeypatch, caplog):
        """The #178 shape: absence of configuration must not weaken the gate.
        Empty falls back to the floor, LOUDLY — it never means 'anyone'."""
        import logging

        from admz import authz
        import admz.fleet_settings as fs
        for empty in ("", "   ", ",  ,"):
            monkeypatch.setattr(fs.fleet_settings, "get", lambda k, *a, **kw: empty)
            with caplog.at_level(logging.WARNING, logger="admz.authz"):
                caplog.clear()
                groups = authz.approver_groups()
            assert groups == ["Administrators", "ADMZ-Admins"]
            # A non-member is still refused — the empty value granted nothing.
            ok, _ = authz.principal_can_approve(_principal(groups=["Users"]))
            assert ok is False
        assert any("does NOT mean" in r.getMessage() for r in caplog.records)

    def test_a_settings_outage_falls_back_rather_than_locking_out(self, monkeypatch):
        from admz import authz
        import admz.fleet_settings as fs

        def boom(*a, **kw):
            raise RuntimeError("settings store unavailable")
        monkeypatch.setattr(fs.fleet_settings, "get", boom)
        assert authz.approver_groups() == ["Administrators", "ADMZ-Admins"]


# ── the real approve path ────────────────────────────────────────────────────
@pytest.fixture
def approve(monkeypatch):
    """Drive the REAL `_approve_session`, stubbing only identity and the store."""
    from admz.api.routes import confirm as C

    session = NS(effective_status=C.ConfirmStatus.PENDING, is_plan=False,
                 plan_id="", device_id="d1", operation_id="param.cgi:update",
                 confirmation_level="url_only", risk_level="service-affecting",
                 token="t1", is_action=False, confirmed_by="",
                 # #270 — the approve row now describes WHAT was approved, so
                 # the stub needs the real session's payload accessors.
                 params={}, action={}, plan_summary={})
    calls = {"completed": 0, "executed": 0}

    monkeypatch.setattr(C.confirm_store, "get_session", lambda t: session)
    monkeypatch.setattr(C.confirm_store, "complete_session",
                        lambda t, confirmed_by="": calls.__setitem__(
                            "completed", calls["completed"] + 1) or True)
    monkeypatch.setattr(C.rate_limiter, "check", lambda *a, **k: True)
    monkeypatch.setattr(C, "_is_locked", lambda t: False)
    monkeypatch.setattr(C, "_note_resolution_to_chat", lambda *a, **k: None)

    async def _exec(*a, **k):
        calls["executed"] += 1
        return {"success": True}
    import admz.operations as ops
    monkeypatch.setattr(ops, "execute_approved_session", _exec)

    def go(principal):
        import admz.auth as auth

        async def _cur(request):
            return principal
        monkeypatch.setattr(auth, "get_current_principal", _cur)
        ctx = NS(catalog=None, registry=NS(), executors={}, plan_engine=None,
                 git_repo=None)
        return _run(C._approve_session(NS(client=None, headers={}), "t1",
                                       None, ctx, "web")), calls
    return go


class TestApprovePathIsGated:
    def test_a_member_can_still_approve(self, approve, monkeypatch):
        """FIRST, and non-negotiable: the gate must not deny everyone."""
        import admz.fleet_settings as fs
        monkeypatch.setattr(fs.fleet_settings, "get", lambda k, *a, **kw: "Administrators")
        result, calls = approve(_principal(groups=["Administrators"]))
        assert result.status == "completed"
        assert calls["completed"] == 1 and calls["executed"] == 1

    def test_a_non_member_is_refused_and_the_token_is_not_consumed(
            self, approve, monkeypatch):
        import admz.fleet_settings as fs
        monkeypatch.setattr(fs.fleet_settings, "get", lambda k, *a, **kw: "ADMZ-Admins")
        result, calls = approve(_principal(groups=["Users"]))
        assert result.status == "not_authorized"
        assert "ADMZ-Admins" in result.detail          # names the requirement
        # Nothing ran, and the session stays PENDING so the right operator can
        # still approve it — a refusal must not burn the token.
        assert calls["completed"] == 0 and calls["executed"] == 0

    def test_an_authenticated_non_member_is_no_longer_enough(
            self, approve, monkeypatch):
        """The defect itself: pre-fix ANY authenticated principal approved."""
        import admz.fleet_settings as fs
        monkeypatch.setattr(fs.fleet_settings, "get", lambda k, *a, **kw: None)
        result, calls = approve(_principal(name="AXIS\\intern", groups=["Users"]))
        assert calls["executed"] == 0
        assert result.status == "not_authorized"

    def test_no_auth_backend_still_approves_but_says_so(
            self, approve, monkeypatch, caplog):
        """ADMZ_AUTH_BACKEND=none is the DEFAULT. There is no identity there, so
        group membership is undefined rather than absent — refusing would make a
        fresh install unable to approve anything, a lockout of a different
        population. Allowed, but never silently: unlike the password fail-open
        #178 was filed for, this warns and records the decision.
        """
        import logging

        import admz.fleet_settings as fs
        monkeypatch.setattr(fs.fleet_settings, "get", lambda k, *a, **kw: None)
        with caplog.at_level(logging.WARNING, logger="admz.api.routes.confirm"):
            result, calls = approve(_principal(name="anonymous", groups=[],
                                               anonymous=True))
        assert result.status == "completed" and calls["executed"] == 1
        assert any("NO identity" in r.getMessage() for r in caplog.records)

    def test_the_anonymous_allowance_does_not_leak_to_real_identities(
            self, approve, monkeypatch):
        """The guard that keeps the branch above from becoming a hole: a REAL
        principal with no groups is still refused."""
        import admz.fleet_settings as fs
        monkeypatch.setattr(fs.fleet_settings, "get", lambda k, *a, **kw: None)
        result, calls = approve(_principal(name="AXIS\\intern", groups=[],
                                           anonymous=False))
        assert result.status == "not_authorized" and calls["executed"] == 0


# ── the setting is protected ─────────────────────────────────────────────────
class TestSettingIsNotLlmWritable:
    def test_the_model_cannot_widen_who_may_approve(self):
        from admz.authz import APPROVER_GROUPS_SETTING
        from admz.setting_policy import KNOWN_SETTING_KEYS, is_llm_writable
        assert APPROVER_GROUPS_SETTING in KNOWN_SETTING_KEYS   # declared
        assert is_llm_writable(APPROVER_GROUPS_SETTING) is False
