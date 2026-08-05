"""HTTP-level tests for #334: a confirm session with catalog-declared
secret-shaped fields (e.g. a new device password) renders a masked
per-field <input type="password"> on the /confirm/{token} page and merges
the submitted value into params only in memory at approval time — never
into params_json, never onto the rendered page.

Mirrors the pattern in test_confirm_reexecution.py: operations.
execute_approved_session is stubbed so no real device/executor stack is
needed — these tests prove the ROUTING (form field -> secret_values kwarg,
template rendering) rather than re-proving the merge/refuse logic itself,
which is unit-tested in tests/test_operations_core.py.
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


def _seed(secret_fields, params=None, level="url_only"):
    from admz.api.confirm_store import confirm_store
    return confirm_store.create_session(
        device_id="dev", operation_id="pwdgrp.cgi:update-user", family="vapix",
        params=params if params is not None else {"user": "root"},
        secret_fields=secret_fields,
        risk_level="service-affecting", confirmation_level=level,
    )


@pytest.fixture
def record_exec(monkeypatch):
    """Stub operations.execute_approved_session and record the secret_values
    kwarg it was called with."""
    from admz import operations
    calls = []

    async def fake(session, secret_values=None, **kw):
        calls.append({"token": session.token, "secret_values": secret_values})
        return {"success": True, "operation_id": session.operation_id,
                "device_id": session.device_id, "confirmed": True}

    monkeypatch.setattr(operations, "execute_approved_session", fake)
    return calls


def test_confirm_page_renders_masked_input_never_plaintext(client):
    session = _seed(["password"])
    r = client.get(f"/confirm/{session.token}")
    assert r.status_code == 200
    # A masked, per-field password input named secret__<name> (#334).
    assert 'type="password"' in r.text
    assert 'name="secret__password"' in r.text
    assert 'id="secret__password"' in r.text
    # The card shows the field NAME (what's changing) but there is no value
    # to leak — none was ever stored in this session.
    assert "never stored" in r.text
    # An ordinary param still renders as before.
    assert "user" in r.text and "root" in r.text


def test_confirm_page_without_secret_fields_is_unaffected(client):
    """The other direction at the HTTP layer: a session with no
    secret_fields renders with none of the new markup at all."""
    session = _seed([], params={"a": "1"})
    r = client.get(f"/confirm/{session.token}")
    assert r.status_code == 200
    assert "secret__" not in r.text
    assert "Also required" not in r.text


def test_web_submit_forwards_secret_field_value(client, record_exec):
    session = _seed(["password"])
    r = client.post(f"/confirm/{session.token}", data={"secret__password": "hunter2SECRET"})
    assert r.status_code == 200
    assert record_exec == [
        {"token": session.token, "secret_values": {"password": "hunter2SECRET"}}
    ]
    # The submitted value is never echoed back onto the resulting page.
    assert "hunter2SECRET" not in r.text


def test_web_submit_missing_secret_field_forwards_empty(client, record_exec):
    """A submission with the field absent (e.g. JS disabled) still reaches
    execute_approved_session, which is the layer that refuses execution —
    proven in test_operations_core.py's refuse tests. Here we only confirm
    the route doesn't silently drop the intent to check it."""
    session = _seed(["password"])
    r = client.post(f"/confirm/{session.token}", data={})
    assert r.status_code == 200
    assert record_exec == [{"token": session.token, "secret_values": {"password": ""}}]


def test_chat_twin_refuses_a_session_with_unresolved_secret_fields(client):
    """The in-chat approval card has no secret-entry UI — it never renders
    session.params at all (chat_confirm_details's response has no "params"
    key). A secret-bearing session approved via chat must therefore be
    refused by the real (unstubbed) execute_approved_session, not silently
    executed with the field missing."""
    session = _seed(["password"])
    r = client.post(f"/api/chat/confirm/{session.token}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"  # the approval STEP completed...
    assert body["outcome"]["success"] is not True  # ...but execution refused
    assert "password" in body["outcome"]["error"]
