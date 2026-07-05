"""Tests for the event-action-rule MCP tools, gated executors, and the
recipient-secret capture flow (admz/rules + operations action executors).

Uses the same widget-gate harness as test_mcp_destructive_gate: a real
ADMZMCPServer over a tmp SQLite registry + confirm store, with the atlas survey
(real) driving capability discovery. Device I/O (runner.*) and the app context
are monkeypatched so nothing touches a live device.
"""

from __future__ import annotations

import json

import pytest

from admz.rules import capabilities, capture


# ---------------------------------------------------------------------------
# Harness (mirrors test_mcp_destructive_gate)
# ---------------------------------------------------------------------------

def _make_server(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    monkeypatch.setenv("ADMZ_PRINCIPAL_NAME", "HOMELAB\\alice")
    monkeypatch.setenv("ADMZ_PRINCIPAL_SOURCE", "windows-local")
    monkeypatch.setenv("ADMZ_PRINCIPAL_GROUPS", "Administrators")

    from admz import audit as audit_module
    monkeypatch.setattr(
        audit_module, "audit_log",
        audit_module.AuditLog(db_path=str(tmp_path / "admz.db")))
    import admz.api.confirm_store as cs_module
    monkeypatch.setattr(
        cs_module, "confirm_store",
        cs_module.ConfirmStore(db_path=str(tmp_path / "admz.db")))

    from admz.mcp.server import ADMZMCPServer
    return ADMZMCPServer()


@pytest.fixture
def server(tmp_path, monkeypatch):
    srv = _make_server(tmp_path, monkeypatch)
    srv.registry.add_device("cam", {"host": "192.0.2.10", "model": "C1710"})
    return srv


async def _call_tool(server, name, arguments):
    from mcp.types import CallToolRequest, CallToolRequestParams
    handler = None
    for req_type, h in server.server.request_handlers.items():
        if req_type.__name__ == "CallToolRequest":
            handler = h
            break
    assert handler is not None
    req = CallToolRequest(
        method="tools/call",
        params=CallToolRequestParams(name=name, arguments=arguments))
    result = await handler(req)
    return json.loads(result.root.content[0].text)


async def _approve(session_token, registry):
    """Complete + execute a confirm session, as the confirm route does."""
    from admz import operations
    import admz.api.confirm_store as cs_module
    store = cs_module.confirm_store
    assert store.get_session(session_token) is not None
    store.complete_session(session_token, confirmed_by="test-approver")
    return await operations.execute_approved_session(
        store.get_session(session_token),
        catalog=None, registry=registry, executors={})


class _FakeResult:
    def __init__(self, available=True):
        self.available = available
        self.error = None if available else "unbuildable"
        self.config_body = "<config/>"
        self.rule_body = "<rule><PrimaryAction>{action_configuration_id}</PrimaryAction></rule>"
        self.action_recurrence = "pulse"
        self.prerequisites = []
        self.warnings = []


class _FakeCtx:
    def __init__(self):
        self.catalog = object()
        self.executors = {"vapix": object()}


def _patch_ctx(monkeypatch):
    import admz.api.context as ctx_module
    monkeypatch.setattr(ctx_module, "get_context", lambda: _FakeCtx())


# ---------------------------------------------------------------------------
# list_rule_capabilities
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_rule_capabilities_surveyed(server, monkeypatch):
    async def _no_rules(**kw):
        return []
    monkeypatch.setattr("admz.rules.runner.list_rules", _no_rules)
    out = await _call_tool(server, "list_rule_capabilities", {"device_id": "cam"})
    assert out["available"] is True
    assert out["model"] == "C1710"
    assert out["conditions"] and out["actions"]
    assert out["current_rules"] == []


@pytest.mark.asyncio
async def test_list_rule_capabilities_unsurveyed_model(server, monkeypatch):
    server.registry.update_device("cam", {"model": "NOPE-9000"})
    out = await _call_tool(server, "list_rule_capabilities", {"device_id": "cam"})
    assert out["available"] is False
    assert "surveyed" in out["reason"].lower()


# ---------------------------------------------------------------------------
# create_action_rule — credential-free path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_action_rule_blocks_then_executes(server, monkeypatch):
    monkeypatch.setattr(capabilities, "build", lambda *a, **k: _FakeResult(True))
    created = {}

    async def _fake_create_rule(**kw):
        created.update(kw)
        return {"rule_id": "7", "config_id": "42", "steps": []}
    monkeypatch.setattr("admz.rules.runner.create_rule", _fake_create_rule)
    _patch_ctx(monkeypatch)

    result = await _call_tool(server, "create_action_rule", {
        "device_id": "cam", "condition_id": "input2",
        "action_token": "com.axis.action.fixed.play.audioclip",
        "param_choices": {"Clip": "ding dong"}, "rule_name": "ding-dong"})
    assert result.get("blocked") is True
    assert result.get("confirmation_level") == "url_only"
    token = result["confirm_token"]
    assert not created  # nothing ran before approval

    outcome = await _approve(token, server.registry)
    assert outcome["success"] is True
    assert outcome["rule_id"] == "7" and outcome["config_id"] == "42"
    assert created["config_body"] == "<config/>"


@pytest.mark.asyncio
async def test_create_action_rule_unbuildable_no_card(server, monkeypatch):
    monkeypatch.setattr(capabilities, "build", lambda *a, **k: _FakeResult(False))
    result = await _call_tool(server, "create_action_rule", {
        "device_id": "cam", "condition_id": "x",
        "action_token": "com.axis.action.fixed.play.audioclip"})
    assert result["success"] is False
    assert result.get("blocked") is not True
    assert "unbuildable" in result["error"]


# ---------------------------------------------------------------------------
# create_action_rule — secret-bearing (notification) path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notification_rule_requests_capture(server, monkeypatch):
    monkeypatch.setattr(capabilities, "build", lambda *a, **k: _FakeResult(True))
    result = await _call_tool(server, "create_action_rule", {
        "device_id": "cam", "condition_id": "motion",
        "action_token": "com.axis.action.fixed.notification.http",
        "rule_name": "notify"})
    assert result["success"] is False
    assert result["needs_recipient_credentials"] is True
    assert result["capture_url"].startswith("/capture/rule/")
    # A confirm session was armed but is not approvable to a real rule yet.
    token = result["capture_url"].rsplit("/", 1)[1]
    import admz.api.confirm_store as cs_module
    session = cs_module.confirm_store.get_session(token)
    assert session is not None and session.action.get("requires_secret_capture")


@pytest.mark.asyncio
async def test_notification_rule_merges_captured_secret(server, monkeypatch):
    build_calls = []

    def _rec_build(model, condition_id, action_token, param_choices=None, rule_name="AtlasRule"):
        build_calls.append(dict(param_choices or {}))
        return _FakeResult(True)
    monkeypatch.setattr(capabilities, "build", _rec_build)

    async def _fake_create_rule(**kw):
        return {"rule_id": "9", "config_id": "50", "steps": []}
    monkeypatch.setattr("admz.rules.runner.create_rule", _fake_create_rule)
    _patch_ctx(monkeypatch)

    result = await _call_tool(server, "create_action_rule", {
        "device_id": "cam", "condition_id": "motion",
        "action_token": "com.axis.action.fixed.notification.http",
        "param_choices": {"upload_url": "http://host/hook"}, "rule_name": "notify"})
    token = result["capture_url"].rsplit("/", 1)[1]

    # User enters recipient creds on the secure form (held in web memory).
    capture.stash_rule_secrets(token, {"login": "operator", "password": "s3cr3t"})

    outcome = await _approve(token, server.registry)
    assert outcome["success"] is True and outcome["rule_id"] == "9"
    # The execute-time build got the NON-secret param + the captured secrets.
    merged = build_calls[-1]
    assert merged["upload_url"] == "http://host/hook"
    assert merged["login"] == "operator" and merged["password"] == "s3cr3t"


@pytest.mark.asyncio
async def test_notification_rule_without_capture_fails_closed(server, monkeypatch):
    monkeypatch.setattr(capabilities, "build", lambda *a, **k: _FakeResult(True))
    _patch_ctx(monkeypatch)
    result = await _call_tool(server, "create_action_rule", {
        "device_id": "cam", "condition_id": "motion",
        "action_token": "com.axis.action.fixed.notification.http",
        "rule_name": "notify"})
    token = result["capture_url"].rsplit("/", 1)[1]
    # Approve WITHOUT capturing the secret.
    outcome = await _approve(token, server.registry)
    assert outcome["success"] is False
    assert "not captured" in outcome["error"].lower()


# ---------------------------------------------------------------------------
# delete_action_rule
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_action_rule_blocks_then_executes(server, monkeypatch):
    async def _fake_delete_rule(**kw):
        return {"removed_rule": kw["rule_id"], "removed_config": "42", "steps": []}
    monkeypatch.setattr("admz.rules.runner.delete_rule", _fake_delete_rule)
    _patch_ctx(monkeypatch)

    result = await _call_tool(server, "delete_action_rule",
                              {"device_id": "cam", "rule_id": "7"})
    assert result.get("blocked") is True
    outcome = await _approve(result["confirm_token"], server.registry)
    assert outcome["success"] is True
    assert outcome["removed_rule"] == "7"
    assert outcome["removed_config"] == "42"


@pytest.mark.asyncio
async def test_action_rule_tools_reject_unknown_device(server):
    for tool, args in (
        ("list_rule_capabilities", {"device_id": "ghost"}),
        ("create_action_rule", {"device_id": "ghost", "condition_id": "c",
                                "action_token": "a"}),
        ("delete_action_rule", {"device_id": "ghost", "rule_id": "1"}),
    ):
        out = await _call_tool(server, tool, args)
        assert out.get("success") is False or out.get("error")


# ---------------------------------------------------------------------------
# capture store (web-memory, single-use)
# ---------------------------------------------------------------------------

def test_capture_store_stash_and_single_use_consume():
    capture.stash_rule_secrets("tok1", {"login": "u", "password": "p"})
    assert capture.has_rule_secrets("tok1") is True
    got = capture.consume_captured_rule_secrets("tok1")
    assert got == {"login": "u", "password": "p"}
    # Single-use: gone after consume.
    assert capture.has_rule_secrets("tok1") is False
    assert capture.consume_captured_rule_secrets("tok1") == {}


def test_capture_store_discard():
    capture.stash_rule_secrets("tok2", {"password": "x"})
    capture.discard_rule_secrets("tok2")
    assert capture.consume_captured_rule_secrets("tok2") == {}


def test_capture_store_unknown_token():
    assert capture.consume_captured_rule_secrets("never") == {}
    assert capture.has_rule_secrets("never") is False
