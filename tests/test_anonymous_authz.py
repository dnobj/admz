"""Tests for CR-3 — anonymous principal cannot reach destructive endpoints.

Background: under ``ADMZ_AUTH_BACKEND=none`` (the default for local
dev), every request maps to the synthetic ``anonymous`` principal.
That's intentional, but five endpoints would be too easy to misuse
that way:

* ``POST /api/api-keys`` — minting long-lived credentials.
* ``POST /confirm-settings`` — every branch writes to a key in
  ``PROTECTED_SETTING_KEYS``.
* ``DELETE /api/devices/{id}`` — destructive.
* ``POST /api/snapshot/restore`` — data-loss.
* ``POST /api/plans/{id}/execute`` — drives real device ops.

These now require an authenticated principal (`require_authenticated_principal`).
Other state-changing routes (create_device, snapshot_device, schedule
CRUD, discovery scan/register, catalog execute) keep working for
anonymous — they just write audit rows attributing the action to
``anonymous``.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from admz.auth import (
    AuthBackend,
    NoAuth,
    Principal,
    set_active_backend,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubBackend(AuthBackend):
    def __init__(self, p):
        self.p = p

    async def authenticate(self, request):
        return self.p


@contextmanager
def _with_admin():
    """Install a Windows-IWA-like authenticated principal."""
    admin = Principal(
        name="AXIS\\admin", display_name="admin", source="windows",
        groups=["Administrators"], is_anonymous=False,
    )
    set_active_backend(_StubBackend(admin))
    try:
        yield admin
    finally:
        set_active_backend(NoAuth())


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")

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

    # Repoint the audit-log singleton so we can read what was written
    # back during the test.
    from admz import audit as audit_module
    fresh_audit = audit_module.AuditLog(db_path=db_path)
    monkeypatch.setattr(audit_module, "audit_log", fresh_audit)

    from admz.api.main import app
    try:
        with TestClient(app, follow_redirects=False) as c:
            yield c
    finally:
        fs_module.fleet_settings = _orig_fs
        devices_route.fleet_settings = _orig_devices_fs
        web_route.fleet_settings = _orig_web_fs


# ---------------------------------------------------------------------------
# Destructive endpoints refuse anonymous
# ---------------------------------------------------------------------------


class TestDestructiveEndpointsRefuseAnonymous:
    def test_anonymous_mint_api_key_403(self, client):
        r = client.post(
            "/api/api-keys", json={"display_name": "test", "expires_at": None}
        )
        assert r.status_code == 403
        assert "anonymous" in r.json()["detail"].lower() or \
               "authenticated" in r.json()["detail"].lower()

    def test_anonymous_confirm_settings_levels_403(self, client):
        r = client.post(
            "/confirm-settings",
            data={"action": "levels", "level_dangerous": "url_only"},
        )
        assert r.status_code == 403

    def test_anonymous_confirm_settings_password_403(self, client):
        r = client.post(
            "/confirm-settings",
            data={"action": "password", "new_password": "x",
                  "confirm_new_password": "x"},
        )
        assert r.status_code == 403

    def test_anonymous_confirm_settings_tool_toggle_403(self, client):
        r = client.post(
            "/confirm-settings",
            data={"action": "tool_toggle",
                  "get_credentials_enabled": "1"},
        )
        assert r.status_code == 403

    def test_anonymous_delete_device_403(self, client):
        # Seed a device first via an unauthenticated route (allowed).
        client.post(
            "/api/devices", json={"device_id": "anon-cam", "host": "x"}
        )
        r = client.delete("/api/devices/anon-cam")
        assert r.status_code == 403

    def test_anonymous_restore_device_403(self, client):
        client.post(
            "/api/devices", json={"device_id": "anon-cam", "host": "x"}
        )
        r = client.post(
            "/api/snapshot/restore",
            json={"device_id": "anon-cam", "ref": "HEAD"},
        )
        assert r.status_code == 403

    def test_anonymous_execute_plan_403(self, client):
        r = client.post("/api/plans/some-plan-id/execute")
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Authenticated principals can reach the same endpoints
# ---------------------------------------------------------------------------


class TestAuthenticatedPasses:
    def test_admin_mint_api_key_succeeds(self, client):
        with _with_admin():
            r = client.post(
                "/api/api-keys",
                json={"display_name": "admin-bot", "expires_at": None},
            )
        # Should mint successfully (201). The plaintext is in the response.
        assert r.status_code == 201
        body = r.json()
        assert "plaintext" in body
        assert body["plaintext"].startswith("admz_")

    def test_admin_confirm_settings_levels_succeeds(self, client):
        with _with_admin():
            r = client.post(
                "/confirm-settings",
                data={"action": "levels", "level_dangerous": "url_only"},
            )
        assert r.status_code == 200

    def test_admin_delete_device_succeeds(self, client):
        client.post(
            "/api/devices", json={"device_id": "to-delete", "host": "x"}
        )
        with _with_admin():
            r = client.delete("/api/devices/to-delete")
        assert r.status_code == 204


# ---------------------------------------------------------------------------
# Non-destructive routes still work for anonymous + are audited
# ---------------------------------------------------------------------------


class TestAnonymousLowRiskAllowedAndAudited:
    def test_anonymous_create_device_succeeds_and_audits(self, client):
        r = client.post(
            "/api/devices",
            json={"device_id": "low-risk-cam", "host": "192.0.2.99"},
        )
        assert r.status_code == 201

        from admz import audit as audit_module
        entries = audit_module.audit_log.list_recent(
            action="device.create", limit=5
        )
        assert entries
        # Anonymous principal should be recorded as the requester.
        assert entries[0].requester == "anonymous"
        assert entries[0].auth_source == "none"
        assert entries[0].success is True

    def test_anonymous_update_device_succeeds_and_audits(self, client):
        client.post(
            "/api/devices",
            json={"device_id": "upd-cam", "host": "192.0.2.50"},
        )
        r = client.put(
            "/api/devices/upd-cam", json={"nickname": "new-nick"}
        )
        assert r.status_code == 200

        from admz import audit as audit_module
        entries = audit_module.audit_log.list_recent(
            action="device.update", limit=5
        )
        assert entries
        assert entries[0].requester == "anonymous"

    def test_anonymous_create_schedule_gates_behind_widget(self, client):
        # Policy change (2026-07-03): creating a scheduled task is standing
        # behavior — non-interactive principals (anonymous included) get the
        # confirmation widget instead of a direct write. Only a console
        # operator's form submission writes directly.
        r = client.post(
            "/api/schedules",
            json={
                "schedule_id": "low-risk-sched",
                "description": "test",
                "interval": "1h",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["blocked"] is True
        assert body["confirm_url"].startswith("/confirm/")
        # nothing written until the card is approved — only the seeded
        # capability-survey cadence exists (ADR-0063 S2).
        ids = [s["id"] for s in client.get("/api/schedules").json()["schedules"]]
        assert ids == ["capability-survey"]


# ---------------------------------------------------------------------------
# require_authenticated_principal helper itself
# ---------------------------------------------------------------------------


class TestRequireAuthenticatedPrincipal:
    def test_anonymous_principal_raises_403(self):
        from fastapi import HTTPException
        from admz.authz import require_authenticated_principal

        anon = Principal(
            name="anonymous", display_name="anonymous",
            source="none", is_anonymous=True,
        )
        with pytest.raises(HTTPException) as ei:
            require_authenticated_principal(anon)
        assert ei.value.status_code == 403

    def test_none_principal_raises_403(self):
        from fastapi import HTTPException
        from admz.authz import require_authenticated_principal

        with pytest.raises(HTTPException) as ei:
            require_authenticated_principal(None)
        assert ei.value.status_code == 403

    def test_real_principal_passes(self):
        from admz.authz import require_authenticated_principal

        real = Principal(
            name="alice", display_name="alice",
            source="windows", is_anonymous=False,
        )
        # Should NOT raise.
        require_authenticated_principal(real)
