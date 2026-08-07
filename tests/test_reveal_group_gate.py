"""Tests for the group-membership Reveal gate (Pattern A).

Background: the /api/fleet/settings/{key}/reveal endpoint (admin secrets
like API keys) is gated by group membership. With Phase-4 authentication
producing real Principals carrying group memberships, it checks
membership in ADMZ_REVEAL_GROUPS (default: Administrators, ADMZ-Admins).

Anonymous callers (``ADMZ_AUTH_BACKEND=none``) are ALWAYS denied for
sensitive keys. The ``tool_get_credentials_enabled`` fallback that used
to let them through was removed (#151) — its documented purpose (the
deleted ``get_credentials`` MCP tool) no longer existed, and what it
actually granted was unauthenticated access to plaintext secrets. A
legacy flag row left behind by an upgrade must NOT resurrect the bypass.

(The per-account device-credential reveal endpoint was removed entirely
— device-account passwords are never displayed through any web/REST
surface; see test_api_routes.py::TestCredentialsEndpointRemoved.)

This file pins:
  - reveal_groups() env-var parsing + defaults
  - principal_can_reveal() decision matrix (anonymous, no-groups,
    mismatch, match by Administrators, match by ADMZ-Admins,
    domain-prefixed group, case-insensitive comparison)
  - /api/fleet/settings/{key}/reveal endpoint: non-sensitive bypass,
    sensitive gate, plaintext on allow, anonymous always denied
  - the windows-local auth chain 401s an unauthenticated request before
    the route runs — the anonymous principal is unreachable there
    (#151's merge precondition, encoded)
  - Audit-log entries on the fleet-setting reveal path
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from admz.auth import (
    AuthBackend,
    Principal,
    set_active_backend,
)
from admz.authz import (
    principal_can_reveal,
    require_reveal_permission,
    reveal_groups,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class StubBackend(AuthBackend):
    """Auth backend that returns a configurable Principal for every request.

    Lets test cases pin the identity they want without going through
    IIS/REMOTE_USER plumbing. The test fixture installs one of these
    via ``set_active_backend`` and rotates the principal between
    cases by reassigning ``backend.principal``.
    """

    def __init__(self, principal: Principal):
        self.principal = principal

    async def authenticate(self, request):
        return self.principal


def _anon() -> Principal:
    return Principal(
        name="anonymous", display_name="anonymous",
        source="none", is_anonymous=True,
    )


def _windows(name: str, groups=None) -> Principal:
    return Principal(
        name=f"AXIS\\{name}", display_name=name, domain="AXIS",
        groups=list(groups or []), source="windows",
    )


# ---------------------------------------------------------------------------
# Unit tests — reveal_groups() and principal_can_reveal()
# ---------------------------------------------------------------------------


class TestRevealGroupsConfig:
    def test_defaults_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("ADMZ_REVEAL_GROUPS", raising=False)
        assert reveal_groups() == ["Administrators", "ADMZ-Admins"]

    def test_defaults_when_env_empty(self, monkeypatch):
        monkeypatch.setenv("ADMZ_REVEAL_GROUPS", "")
        assert reveal_groups() == ["Administrators", "ADMZ-Admins"]

    def test_defaults_when_env_whitespace_only(self, monkeypatch):
        monkeypatch.setenv("ADMZ_REVEAL_GROUPS", "   ,  ,")
        # All entries are empty after stripping → fall back to defaults.
        assert reveal_groups() == ["Administrators", "ADMZ-Admins"]

    def test_custom_single(self, monkeypatch):
        monkeypatch.setenv("ADMZ_REVEAL_GROUPS", "CredAdmins")
        assert reveal_groups() == ["CredAdmins"]

    def test_custom_multiple_trimmed(self, monkeypatch):
        monkeypatch.setenv(
            "ADMZ_REVEAL_GROUPS", " CredAdmins , DomainAdmins , Ops "
        )
        assert reveal_groups() == ["CredAdmins", "DomainAdmins", "Ops"]

    def test_explicit_override_argument_wins(self):
        # Passing env_value explicitly bypasses the env var.
        assert reveal_groups(env_value="Foo,Bar") == ["Foo", "Bar"]


class TestPrincipalCanReveal:
    def test_anonymous_denied(self):
        allowed, reason = principal_can_reveal(_anon())
        assert allowed is False
        assert reason == "anonymous"

    def test_none_principal_denied(self):
        allowed, reason = principal_can_reveal(None)
        assert allowed is False
        assert reason == "anonymous"

    def test_authenticated_no_groups_denied(self):
        allowed, reason = principal_can_reveal(_windows("alice", []))
        assert allowed is False
        assert reason == "no-groups"

    def test_authenticated_wrong_groups_denied(self):
        allowed, reason = principal_can_reveal(
            _windows("alice", ["Users", "Helpdesk"])
        )
        assert allowed is False
        assert reason == "not-in-reveal-groups"

    def test_administrators_allowed(self):
        allowed, reason = principal_can_reveal(
            _windows("alice", ["Users", "Administrators"])
        )
        assert allowed is True
        assert reason == "group:administrators"

    def test_admz_admins_allowed(self):
        allowed, reason = principal_can_reveal(
            _windows("bob", ["ADMZ-Admins"])
        )
        assert allowed is True
        assert reason == "group:admz-admins"

    def test_case_insensitive_match(self):
        # AD often returns differently-cased group names depending on
        # how the resolver formats them. The check must be tolerant.
        allowed, reason = principal_can_reveal(
            _windows("carol", ["aDmInIsTrAtOrS"])
        )
        assert allowed is True
        assert reason.startswith("group:")

    def test_domain_qualified_group_matches_bare_config(self):
        # LDAP enrichment may return "AXIS\\Administrators". The
        # configured list ("Administrators") should still match.
        allowed, reason = principal_can_reveal(
            _windows("dave", ["AXIS\\Administrators"])
        )
        assert allowed is True

    def test_custom_groups_via_argument(self):
        # Use the explicit configured_groups arg to pin behavior in
        # the unit test without env-var fiddling.
        allowed, reason = principal_can_reveal(
            _windows("eve", ["CredAdmins"]),
            configured_groups=["CredAdmins"],
        )
        assert allowed is True

    def test_match_in_custom_groups_only(self):
        # 'Administrators' is the default but if the operator
        # overrides ADMZ_REVEAL_GROUPS to a custom list, the defaults
        # no longer grant.
        allowed, reason = principal_can_reveal(
            _windows("frank", ["Administrators"]),
            configured_groups=["CredAdmins"],
        )
        assert allowed is False
        assert reason == "not-in-reveal-groups"


class TestRequireRevealPermission:
    def test_returns_reason_on_success(self):
        reason = require_reveal_permission(
            _windows("alice", ["Administrators"])
        )
        assert reason.startswith("group:")

    def test_raises_403_for_anonymous(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as ei:
            require_reveal_permission(_anon())
        assert ei.value.status_code == 403

    def test_raises_403_for_missing_group(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as ei:
            require_reveal_permission(_windows("alice", ["Users"]))
        assert ei.value.status_code == 403
        # The error message should name the configured groups so the
        # operator knows what to ask for.
        assert "Administrators" in ei.value.detail


# ---------------------------------------------------------------------------
# Integration tests — REST endpoints
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient with an isolated DB + repointed fleet_settings
    singletons + a swappable auth backend."""
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")
    monkeypatch.delenv("ADMZ_REVEAL_GROUPS", raising=False)

    from admz import fleet_settings as fs_module
    from admz.api.routes import devices as devices_route
    from admz.api.routes import web as web_route
    db_path = str(tmp_path / "admz.db")
    _orig_fs = fs_module.fleet_settings
    _orig_devices_fs = devices_route.fleet_settings
    _orig_web_fs = web_route.fleet_settings
    fresh_fs = fs_module.FleetSettings(db_path)
    fs_module.fleet_settings = fresh_fs
    devices_route.fleet_settings = fresh_fs
    web_route.fleet_settings = fresh_fs

    # Default backend is NoAuth (anonymous). Tests rotate it by calling
    # client.app.state.auth = StubBackend(...) before the request.
    backend = StubBackend(_anon())
    set_active_backend(backend)

    from admz.api.main import app
    app.state._stub_backend = backend
    try:
        with TestClient(app, follow_redirects=False) as c:
            from admz.api.main import registry
            registry.add_device(
                "cam-gate-test", {"host": "192.0.2.42", "model": "M"}
            )
            registry.add_account(
                "cam-gate-test", "default",
                {
                    "username": "root", "password": "topsecret",
                    "account_type": "admin", "purpose": "primary",
                },
            )
            yield c
    finally:
        fs_module.fleet_settings = _orig_fs
        devices_route.fleet_settings = _orig_devices_fs
        web_route.fleet_settings = _orig_web_fs
        # Drop the stub so other test modules don't see it.
        from admz.auth import NoAuth
        set_active_backend(NoAuth())


def _set_principal(client, principal: Principal) -> None:
    """Swap the principal the stub backend returns for subsequent
    requests."""
    from admz.api.main import app
    app.state._stub_backend.principal = principal


# --- /api/fleet/settings/{key}/reveal endpoint -----------------------------


class TestFleetSettingReveal:
    def test_nonsensitive_key_returns_plaintext_without_gate(self, client):
        """Non-password keys don't need to be gated — there's nothing
        to protect — so the JS can use the same endpoint uniformly."""
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("default_username", "root")

        r = client.get("/api/fleet/settings/default_username/reveal")
        assert r.status_code == 200
        assert r.json() == {"key": "default_username", "value": "root"}

    def test_missing_key_404(self, client):
        r = client.get("/api/fleet/settings/no_such_key/reveal")
        assert r.status_code == 404

    def test_sensitive_anonymous_403(self, client):
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("default_password", "pass")

        r = client.get("/api/fleet/settings/default_password/reveal")
        assert r.status_code == 403

    def test_sensitive_anonymous_denied_even_with_legacy_flag_row(self, client):
        # Upgrade path (#151): an install that had "Allow LLMs to retrieve
        # plaintext" checked still carries the flag row in fleet_settings.
        # The row must be inert — the anonymous bypass it powered is gone.
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("default_password", "pass")
        fleet_settings.set("tool_get_credentials_enabled", "true")
        try:
            r = client.get("/api/fleet/settings/default_password/reveal")
            assert r.status_code == 403
            assert "pass" not in r.text
        finally:
            fleet_settings.delete("tool_get_credentials_enabled")

    def test_sensitive_admin_returns_plaintext(self, client):
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("default_password", "pass")

        _set_principal(client, _windows("alice", ["Administrators"]))
        r = client.get("/api/fleet/settings/default_password/reveal")
        assert r.status_code == 200
        assert r.json()["value"] == "pass"

    def test_sensitive_non_admin_denied(self, client):
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("default_password", "pass")

        _set_principal(client, _windows("carol", ["Users"]))
        r = client.get("/api/fleet/settings/default_password/reveal")
        assert r.status_code == 403


# --- windows-local: the anonymous principal is unreachable ------------------


class TestWindowsLocalChainNeverAnonymous:
    """#151's merge precondition, encoded as a test.

    Under ``ADMZ_AUTH_BACKEND=windows-local`` the chain is
    ``CompositeAuth([ApiKeyAuth, SessionAuth])`` — both raise 401 rather
    than synthesize a principal, and ``/api/fleet/settings/*`` is not in
    the middleware's exempt list. So an unauthenticated request dies at
    the middleware with 401; the reveal route (and with it any anonymous
    branch) is never reached. This holds regardless of legacy flag rows.
    """

    def test_unauthenticated_request_is_401_not_403(self, client):
        from admz.api.main import app
        from admz.auth import build_auth_backend, set_active_backend
        from admz.fleet_settings import fleet_settings

        fleet_settings.set("default_password", "pass")
        fleet_settings.set("tool_get_credentials_enabled", "true")
        set_active_backend(build_auth_backend("windows-local"))
        try:
            r = client.get("/api/fleet/settings/default_password/reveal")
            # 401 from the auth middleware — the route never ran. A 403
            # here would mean the route saw an (anonymous) principal.
            assert r.status_code == 401
            assert "pass" not in r.text
        finally:
            fleet_settings.delete("tool_get_credentials_enabled")
            set_active_backend(app.state._stub_backend)


# --- Audit log integration -------------------------------------------------


class TestRevealAuditing:
    def test_fleet_setting_reveal_is_audited(self, client):
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("default_password", "pass")
        _set_principal(client, _windows("alice", ["Administrators"]))

        r = client.get("/api/fleet/settings/default_password/reveal")
        assert r.status_code == 200

        from admz.audit import AuditLog
        entries = AuditLog().list_recent(action="reveal_fleet_setting", limit=5)
        assert entries
        assert entries[0].success is True
        assert entries[0].resource == "fleet_setting:default_password"
