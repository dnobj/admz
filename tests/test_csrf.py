"""#3 — same-origin enforcement on the browser-only capture POSTs.

## The vacuity shape, and how it is closed

"A request with a bad Origin is rejected" is trivially green if the endpoint
rejects everything — a broken route, a 404, a 500 and a working guard all look
identical from the outside. So every rejection case here is paired with an
**acceptance** case on the same endpoint and the same fixture, and the
acceptance asserts a real success status rather than merely "not 403".

The missing-header case is asserted **explicitly** rather than left implied,
because fail-closed-vs-fail-open is the actual decision inside "add a check"
(see ``admz/csrf.py``). If someone later flips it to fail-open, this test is
what says so out loud.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from admz import csrf


# ---------------------------------------------------------------------------
# The pure parts — no app, no client.
# ---------------------------------------------------------------------------


class _FakeRequest:
    """Minimal stand-in: check_same_origin only reads headers + url.path."""

    def __init__(self, headers: dict):
        self.headers = {k.lower(): v for k, v in headers.items()}
        self.method = "POST"
        self.url = type("U", (), {"path": "/capture/tok"})()


def _req(**headers):
    return _FakeRequest(headers)


class TestHostportNormalisation:
    def test_bare_origin(self):
        assert csrf._hostport("http://admz.corp:4242") == "admz.corp:4242"

    def test_full_url_referer(self):
        assert csrf._hostport("http://admz.corp/capture/abc?x=1") == "admz.corp"

    def test_case_is_normalised(self):
        assert csrf._hostport("HTTP://ADMZ.CORP") == "admz.corp"

    def test_userinfo_is_stripped(self):
        """``http://admz.corp@evil.example`` must normalise to the REAL host.

        Without the strip this reads as admz.corp and the check is bypassable
        with a crafted Referer.
        """
        assert csrf._hostport("http://admz.corp@evil.example/") == "evil.example"

    def test_no_host_is_none(self):
        assert csrf._hostport("") is None
        assert csrf._hostport("not-a-url") is None


class TestCheckSameOrigin:
    HOST = "admz.corp:4242"

    def test_matching_origin_is_accepted(self):
        csrf.check_same_origin(
            _req(host=self.HOST, origin=f"http://{self.HOST}")
        )  # must not raise

    def test_scheme_is_ignored(self):
        """Behind a TLS-terminating proxy the browser says https while ADMZ
        sees http. Rejecting on scheme would break the deployment that most
        needs this check."""
        csrf.check_same_origin(
            _req(host=self.HOST, origin=f"https://{self.HOST}")
        )

    def test_foreign_origin_is_rejected(self):
        with pytest.raises(HTTPException) as exc:
            csrf.check_same_origin(
                _req(host=self.HOST, origin="http://evil.example")
            )
        assert exc.value.status_code == 403

    def test_different_port_is_rejected(self):
        with pytest.raises(HTTPException):
            csrf.check_same_origin(
                _req(host=self.HOST, origin="http://admz.corp:9999")
            )

    def test_null_origin_is_rejected_not_ignored(self):
        """A sandboxed iframe sends ``Origin: null``. Falling through to
        Referer there would let an attacker choose which header we read."""
        with pytest.raises(HTTPException):
            csrf.check_same_origin(
                _req(host=self.HOST, origin="null",
                     referer=f"http://{self.HOST}/capture/x")
            )

    def test_referer_is_used_when_origin_absent(self):
        csrf.check_same_origin(
            _req(host=self.HOST, referer=f"http://{self.HOST}/capture/x")
        )

    def test_foreign_referer_is_rejected(self):
        with pytest.raises(HTTPException):
            csrf.check_same_origin(
                _req(host=self.HOST, referer="http://evil.example/x")
            )

    def test_origin_wins_over_referer(self):
        """If both are present, Origin decides. A good Referer must not
        rescue a bad Origin."""
        with pytest.raises(HTTPException):
            csrf.check_same_origin(
                _req(host=self.HOST, origin="http://evil.example",
                     referer=f"http://{self.HOST}/capture/x")
            )

    # -- THE decision, pinned explicitly ------------------------------------

    def test_missing_both_headers_is_REJECTED(self):
        """Fail closed. These endpoints serve a browser form only; a request
        with no browser provenance has no legitimate shape.

        If this ever flips to fail-open, that is a deliberate posture change
        and this test is where it has to be argued.
        """
        with pytest.raises(HTTPException) as exc:
            csrf.check_same_origin(_req(host=self.HOST))
        assert exc.value.status_code == 403
        assert "Origin or Referer" in str(exc.value.detail)

    def test_trusted_origins_env_is_honoured(self, monkeypatch):
        """Escape hatch for a proxy whose public hostname differs from Host."""
        monkeypatch.setenv(csrf.ENV_TRUSTED_ORIGINS, "admz.public.example")
        csrf.check_same_origin(
            _req(host=self.HOST, origin="http://admz.public.example")
        )

    def test_trusted_origins_does_not_open_everything(self, monkeypatch):
        monkeypatch.setenv(csrf.ENV_TRUSTED_ORIGINS, "admz.public.example")
        with pytest.raises(HTTPException):
            csrf.check_same_origin(
                _req(host=self.HOST, origin="http://evil.example")
            )


# ---------------------------------------------------------------------------
# End-to-end through the real routes. Each rejection is paired with an
# acceptance so neither can pass because the endpoint is simply broken.
# ---------------------------------------------------------------------------


@pytest.fixture
def capture_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")
    monkeypatch.delenv(csrf.ENV_TRUSTED_ORIGINS, raising=False)

    from fastapi.testclient import TestClient
    import admz.api.main as main_module
    from admz.api import capture as cap_module
    from admz.api.routes import capture as cap_route_module

    db = str(tmp_path / "admz.db")
    store = cap_module.CaptureStore(db_path=db)
    monkeypatch.setattr(cap_module, "capture_store", store)
    monkeypatch.setattr(cap_route_module, "capture_store", store)

    with TestClient(main_module.app) as client:
        from admz.factory import create_device_registry
        reg = create_device_registry()
        reg.add_device("cam-1", {"host": "192.0.2.10", "model": "M-test"})
        yield client, store


def _new_token(store):
    return store.create_session(
        device_id="cam-1", account_id="default",
        account_type="admin", purpose="csrf test",
    ).token


class TestCaptureSubmitEndToEnd:
    FORM = {"username": "root", "password": "s3cret"}

    def test_same_origin_post_succeeds(self, capture_client):
        client, store = capture_client
        r = client.post(
            f"/capture/{_new_token(store)}", data=self.FORM,
            headers={"origin": "http://testserver"},
        )
        # The acceptance half. Without this the rejection tests below would
        # pass just as happily against a route that 500s on everything.
        assert r.status_code == 200, r.text

    def test_cross_origin_post_is_rejected(self, capture_client):
        client, store = capture_client
        token = _new_token(store)
        r = client.post(
            f"/capture/{token}", data=self.FORM,
            headers={"origin": "http://evil.example"},
        )
        assert r.status_code == 403, r.text
        # And it really did not take effect: the session is still pending,
        # so a 403 that happened *after* the write would be caught here.
        assert store.get_session(token) is not None

    def test_post_without_origin_or_referer_is_rejected(self, capture_client):
        client, store = capture_client
        r = client.post(f"/capture/{_new_token(store)}", data=self.FORM)
        assert r.status_code == 403, r.text

    def test_fleet_capture_is_guarded_too(self, capture_client):
        """Not named in #3, but the same file and the same shape."""
        client, store = capture_client
        token = store.create_fleet_session(setting_key="default_password").token
        bad = client.post(
            f"/capture/fleet/{token}", data={"password": "p", "username": "admin"},
            headers={"origin": "http://evil.example"},
        )
        assert bad.status_code == 403, bad.text
        good = client.post(
            f"/capture/fleet/{token}", data={"password": "p", "username": "admin"},
            headers={"origin": "http://testserver"},
        )
        assert good.status_code == 200, good.text

    def test_the_get_form_is_not_blocked(self, capture_client):
        """Only the state-changing POST is guarded. A GET carries no Origin
        on a top-level navigation and must keep working."""
        client, store = capture_client
        r = client.get(f"/capture/{_new_token(store)}")
        assert r.status_code == 200, r.text
