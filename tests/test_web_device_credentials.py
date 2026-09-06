"""ADR-0064 slice B — the device page's durable way back in.

The chat's capture card lasts five minutes and its session ten; a device in
`no_credentials` (or `auth_failed`) needs an action that lasts as long as
the state does. `POST /device/{id}/credentials` opens a capture session
bound to the `default` account as an admin and sends the operator to the
standard capture form; the page also offers **Run onboarding**.
"""

import re
from pathlib import Path

import pytest

import admz.api as api_pkg

TEMPLATES = Path(api_pkg.__file__).parent / "templates"
SAME_ORIGIN = {"Origin": "http://testserver"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    from fastapi.testclient import TestClient
    from admz.api.main import app
    import admz.api.main as main_module
    from admz.backends.sqlite_backend import SQLiteDeviceRegistry

    fresh = SQLiteDeviceRegistry(
        db_path=str(tmp_path / "admz.db"),
        key_path=str(tmp_path / "admz.key"),
    )
    monkeypatch.setattr(main_module, "registry", fresh)
    import admz.api.templating as templating
    monkeypatch.setattr(templating, "_registry", lambda: fresh)

    # A device with NO account row — the #443 shape.
    fresh.add_device("cam-none", {"host": "10.0.0.1", "nickname": "NoCreds", "tags": []})
    # A device WITH an account — the auth_failed shape.
    fresh.add_device("cam-stale", {"host": "10.0.0.2", "nickname": "Stale", "tags": []},
                     {"default": {"username": "root", "password": "old",
                                  "account_type": "admin"}})

    with TestClient(app) as c:
        c.registry = fresh
        yield c


class TestEnterCredentials:
    def test_opens_a_capture_session_for_the_default_admin_account(self, client):
        from admz.api.capture import capture_store

        r = client.post("/device/cam-none/credentials", headers=SAME_ORIGIN,
                        follow_redirects=False)
        assert r.status_code == 303
        location = r.headers["location"]
        assert location.startswith("/capture/")
        token = location.rsplit("/", 1)[1]
        session = capture_store.get_session(token)
        assert session is not None
        assert session.device_id == "cam-none"
        assert session.account_id == "default"
        assert session.account_type == "admin", (
            "a device with no account gets an admin, not the session default 'service'"
        )

    def test_a_device_with_a_stale_account_gets_a_session_too(self, client):
        """`auth_failed` uses the same action: the form's submit updates the
        existing `default` row."""
        r = client.post("/device/cam-stale/credentials", headers=SAME_ORIGIN,
                        follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].startswith("/capture/")

    def test_an_unknown_device_is_404(self, client):
        r = client.post("/device/nope/credentials", headers=SAME_ORIGIN,
                        follow_redirects=False)
        assert r.status_code == 404

    @pytest.mark.parametrize("headers", [{}, {"Origin": "http://evil.example"}, {"Origin": "null"}])
    def test_a_cross_origin_or_headerless_post_is_refused(self, client, headers, monkeypatch):
        """Browser-only, like every capture POST (#3): no session is minted
        for a request that did not come from our own origin."""
        def _never(*a, **k):
            raise AssertionError("no session for a cross-origin POST")

        monkeypatch.setattr("admz.api.capture.capture_store.create_session", _never)
        r = client.post("/device/cam-none/credentials", headers=headers,
                        follow_redirects=False)
        assert r.status_code == 403

    def test_the_capture_form_renders_for_the_session(self, client):
        r = client.post("/device/cam-none/credentials", headers=SAME_ORIGIN,
                        follow_redirects=False)
        page = client.get(r.headers["location"])
        assert page.status_code == 200
        assert "Enter Credentials" in page.text
        assert "NoCreds" in page.text, "the form names the device (by nickname)"


class TestTheDevicePageOffersTheActions:
    def test_the_banner_covers_both_states_and_both_actions(self):
        text = (TEMPLATES / "device_detail.html").read_text(encoding="utf-8", errors="replace")
        assert "me.status === 'no_credentials' || me.status === 'auth_failed'" in text
        assert "/credentials" in text and "Enter credentials" in text
        assert "Run onboarding" in text and "/onboard'" in text
        # the form posts to the route this slice adds, for THIS device
        assert re.search(r"action=\"/device/' \+ encodeURIComponent\(DEVICE_ID\) \+ '/credentials\"", text)

    def test_the_onboarding_notes_know_every_outcome(self):
        """The `?onboarding=` banner used to know five of the eight outcomes."""
        from admz import onboarding

        text = (TEMPLATES / "device_detail.html").read_text(encoding="utf-8", errors="replace")
        notes = re.search(r"const NOTES = \{(.*?)\n  \};", text, re.S)
        assert notes, "NOTES map not found"
        for word in (onboarding.CREDENTIALS_NEEDED, onboarding.OWN_ACCOUNT_CREATED,
                     onboarding.APPROVAL_REQUIRED, onboarding.PROVISIONED,
                     onboarding.ALREADY_CREDENTIALED, onboarding.PROVISION_FAILED,
                     onboarding.ENTRY_CREDENTIALS_SAVED):
            assert re.search(rf"\b{word}\s*:", notes.group(1)), f"NOTES lacks {word}"
