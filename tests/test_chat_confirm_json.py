"""Tests for the JSON twin of the /confirm/{token} flow (Phase 5C).

The chat client uses /api/chat/confirm/{token} GET to fetch session
details and POST to submit approval. These tests verify that:

  - GET returns the correct shape and respects expired/completed
  - POST completes a pending session
  - Password gating works the same way as the HTML form
  - Per-token lockout still fires
  - Rate limiter still fires
  - 410/429/403 status codes match what the chat client expects
"""

import pytest
from fastapi.testclient import TestClient

from admz.rate_limit import rate_limiter as global_limiter


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")

    global_limiter.reset()
    # Don't let an exhausted bucket from a previous test cause a
    # spurious 429 — give the test plenty of headroom.
    global_limiter.configure("confirm", capacity=100, refill_per_s=100)

    import admz.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_ACTIVE_BACKEND", None)

    from admz.api.main import app

    try:
        with TestClient(app) as c:
            yield c
    finally:
        # Restore the rate-limit policy to defaults so subsequent
        # tests in other files don't see our tight 'rate_limited_per_ip'
        # bucket config. RateLimiter.reset() only clears buckets, not
        # policy — we have to reconfigure explicitly.
        global_limiter.configure("confirm", capacity=10, refill_per_s=1.0 / 6.0)
        global_limiter.reset()
        # Best-effort cleanup of the in-memory lockout tracker.
        from admz.api.routes.confirm import _PW_ATTEMPTS
        _PW_ATTEMPTS.clear()


def _make_session(confirmation_level="url_only", risk_level="dangerous"):
    """Create a confirm session and return its token."""
    from admz.api.confirm_store import confirm_store
    return confirm_store.create_session(
        device_id="cam-01",
        operation_id="factorydefault.cgi:factory-reset",
        family="vapix",
        params={},
        risk_level=risk_level,
        confirmation_level=confirmation_level,
        danger_description="Resets the device to factory defaults.",
    )


# ---------------------------------------------------------------------------
# GET /api/chat/confirm/{token}
# ---------------------------------------------------------------------------


class TestChatConfirmDetails:
    def test_returns_session_shape(self, client):
        session = _make_session()
        r = client.get(f"/api/chat/confirm/{session.token}")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "pending"
        assert body["device_id"] == "cam-01"
        assert body["operation_id"] == "factorydefault.cgi:factory-reset"
        assert body["risk_level"] == "dangerous"
        assert body["confirmation_level"] == "url_only"
        assert body["danger_description"].startswith("Resets")
        assert body["needs_password"] is False
        assert body["is_plan"] is False

    def test_needs_password_when_configured(self, client):
        from admz.api.confirm_store import hash_confirm_password
        from admz.fleet_settings import fleet_settings as fs
        fs.set("confirm_password_hash", hash_confirm_password("hunter2"))

        try:
            session = _make_session(confirmation_level="url_and_password")
            r = client.get(f"/api/chat/confirm/{session.token}")
            assert r.status_code == 200
            assert r.json()["needs_password"] is True
        finally:
            fs.delete("confirm_password_hash")

    def test_url_and_password_downgrades_when_no_password_set(self, client):
        # If url_and_password is requested but no password is in the
        # fleet store, treat as url_only so the operator isn't locked
        # out. Mirrors HTML form behavior.
        from admz.fleet_settings import fleet_settings as fs
        fs.delete("confirm_password_hash")

        session = _make_session(confirmation_level="url_and_password")
        r = client.get(f"/api/chat/confirm/{session.token}")
        assert r.status_code == 200
        assert r.json()["needs_password"] is False

    def test_unknown_token_returns_410(self, client):
        r = client.get("/api/chat/confirm/does-not-exist-token")
        assert r.status_code == 410
        assert r.json()["status"] == "expired_or_not_found"


# ---------------------------------------------------------------------------
# POST /api/chat/confirm/{token}
# ---------------------------------------------------------------------------


class TestChatConfirmSubmit:
    def test_approve_without_password(self, client):
        session = _make_session(confirmation_level="url_only")
        r = client.post(f"/api/chat/confirm/{session.token}")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "completed"
        assert body["device_id"] == "cam-01"

    def test_approve_with_correct_password(self, client):
        from admz.api.confirm_store import hash_confirm_password
        from admz.fleet_settings import fleet_settings as fs
        fs.set("confirm_password_hash", hash_confirm_password("hunter2"))

        try:
            session = _make_session(confirmation_level="url_and_password")
            r = client.post(
                f"/api/chat/confirm/{session.token}",
                data={"confirm_password": "hunter2"},
            )
            assert r.status_code == 200
            assert r.json()["status"] == "completed"
        finally:
            fs.delete("confirm_password_hash")

    def test_wrong_password_returns_403(self, client):
        from admz.api.confirm_store import hash_confirm_password
        from admz.fleet_settings import fleet_settings as fs
        fs.set("confirm_password_hash", hash_confirm_password("hunter2"))

        try:
            session = _make_session(confirmation_level="url_and_password")
            r = client.post(
                f"/api/chat/confirm/{session.token}",
                data={"confirm_password": "wrong"},
            )
            assert r.status_code == 403
            assert r.json()["status"] == "wrong_password"
        finally:
            fs.delete("confirm_password_hash")

    def test_already_completed_returns_410(self, client):
        session = _make_session()
        # First approval succeeds
        r1 = client.post(f"/api/chat/confirm/{session.token}")
        assert r1.status_code == 200
        # Second attempt against the same token: 410.
        r2 = client.post(f"/api/chat/confirm/{session.token}")
        assert r2.status_code == 410
        assert r2.json()["status"] == "expired_or_not_found"

    def test_lockout_after_five_wrong_passwords(self, client):
        from admz.api.confirm_store import hash_confirm_password
        from admz.fleet_settings import fleet_settings as fs
        fs.set("confirm_password_hash", hash_confirm_password("hunter2"))

        try:
            session = _make_session(confirmation_level="url_and_password")
            # 5 wrong tries → on the 5th, lockout kicks in
            for attempt in range(5):
                r = client.post(
                    f"/api/chat/confirm/{session.token}",
                    data={"confirm_password": "wrong"},
                )
                assert r.status_code in (403, 429), \
                    f"attempt {attempt}: status {r.status_code}"

            # 6th attempt with correct password should be locked
            r = client.post(
                f"/api/chat/confirm/{session.token}",
                data={"confirm_password": "hunter2"},
            )
            assert r.status_code == 429
            assert r.json()["status"] == "locked"
        finally:
            fs.delete("confirm_password_hash")

    def test_rate_limited_per_ip(self, client):
        # Configure a tiny bucket so the rate limit fires quickly.
        global_limiter.configure("confirm", capacity=2, refill_per_s=0.001)

        statuses = []
        for _ in range(8):
            r = client.post("/api/chat/confirm/no-such-token")
            statuses.append(r.status_code)

        # Expect 429s after the bucket drains. (Some will be 410
        # because the rate limit lets a few through, and unknown
        # token returns 410.)
        assert 429 in statuses, f"expected at least one 429, got {statuses}"
        # The 429 body should be JSON with status=rate_limited.
        for r in (client.post("/api/chat/confirm/no-such-token") for _ in range(3)):
            if r.status_code == 429:
                body = r.json()
                assert body["status"] in ("rate_limited", "locked")
                break


# ---------------------------------------------------------------------------
# Cross-check: HTML form route still works (we didn't break it)
# ---------------------------------------------------------------------------


class TestHtmlFormUnchanged:
    def test_get_form_still_renders(self, client):
        session = _make_session()
        r = client.get(f"/confirm/{session.token}")
        assert r.status_code == 200
        # HTML, not JSON.
        assert "text/html" in r.headers["content-type"]
        assert b"factory-reset" in r.content or b"factorydefault" in r.content
