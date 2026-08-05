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
from tests import mcp_harness


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
    return await mcp_harness.call_tool(server, name, arguments)


async def _approve(session_token, registry):
    """Complete + execute a confirm session, as the confirm route does."""
    from admz import operations
    import admz.api.confirm_store as cs_module
    store = cs_module.confirm_store
    # Fetch BEFORE completing and execute from that object — which is what the
    # route actually does (routes/confirm.py: get_session :203 ->
    # complete_session :274 -> execute_approved_session(session) :284). This
    # helper used to re-fetch *after* completing, which the route never does;
    # #266 strips the payload on completion, so the re-fetch handed the executor
    # an empty action and it fell through to the operation branch.
    session = store.get_session(session_token)
    assert session is not None
    store.complete_session(session_token, confirmed_by="test-approver")
    return await operations.execute_approved_session(
        session, catalog=None, registry=registry, executors={})


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


# ---------------------------------------------------------------------------
# GH #170: discard on every terminal path, not just success
# ---------------------------------------------------------------------------


def test_has_rule_secrets_purges_an_expired_entry_as_a_side_effect(monkeypatch):
    """A caller that only ever CHECKS (never stashes or consumes again) must
    still keep the dict bounded -- has_rule_secrets must not just report an
    expired stash as absent, it must remove it."""
    clock = [1_000_000.0]
    monkeypatch.setattr(capture.time, "time", lambda: clock[0])

    capture.stash_rule_secrets("tok-expiring", {"password": "x"})
    assert "tok-expiring" in capture._SECRETS

    clock[0] += capture._TTL_SECONDS + 1  # past expiry
    assert capture.has_rule_secrets("tok-expiring") is False
    assert "tok-expiring" not in capture._SECRETS, (
        "has_rule_secrets reported the entry gone but left it in the dict")


def test_sweep_once_purges_a_token_nothing_else_ever_touches_again(monkeypatch):
    """The scenario purge-on-access structurally cannot reach: an abandoned
    token that nothing reads or writes again after it expires. Only a
    time-triggered sweep closes this -- drive one pass directly rather than
    waiting on the real 60s loop interval."""
    clock = [2_000_000.0]
    monkeypatch.setattr(capture.time, "time", lambda: clock[0])

    capture.stash_rule_secrets("tok-orphan", {"password": "x"})
    clock[0] += capture._TTL_SECONDS + 1
    assert "tok-orphan" in capture._SECRETS, (
        "control failed: the entry must still be present (just expired) "
        "before the sweep runs, or its removal below proves nothing")

    capture._sweep_once()

    assert "tok-orphan" not in capture._SECRETS


@pytest.mark.asyncio
async def test_background_purge_start_stop_is_idempotent_and_does_not_raise():
    """start/stop must tolerate being called more than once (a lifespan that
    restarts without a clean shutdown) and must not error when stop is called
    before start."""
    capture.stop_background_purge()  # stop before start: must not raise
    capture.start_background_purge()
    capture.start_background_purge()  # second start: must not spawn a second task
    task = capture._sweep_task
    assert task is not None and not task.done()
    capture.stop_background_purge()
    capture.stop_background_purge()  # second stop: must not raise
    assert capture._sweep_task is None


# ---------------------------------------------------------------------------
# Condition grounding: survey notes, device applications, publisher lint
# ---------------------------------------------------------------------------

from types import SimpleNamespace


def test_condition_dicts_carry_notes_and_requires():
    caps = capabilities.list_capabilities("AXIS C1710")
    assert caps["available"] is True
    pir = next(c for c in caps["conditions"] if c["id"] == "pir-sensor")
    assert pir["requires"] == {"hardware": "pir_sensor"}
    assert pir["notes"]  # survey caveats reach the model


def test_trim_notes_collapses_and_caps():
    noisy = "line one\n  line   two\n" + "x" * 500
    out = capabilities._trim_notes(noisy)
    assert "\n" not in out
    assert len(out) <= 281  # 280 + ellipsis


def test_device_applications_reads_latest_observation():
    registry = SimpleNamespace(
        get_device_info=lambda did: {"latest_observed_sha": "abc123"})
    seen = {}

    class Repo:
        def read_facet(self, device_id, facet, ref):
            seen.update(device_id=device_id, facet=facet, ref=ref)
            return {"vmd": {"status": "Running", "version": "4.5.66"},
                    "BarcodeReader": {"status": "Stopped"}}

    apps = capabilities.device_applications(Repo(), registry, "dev1")
    assert apps == {"vmd": "Running", "BarcodeReader": "Stopped"}
    assert seen == {"device_id": "dev1", "facet": "applications", "ref": "abc123"}


def test_device_applications_degrades_to_empty():
    registry = SimpleNamespace(
        get_device_info=lambda did: (_ for _ in ()).throw(RuntimeError("boom")))
    assert capabilities.device_applications(object(), registry, "dev1") == {}


# --- device_applications_detail (#189) --------------------------------------


def test_detail_reports_apps_and_has_snapshot_true():
    registry = SimpleNamespace(
        get_device_info=lambda did: {"latest_observed_sha": "abc123"})

    class Repo:
        def read_facet(self, device_id, facet, ref):
            return {"vmd": {"status": "Running"}}

    apps, has_snapshot = capabilities.device_applications_detail(Repo(), registry, "dev1")
    assert apps == {"vmd": "Running"}
    assert has_snapshot is True


def test_detail_has_snapshot_true_via_baseline_sha_fallback():
    """``baseline_sha`` counts as a snapshot ref too, same as ``device_applications``
    itself falls back to it."""
    registry = SimpleNamespace(
        get_device_info=lambda did: {"baseline_sha": "base1"})

    class Repo:
        def read_facet(self, device_id, facet, ref):
            return {}

    apps, has_snapshot = capabilities.device_applications_detail(Repo(), registry, "dev1")
    assert apps == {} and has_snapshot is True


def test_detail_has_snapshot_false_when_registry_has_no_ref_at_all():
    """No ``latest_observed_sha`` and no ``baseline_sha`` — never snapshotted,
    the one case that IS reliably distinguishable."""
    registry = SimpleNamespace(get_device_info=lambda did: {})

    class Repo:
        def read_facet(self, device_id, facet, ref):
            raise AssertionError("must not read a facet with no ref to read")

    apps, has_snapshot = capabilities.device_applications_detail(Repo(), registry, "dev1")
    assert apps == {} and has_snapshot is False


def test_detail_ref_present_but_apps_empty_is_still_has_snapshot_true():
    """The exact ambiguous case the docstring names: a ref exists, but the
    facet reads back empty. ``has_snapshot`` is True — this function makes NO
    claim about whether that's a genuinely-empty inventory or a failed read."""
    registry = SimpleNamespace(
        get_device_info=lambda did: {"latest_observed_sha": "sha-that-may-be-stale"})

    class Repo:
        def read_facet(self, device_id, facet, ref):
            return None   # what a failed `git show` AND a legitimately-empty
                          # facet both look like — see GitRepo.get_file

    apps, has_snapshot = capabilities.device_applications_detail(Repo(), registry, "dev1")
    assert apps == {} and has_snapshot is True


def test_detail_degrades_has_snapshot_to_false_when_registry_read_fails():
    registry = SimpleNamespace(
        get_device_info=lambda did: (_ for _ in ()).throw(RuntimeError("boom")))
    apps, has_snapshot = capabilities.device_applications_detail(
        object(), registry, "dev1")
    assert apps == {} and has_snapshot is False


def test_publisher_app_for_topic_matrix():
    cases = [
        ("tnsaxis:CameraApplicationPlatform/VMD/Camera1ProfileANY", "vmd"),
        ("tnsaxis:RuleEngine/VMD3/vmd3_video_1", "vmd"),
        ("tnsaxis:CameraApplicationPlatform/ObjectAnalytics/Device1Scenario1",
         "objectanalytics"),
        ("tns1:Device/tnsaxis:Sensor/PIR", None),
        ("tns1:VideoSource/MotionAlarm", None),
    ]
    for topic, expected in cases:
        cond = SimpleNamespace(topic=topic)
        assert capabilities.publisher_app_for(cond) == expected, topic


def test_check_condition_publisher_blocks_absent_and_stopped():
    vmd_cond = SimpleNamespace(
        topic="tnsaxis:CameraApplicationPlatform/VMD/Camera1ProfileANY",
        label="VMD any profile", id="vmd4-camera1-profile-any")
    absent = capabilities.check_condition_publisher(
        vmd_cond, {"stream_monitor": "Running"})
    assert absent and "not installed" in absent and "'vmd'" in absent
    stopped = capabilities.check_condition_publisher(
        vmd_cond, {"vmd": "Stopped"})
    assert stopped and "Stopped" in stopped
    # Running app, unknown state, and built-in topics never block.
    assert capabilities.check_condition_publisher(
        vmd_cond, {"vmd": "Running"}) is None
    assert capabilities.check_condition_publisher(vmd_cond, {}) is None
    pir = SimpleNamespace(topic="tns1:Device/tnsaxis:Sensor/PIR")
    assert capabilities.check_condition_publisher(
        pir, {"stream_monitor": "Running"}) is None


def test_condition_caution_flags_shadowed_motion_alarm():
    motion = SimpleNamespace(topic="tns1:VideoSource/MotionAlarm")
    caution = capabilities.condition_caution(motion, {"vmd": "Running"})
    assert caution and "never fire" in caution and "vmd" in caution
    # No analytics running -> MotionAlarm may be the only motion source; no nag.
    assert capabilities.condition_caution(
        motion, {"stream_monitor": "Running"}) is None
    assert capabilities.condition_caution(motion, {}) is None
    other = SimpleNamespace(topic="tns1:Device/tnsaxis:IO/Port")
    assert capabilities.condition_caution(other, {"vmd": "Running"}) is None


@pytest.mark.asyncio
async def test_list_rule_capabilities_includes_device_applications(
        server, monkeypatch):
    async def _no_rules(**kw):
        return []
    monkeypatch.setattr("admz.rules.runner.list_rules", _no_rules)
    monkeypatch.setattr(
        capabilities, "device_applications",
        lambda git_repo, registry, device_id: {"vmd": "Running"})
    out = await _call_tool(server, "list_rule_capabilities", {"device_id": "cam"})
    assert out["device_applications"] == {"vmd": "Running"}
    assert "Running" in out["device_applications_note"]


@pytest.mark.asyncio
async def test_create_rule_blocked_when_publisher_app_missing(
        server, monkeypatch):
    server.registry.update_device("cam", {"model": "AXIS I8016-LVE"})
    monkeypatch.setattr(capabilities, "build", lambda *a, **k: _FakeResult(True))
    monkeypatch.setattr(
        capabilities, "device_applications",
        lambda git_repo, registry, device_id: {"stream_monitor": "Running"})
    result = await _call_tool(server, "create_action_rule", {
        "device_id": "cam", "condition_id": "vmd4-camera1-profile-any",
        "action_token": "com.axis.action.fixed.ledcontrol",
        "rule_name": "doomed"})
    assert result["success"] is False
    assert result.get("blocked") is not True  # refused outright, no card
    assert "'vmd'" in result["error"] and "not installed" in result["error"]
    assert result["device_applications"] == {"stream_monitor": "Running"}


@pytest.mark.asyncio
async def test_create_rule_warns_on_shadowed_motion_alarm(server, monkeypatch):
    server.registry.update_device("cam", {"model": "AXIS I8016-LVE"})
    monkeypatch.setattr(capabilities, "build", lambda *a, **k: _FakeResult(True))
    monkeypatch.setattr(
        capabilities, "device_applications",
        lambda git_repo, registry, device_id: {"vmd": "Running"})
    result = await _call_tool(server, "create_action_rule", {
        "device_id": "cam", "condition_id": "motion-alarm",
        "action_token": "com.axis.action.fixed.ledcontrol",
        "rule_name": "shadowed"})
    # Card still offered (the user may know better), but with a loud warning.
    assert result.get("blocked") is True
    assert result["warnings"] and "never fire" in result["warnings"][0]
