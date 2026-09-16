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
        # Execute the session fetched ABOVE, before completion — which is the
        # ordering the route actually uses (routes/confirm.py: get_session :203
        # -> complete_session :274 -> execute_approved_session(session) :284).
        # This re-fetched instead, and #266 strips the payload on completion, so
        # the second read handed the executor an empty action.
        session,
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
# delete_devices — several devices, one approval (ADR-0069)
# ---------------------------------------------------------------------------


def _session_rows(tmp_path):
    """How many confirm sessions exist: the "one card" claim, counted."""
    import contextlib
    import sqlite3

    import admz.api.confirm_store as cs_module
    cs_module.confirm_store.get_session("schema-ensure")  # the table exists
    with contextlib.closing(sqlite3.connect(str(tmp_path / "admz.db"))) as conn:
        return conn.execute("SELECT COUNT(*) FROM confirm_sessions").fetchone()[0]


def _stored_session(token):
    import admz.api.confirm_store as cs_module
    session = cs_module.confirm_store.get_session(token)
    assert session is not None
    return session


def _register(server, *devices):
    for n, (device_id, nickname) in enumerate(devices, start=10):
        server.registry.add_device(
            device_id, {"host": f"192.0.2.{n}", "nickname": nickname})


_THREE = (("cam-a", "Lobby"), ("cam-b", "Dock"), ("cam-c", "Gate"))
_THREE_IDS = [device_id for device_id, _ in _THREE]


class TestDeleteDevicesWidgetGate:
    """On 2026-09-15 "remove all devices" meant a card per device, and the
    chain broke after the first. One call, one session, one card — behind
    exactly the gate single removal has."""

    @pytest.mark.asyncio
    async def test_one_call_opens_one_session_covering_every_device(
        self, auth_mcp_server, tmp_path,
    ):
        _register(auth_mcp_server, *_THREE)
        result = await _call_tool(
            auth_mcp_server, "delete_devices", {"device_ids": _THREE_IDS})
        assert result.get("blocked") is True
        assert result.get("confirm_url") == f"/confirm/{result['confirm_token']}"
        assert result.get("device_count") == 3
        assert _session_rows(tmp_path) == 1
        session = _stored_session(result["confirm_token"])
        assert session.action == {"action": "delete_devices",
                                  "device_ids": _THREE_IDS}
        assert session.device_id == "multiple"
        # Nothing happened yet.
        for device_id in _THREE_IDS:
            assert auth_mcp_server.registry.device_exists(device_id)

    @pytest.mark.asyncio
    async def test_the_card_names_every_device(self, auth_mcp_server):
        """Both approval surfaces render danger_description and neither renders
        the action payload, so this sentence is the whole review."""
        _register(auth_mcp_server, *_THREE)
        result = await _call_tool(
            auth_mcp_server, "delete_devices", {"device_ids": _THREE_IDS})
        text = _stored_session(result["confirm_token"]).danger_description
        assert text.startswith("Remove 3 devices from the registry: ")
        for device_id, nickname in _THREE:
            assert f"{nickname} ({device_id})" in text

    @pytest.mark.asyncio
    async def test_single_removal_is_unchanged(self, auth_mcp_server):
        """Control: the batch is a new tool beside delete_device, not an edit
        of it — the single session's payload and sentence stay as they were."""
        _register(auth_mcp_server, ("cam-a", "Lobby"))
        result = await _call_tool(
            auth_mcp_server, "delete_device", {"device_id": "cam-a"})
        session = _stored_session(result["confirm_token"])
        assert session.action == {"action": "delete_device", "device_id": "cam-a"}
        assert session.danger_description == (
            "Remove Lobby (cam-a) from the registry, including its stored "
            "accounts/credentials. The device itself is not touched; its git "
            "config history is retained.")

    @pytest.mark.asyncio
    async def test_an_unknown_id_rejects_the_whole_request(
        self, auth_mcp_server, tmp_path,
    ):
        _register(auth_mcp_server, *_THREE[:2])
        result = await _call_tool(
            auth_mcp_server, "delete_devices",
            {"device_ids": ["cam-a", "ghost", "cam-b"]})
        assert result.get("blocked") is not True
        assert result.get("error") == "DeviceNotFound"
        assert "ghost" in result.get("message", "")
        # No session at all — not a card for the two ids that do exist.
        assert _session_rows(tmp_path) == 0
        assert auth_mcp_server.registry.device_exists("cam-a")
        assert auth_mcp_server.registry.device_exists("cam-b")

    @pytest.mark.asyncio
    async def test_duplicates_collapse_in_order(self, auth_mcp_server):
        _register(auth_mcp_server, *_THREE[:2])
        result = await _call_tool(
            auth_mcp_server, "delete_devices",
            {"device_ids": ["cam-b", "cam-a", "cam-b"]})
        assert result.get("device_count") == 2
        session = _stored_session(result["confirm_token"])
        assert session.action["device_ids"] == ["cam-b", "cam-a"]

    @pytest.mark.asyncio
    async def test_a_batch_of_one_keeps_its_device_id(self, auth_mcp_server):
        _register(auth_mcp_server, ("cam-a", "Lobby"))
        result = await _call_tool(
            auth_mcp_server, "delete_devices", {"device_ids": ["cam-a"]})
        session = _stored_session(result["confirm_token"])
        assert session.device_id == "cam-a"
        assert session.danger_description.startswith(
            "Remove 1 device from the registry: Lobby (cam-a), including its ")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "device_ids", [[], "cam-a", [""], ["cam-a", 7], None],
        ids=["empty", "not-a-list", "blank-id", "non-string-id", "missing"])
    async def test_malformed_ids_open_no_session(
        self, auth_mcp_server, tmp_path, device_ids,
    ):
        _register(auth_mcp_server, ("cam-a", "Lobby"))
        arguments = {} if device_ids is None else {"device_ids": device_ids}
        result = await _call_tool(auth_mcp_server, "delete_devices", arguments)
        assert result.get("blocked") is not True
        assert result.get("error") == "InvalidInput"
        assert _session_rows(tmp_path) == 0
        assert auth_mcp_server.registry.device_exists("cam-a")

    @pytest.mark.asyncio
    async def test_the_gate_is_single_removals(self, auth_mcp_server, monkeypatch):
        """Same risk class, same pinned level, same token lifetime. The level
        lookup is forced to "none" — what a softening operator override would
        yield — so a session resolved through it instead of pinned cannot pass."""
        from admz import operations
        monkeypatch.setattr(operations, "resolve_confirmation", lambda risk: "none")
        _register(auth_mcp_server, *_THREE[:2])
        single = await _call_tool(
            auth_mcp_server, "delete_device", {"device_id": "cam-a"})
        batch = await _call_tool(
            auth_mcp_server, "delete_devices", {"device_ids": ["cam-a", "cam-b"]})
        one = _stored_session(single["confirm_token"])
        many = _stored_session(batch["confirm_token"])
        assert many.confirmation_level == one.confirmation_level == "url_only"
        assert many.risk_level == one.risk_level == "service-affecting"
        assert many.ttl == one.ttl

    @pytest.mark.asyncio
    async def test_approval_removes_every_device_through_single_removal(
        self, auth_mcp_server, monkeypatch,
    ):
        from admz import operations
        tombstoned = []
        monkeypatch.setattr(
            operations, "tombstone_device",
            lambda device_id, git_repo, removed_by="": tombstoned.append(device_id))
        _register(auth_mcp_server, *_THREE)
        result = await _call_tool(
            auth_mcp_server, "delete_devices", {"device_ids": _THREE_IDS})
        outcome = await _approve(result["confirm_token"])
        assert outcome["success"] is True
        assert outcome["action"] == "delete_devices"
        assert outcome["removed"] == _THREE_IDS
        assert outcome["failed"] == []
        assert outcome["removed_devices"] == "cam-a,cam-b,cam-c"
        assert "failed_devices" not in outcome
        # Each device went through _action_delete_device; the tombstone shows it.
        assert tombstoned == _THREE_IDS
        for device_id in _THREE_IDS:
            assert not auth_mcp_server.registry.device_exists(device_id)

    @pytest.mark.asyncio
    async def test_one_failure_does_not_stop_the_rest(self, auth_mcp_server):
        _register(auth_mcp_server, *_THREE)
        result = await _call_tool(
            auth_mcp_server, "delete_devices", {"device_ids": _THREE_IDS})
        # Removed out-of-band between the request and the approval.
        auth_mcp_server.registry.remove_device("cam-b")
        outcome = await _approve(result["confirm_token"])
        assert outcome["success"] is False
        assert outcome["removed"] == ["cam-a", "cam-c"]
        assert outcome["failed"] == [
            {"device_id": "cam-b", "error": "Device not found: cam-b"}]
        assert outcome["removed_devices"] == "cam-a,cam-c"
        assert outcome["failed_devices"] == "cam-b"
        assert outcome["error"].startswith("removed 2 of 3; cam-b: ")
        assert not auth_mcp_server.registry.device_exists("cam-a")
        assert not auth_mcp_server.registry.device_exists("cam-c")

    @pytest.mark.asyncio
    async def test_an_exception_on_one_device_does_not_stop_the_rest(
        self, auth_mcp_server, monkeypatch,
    ):
        from admz import operations

        def _tombstone(device_id, git_repo, removed_by=""):
            if device_id == "cam-b":
                raise RuntimeError("config repo locked")

        monkeypatch.setattr(operations, "tombstone_device", _tombstone)
        _register(auth_mcp_server, *_THREE)
        result = await _call_tool(
            auth_mcp_server, "delete_devices", {"device_ids": _THREE_IDS})
        outcome = await _approve(result["confirm_token"])
        assert outcome["success"] is False
        assert outcome["removed"] == ["cam-a", "cam-c"]
        assert outcome["failed"] == [
            {"device_id": "cam-b", "error": "RuntimeError: config repo locked"}]
        assert auth_mcp_server.registry.device_exists("cam-b")

    def test_an_empty_batch_is_not_a_success(self):
        from admz import operations
        out = operations._action_delete_devices(
            {"action": "delete_devices"}, registry=None)
        assert out["success"] is False
        assert out["removed"] == [] and out["failed"] == []

    @pytest.mark.asyncio
    async def test_anonymous_gets_the_same_widget_not_refusal(
        self, anon_mcp_server,
    ):
        _register(anon_mcp_server, *_THREE[:2])
        result = await _call_tool(
            anon_mcp_server, "delete_devices", {"device_ids": ["cam-a", "cam-b"]})
        assert result.get("error") != "PermissionDenied"
        assert result.get("blocked") is True
        assert anon_mcp_server.registry.device_exists("cam-a")


class TestDeleteDevicesIsWhatTheModelIsTold:
    """ADR-0069 §4. The description is the artefact the model selects on
    (#366, #438), so the trigger, the one-approval payoff and the whole-request
    rejection each have to be in the string itself."""

    @pytest.mark.asyncio
    async def test_the_batch_tool_states_trigger_payoff_and_consequence(
        self, auth_mcp_server,
    ):
        tool = await mcp_harness.find_tool(auth_mcp_server, "delete_devices")
        d = tool.description
        assert "Use this when the user wants MORE THAN ONE device removed" in d
        assert "ONE approval card for the whole batch" in d
        assert "ONE unknown id rejects the WHOLE request" in d
        assert "can never be a create_plan step" in d

    @pytest.mark.asyncio
    async def test_single_removal_points_to_the_batch_tool(self, auth_mcp_server):
        tool = await mcp_harness.find_tool(auth_mcp_server, "delete_device")
        assert "call delete_devices once instead" in tool.description


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
# accept_baseline — note, principal, exclusions (ADR-0070 §3)
# ---------------------------------------------------------------------------


def _observed(server, device_id="test-cam", value="1920x1080"):
    """Register the device with one recorded observation; return its sha."""
    if not server.registry.device_exists(device_id):
        server.registry.add_device(
            device_id, {"host": "192.0.2.10", "nickname": "Lobby"})
    sha = _commit_facet(server, device_id, "image",
                        {"I0.Resolution": value}, f"Audit: {device_id}")
    server.registry.set_config_pointers(device_id, latest_observed_sha=sha)
    return sha


async def _approve_with_repo(server, token):
    """``_approve``, plus the git repo the confirm route passes."""
    from admz import operations
    import admz.api.confirm_store as cs_module
    store = cs_module.confirm_store
    session = store.get_session(token)
    store.complete_session(token, confirmed_by="test-approver")
    return await operations.execute_approved_session(
        session, catalog=None, registry=server.registry, executors={},
        git_repo=server.git_repo,
    )


class TestAcceptBaselineCarriesTheReview:
    @pytest.mark.asyncio
    async def test_the_card_names_the_note_and_the_exclusions(self, auth_mcp_server):
        sha = _observed(auth_mcp_server)
        result = await _call_tool(auth_mcp_server, "accept_baseline", {
            "device_id": "test-cam", "note": "fw 12.9.57→12.11.77 upgrade",
            "ignore_keys": ["root.Properties.FirmwareManagement.*"],
            "ignore_scope": "device:test-cam",
        })
        assert result["blocked"] is True
        card = _stored_session(result["confirm_token"]).danger_description
        assert card == (
            f"Accept the current observed config of Lobby (test-cam) as its new "
            f"baseline (commit {sha[:12]}, 1 facet). "
            'Note: "fw 12.9.57→12.11.77 upgrade". '
            "Also exclude from drift tracking (device:test-cam): "
            "root.Properties.FirmwareManagement.*."
        )

    @pytest.mark.asyncio
    async def test_a_chat_accept_writes_the_changelog_with_the_principal(
            self, auth_mcp_server):
        import yaml
        sha = _observed(auth_mcp_server)
        result = await _call_tool(auth_mcp_server, "accept_baseline", {
            "device_id": "test-cam", "note": "MQTT prefix case normalised"})
        outcome = await _approve_with_repo(auth_mcp_server, result["confirm_token"])
        assert outcome["success"] is True
        text = auth_mcp_server.git_repo.get_file(
            "fleet/test-cam/BASELINE.yaml", "HEAD")
        doc = yaml.safe_load(text)
        assert doc["note"] == "MQTT prefix case normalised"
        assert doc["accepted_by"] == "HOMELAB\\alice"
        assert doc["baseline_sha"] == sha

    @pytest.mark.asyncio
    async def test_exclusions_land_only_when_the_card_is_approved(
            self, auth_mcp_server):
        from admz.audit import outcome_identity_fields
        from admz.snapshot import ignore
        _observed(auth_mcp_server)
        result = await _call_tool(auth_mcp_server, "accept_baseline", {
            "device_id": "test-cam",
            "ignore_keys": ["root.Properties.FirmwareManagement.*",
                            "root.Noise.Counter", "root.Noise.Counter"],
        })
        key = "root.Properties.FirmwareManagement.Version"
        assert not ignore.is_ignored(key, "test-cam", [])        # minted only

        outcome = await _approve_with_repo(auth_mcp_server, result["confirm_token"])
        assert outcome["success"] is True
        assert ignore.is_ignored(key, "test-cam", [])            # approved
        assert ignore.is_ignored("root.Noise.Counter", "other-cam", [])  # global
        assert outcome["ignore_added_keys"] == (
            "root.Properties.FirmwareManagement.*, root.Noise.Counter")
        assert outcome_identity_fields(outcome)["ignore_added_keys"] == (
            outcome["ignore_added_keys"])

    @pytest.mark.asyncio
    async def test_a_rule_already_in_force_is_not_news(self, auth_mcp_server):
        from admz.snapshot import ignore
        _observed(auth_mcp_server)
        ignore.add_rules([{"key": "root.Noise.Counter", "scope": "global"}])
        result = await _call_tool(auth_mcp_server, "accept_baseline", {
            "device_id": "test-cam", "ignore_keys": ["root.Noise.Counter"]})
        session = _stored_session(result["confirm_token"])
        assert "exclude" not in session.danger_description
        assert "ignore_rules" not in session.action
        outcome = await _approve_with_repo(auth_mcp_server, result["confirm_token"])
        assert "ignore_added_keys" not in outcome

    @pytest.mark.asyncio
    @pytest.mark.parametrize("args, fragment", [
        # the schema rejects these before the handler runs
        ({"note": "x" * 501}, "is too long"),
        ({"ignore_keys": "root.A"}, "is not of type 'array'"),
        ({"ignore_keys": [f"root.K{i}" for i in range(51)]}, "is too long"),
        ({"ignore_keys": [7]}, "is not of type 'string'"),
        # the schema cannot express these; the handler rejects them
        ({"ignore_keys": ["root.A\nroot.B"]}, "single-line"),
        ({"ignore_keys": ["root.A"], "ignore_scope": "fleet"}, "ignore_scope"),
    ])
    async def test_bad_input_opens_no_card(self, auth_mcp_server, tmp_path,
                                           args, fragment):
        _observed(auth_mcp_server)
        before = _session_rows(tmp_path)
        result = await _call_tool(auth_mcp_server, "accept_baseline",
                                  {"device_id": "test-cam", **args})
        assert result["success"] is False
        assert result["error"] == "InvalidInput"
        assert fragment in result["message"]
        assert _session_rows(tmp_path) == before

    @pytest.mark.asyncio
    @pytest.mark.parametrize("kwargs, fragment", [
        ({"note": "x" * 501}, "500"),
        ({"ignore_keys": "root.A"}, "ignore_keys"),
        ({"ignore_keys": [f"root.K{i}" for i in range(51)]}, "at most 50"),
        ({"ignore_keys": [7]}, "ignore_keys"),
    ])
    async def test_the_handler_does_not_rely_on_the_schema(
            self, auth_mcp_server, tmp_path, kwargs, fragment):
        _observed(auth_mcp_server)
        before = _session_rows(tmp_path)
        result = await auth_mcp_server._accept_baseline("test-cam", None, **kwargs)
        assert result["error"] == "InvalidInput"
        assert fragment in result["message"]
        assert _session_rows(tmp_path) == before

    @pytest.mark.asyncio
    async def test_the_reviewed_observation_is_the_default_target(
            self, auth_mcp_server, tmp_path, monkeypatch):
        """Accept blesses what the operator was shown — the cached review's
        observation — not a newer one recorded since (the REST order)."""
        from admz.snapshot import drift_alerts as da_module
        from admz.snapshot.models import DriftField, DriftReport
        alerts = da_module.DriftAlertStore(str(tmp_path / "admz.db"))
        monkeypatch.setattr(da_module, "drift_alerts", alerts)

        reviewed = _observed(auth_mcp_server, value="1280x720")
        auth_mcp_server.registry.set_config_pointers(
            "test-cam", baseline_sha=reviewed)
        report = DriftReport(
            device_id="test-cam", has_drift=True, baseline_sha=reviewed,
            observed_sha=reviewed,
            fields=[DriftField(facet="image", path="I0.A", expected="1", actual="2"),
                    DriftField(facet="image", path="I0.B", expected="1", actual="3"),
                    DriftField(facet="image", path="I0.C", expected="1", actual="4",
                               bucket="demo_set")])
        alerts.store_report(report)
        newer = _observed(auth_mcp_server, value="640x480")
        assert newer != reviewed

        result = await _call_tool(auth_mcp_server, "accept_baseline",
                                  {"device_id": "test-cam"})
        session = _stored_session(result["confirm_token"])
        assert session.action["baseline_sha"] == reviewed
        assert session.action["drifted_count"] == 2
        assert session.action["accepted_by"] == "HOMELAB\\alice"
        assert session.danger_description.startswith(
            "Accept the current observed config of Lobby (test-cam)")
        assert "2 drifted fields absorbed" in session.danger_description

    @pytest.mark.asyncio
    async def test_an_explicit_historical_commit_is_named_as_one(
            self, auth_mcp_server):
        old = _observed(auth_mcp_server, value="1280x720")
        _observed(auth_mcp_server, value="640x480")
        result = await _call_tool(auth_mcp_server, "accept_baseline",
                                  {"device_id": "test-cam", "commit_sha": old})
        card = _stored_session(result["confirm_token"]).danger_description
        assert card.startswith(
            f"Accept the config recorded at commit {old[:12]} of Lobby")


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
