"""End-to-end tests for the windows-local auth backend (ADR-0033).

Login form → LogonUser (mocked) → session cookie → authenticated
requests; HTML redirects vs API 401s; logout; rate limiting; Bearer API
keys continuing to work for agents.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from admz.win_auth import WindowsIdentity


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient running the real app under ADMZ_AUTH_BACKEND=windows-local
    with a tmp DB, a tmp session store, and a mocked LogonUser."""
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "windows-local")

    # Fresh session store on the tmp DB.
    import admz.session_store as ss_module
    ss_module.set_session_store(ss_module.SessionStore(str(tmp_path / "admz.db")))

    # Mock Windows credential validation: alice/correct-horse succeeds.
    import admz.win_auth as win_auth_module

    def fake_validate(username, password, domain=None):
        if username in ("alice", ".\\alice") and password == "correct-horse":
            return WindowsIdentity(
                username="alice", domain=None,
                groups=["Administrators", "Users"],
            )
        return None

    monkeypatch.setattr(
        win_auth_module, "validate_windows_credentials", fake_validate
    )

    # Repoint the audit-log singleton at the tmp DB (it was built at
    # import time against whatever ADMZ_DB_PATH was then).
    from admz import audit as audit_module
    monkeypatch.setattr(
        audit_module, "audit_log",
        audit_module.AuditLog(db_path=str(tmp_path / "admz.db")),
    )

    # Install the enforcing backend for the app's middleware.
    from admz.auth import NoAuth, build_auth_backend, set_active_backend
    set_active_backend(build_auth_backend("windows-local"))

    import admz.api.main as main_module
    from admz.backends.sqlite_backend import SQLiteDeviceRegistry
    fresh = SQLiteDeviceRegistry(
        db_path=str(tmp_path / "admz.db"), key_path=str(tmp_path / "admz.key"),
    )
    monkeypatch.setattr(main_module, "registry", fresh)
    import admz.api.templating as templating
    monkeypatch.setattr(templating, "_registry", lambda: fresh)

    try:
        with TestClient(main_module.app) as c:
            yield c
    finally:
        # Restore the permissive default so other test files are unaffected.
        set_active_backend(NoAuth())
        ss_module.set_session_store(None)


def _login(client, username="alice", password="correct-horse"):
    return client.post(
        "/login",
        data={"username": username, "password": password, "next": "/devices"},
        follow_redirects=False,
    )


class TestUnauthenticated:
    def test_html_page_redirects_to_login(self, client):
        resp = client.get(
            "/devices", headers={"Accept": "text/html"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers["location"].startswith("/login?next=")

    def test_api_request_gets_401_json(self, client):
        resp = client.get("/api/devices")
        assert resp.status_code == 401
        assert resp.headers["content-type"].startswith("application/json")

    def test_login_page_is_reachable(self, client):
        resp = client.get("/login", headers={"Accept": "text/html"})
        assert resp.status_code == 200
        assert "Windows username" in resp.text

    def test_health_stays_exempt(self, client):
        assert client.get("/api/health").status_code == 200


class TestLoginFlow:
    def test_successful_login_sets_session_and_authenticates(self, client):
        resp = _login(client)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/devices"
        assert "admz_session" in resp.cookies

        who = client.get("/api/whoami")
        assert who.status_code == 200
        body = who.json()
        assert body["name"] == "alice"
        assert body["source"] == "windows-local"
        assert body["is_anonymous"] is False
        assert "Administrators" in body["groups"]

        # The HTML UI now renders (no redirect) with a sign-out control.
        page = client.get("/devices", headers={"Accept": "text/html"})
        assert page.status_code == 200
        assert "/logout" in page.text

    def test_bad_password_generic_error(self, client):
        resp = _login(client, password="wrong")
        assert resp.status_code == 401
        assert "Sign-in failed" in resp.text
        # No hint about which part was wrong; no session cookie.
        assert "wrong" not in resp.text
        assert "admz_session" not in resp.cookies

    def test_password_never_echoed_or_stored(self, client, tmp_path):
        _login(client)
        import sqlite3
        blobs = sqlite3.connect(str(tmp_path / "admz.db")).execute(
            "SELECT principal_json FROM web_sessions"
        ).fetchall()
        assert blobs
        assert all("correct-horse" not in b[0] for b in blobs)

    def test_next_redirect_only_same_site(self, client):
        resp = client.post(
            "/login",
            data={"username": "alice", "password": "correct-horse",
                  "next": "https://evil.example/phish"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == "/devices"

    def test_rate_limit_kicks_in(self, client):
        from admz.rate_limit import rate_limiter
        rate_limiter.reset()
        last = None
        for _ in range(6):
            last = _login(client, password="wrong")
        assert last.status_code == 429
        assert "Too many" in last.text

    def test_login_audited(self, client):
        _login(client)
        _login(client, password="wrong")
        from admz import audit as audit_module
        entries = audit_module.audit_log.list_recent(
            action="auth.login", limit=5,
        )
        assert entries
        outcomes = {e.success for e in entries}
        assert True in outcomes and False in outcomes  # success + failure rows


class TestLogout:
    def test_logout_revokes_session(self, client):
        _login(client)
        assert client.get("/api/whoami").status_code == 200
        out = client.post("/logout", follow_redirects=False)
        assert out.status_code == 303
        assert out.headers["location"] == "/login"
        # Session is dead server-side even if a cookie copy survived.
        resp = client.get(
            "/devices", headers={"Accept": "text/html"},
            follow_redirects=False,
        )
        assert resp.status_code == 303


class TestAgentsKeepBearer:
    def test_api_key_authenticates(self, client, tmp_path):
        from admz.api_keys import ApiKeyStore
        created = ApiKeyStore(str(tmp_path / "admz.db")).create(
            "ci-bot", created_by="test", groups=["Administrators"],
        )
        resp = client.get(
            "/api/whoami",
            headers={"Authorization": f"Bearer {created.plaintext}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "api-key:ci-bot"
        assert body["is_anonymous"] is False


# ---------------------------------------------------------------------------
# Negotiate SSO (ADR-0035) — route flow with a mocked SSPI handshake
# ---------------------------------------------------------------------------

_LEG1 = b"\x01leg1"      # browser's opening token  → server challenges
_LEG2 = b"\x03leg2"      # browser's answer         → handshake completes
_CHALLENGE = b"\x02challenge"


def _negotiate_header(blob: bytes) -> dict:
    import base64
    return {"Authorization": f"Negotiate {base64.b64encode(blob).decode()}"}


@pytest.fixture
def sso(client, monkeypatch):
    """The windows-local client with Negotiate SSO mocked: a deterministic
    two-leg (NTLM-shaped) handshake that signs in alice."""
    import admz.win_sspi as win_sspi

    monkeypatch.setattr(win_sspi, "sso_available", lambda: True)
    # Fresh parking lot so tests can't see each other's partial handshakes.
    monkeypatch.setattr(
        win_sspi, "pending_handshakes", win_sspi.PendingHandshakes()
    )

    class FakeHandshake:
        def step(self, blob):
            if blob == _LEG1:
                return win_sspi.CONTINUE, _CHALLENGE, None
            if blob == _LEG2:
                return win_sspi.COMPLETE, b"", WindowsIdentity(
                    username="alice", domain=None,
                    groups=["Administrators", "Users"],
                )
            return win_sspi.FAILED, b"", None

        def close(self):
            pass

    monkeypatch.setattr(win_sspi, "NegotiateHandshake", FakeHandshake)

    from admz.rate_limit import rate_limiter
    rate_limiter.reset()
    return client


class TestSsoLogin:
    def test_login_page_offers_sso_button(self, sso):
        page = sso.get("/login", headers={"Accept": "text/html"})
        assert page.status_code == 200
        assert "/login/sso" in page.text
        assert "Continue as the signed-in Windows user" in page.text
        # The "different user" form is still there (ACS parity).
        assert "Windows username" in page.text

    def test_login_page_hides_button_when_unavailable(self, client, monkeypatch):
        import admz.win_sspi as win_sspi
        monkeypatch.setattr(win_sspi, "sso_available", lambda: False)
        page = client.get("/login", headers={"Accept": "text/html"})
        assert "/login/sso" not in page.text

    def test_loopback_ip_origin_gets_localhost_hint(self, sso):
        """KL-AUTH-008, observed live: browsers never treat a literal IP
        as intranet zone, so SSO prompts instead of being silent. The
        page steers 127.0.0.1 visitors to localhost — and only them."""
        on_ip = sso.get(
            "http://127.0.0.1/login?next=/devices",
            headers={"Accept": "text/html"},
        )
        assert "rather than using your" in on_ip.text
        assert "http://localhost/login?next=/devices" in on_ip.text

        on_name = sso.get(
            "http://localhost/login", headers={"Accept": "text/html"},
        )
        assert "rather than using your" not in on_name.text

    def test_bare_get_issues_negotiate_challenge(self, sso):
        resp = sso.get("/login/sso", follow_redirects=False)
        assert resp.status_code == 401
        assert resp.headers["www-authenticate"] == "Negotiate"
        # Unsupporting browsers render the body — it must route back.
        assert "/login?sso=failed" in resp.text

    def test_full_dance_signs_in(self, sso):
        import base64

        # Leg 1: browser's opening token → challenge comes back.
        leg1 = sso.get(
            "/login/sso?next=/devices", headers=_negotiate_header(_LEG1),
            follow_redirects=False,
        )
        assert leg1.status_code == 401
        challenge = leg1.headers["www-authenticate"]
        assert challenge.startswith("Negotiate ")
        assert base64.b64decode(challenge.split(" ", 1)[1]) == _CHALLENGE

        # Leg 2: browser answers → session established, redirected.
        leg2 = sso.get(
            "/login/sso?next=/devices", headers=_negotiate_header(_LEG2),
            follow_redirects=False,
        )
        assert leg2.status_code == 303
        assert leg2.headers["location"] == "/devices"
        assert "admz_session" in leg2.cookies

        who = sso.get("/api/whoami")
        assert who.status_code == 200
        body = who.json()
        assert body["name"] == "alice"
        assert body["source"] == "windows-local"
        assert "Administrators" in body["groups"]

    def test_failed_handshake_redirects_to_form(self, sso):
        resp = sso.get(
            "/login/sso", headers=_negotiate_header(b"junk-token"),
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers["location"].startswith("/login?sso=failed")
        assert "admz_session" not in resp.cookies
        # The form page explains, gently.
        page = sso.get(resp.headers["location"], headers={"Accept": "text/html"})
        assert "Single sign-on didn" in page.text

    def test_sso_unavailable_redirects_to_form(self, client, monkeypatch):
        import admz.win_sspi as win_sspi
        monkeypatch.setattr(win_sspi, "sso_available", lambda: False)
        resp = client.get("/login/sso", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"].startswith("/login?sso=failed")

    def test_next_redirect_only_same_site(self, sso):
        resp = sso.get(
            "/login/sso?next=https://evil.example/phish",
            headers=_negotiate_header(_LEG2),
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == "/devices"

    def test_sso_login_audited_with_method(self, sso):
        sso.get(
            "/login/sso", headers=_negotiate_header(_LEG2),
            follow_redirects=False,
        )
        from admz import audit as audit_module
        entries = audit_module.audit_log.list_recent(
            action="auth.login", limit=5,
        )
        assert any(
            e.success and e.details.get("method") == "negotiate"
            for e in entries
        )
