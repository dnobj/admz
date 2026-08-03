"""Unit tests for the reboot-recovery poller (admz/recovery.py, GH #49 v1).

All polling runs against a scripted fake probe executor and a fake clock —
no real sleeping, no network. The fake clock advances only inside sleep(),
so waited_s/polls assertions are exact.
"""

from __future__ import annotations

import pytest

from admz.exceptions import DeviceNotFoundError, OperationNotFoundError
from admz.executor.models import StepResult
from admz.recovery import await_device_recovery
from tests import mcp_harness


# --- fakes -----------------------------------------------------------------


class _FakeOp:
    def to_executor_dict(self):
        return {"id": "systemready.cgi:systemReady"}


class _FakeCatalog:
    def __init__(self, op=_FakeOp()):
        self._op = op

    def get_operation(self, family, op_id):
        return self._op


class _FakeRegistry:
    def __init__(self, exists=True):
        self._exists = exists

    def device_exists(self, device_id):
        return self._exists

    def get_device_info(self, device_id):
        return {"host": "192.0.2.1"}

    def get_credentials(self, device_id):
        return {"username": "root", "password": "x"}


class _Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    async def sleep(self, s):
        self.t += s


class _FakeProbe:
    """Returns the scripted StepResults in order; repeats the last forever."""

    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    async def execute(self, op, device, credentials, params):
        self.calls += 1
        assert params == {}  # the long-poll timeout param must be omitted
        if len(self.results) > 1:
            return self.results.pop(0)
        return self.results[0]


def _ok(bootid="7", uptime="5000", ready="yes", needsetup="no"):
    return StepResult(
        operation_id="systemready.cgi:systemReady", device_id="dev",
        success=True, status_code=200,
        parsed_data={
            "systemready": ready, "needsetup": needsetup,
            "uptime": uptime, "bootid": bootid,
        },
    )


def _offline():
    return StepResult(
        operation_id="systemready.cgi:systemReady", device_id="dev",
        success=False, status_code=None, error="Connection failed: down",
    )


def _auth(code=401):
    return StepResult(
        operation_id="systemready.cgi:systemReady", device_id="dev",
        success=False, status_code=code,
        error=f"Authentication failed ({code}). Check credentials.",
    )


async def _run(probe, clock, **kwargs):
    defaults = dict(
        device_id="dev", catalog=_FakeCatalog(), registry=_FakeRegistry(),
        probe_executor=probe, sleep=clock.sleep, monotonic=clock.now,
    )
    defaults.update(kwargs)
    return await await_device_recovery(**defaults)


# --- recovery detection ------------------------------------------------------


@pytest.mark.asyncio
async def test_recovers_after_offline_then_new_bootid():
    clock = _Clock()
    probe = _FakeProbe([_ok("7", "99999"), _offline(), _offline(), _ok("8", "12")])
    result = await _run(probe, clock)
    assert result["status"] == "recovered"
    assert result["recovered"] is True
    assert result["success"] is True
    assert result["offline_observed"] is True
    assert result["bootid"] == "8"
    assert result["baseline_bootid"] == "7"
    assert result["polls"] == 4
    assert result["waited_s"] == 9.0  # 3 sleeps of poll_interval_s=3


@pytest.mark.asyncio
async def test_recovers_immediately_on_fresh_uptime():
    # Called late: device already came back, uptime < FRESH_BOOT_UPTIME_S.
    clock = _Clock()
    result = await _run(_FakeProbe([_ok("9", "25")]), clock)
    assert result["status"] == "recovered"
    assert result["polls"] == 1
    assert result["waited_s"] == 0.0
    assert result["uptime_s"] == 25


@pytest.mark.asyncio
async def test_first_healthy_old_boot_does_not_recover():
    # The critical edge: the reboot was just issued and the device hasn't
    # gone down yet — a healthy pre-reboot response must NOT be "recovered".
    clock = _Clock()
    probe = _FakeProbe([_ok("7", "100000")])
    result = await _run(probe, clock, timeout_s=10)
    assert result["status"] == "still_waiting"
    assert result["recovered"] is False
    assert result["success"] is True  # not an error — invites a re-call
    assert result["waited_s"] <= 10


@pytest.mark.asyncio
async def test_still_waiting_carries_baseline_and_recall_guidance():
    clock = _Clock()
    result = await _run(_FakeProbe([_ok("7", "100000")]), clock, timeout_s=10)
    assert result["baseline_bootid"] == "7"
    assert "baseline_bootid='7'" in result["message"]
    assert "pre-reboot state" in result["message"]


@pytest.mark.asyncio
async def test_continuation_with_baseline_param():
    # A follow-up call carries the previous call's baseline: even with no
    # offline period observed and stale uptime, a changed bootid is proof.
    clock = _Clock()
    result = await _run(
        _FakeProbe([_ok("8", "4000")]), clock, baseline_bootid="7"
    )
    assert result["status"] == "recovered"
    assert result["polls"] == 1
    assert result["bootid"] == "8"
    assert result["baseline_bootid"] == "7"
    assert "changed from 7" in result["message"]


@pytest.mark.asyncio
async def test_uptime_decrease_recovers_without_bootid():
    # Older firmware without bootid: uptime going backwards proves a reboot
    # (500 > FRESH_BOOT_UPTIME_S, so freshness alone doesn't explain it).
    clock = _Clock()
    probe = _FakeProbe([_ok("", "5000"), _ok("", "500")])
    result = await _run(probe, clock)
    assert result["status"] == "recovered"
    assert result["polls"] == 2


@pytest.mark.asyncio
async def test_not_ready_then_ready_recovers():
    clock = _Clock()
    probe = _FakeProbe([_ok("", "99999", ready="no"), _ok("", "99999")])
    result = await _run(probe, clock)
    assert result["status"] == "recovered"
    assert result["not_ready_observed"] is True


@pytest.mark.asyncio
async def test_needsetup_surfaced_in_message():
    clock = _Clock()
    result = await _run(_FakeProbe([_ok("9", "15", needsetup="yes")]), clock)
    assert result["status"] == "recovered"
    assert result["needsetup"] is True
    assert "factory-default" in result["message"]


# --- auth fail-fast ----------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_failure_fails_fast():
    clock = _Clock()
    probe = _FakeProbe([_auth(), _auth()])
    result = await _run(probe, clock)
    assert result["status"] == "auth_failed"
    assert result["success"] is False
    assert result["recovered"] is False
    assert result["polls"] == 2
    assert "401" in result["error"]
    assert "credentials" in result["message"]


@pytest.mark.asyncio
async def test_single_transient_401_does_not_abort():
    # Mid-boot the web server can answer 401 before auth is fully up; one
    # 401 followed by offline must reset the counter and keep polling.
    clock = _Clock()
    probe = _FakeProbe([_auth(), _offline(), _ok("8", "10")])
    result = await _run(probe, clock)
    assert result["status"] == "recovered"
    assert result["polls"] == 3


@pytest.mark.asyncio
async def test_403_also_counts_as_auth_failure():
    clock = _Clock()
    result = await _run(_FakeProbe([_auth(403), _auth(403)]), clock)
    assert result["status"] == "auth_failed"


# --- setup errors ------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_device_raises():
    clock = _Clock()
    with pytest.raises(DeviceNotFoundError):
        await _run(_FakeProbe([_ok()]), clock, registry=_FakeRegistry(exists=False))


@pytest.mark.asyncio
async def test_missing_catalog_op_raises():
    clock = _Clock()
    with pytest.raises(OperationNotFoundError):
        await _run(_FakeProbe([_ok()]), clock, catalog=_FakeCatalog(op=None))


# --- param clamping ----------------------------------------------------------


@pytest.mark.asyncio
async def test_param_clamping():
    clock = _Clock()
    result = await _run(
        _FakeProbe([_ok("7", "100000")]), clock,
        timeout_s=99999, poll_interval_s=0,
    )
    assert result["timeout_s"] == 600.0
    assert result["poll_interval_s"] == 1.0
    assert clock.t <= 600.0


@pytest.mark.asyncio
async def test_garbage_params_fall_back_to_defaults():
    clock = _Clock()
    result = await _run(
        _FakeProbe([_ok("7", "100000")]), clock,
        timeout_s="abc", poll_interval_s=None,
    )
    assert result["timeout_s"] == 90.0
    assert result["poll_interval_s"] == 3.0


# --- MCP layer ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_mcp_handler_delegates(monkeypatch):
    """_await_device_recovery forwards args to the recovery core verbatim."""
    from unittest.mock import AsyncMock

    import admz.recovery
    from admz.mcp.server import ADMZMCPServer

    server = ADMZMCPServer.__new__(ADMZMCPServer)
    server.catalog = object()
    server.registry = object()

    fake = AsyncMock(return_value={"status": "recovered"})
    monkeypatch.setattr(admz.recovery, "await_device_recovery", fake)

    result = await server._await_device_recovery(
        {"device_id": "dev", "timeout_s": 30, "baseline_bootid": "7"}
    )
    assert result == {"status": "recovered"}
    fake.assert_awaited_once_with(
        device_id="dev", timeout_s=30, poll_interval_s=3, baseline_bootid="7",
        catalog=server.catalog, registry=server.registry,
    )


@pytest.mark.asyncio
async def test_tool_in_list_tools_schema(tmp_path, monkeypatch):
    """await_device_recovery is registered with the expected schema."""
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")

    from admz.mcp.server import ADMZMCPServer

    server = ADMZMCPServer()
    tools = {t.name: t for t in await mcp_harness.list_tools(server)}

    assert "await_device_recovery" in tools
    schema = tools["await_device_recovery"].input_schema
    assert schema["required"] == ["device_id"]
    props = schema["properties"]
    assert props["timeout_s"]["default"] == 90
    assert props["poll_interval_s"]["default"] == 3
    assert props["baseline_bootid"]["default"] == ""
