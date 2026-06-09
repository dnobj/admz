"""The confirm gap-fix: approving at /confirm/{token} must EXECUTE the op.

Before the shared-core refactor, the web form (and its in-chat JSON twin)
completed the confirm token but never ran the held operation — so url_only /
url_and_password ops (the default for *dangerous*) were approved-but-never-run.
These tests verify both endpoints now invoke operations.execute_approved_session
after a successful approval, and skip it on a failed password.

The actual execution is stubbed (operations.execute_approved_session) so the
test never touches a real device — we assert the wiring + the outcome surfacing.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


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
        yield c


def _seed(level, **kw):
    from admz.api.confirm_store import confirm_store
    return confirm_store.create_session(
        device_id=kw.get("device_id", "dev"),
        operation_id=kw.get("operation_id", "restart.cgi:restart"),
        family="vapix", params={}, risk_level=kw.get("risk", "dangerous"),
        confirmation_level=level,
    )


@pytest.fixture
def record_exec(monkeypatch):
    """Stub operations.execute_approved_session so no device is contacted."""
    from admz import operations
    calls = []

    async def fake(session, **kw):
        calls.append(session.token)
        return {"success": True, "operation_id": session.operation_id,
                "device_id": session.device_id, "confirmed": True}

    monkeypatch.setattr(operations, "execute_approved_session", fake)
    return calls


def test_web_form_executes_on_approval(client, record_exec):
    session = _seed("url_only")
    r = client.post(f"/confirm/{session.token}")
    assert r.status_code == 200
    # The held op was executed on approval (not just token-completed).
    assert record_exec == [session.token]


def test_web_form_wrong_password_does_not_execute(client, record_exec):
    # Configure a confirm password, then submit the wrong one.
    from admz.api.confirm_store import hash_confirm_password
    from admz.fleet_settings import fleet_settings
    fleet_settings.set("confirm_password_hash", hash_confirm_password("correct-horse"))

    session = _seed("url_and_password")
    r = client.post(f"/confirm/{session.token}", data={"confirm_password": "wrong"})
    # Form re-rendered with an error; the op must NOT have executed.
    assert "Incorrect" in r.text or "incorrect" in r.text
    assert record_exec == []


def test_web_form_correct_password_executes(client, record_exec):
    from admz.api.confirm_store import hash_confirm_password
    from admz.fleet_settings import fleet_settings
    fleet_settings.set("confirm_password_hash", hash_confirm_password("correct-horse"))

    session = _seed("url_and_password")
    r = client.post(f"/confirm/{session.token}", data={"confirm_password": "correct-horse"})
    assert r.status_code == 200
    assert record_exec == [session.token]


def test_chat_twin_executes_and_returns_outcome(client, record_exec):
    session = _seed("url_only")
    r = client.post(f"/api/chat/confirm/{session.token}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["outcome"]["success"] is True
    assert record_exec == [session.token]
