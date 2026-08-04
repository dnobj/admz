"""Route tests for the GitHub App "Connect GitHub" flow (ADR-0045):
signed-state guard, the manifest connect form, the two OAuth callbacks
(exempt + self-authenticating), and test / disconnect.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import admz.api.main as main_module
from admz.api.routes import github_app as gh_routes
from admz.github_app import client as gh_client
from admz.github_app import secrets as gh_secrets


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")
    # connect/test/disconnect require an authenticated principal; under the
    # 'none' backend the principal is anonymous, so neutralize that gate here.
    monkeypatch.setattr("admz.authz.require_authenticated_principal", lambda p: None)
    gh_secrets.clear()
    gh_client.clear_token_cache()
    with TestClient(main_module.app, follow_redirects=False) as c:
        yield c
    gh_secrets.clear()
    gh_client.clear_token_cache()


@pytest.fixture
def anon_client(monkeypatch):
    """Like ``client`` but with the REAL ``require_authenticated_principal``
    still installed (#211).

    ``client`` neutralizes the gate so the happy-path tests can run without
    constructing a principal — which left ``_require_principal`` (github_app.py
    line 87) unexecuted by every test in this file. Under
    ``ADMZ_AUTH_BACKEND=none``, the documented default, the middleware resolves
    each request to the synthetic *anonymous* principal and lets it through, so
    that in-route gate is the only thing standing between an unauthenticated
    caller and the fleet's config-push credentials. These requests are
    therefore the genuine article: real backend, real principal, real gate.
    """
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")
    with TestClient(main_module.app, follow_redirects=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Signed state (pure)
# ---------------------------------------------------------------------------


class TestState:
    def test_sign_verify_roundtrip_and_phase(self):
        s = gh_routes.sign_state("setup")
        assert gh_routes.verify_state(s, phase="setup")
        assert not gh_routes.verify_state(s, phase="install")  # wrong phase

    def test_tamper_rejected(self):
        s = gh_routes.sign_state("setup")
        body, sig = s.split(".", 1)
        flip = "A" if body[-1] != "A" else "B"
        assert not gh_routes.verify_state(f"{body[:-1]}{flip}.{sig}", phase="setup")

    def test_expiry(self):
        s = gh_routes.sign_state("setup", now=1000)
        assert gh_routes.verify_state(s, phase="setup", now=1100)
        assert not gh_routes.verify_state(
            s, phase="setup", now=1000 + gh_routes._STATE_TTL + 5
        )

    def test_callback_paths_are_auth_exempt(self):
        from admz.auth import is_exempt
        assert is_exempt("/api/github/setup/callback")
        assert is_exempt("/api/github/install/callback")
        assert not is_exempt("/api/github/connect")  # connect requires auth


# ---------------------------------------------------------------------------
# Connect (manifest form)
# ---------------------------------------------------------------------------


class TestConnect:
    def test_connect_returns_manifest_form(self, client):
        r = client.get("/api/github/connect")
        assert r.status_code == 200
        body = r.text
        assert "github.com/settings/apps/new" in body
        assert "manifest" in body
        assert "contents" in body  # default_permissions in the manifest JSON


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


class TestCallbacks:
    def test_setup_bad_state_400(self, client):
        r = client.get("/api/github/setup/callback?code=x&state=bogus")
        assert r.status_code == 400

    def test_setup_stores_creds_and_redirects_to_install(self, client, monkeypatch):
        monkeypatch.setattr(
            gh_client, "exchange_manifest_code",
            lambda code, session=None: {
                "id": 55, "slug": "admz-cfg", "pem": "PEMDATA",
                "client_secret": "cs",
            },
        )
        state = gh_routes.sign_state("setup")
        r = client.get(f"/api/github/setup/callback?code=abc&state={state}")
        assert r.status_code == 303
        assert "github.com/apps/admz-cfg/installations/new" in r.headers["location"]
        assert gh_secrets.get_app_id() == "55"
        assert gh_secrets.get_private_key() == "PEMDATA"

    def test_install_without_app_redirects_error(self, client):
        # No app registered yet → nothing to install into.
        r = client.get("/api/github/install/callback?installation_id=7")
        assert r.status_code == 303
        assert "github_error=register" in r.headers["location"]

    def test_install_completes_via_jwt_discovery(self, client, monkeypatch):
        # GitHub's post-install redirect carries no signed state — ADMZ
        # authenticates by discovering the installation with the App JWT.
        gh_secrets.save_app(1, "s", "PEM")
        gh_secrets.set_config_repo("o/r")
        monkeypatch.setattr(gh_client, "list_app_installations",
                            lambda app_id, pem, session=None: [{"id": 145, "account": "o"}])
        monkeypatch.setattr(gh_client, "get_installation_token", lambda *a, **k: "tok")
        monkeypatch.setattr(
            gh_client, "list_installation_repositories",
            lambda tok, session=None: [{"full_name": "o/r", "owner": "o", "name": "r"}])
        monkeypatch.setattr("admz.snapshot.git_repo.GitRepo.set_remote_url",
                            lambda self, url: None)
        r = client.get("/api/github/install/callback?installation_id=145")
        assert r.status_code == 303
        assert "github_connected=1" in r.headers["location"]
        assert gh_secrets.get_installation_id() == "145"
        assert gh_secrets.is_connected()


# ---------------------------------------------------------------------------
# Test + Disconnect
# ---------------------------------------------------------------------------


class TestTestAndDisconnect:
    def test_test_when_not_connected(self, client):
        r = client.post("/api/github/test")
        assert r.status_code == 200 and r.json()["ok"] is False

    def test_test_when_connected(self, client, monkeypatch):
        gh_secrets.save_app(1, "s", "PEM")
        gh_secrets.set_installation_id(9)
        gh_secrets.set_config_repo("o/r")
        monkeypatch.setattr(gh_client, "get_installation_token",
                            lambda *a, **k: "ghs_tok")
        monkeypatch.setattr(
            gh_client, "list_installation_repositories",
            lambda tok, session=None: [
                {"full_name": "o/r", "owner": "o", "name": "r"}
            ],
        )
        r = client.post("/api/github/test")
        j = r.json()
        assert r.status_code == 200 and j["ok"] is True and j["repo"] == "o/r"

    def test_disconnect_clears_everything(self, client, monkeypatch):
        gh_secrets.save_app(1, "s", "PEM")
        gh_secrets.set_installation_id(9)
        monkeypatch.setattr(
            "admz.snapshot.git_repo.GitRepo.set_remote_url",
            lambda self, url: None,  # don't mutate the real config-repo
        )
        r = client.post("/api/github/disconnect")
        assert r.status_code == 200 and r.json()["ok"] is True
        assert not gh_secrets.is_connected()
        assert gh_secrets.get_app_id() is None


class TestRefresh:
    def test_refresh_without_app(self, client):
        r = client.post("/api/github/refresh")
        assert r.status_code == 200 and r.json()["ok"] is False

    def test_refresh_discovers_and_connects(self, client, monkeypatch):
        gh_secrets.save_app(1, "s", "PEM")
        gh_secrets.set_config_repo("o/r")
        monkeypatch.setattr(gh_client, "list_app_installations",
                            lambda app_id, pem, session=None: [{"id": 7, "account": "o"}])
        monkeypatch.setattr(gh_client, "get_installation_token", lambda *a, **k: "tok")
        monkeypatch.setattr(
            gh_client, "list_installation_repositories",
            lambda tok, session=None: [{"full_name": "o/r", "owner": "o", "name": "r"}])
        monkeypatch.setattr("admz.snapshot.git_repo.GitRepo.set_remote_url",
                            lambda self, url: None)
        r = client.post("/api/github/refresh")
        j = r.json()
        assert j["ok"] is True and j["repo"] == "o/r" and j["connected"] is True
        assert gh_secrets.get_installation_id() == "7"


class TestAnonymousRefused:
    """One guard per route that goes through ``_require_principal`` (#211).

    Deleting ``require_authenticated_principal(principal)`` from
    ``_require_principal`` — or dropping the ``await _require_principal(request)``
    from any single route below — turns the corresponding test red. Before
    these existed, all of that could be deleted with the suite still green.

    The two OAuth callbacks are deliberately absent: they are on the auth
    exemption list by design (asserted in ``test_callback_paths_are_auth_exempt``)
    because GitHub calls them, and they authenticate on signed state / App JWT
    instead.
    """

    def test_anonymous_connect_403(self, anon_client):
        r = anon_client.get("/api/github/connect")
        assert r.status_code == 403
        assert "authenticated" in r.json()["detail"].lower()

    def test_anonymous_refresh_403(self, anon_client):
        # No app is registered, so without the gate this returns 200
        # {"ok": false} — 403 can only come from the gate.
        r = anon_client.post("/api/github/refresh")
        assert r.status_code == 403

    def test_anonymous_test_403(self, anon_client):
        # Likewise: not connected → 200 {"ok": false} if the gate is gone.
        r = anon_client.post("/api/github/test")
        assert r.status_code == 403

    def test_anonymous_disconnect_403(self, anon_client):
        r = anon_client.post("/api/github/disconnect")
        assert r.status_code == 403


class TestSettingsCard:
    def test_settings_renders_github_card(self, client):
        r = client.get("/settings")
        assert r.status_code == 200
        assert "GitHub config backup" in r.text
        assert "Connect GitHub" in r.text  # not connected → shows Connect

    def test_settings_shows_finish_when_app_registered(self, client):
        gh_secrets.save_app(1, "admz-cfg", "PEM")  # registered, not installed
        r = client.get("/settings")
        assert "Finish connecting" in r.text
        assert "Finish install" in r.text  # the badge text
