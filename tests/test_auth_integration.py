"""End-to-end integration tests for Phase 4 auth.

Spins up the FastAPI app via TestClient under each auth backend and
verifies the full request lifecycle — middleware → backend → route.

Foundation-level tests live in ``test_web_auth.py``; backend-internal
behavior in ``test_web_auth_backends.py``. This file is about wiring.
"""

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolate_admz_dirs(tmp_path, monkeypatch):
    """Same isolation fixture as test_api_routes.py — point ADMZ paths
    at a temp dir so tests don't touch real state."""
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))


def _make_client(monkeypatch, backend_name: str = "none", **env):
    """Build a TestClient with the requested auth backend active.

    Sets ADMZ_AUTH_TRUSTED_PROXIES to include "testclient" so the
    FastAPI TestClient (which sets ``request.client.host = "testclient"``)
    isn't rejected by the reverse-proxy backend's source-IP check.
    Production deployments use the default 127.0.0.1/::1 list.
    """
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", backend_name)
    monkeypatch.setenv(
        "ADMZ_AUTH_TRUSTED_PROXIES",
        "testclient,127.0.0.1,::1",
    )
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    # Reset module-level singletons so the new env is honored.
    import admz.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_ACTIVE_BACKEND", None)

    # Import (or re-import) the app after env is configured
    from admz.api.main import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# NoAuth — backward-compatible default
# ---------------------------------------------------------------------------


class TestNoAuthIntegration:
    """ADMZ_AUTH_BACKEND=none — existing zero-config behavior preserved."""

    def test_whoami_returns_anonymous(self, monkeypatch, tmp_path):
        client = _make_client(monkeypatch, "none")
        with client:
            r = client.get("/api/whoami")
            assert r.status_code == 200
            assert r.json()["is_anonymous"] is True
            assert r.json()["source"] == "none"

    def test_devices_endpoint_works_without_credentials(
        self, monkeypatch, tmp_path
    ):
        client = _make_client(monkeypatch, "none")
        # Need to set up git repo for the snapshot subsystem
        import subprocess
        (tmp_path / "config-repo").mkdir(parents=True, exist_ok=True)
        with client:
            r = client.get("/api/devices")
            # 200 with empty list — auth is permissive
            assert r.status_code == 200
            assert r.json() == []

    def test_health_endpoint_works(self, monkeypatch, tmp_path):
        client = _make_client(monkeypatch, "none")
        with client:
            r = client.get("/health")
            assert r.status_code == 200
            assert r.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# ReverseProxyAuth — Windows IWA via header
# ---------------------------------------------------------------------------


class TestReverseProxyAuthIntegration:
    """ADMZ_AUTH_BACKEND=windows — REMOTE_USER header required."""

    def test_no_header_returns_401(self, monkeypatch, tmp_path):
        client = _make_client(monkeypatch, "windows")
        with client:
            r = client.get("/api/whoami")
            assert r.status_code == 401
            assert "REMOTE_USER" in r.json()["detail"]

    def test_valid_header_returns_principal(self, monkeypatch, tmp_path):
        client = _make_client(monkeypatch, "windows")
        with client:
            r = client.get(
                "/api/whoami",
                headers={"REMOTE_USER": "AXIS\\alice"},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["display_name"] == "alice"
            assert body["domain"] == "AXIS"
            assert body["source"] == "windows"
            assert body["is_anonymous"] is False

    def test_health_bypasses_auth(self, monkeypatch, tmp_path):
        """The reverse proxy must be able to probe ADMZ liveness
        without forwarding credentials."""
        client = _make_client(monkeypatch, "windows")
        with client:
            r = client.get("/health")
            assert r.status_code == 200
            r2 = client.get("/api/health")
            assert r2.status_code == 200

    def test_protected_route_returns_401_without_header(
        self, monkeypatch, tmp_path
    ):
        client = _make_client(monkeypatch, "windows")
        with client:
            r = client.get("/api/devices")
            assert r.status_code == 401

    def test_protected_route_works_with_header(self, monkeypatch, tmp_path):
        client = _make_client(monkeypatch, "windows")
        with client:
            r = client.get(
                "/api/devices",
                headers={"REMOTE_USER": "AXIS\\alice"},
            )
            assert r.status_code == 200


# ---------------------------------------------------------------------------
# ApiKeyAuth — Bearer token
# ---------------------------------------------------------------------------


class TestApiKeyAuthIntegration:
    """ADMZ_AUTH_BACKEND=api-key — Authorization: Bearer admz_..."""

    def _mint_key(self, tmp_path, display_name="test-bot"):
        """Helper: create a key directly via the store so we have a
        plaintext to test with."""
        from admz.api_keys import ApiKeyStore

        store = ApiKeyStore(db_path=str(tmp_path / "admz.db"))
        return store.create(display_name=display_name, created_by="setup")

    def test_no_authorization_returns_401(self, monkeypatch, tmp_path):
        client = _make_client(monkeypatch, "api-key")
        with client:
            r = client.get("/api/whoami")
            assert r.status_code == 401

    def test_invalid_key_returns_401(self, monkeypatch, tmp_path):
        client = _make_client(monkeypatch, "api-key")
        with client:
            r = client.get(
                "/api/whoami",
                headers={"Authorization": "Bearer admz_invalid"},
            )
            assert r.status_code == 401

    def test_valid_key_returns_principal(self, monkeypatch, tmp_path):
        # Mint key BEFORE creating client so the same DB file is used
        created = self._mint_key(tmp_path, "nightly-bot")
        client = _make_client(monkeypatch, "api-key")
        with client:
            r = client.get(
                "/api/whoami",
                headers={"Authorization": "Bearer " + created.plaintext},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["source"] == "api-key"
            assert body["display_name"] == "nightly-bot"


# ---------------------------------------------------------------------------
# CompositeAuth — accept either method
# ---------------------------------------------------------------------------


class TestCompositeAuthIntegration:
    def test_accepts_windows_when_no_api_key(self, monkeypatch, tmp_path):
        client = _make_client(monkeypatch, "composite")
        with client:
            r = client.get(
                "/api/whoami", headers={"REMOTE_USER": "AXIS\\alice"}
            )
            assert r.status_code == 200
            assert r.json()["source"] == "windows"

    def test_accepts_api_key_when_no_windows(self, monkeypatch, tmp_path):
        from admz.api_keys import ApiKeyStore

        store = ApiKeyStore(db_path=str(tmp_path / "admz.db"))
        created = store.create(display_name="bot", created_by="setup")
        client = _make_client(monkeypatch, "composite")
        with client:
            r = client.get(
                "/api/whoami",
                headers={"Authorization": "Bearer " + created.plaintext},
            )
            assert r.status_code == 200
            assert r.json()["source"] == "api-key"

    def test_no_credentials_returns_401(self, monkeypatch, tmp_path):
        client = _make_client(monkeypatch, "composite")
        with client:
            r = client.get("/api/whoami")
            assert r.status_code == 401


# ---------------------------------------------------------------------------
# /api/api-keys CRUD endpoints
# ---------------------------------------------------------------------------


class TestApiKeyCrudEndpoints:
    """The minting / listing / revoking endpoints themselves require
    auth, so we run these tests in NoAuth mode (where the principal is
    'anonymous') to verify the routes work without dragging the auth
    test setup into every assertion."""

    def test_list_empty(self, monkeypatch, tmp_path):
        client = _make_client(monkeypatch, "none")
        with client:
            r = client.get("/api/api-keys")
            assert r.status_code == 200
            assert r.json() == []

    def test_create_returns_plaintext_once(self, monkeypatch, tmp_path):
        client = _make_client(monkeypatch, "none")
        with client:
            r = client.post(
                "/api/api-keys",
                json={"display_name": "nightly-bot"},
            )
            assert r.status_code == 201
            body = r.json()
            assert body["display_name"] == "nightly-bot"
            assert body["plaintext"].startswith("admz_")
            assert body["created_by"] == "anonymous"
            assert body["revoked"] is False

    def test_create_empty_display_name_returns_400(
        self, monkeypatch, tmp_path
    ):
        client = _make_client(monkeypatch, "none")
        with client:
            r = client.post("/api/api-keys", json={"display_name": ""})
            # Pydantic validation kicks in first (min_length=1) → 422
            assert r.status_code in (400, 422)

    def test_create_then_list(self, monkeypatch, tmp_path):
        client = _make_client(monkeypatch, "none")
        with client:
            client.post("/api/api-keys", json={"display_name": "bot-1"})
            client.post("/api/api-keys", json={"display_name": "bot-2"})
            r = client.get("/api/api-keys")
            assert r.status_code == 200
            names = {k["display_name"] for k in r.json()}
            assert names == {"bot-1", "bot-2"}
            # Plaintext is NEVER in list responses
            assert all("plaintext" not in k for k in r.json())

    def test_revoke_returns_204_and_excludes_from_list(
        self, monkeypatch, tmp_path
    ):
        client = _make_client(monkeypatch, "none")
        with client:
            r = client.post("/api/api-keys", json={"display_name": "doomed"})
            new_id = r.json()["id"]
            r = client.delete(f"/api/api-keys/{new_id}")
            assert r.status_code == 204
            r = client.get("/api/api-keys")
            assert all(k["id"] != new_id for k in r.json())

    def test_revoke_nonexistent_returns_404(self, monkeypatch, tmp_path):
        client = _make_client(monkeypatch, "none")
        with client:
            r = client.delete("/api/api-keys/99999")
            assert r.status_code == 404
