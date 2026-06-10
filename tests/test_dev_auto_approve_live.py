"""End-to-end: the dev auto-approver drives the REAL confirm route.

Wires the approver's HTTP poster to a FastAPI TestClient so the actual
`/api/chat/confirm/{token}` route runs (session completion + execution +
audit), against an isolated tmp DB. Proves the full loop without a live
server or any change to the production package — and proves the lab/test
scope guard holds against the real app.
"""

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_TOOL_PATH = Path(__file__).resolve().parent.parent / "tools" / "dev_auto_approve.py"
_spec = importlib.util.spec_from_file_location("dev_auto_approve", _TOOL_PATH)
daa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(daa)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")

    import admz.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_ACTIVE_BACKEND", None)

    from admz.rate_limit import rate_limiter as global_limiter
    global_limiter.reset()
    global_limiter.configure("confirm", capacity=100, refill_per_s=100)

    from admz.api.main import app
    with TestClient(app) as client:
        yield client

    global_limiter.configure("confirm", capacity=10, refill_per_s=1.0 / 6.0)
    global_limiter.reset()


def _poster(client):
    def post(url, data):
        # url is absolute (http://testserver/...); TestClient wants the path.
        path = url.split("testserver", 1)[-1] if "testserver" in url else url
        if path.startswith("http"):
            path = "/" + path.split("/", 3)[-1]
        return client.post(path, data=data)
    return post


def _make_session(device_id, level="url_only", op="systemready.cgi:restart"):
    from admz.api.confirm_store import confirm_store
    return confirm_store.create_session(
        device_id=device_id, operation_id=op, family="vapix", params={},
        risk_level="service-affecting", confirmation_level=level,
        danger_description="restart the device",
    )


def test_lab_device_session_is_approved_via_real_route(env):
    client = env
    from admz.factory import create_device_registry
    from admz.api.confirm_store import confirm_store, ConfirmStatus

    registry = create_device_registry()
    registry.add_device("lab-cam", {"host": "192.0.2.10", "tags": ["lab"]})

    session = _make_session("lab-cam")
    store = confirm_store

    result = daa.approve_token(
        session.token,
        base_url="http://testserver",
        password=None,
        registry=registry,
        allow_tags={"lab", "test"},
        scope_all=False,
        store=store,
        http_post=_poster(client),
    )

    assert result == "approved"
    # The real route completed the session in the shared store.
    done = confirm_store.get_session(session.token)
    assert done.effective_status == ConfirmStatus.COMPLETED
    assert done.confirmed_by == "chat"  # the JSON approval route stamps this


def test_prod_device_session_is_skipped_and_left_pending(env):
    client = env
    from admz.factory import create_device_registry
    from admz.api.confirm_store import confirm_store, ConfirmStatus

    registry = create_device_registry()
    registry.add_device("prod-cam", {"host": "192.0.2.20", "tags": ["production"]})

    session = _make_session("prod-cam")
    poster = _poster(client)
    calls = []
    def counting_post(url, data):
        calls.append(url)
        return poster(url, data)

    result = daa.approve_token(
        session.token,
        base_url="http://testserver",
        password=None,
        registry=registry,
        allow_tags={"lab", "test"},
        scope_all=False,
        store=confirm_store,
        http_post=counting_post,
    )

    assert result == "out-of-scope"
    assert calls == []  # never touched the endpoint
    # Session is still pending — a human (or a prod) would still have to approve.
    still = confirm_store.get_session(session.token)
    assert still.effective_status == ConfirmStatus.PENDING


def test_dev_approval_writes_distinct_audit_row(env):
    client = env
    from admz.factory import create_device_registry
    from admz.api.confirm_store import confirm_store
    from admz.audit import AuditLog

    registry = create_device_registry()
    registry.add_device("lab-cam", {"host": "192.0.2.10", "tags": ["test"]})
    session = _make_session("lab-cam")

    daa.approve_token(
        session.token, base_url="http://testserver", password=None,
        registry=registry, allow_tags={"lab", "test"}, scope_all=False,
        store=confirm_store, http_post=_poster(client),
    )

    rows = AuditLog().list_recent(action="dev.auto_approve")
    assert len(rows) == 1
    assert rows[0].details["confirmed_by"] == "dev-auto-approver"
    assert rows[0].details["note"].startswith("DEV auto-approval")
    # And the normal confirm.approve row from the real route is also present.
    assert len(AuditLog().list_recent(action="confirm.approve")) == 1
