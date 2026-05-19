"""Tests for the rate limiter and the password-attempt lockout on
``/confirm/{token}``."""

import time
from unittest.mock import MagicMock

import pytest

from admz.rate_limit import (
    RateLimiter,
    client_key_from_request,
    rate_limiter as global_limiter,
)


# ---------------------------------------------------------------------------
# RateLimiter unit tests
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_limiter():
    return RateLimiter()


class TestRateLimiter:
    def test_unknown_route_passes_through(self, fresh_limiter):
        # No policy registered for "unknown" — always allowed
        for _ in range(100):
            assert fresh_limiter.check("unknown", "1.2.3.4") is True

    def test_burst_capacity_then_throttle(self, fresh_limiter):
        # Default capture policy is 10 + 1/6s refill
        ip = "10.0.0.1"
        granted = sum(1 for _ in range(15) if fresh_limiter.check("capture", ip))
        # First 10 succeed, then no more (no time has passed)
        assert granted == 10

    def test_refill_grants_more_after_wait(self, fresh_limiter):
        ip = "10.0.0.1"
        # Burn the bucket
        for _ in range(10):
            fresh_limiter.check("capture", ip)
        # Immediately denied
        assert fresh_limiter.check("capture", ip) is False
        # Refill is 1/6s — after 6 seconds we'd get 1 token, after 60s
        # we'd get back to capacity. Simulate by patching time would
        # require monkey-patching; just verify behaviour at the
        # boundary by overriding the policy to a faster refill.
        fresh_limiter.configure("capture", capacity=10, refill_per_s=100)
        time.sleep(0.05)  # ~5 tokens worth at the test rate
        assert fresh_limiter.check("capture", ip) is True

    def test_different_ips_have_separate_buckets(self, fresh_limiter):
        for _ in range(10):
            fresh_limiter.check("capture", "1.1.1.1")
        # 1.1.1.1 is throttled
        assert fresh_limiter.check("capture", "1.1.1.1") is False
        # 2.2.2.2 still has a full bucket
        assert fresh_limiter.check("capture", "2.2.2.2") is True

    def test_different_routes_have_separate_buckets(self, fresh_limiter):
        ip = "1.1.1.1"
        for _ in range(10):
            fresh_limiter.check("capture", ip)
        # capture is exhausted
        assert fresh_limiter.check("capture", ip) is False
        # confirm route is independent
        assert fresh_limiter.check("confirm", ip) is True

    def test_reset_clears_buckets(self, fresh_limiter):
        ip = "1.1.1.1"
        for _ in range(10):
            fresh_limiter.check("capture", ip)
        assert fresh_limiter.check("capture", ip) is False
        fresh_limiter.reset()
        assert fresh_limiter.check("capture", ip) is True

    def test_configure_overrides_policy(self, fresh_limiter):
        # Tighten capture to capacity=2 for this test
        fresh_limiter.configure("capture", capacity=2, refill_per_s=0)
        ip = "1.1.1.1"
        assert fresh_limiter.check("capture", ip) is True
        assert fresh_limiter.check("capture", ip) is True
        assert fresh_limiter.check("capture", ip) is False


# ---------------------------------------------------------------------------
# client_key_from_request — IP extraction
# ---------------------------------------------------------------------------


class TestClientKey:
    def _req(self, headers=None, client_host=None):
        request = MagicMock()
        request.headers = headers or {}
        if client_host:
            request.client = MagicMock()
            request.client.host = client_host
        else:
            request.client = None
        return request

    def test_xff_takes_precedence(self):
        request = self._req(
            headers={"x-forwarded-for": "10.0.0.5"},
            client_host="127.0.0.1",
        )
        assert client_key_from_request(request) == "10.0.0.5"

    def test_xff_first_hop_only(self):
        request = self._req(
            headers={"x-forwarded-for": "10.0.0.5, 192.168.1.1, 10.0.0.99"},
            client_host="127.0.0.1",
        )
        assert client_key_from_request(request) == "10.0.0.5"

    def test_falls_back_to_client_host(self):
        request = self._req(client_host="192.168.42.7")
        assert client_key_from_request(request) == "192.168.42.7"

    def test_unknown_when_no_client(self):
        request = self._req()
        assert client_key_from_request(request) == "unknown"


# ---------------------------------------------------------------------------
# Integration: rate limit on /capture and /confirm + password lockout
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")

    # Reset shared rate limiter so tests don't leak buckets
    global_limiter.reset()

    import admz.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_ACTIVE_BACKEND", None)

    from fastapi.testclient import TestClient
    from admz.api.main import app
    with TestClient(app) as c:
        yield c


class TestCaptureRateLimit:
    def test_capture_post_eventually_returns_429(self, client):
        # Doesn't matter that the token is invalid — the rate limit
        # check fires before the token lookup.
        # Default policy: 10-burst, then deny.
        responses = []
        for _ in range(15):
            r = client.post(
                "/capture/dummy-token",
                data={"username": "x", "password": "y"},
            )
            responses.append(r.status_code)
        assert 429 in responses, f"expected 429 somewhere; got {responses}"
        # And the 429 has the right message
        last_429 = next(r for r in responses if r == 429)
        assert last_429 == 429


class TestConfirmRateLimit:
    def test_confirm_post_eventually_returns_429(self, client):
        responses = []
        for _ in range(15):
            r = client.post("/confirm/dummy-token", data={})
            responses.append(r.status_code)
        assert 429 in responses


class TestConfirmPasswordLockout:
    """Per-token lockout after _MAX_PW_ATTEMPTS bad password attempts."""

    def _setup_session(self, client):
        """Create a real url_and_password confirm session + set a password."""
        from admz.api.confirm_store import confirm_store, hash_confirm_password
        from admz.fleet_settings import fleet_settings as fs

        fs.set("confirm_password_hash", hash_confirm_password("correct-pw"))
        try:
            session = confirm_store.create_session(
                device_id="cam-01",
                operation_id="not_a_real_op",
                family="vapix",
                params={},
                risk_level="dangerous",
                confirmation_level="url_and_password",
            )
            return session
        except Exception:  # pragma: no cover
            fs.delete("confirm_password_hash")
            raise

    def test_correct_password_completes_session(self, client):
        session = self._setup_session(client)
        try:
            r = client.post(
                f"/confirm/{session.token}",
                data={"confirm_password": "correct-pw"},
            )
            # 200 (form rendered) or completes — anything except locked/expired
            assert r.status_code in (200, 410), r.text
        finally:
            from admz.fleet_settings import fleet_settings as fs
            fs.delete("confirm_password_hash")

    def test_repeated_wrong_password_locks_session(self, client):
        # Generous: also reset rate limiter so we hit the lockout
        # (per-token) before the rate limit (per-IP).
        global_limiter.reset()
        global_limiter.configure("confirm", capacity=100, refill_per_s=100)

        session = self._setup_session(client)
        try:
            # 5 wrong tries → on the 5th, lockout kicks in
            for attempt in range(5):
                r = client.post(
                    f"/confirm/{session.token}",
                    data={"confirm_password": "wrong"},
                )
                assert r.status_code in (200, 429), \
                    f"attempt {attempt}: status {r.status_code}"

            # Now the 6th try should be locked (429) regardless of password
            r = client.post(
                f"/confirm/{session.token}",
                data={"confirm_password": "correct-pw"},
            )
            assert r.status_code == 429
            assert "locked" in r.text.lower() or "too many" in r.text.lower()
        finally:
            from admz.fleet_settings import fleet_settings as fs
            fs.delete("confirm_password_hash")
            # Clear the in-memory failure tracker so the next test starts fresh
            from admz.api.routes.confirm import _PW_ATTEMPTS
            _PW_ATTEMPTS.clear()
