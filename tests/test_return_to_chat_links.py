"""#340, item 2: the capture-complete and confirm-complete pages said
"you can return to your chat session" with no actual way to do it except
the browser back button or the left-hand nav — a genuine dead end the
operator hit on every capture. Pins that all three affected templates
(capture_done.html, confirm_done.html, and capture_expired.html — which
confirm.py's own expired/denied path reuses) now render a real link back
to /chat.

Deliberately not just a template-source grep: these render the templates
through the REAL routes, the same way #340's rehydration fix is tested,
so a change to the route context (a renamed variable, a removed block)
would break this the same way it would break in production.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

_RETURN_LINK = 'href="/chat"'


@pytest.fixture(autouse=True)
def isolate_admz_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))


@pytest.fixture
def client(isolate_admz_dirs, tmp_path):
    from admz.api.main import app

    with TestClient(app) as c:
        import subprocess
        repo = str(tmp_path / "config-repo")
        for k, v in [("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")]:
            subprocess.run(["git", "config", k, v], cwd=repo, check=True)

        from admz.factory import create_device_registry
        reg = create_device_registry()
        reg.add_device("dev", {"host": "192.0.2.10", "model": "M-test"})
        yield c


def test_capture_done_page_has_return_to_chat_link(client):
    from admz.api.capture import capture_store

    session = capture_store.create_session(device_id="dev", account_id="default")
    r = client.post(
        f"/capture/{session.token}",
        data={"username": "root", "password": "s3cret"},
        headers={"origin": "http://testserver"},
    )
    assert r.status_code == 200
    assert "Credentials Saved" in r.text
    assert _RETURN_LINK in r.text


def test_confirm_done_page_has_return_to_chat_link(client, monkeypatch):
    """Stub execute_approved_session (as test_confirm_reexecution.py does)
    so this only exercises the approve -> render path, not a real device
    executor."""
    from admz import operations
    from admz.api.confirm_store import confirm_store

    async def fake(session, **kw):
        return {"success": True, "operation_id": session.operation_id,
                "device_id": session.device_id, "confirmed": True}
    monkeypatch.setattr(operations, "execute_approved_session", fake)

    session = confirm_store.create_session(
        device_id="dev", operation_id="restart.cgi:restart", family="vapix",
        params={}, risk_level="dangerous", confirmation_level="url_only",
    )
    r = client.post(f"/confirm/{session.token}")
    assert r.status_code == 200
    assert "confirmed" in r.text.lower()
    assert _RETURN_LINK in r.text


def test_capture_expired_page_has_return_to_chat_link(client):
    r = client.get("/capture/no-such-token-at-all")
    assert r.status_code == 410
    assert "Link Expired" in r.text
    assert _RETURN_LINK in r.text


def test_confirm_expired_page_has_return_to_chat_link(client):
    """confirm.py's own expired/not-found path renders the SAME
    capture_expired.html template (checked by reading confirm_form route) —
    this pins that sharing didn't leave the confirm side of it un-fixed."""
    r = client.get("/confirm/no-such-token-at-all")
    assert r.status_code == 410
    assert _RETURN_LINK in r.text
