"""Tests for auth-aware health probing (admz/fleet/health.py).

The I8016 case: systemready returns 200 even with a wrong password (it
doesn't validate auth on some firmware), so the health monitor must confirm
credentials with an auth-required call — otherwise a bad-password device
shows misleadingly "online".
"""

import pytest

from admz.fleet import health as health_mod
from admz.fleet.health import probe_device, DeviceHealthStatus, SYSTEMREADY_OP, AUTH_CHECK_OP
from admz.executor.models import StepResult


class _Op:
    def __init__(self, op_id):
        self._id = op_id

    def to_executor_dict(self):
        return {"id": self._id}


class _Catalog:
    def __init__(self, have_auth_op=True):
        self._have_auth_op = have_auth_op

    def get_operation(self, family, op_id):
        if op_id == AUTH_CHECK_OP and not self._have_auth_op:
            return None
        return _Op(op_id)


class _Executor:
    """Returns a scripted StepResult per op id."""
    def __init__(self, by_op):
        self.by_op = by_op
        self.calls = []

    async def execute(self, op, device, credentials, params):
        op_id = op["id"]
        self.calls.append(op_id)
        spec = self.by_op[op_id]
        if isinstance(spec, Exception):
            raise spec
        return spec


def _systemready_ok():
    return StepResult(operation_id=SYSTEMREADY_OP, device_id="dev", success=True,
                      status_code=200, parsed_data={"systemready": "yes",
                                                     "uptime": "1000", "bootid": "b1"})


def _result(status_code, success=False):
    return StepResult(operation_id=AUTH_CHECK_OP, device_id="dev",
                      success=success, status_code=status_code,
                      parsed_data={} if success else None,
                      error=None if success else f"HTTP {status_code}")


@pytest.fixture
def _verify_on(monkeypatch):
    """Credential verification on (don't depend on the real DB)."""
    monkeypatch.setattr(health_mod, "_verify_credentials_enabled", lambda: True)


async def _probe(catalog, executor):
    return await probe_device(
        device_id="dev",
        device_info={"host": "192.0.2.1"},
        credentials={"username": "root", "password": "pw"},
        catalog=catalog, executor=executor, timeout_seconds=2.0,
    )


@pytest.mark.asyncio
async def test_wrong_password_marks_auth_failed_not_online(_verify_on):
    """systemready 200 but basicdeviceinfo 401 → auth_failed (the I8016 bug)."""
    execs = _Executor({SYSTEMREADY_OP: _systemready_ok(), AUTH_CHECK_OP: _result(401)})
    rec = await _probe(_Catalog(), execs)
    assert rec.status == DeviceHealthStatus.AUTH_FAILED
    assert "credentials rejected" in rec.last_error
    # we still captured uptime/bootid from systemready
    assert rec.uptime_seconds == 1000
    assert AUTH_CHECK_OP in execs.calls  # the second, auth-required call ran


@pytest.mark.asyncio
async def test_valid_creds_marks_online(_verify_on):
    execs = _Executor({SYSTEMREADY_OP: _systemready_ok(),
                       AUTH_CHECK_OP: _result(200, success=True)})
    rec = await _probe(_Catalog(), execs)
    assert rec.status == DeviceHealthStatus.ONLINE
    assert rec.uptime_seconds == 1000


@pytest.mark.asyncio
async def test_auth_check_transient_error_does_not_flap(_verify_on):
    """If the auth-check call errors transiently, don't flip to auth_failed."""
    execs = _Executor({SYSTEMREADY_OP: _systemready_ok(),
                       AUTH_CHECK_OP: RuntimeError("boom")})
    rec = await _probe(_Catalog(), execs)
    assert rec.status == DeviceHealthStatus.ONLINE


@pytest.mark.asyncio
async def test_auth_check_op_missing_stays_online(_verify_on):
    execs = _Executor({SYSTEMREADY_OP: _systemready_ok()})
    rec = await _probe(_Catalog(have_auth_op=False), execs)
    assert rec.status == DeviceHealthStatus.ONLINE
    assert AUTH_CHECK_OP not in execs.calls  # never tried the auth op


@pytest.mark.asyncio
async def test_verification_disabled_skips_auth_check(monkeypatch):
    monkeypatch.setattr(health_mod, "_verify_credentials_enabled", lambda: False)
    execs = _Executor({SYSTEMREADY_OP: _systemready_ok(), AUTH_CHECK_OP: _result(401)})
    rec = await _probe(_Catalog(), execs)
    assert rec.status == DeviceHealthStatus.ONLINE
    assert AUTH_CHECK_OP not in execs.calls  # auth check skipped


def test_verify_enabled_reads_fleet_setting(monkeypatch):
    """The real toggle reads the fleet setting (default on)."""
    import admz.fleet.health as h
    calls = {}
    class _FS:
        def get(self, k):
            calls["k"] = k
            return None
    monkeypatch.setattr(h, "_fs", lambda: _FS())
    assert h._verify_credentials_enabled() is True
    assert calls["k"] == "health_verify_credentials"

    class _FSOff:
        def get(self, k):
            return "false"
    monkeypatch.setattr(h, "_fs", lambda: _FSOff())
    assert h._verify_credentials_enabled() is False
