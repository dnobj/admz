"""Anti-drift guard: MCP and REST must emit the shared core's gate envelope.

Both ``admz.mcp.server.ADMZMCPServer._execute_operation`` and the REST
``POST /catalog/execute`` delegate to ``admz.operations.execute_gated_operation``.
These tests pin that delegation — each surface is driven with the core stubbed
to a sentinel envelope, and we assert the surface returns it VERBATIM. If anyone
later reshapes one surface's blocked response without the other, this fails.
A separate contract test pins the blocked-envelope shape itself.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# The canonical blocked envelope every surface must return unchanged.
SENTINEL = {
    "blocked": True,
    "risk_level": "service-affecting",
    "confirmation_level": "llm_confirm",
    "reason": "reason text",
    "confirm_token": "TKN",
    "confirm_tool": "confirm_dangerous_operation",
    "confirm_url": "/confirm/TKN",
    "message": "guidance",
}


# --- the blocked-envelope contract ----------------------------------------


def test_blocked_envelope_contract():
    """The single source both surfaces build from. Pin its exact key set."""
    from admz import operations
    from admz.api.confirm_store import ConfirmSession

    sess = ConfirmSession(
        token="tok", device_id="d", operation_id="o", family="vapix",
        params_json="{}", risk_level="dangerous",
        confirmation_level="url_and_password",
    )
    env = operations.blocked_envelope(sess, reason="because")
    assert set(env) == {
        "blocked", "risk_level", "confirmation_level", "reason",
        "confirm_token", "confirm_tool", "confirm_url", "message",
    }
    assert env["blocked"] is True
    assert env["confirm_url"] == "/confirm/tok"
    assert env["confirm_tool"] == "confirm_dangerous_operation"
    # The legacy REST-only field must NOT reappear.
    assert "confirm_endpoint" not in env


# --- MCP delegates to the core --------------------------------------------


@pytest.mark.asyncio
async def test_mcp_execute_returns_core_envelope_verbatim(monkeypatch):
    from admz import operations
    from admz.mcp.server import ADMZMCPServer

    async def fake(**kwargs):
        return dict(SENTINEL)

    monkeypatch.setattr(operations, "execute_gated_operation", fake)

    server = ADMZMCPServer.__new__(ADMZMCPServer)
    server.catalog = None  # forwarded to the (stubbed) core, unused here

    result = await server._execute_operation(
        device_id="d", operation_id="o", params={}, family="vapix",
    )
    assert result == SENTINEL


# --- REST delegates to the core -------------------------------------------


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))


@pytest.fixture
def client(isolate, tmp_path):
    from admz.api.main import app

    with TestClient(app) as c:
        import subprocess
        repo = str(tmp_path / "config-repo")
        for k, v in [("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")]:
            subprocess.run(["git", "config", k, v], cwd=repo, check=True)
        yield c


def test_rest_execute_returns_core_envelope_verbatim(client, monkeypatch):
    from admz import operations

    async def fake(**kwargs):
        return dict(SENTINEL)

    monkeypatch.setattr(operations, "execute_gated_operation", fake)

    r = client.post(
        "/api/catalog/execute",
        json={"device_id": "d", "operation_id": "o", "params": {}},
    )
    assert r.status_code == 200
    assert r.json() == SENTINEL
