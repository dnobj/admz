"""Tests for the group-membership Reveal gate (Pattern A).

Background: previously, the per-account /credentials endpoint and the
new /api/fleet/settings/{key}/reveal endpoint were gated only by
fleet-wide flags. With Phase-4 authentication producing real
Principals carrying group memberships, sensitive operations now check
membership in ADMZ_REVEAL_GROUPS (default: Administrators, ADMZ-Admins).

For ``ADMZ_AUTH_BACKEND=none`` deployments (anonymous principal),
the endpoints fall back to the existing
``web_reveal_credentials_enabled`` / ``tool_get_credentials_enabled``
flag pair so local single-user installs keep working without IIS.

This file pins:
  - reveal_groups() env-var parsing + defaults
  - principal_can_reveal() decision matrix (anonymous, no-groups,
    mismatch, match by Administrators, match by ADMZ-Admins,
    domain-prefixed group, case-insensitive comparison)
  - /api/devices/{id}/credentials endpoint: gate matrix end-to-end
  - /api/fleet/settings/{key}/reveal endpoint: non-sensitive bypass,
    sensitive gate, plaintext on allow
  - Audit-log entries on both allow and deny paths
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
    def test_anonymous_returns_fallback_sentinel(self):
        allowed, reason = principal_can_reveal(_anon())
        assert allowed is False
        assert reason == "anonymous-fallback"

    def test_none_principal_returns_fallback_sentinel(self):
        allowed, reason = principal_can_reveal(None)
        assert allowed is False
        assert reason == "anonymous-fallback"

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


# --- per-account /credentials endpoint -------------------------------------


class TestAccountRevealGate:
    def test_anonymous_flag_off_403(self, client):
        # Default principal is anonymous + no flag set → flag fallback
        # produces 403 with the existing helpful message.
        from admz.fleet_settings import fleet_settings
        fleet_settings.delete("web_reveal_credentials_enabled")
        fleet_settings.delete("tool_get_credentials_enabled")

        r = client.get("/api/devices/cam-gate-test/credentials?account_id=default")
        assert r.status_code == 403
        detail = r.json()["detail"].lower()
        assert "/confirm-settings" in detail

    def test_anonymous_web_flag_on_returns_creds(self, client):
        """The 'local dev' path: ADMZ_AUTH_BACKEND=none + web flag on."""
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("web_reveal_credentials_enabled", "true")

        r = client.get("/api/devices/cam-gate-test/credentials?account_id=default")
        assert r.status_code == 200
        assert r.json()["password"] == "topsecret"

    def test_authenticated_administrators_allowed_without_flag(self, client):
        """The 'production' path: authenticated Windows user in
        Administrators → allowed regardless of fleet flag."""
        from admz.fleet_settings import fleet_settings
        fleet_settings.delete("web_reveal_credentials_enabled")
        fleet_settings.delete("tool_get_credentials_enabled")

        _set_principal(client, _windows("alice", ["Administrators"]))
        r = client.get("/api/devices/cam-gate-test/credentials?account_id=default")
        assert r.status_code == 200
        assert r.json()["password"] == "topsecret"

    def test_authenticated_admz_admins_allowed(self, client):
        from admz.fleet_settings import fleet_settings
        fleet_settings.delete("web_reveal_credentials_enabled")

        _set_principal(client, _windows("bob", ["ADMZ-Admins"]))
        r = client.get("/api/devices/cam-gate-test/credentials?account_id=default")
        assert r.status_code == 200

    def test_authenticated_non_admin_denied_even_with_flag_on(self, client):
        """Once you're authenticated, the group gate is authoritative.
        Turning on the flag does NOT grant access to a non-admin Windows
        user — the flag is the *anonymous* fallback only."""
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("web_reveal_credentials_enabled", "true")

        _set_principal(client, _windows("carol", ["Users"]))
        r = client.get("/api/devices/cam-gate-test/credentials?account_id=default")
        assert r.status_code == 403
        detail = r.json()["detail"]
        assert "not in any of the configured reveal groups" in detail

    def test_authenticated_no_groups_denied(self, client):
        # IWA without LDAP enrichment → empty groups → denied.
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("web_reveal_credentials_enabled", "true")

        _set_principal(client, _windows("dave", []))
        r = client.get("/api/devices/cam-gate-test/credentials?account_id=default")
        assert r.status_code == 403

    def test_custom_reveal_groups_via_env(self, client, monkeypatch):
        monkeypatch.setenv("ADMZ_REVEAL_GROUPS", "CredAdmins")
        # Administrators no longer counts when the custom list overrides
        _set_principal(client, _windows("alice", ["Administrators"]))
        r = client.get("/api/devices/cam-gate-test/credentials?account_id=default")
        assert r.status_code == 403
        # CredAdmins does.
        _set_principal(client, _windows("eve", ["CredAdmins"]))
        r = client.get("/api/devices/cam-gate-test/credentials?account_id=default")
        assert r.status_code == 200


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

    def test_sensitive_anonymous_flag_off_403(self, client):
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("default_password", "pass")
        fleet_settings.delete("web_reveal_credentials_enabled")

        r = client.get("/api/fleet/settings/default_password/reveal")
        assert r.status_code == 403

    def test_sensitive_anonymous_flag_on_returns_plaintext(self, client):
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("default_password", "pass")
        fleet_settings.set("web_reveal_credentials_enabled", "true")

        r = client.get("/api/fleet/settings/default_password/reveal")
        assert r.status_code == 200
        assert r.json()["value"] == "pass"

    def test_sensitive_admin_returns_plaintext_without_flag(self, client):
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("default_password", "pass")
        fleet_settings.delete("web_reveal_credentials_enabled")

        _set_principal(client, _windows("alice", ["Administrators"]))
        r = client.get("/api/fleet/settings/default_password/reveal")
        assert r.status_code == 200
        assert r.json()["value"] == "pass"

    def test_sensitive_non_admin_denied(self, client):
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("default_password", "pass")
        fleet_settings.set("web_reveal_credentials_enabled", "true")

        _set_principal(client, _windows("carol", ["Users"]))
        r = client.get("/api/fleet/settings/default_password/reveal")
        assert r.status_code == 403


# --- Audit log integration -------------------------------------------------


class TestRevealAuditing:
    def test_successful_reveal_is_audited(self, client):
        from admz.fleet_settings import fleet_settings
        fleet_settings.set("web_reveal_credentials_enabled", "true")

        r = client.get("/api/devices/cam-gate-test/credentials?account_id=default")
        assert r.status_code == 200

        from admz.audit import AuditLog
        entries = AuditLog().list_recent(action="get_credentials", limit=5)
        assert entries, "expected an audit entry"
        # The most recent entry should be the success path.
        assert entries[0].success is True
        assert "decision" in entries[0].details

    def test_denied_reveal_is_audited(self, client):
        from admz.fleet_settings import fleet_settings
        fleet_settings.delete("web_reveal_credentials_enabled")
        fleet_settings.delete("tool_get_credentials_enabled")

        r = client.get("/api/devices/cam-gate-test/credentials?account_id=default")
        assert r.status_code == 403

        from admz.audit import AuditLog
        entries = AuditLog().list_recent(action="get_credentials", limit=5)
        assert entries
        assert entries[0].success is False
        assert "reveal-denied" in entries[0].error_message

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
