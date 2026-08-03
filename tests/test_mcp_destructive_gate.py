"""Tests for ADR-0034 — uniform widget gating of destructive MCP tools.

History: Task #41 (CR-4) flat-refused delete_device / restore_device /
execute_plan for anonymous principals after a live incident where the
LLM deleted a real device. ADR-0034 supersedes that posture: every
destructive tool now takes the SAME deterministic human/widget approval
path as device writes (parity with how a reboot is approved), for every
principal:

  * restore_device builds a plan only; execute_plan blocks at the
    plan-level url_* gate (confirm widget) — approval runs the plan.
  * accept_baseline / delete_device return a blocked envelope holding a
    url_only ACTION session; the action executes only when the user
    approves /confirm/{token}.

This file pins: the empty flat-refusal set, the blocked envelopes (for
anonymous AND authenticated callers), no side effects before approval,
and that approval actually executes the action.
"""

from __future__ import annotations

import json

import pytest

from admz.mcp.server import _DESTRUCTIVE_MCP_TOOLS
from tests import mcp_harness


class TestDestructiveToolSet:
    def test_flat_refusal_set_is_empty(self):
        # ADR-0034: nothing is flat-refused anymore — destructive tools
        # are widget-gated instead. Growing this set again is a
        # deliberate policy decision, not a default.
        assert _DESTRUCTIVE_MCP_TOOLS == frozenset()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_server(tmp_path, monkeypatch, *, anonymous: bool):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")

    if anonymous:
        monkeypatch.setenv("ADMZ_PRINCIPAL_NAME", "anonymous")
        monkeypatch.setenv("ADMZ_PRINCIPAL_SOURCE", "none")
        monkeypatch.delenv("ADMZ_PRINCIPAL_GROUPS", raising=False)
    else:
        monkeypatch.setenv("ADMZ_PRINCIPAL_NAME", "HOMELAB\\alice")
        monkeypatch.setenv("ADMZ_PRINCIPAL_SOURCE", "windows-local")
        monkeypatch.setenv("ADMZ_PRINCIPAL_GROUPS", "Administrators")

    from admz import audit as audit_module
    monkeypatch.setattr(
        audit_module, "audit_log",
        audit_module.AuditLog(db_path=str(tmp_path / "admz.db")),
    )
    # Point the module-level confirm store (operations._resolve_store reads
    # it lazily) at the tmp DB so sessions are visible to the test.
    import admz.api.confirm_store as cs_module
    monkeypatch.setattr(
        cs_module, "confirm_store",
        cs_module.ConfirmStore(db_path=str(tmp_path / "admz.db")),
    )

    from admz.mcp.server import ADMZMCPServer
    return ADMZMCPServer()


@pytest.fixture
def auth_mcp_server(tmp_path, monkeypatch):
    server = _make_server(tmp_path, monkeypatch, anonymous=False)
    assert server.principal.is_anonymous is False
    return server


@pytest.fixture
def anon_mcp_server(tmp_path, monkeypatch):
    server = _make_server(tmp_path, monkeypatch, anonymous=True)
    assert server.principal.is_anonymous is True
    return server


async def _call_tool(server, name: str, arguments: dict):
    return await mcp_harness.call_tool(server, name, arguments)


def _commit_facet(server, device_id, facet, data, message):
    import subprocess
    for key, val in [
        ("user.email", "test@test.com"),
        ("user.name", "Test"),
        ("commit.gpgsign", "false"),
    ]:
        subprocess.run(
            ["git", "config", key, val],
            cwd=server.git_repo.repo_path, check=True,
        )
    server.git_repo.write_facet(device_id, facet, data)
    return server.git_repo.commit_snapshot(device_id, message=message)


async def _approve(session_token):
    """Simulate the user approving /confirm/{token}: complete the session
    and execute the held action — the same two steps the confirm route's
    _approve_session performs."""
    from admz import operations
    import admz.api.confirm_store as cs_module
    store = cs_module.confirm_store
    session = store.get_session(session_token)
    assert session is not None
    store.complete_session(session_token, confirmed_by="test-approver")
    # Action sessions only need the registry.
    from admz.factory import create_device_registry
    return await operations.execute_approved_session(
        store.get_session(session_token),
        catalog=None,
        registry=create_device_registry(),
        executors={},
    )


# ---------------------------------------------------------------------------
# delete_device — widget-gated for everyone
# ---------------------------------------------------------------------------


class TestDeleteDeviceWidgetGate:
    @pytest.mark.asyncio
    async def test_blocked_envelope_no_side_effect(self, auth_mcp_server):
        auth_mcp_server.registry.add_device("test-cam", {"host": "192.0.2.10"})
        result = await _call_tool(
            auth_mcp_server, "delete_device", {"device_id": "test-cam"},
        )
        assert result.get("blocked") is True
        assert result.get("confirm_token")
        assert result.get("confirmation_level") == "url_only"
        # Nothing happened yet.
        assert auth_mcp_server.registry.device_exists("test-cam")

    @pytest.mark.asyncio
    async def test_approval_executes_deletion(self, auth_mcp_server):
        auth_mcp_server.registry.add_device("test-cam", {"host": "192.0.2.10"})
        result = await _call_tool(
            auth_mcp_server, "delete_device", {"device_id": "test-cam"},
        )
        outcome = await _approve(result["confirm_token"])
        assert outcome["success"] is True
        assert outcome["action"] == "delete_device"
        assert not auth_mcp_server.registry.device_exists("test-cam")

    @pytest.mark.asyncio
    async def test_anonymous_gets_the_same_widget_not_refusal(
        self, anon_mcp_server
    ):
        # ADR-0034: the gate is the widget, uniformly — no PermissionDenied.
        anon_mcp_server.registry.add_device("test-cam", {"host": "192.0.2.10"})
        result = await _call_tool(
            anon_mcp_server, "delete_device", {"device_id": "test-cam"},
        )
        assert result.get("error") != "PermissionDenied"
        assert result.get("blocked") is True
        assert anon_mcp_server.registry.device_exists("test-cam")

    @pytest.mark.asyncio
    async def test_unknown_device_errors_immediately(self, auth_mcp_server):
        result = await _call_tool(
            auth_mcp_server, "delete_device", {"device_id": "nope"},
        )
        assert result.get("blocked") is not True
        assert "not found" in str(result.get("message", result)).lower() or \
            result.get("error")


# ---------------------------------------------------------------------------
# accept_baseline — widget-gated; validation still immediate
# ---------------------------------------------------------------------------


class TestAcceptBaselineWidgetGate:
    @pytest.mark.asyncio
    async def test_blocked_then_approval_repoints(self, auth_mcp_server):
        auth_mcp_server.registry.add_device("test-cam", {"host": "192.0.2.10"})
        sha = _commit_facet(
            auth_mcp_server, "test-cam", "image",
            {"I0.Resolution": "1920x1080"}, "Audit: test-cam",
        )
        result = await _call_tool(
            auth_mcp_server, "accept_baseline",
            {"device_id": "test-cam", "commit_sha": sha},
        )
        assert result.get("blocked") is True
        token = result["confirm_token"]
        # Not yet re-pointed.
        info = auth_mcp_server.registry.get_device_info("test-cam")
        assert info.get("baseline_sha") != sha

        outcome = await _approve(token)
        assert outcome["success"] is True
        assert outcome["baseline_sha"] == sha
        info = auth_mcp_server.registry.get_device_info("test-cam")
        assert info["baseline_sha"] == sha

    @pytest.mark.asyncio
    async def test_defaults_to_latest_observation(self, auth_mcp_server):
        auth_mcp_server.registry.add_device("test-cam", {"host": "192.0.2.10"})
        sha = _commit_facet(
            auth_mcp_server, "test-cam", "image",
            {"I0.Resolution": "1280x720"}, "Audit: test-cam",
        )
        auth_mcp_server.registry.set_config_pointers(
            "test-cam", latest_observed_sha=sha,
        )
        result = await _call_tool(
            auth_mcp_server, "accept_baseline", {"device_id": "test-cam"},
        )
        assert result.get("blocked") is True
        outcome = await _approve(result["confirm_token"])
        assert outcome["success"] is True
        assert outcome["baseline_sha"] == sha

    @pytest.mark.asyncio
    async def test_no_observation_errors_immediately(self, auth_mcp_server):
        auth_mcp_server.registry.add_device("test-cam", {"host": "192.0.2.10"})
        result = await _call_tool(
            auth_mcp_server, "accept_baseline", {"device_id": "test-cam"},
        )
        assert result.get("success") is False
        assert result.get("blocked") is not True
        assert "No commit to accept" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_commit_without_device_config_errors_immediately(
        self, auth_mcp_server
    ):
        auth_mcp_server.registry.add_device("test-cam", {"host": "192.0.2.10"})
        auth_mcp_server.registry.add_device("other", {"host": "192.0.2.11"})
        sha = _commit_facet(
            auth_mcp_server, "other", "image",
            {"I0.Resolution": "640x480"}, "Audit: other",
        )
        result = await _call_tool(
            auth_mcp_server, "accept_baseline",
            {"device_id": "test-cam", "commit_sha": sha},
        )
        assert result.get("success") is False
        assert result.get("blocked") is not True
        assert "no config" in result.get("error", "")


# ---------------------------------------------------------------------------
# restore_device / execute_plan — reach their handlers (plan gate covers them)
# ---------------------------------------------------------------------------


class TestRestoreAndPlansReachHandlers:
    @pytest.mark.asyncio
    async def test_restore_device_not_refused(self, anon_mcp_server):
        anon_mcp_server.registry.add_device("test-cam", {"host": "192.0.2.10"})
        result = await _call_tool(
            anon_mcp_server, "restore_device", {"device_id": "test-cam"},
        )
        # No config in git -> the handler's own "no config" outcome, not
        # a permission refusal. (Real restores then gate at execute_plan
        # via the plan-level url_* confirm widget.)
        assert result.get("error") != "PermissionDenied"

    @pytest.mark.asyncio
    async def test_execute_plan_not_refused(self, anon_mcp_server):
        result = await _call_tool(
            anon_mcp_server, "execute_plan", {"plan_id": "plan-deadbeef"},
        )
        assert result.get("error") != "PermissionDenied"
        # Unknown plan surfaces the engine's own error.
        assert "not found" in str(result.get("error", "")).lower() or \
            result.get("success") is False
