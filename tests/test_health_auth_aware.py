"""Tests for auth-aware health probing (admz/fleet/health.py).

The I8016 case: systemready returns 200 even with a wrong password (it
doesn't validate auth on some firmware), so the health monitor must confirm
credentials with an auth-required call — otherwise a bad-password device
shows misleadingly "online".
"""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from admz.fleet import health as health_mod
from admz.fleet.health import (
    AUTH_CHECK_OP,
    CORROBORATION_OP,
    PROBE_MARKER_KEY,
    SYSTEMREADY_OP,
    DeviceHealthRecord,
    DeviceHealthStatus,
    DeviceHealthStore,
    HealthMonitor,
    probe_device,
)
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


async def _probe(catalog, executor, device_info=None):
    return await probe_device(
        device_id="dev",
        device_info=device_info or {"host": "192.0.2.1"},
        credentials={"username": "root", "password": "pw"},
        catalog=catalog, executor=executor, timeout_seconds=2.0,
    )


@pytest.mark.asyncio
async def test_wrong_password_marks_auth_failed_not_online(_verify_on):
    """systemready 200 but the auth-required ops 401 → auth_failed (the I8016
    bug). Since GH #149 a rejection has to be corroborated, so the corroborator
    is scripted to refuse too — that is what a wrong password looks like."""
    execs = _Executor({SYSTEMREADY_OP: _systemready_ok(),
                       AUTH_CHECK_OP: _result(401),
                       CORROBORATION_OP: _param_result(401)})
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


# ---------------------------------------------------------------------------
# GH #149 — a 401 from ONE op is not proof of bad credentials.
#
# The AXIS P8815-2 3D People Counter authenticates root/digest perfectly on
# param.cgi and usergroup.cgi while basicdeviceinfo's *data* methods 401. It
# sat at auth_failed with 18,004 consecutive failures while fully manageable.
# So a rejection is corroborated with a second, independent auth-required op
# before the device is condemned — the same defect class as #138, where
# `unreachable` absorbed "reachable but the API didn't answer".
# ---------------------------------------------------------------------------


def _param_ok():
    """param.cgi:list answering a `group=root.Brand` read — a param dump, not
    basicdeviceinfo's shape (which is why no identity facts come back)."""
    return StepResult(operation_id=CORROBORATION_OP, device_id="dev",
                      success=True, status_code=200,
                      parsed_data={"raw": "root.Brand.ProdNbr=P8815-2\n"})


def _param_result(status_code, success=False):
    return StepResult(operation_id=CORROBORATION_OP, device_id="dev",
                      success=success, status_code=status_code,
                      parsed_data=None, error=f"HTTP {status_code}")


def _auth_calls(execs):
    """Only the auth-required ops — the opportunistic SD probe on the online
    path is noise for "how many credential checks ran?" assertions."""
    return [c for c in execs.calls if c in (AUTH_CHECK_OP, CORROBORATION_OP)]


_MARKED = {
    "host": "192.0.2.1",
    PROBE_MARKER_KEY: {"auth_check_op": CORROBORATION_OP},
}


@pytest.mark.asyncio
async def test_restricted_op_401_corroborated_by_param_cgi_is_online(_verify_on):
    """The P8815-2 case: basicdeviceinfo 401s but param.cgi authenticates, so
    the credentials are GOOD and the device is online — not auth_failed."""
    execs = _Executor({SYSTEMREADY_OP: _systemready_ok(),
                       AUTH_CHECK_OP: _result(401),
                       CORROBORATION_OP: _param_ok()})
    rec = await _probe(_Catalog(), execs)
    assert rec.status == DeviceHealthStatus.ONLINE
    assert rec.consecutive_failures == 0
    # Exactly the two auth ops, in that order: the corroborator runs only
    # after the rejection.
    assert _auth_calls(execs) == [AUTH_CHECK_OP, CORROBORATION_OP]
    # ...and we learned to lead with param.cgi next sweep.
    assert rec.learned_probe == {"auth_check_op": CORROBORATION_OP}


@pytest.mark.asyncio
async def test_both_ops_401_is_still_auth_failed(_verify_on):
    """The criterion that matters most: a genuinely wrong password is still
    caught. Two independent auth-required ops refuse → auth_failed."""
    execs = _Executor({SYSTEMREADY_OP: _systemready_ok(),
                       AUTH_CHECK_OP: _result(401),
                       CORROBORATION_OP: _param_result(401)})
    rec = await _probe(_Catalog(), execs)
    assert rec.status == DeviceHealthStatus.AUTH_FAILED
    assert rec.consecutive_failures == 1
    assert _auth_calls(execs) == [AUTH_CHECK_OP, CORROBORATION_OP]
    # The message names what actually happened — both ops, not just one.
    assert AUTH_CHECK_OP in rec.last_error
    assert CORROBORATION_OP in rec.last_error
    assert rec.learned_probe is None  # a rejection teaches us nothing


@pytest.mark.asyncio
async def test_403_is_corroborated_too(_verify_on):
    """403 takes the same path — it was never single-op proof either."""
    execs = _Executor({SYSTEMREADY_OP: _systemready_ok(),
                       AUTH_CHECK_OP: _result(403),
                       CORROBORATION_OP: _param_ok()})
    rec = await _probe(_Catalog(), execs)
    assert rec.status == DeviceHealthStatus.ONLINE


@pytest.mark.asyncio
async def test_corroborator_transient_error_does_not_flap(_verify_on):
    """basicdeviceinfo 401 + the corroborating call blows up → unknown. The
    status must not move to auth_failed on a second-call hiccup."""
    execs = _Executor({SYSTEMREADY_OP: _systemready_ok(),
                       AUTH_CHECK_OP: _result(401),
                       CORROBORATION_OP: RuntimeError("boom")})
    rec = await _probe(_Catalog(), execs)
    assert rec.status == DeviceHealthStatus.ONLINE
    assert rec.learned_probe is None


@pytest.mark.asyncio
async def test_corroborator_non_auth_answer_does_not_flap(_verify_on):
    """A 500 from the corroborator proves nothing in either direction."""
    execs = _Executor({SYSTEMREADY_OP: _systemready_ok(),
                       AUTH_CHECK_OP: _result(401),
                       CORROBORATION_OP: _param_result(500)})
    rec = await _probe(_Catalog(), execs)
    assert rec.status == DeviceHealthStatus.ONLINE


@pytest.mark.asyncio
async def test_common_path_runs_exactly_one_auth_op(_verify_on):
    """No extra probe on the common path — a device whose basicdeviceinfo
    answers never touches the corroborator, and writes no marker."""
    execs = _Executor({SYSTEMREADY_OP: _systemready_ok(),
                       AUTH_CHECK_OP: _result(200, success=True),
                       CORROBORATION_OP: _param_ok()})
    rec = await _probe(_Catalog(), execs)
    assert rec.status == DeviceHealthStatus.ONLINE
    assert _auth_calls(execs) == [AUTH_CHECK_OP]
    assert rec.learned_probe is None


@pytest.mark.asyncio
async def test_marked_device_leads_with_param_cgi(_verify_on):
    """The no-extra-cost claim: once learned, a restricted device pays two
    calls per sweep (systemready + param.cgi), not three."""
    execs = _Executor({SYSTEMREADY_OP: _systemready_ok(),
                       AUTH_CHECK_OP: _result(401),
                       CORROBORATION_OP: _param_ok()})
    rec = await _probe(_Catalog(), execs, device_info=_MARKED)
    assert rec.status == DeviceHealthStatus.ONLINE
    assert _auth_calls(execs) == [CORROBORATION_OP]
    assert AUTH_CHECK_OP not in execs.calls
    assert rec.learned_probe is None  # already known — no registry churn


@pytest.mark.asyncio
async def test_marked_device_with_stale_password_still_auth_failed(_verify_on):
    """The marker selects probe ORDER, never a trust bypass: a marked device
    whose password later goes stale must still surface as auth_failed."""
    execs = _Executor({SYSTEMREADY_OP: _systemready_ok(),
                       AUTH_CHECK_OP: _result(401),
                       CORROBORATION_OP: _param_result(401)})
    rec = await _probe(_Catalog(), execs, device_info=_MARKED)
    assert rec.status == DeviceHealthStatus.AUTH_FAILED
    # Corroborated the other way round: param.cgi refused first, then
    # basicdeviceinfo was asked to confirm.
    assert _auth_calls(execs) == [CORROBORATION_OP, AUTH_CHECK_OP]


@pytest.mark.asyncio
async def test_marker_self_corrects(_verify_on):
    """A marked device whose param.cgi refuses but whose basicdeviceinfo
    authenticates re-learns the other way — the marker is not sticky-wrong."""
    execs = _Executor({SYSTEMREADY_OP: _systemready_ok(),
                       AUTH_CHECK_OP: _result(200, success=True),
                       CORROBORATION_OP: _param_result(401)})
    rec = await _probe(_Catalog(), execs, device_info=_MARKED)
    assert rec.status == DeviceHealthStatus.ONLINE
    assert rec.learned_probe == {"auth_check_op": AUTH_CHECK_OP}


@pytest.mark.asyncio
async def test_garbage_marker_is_ignored(_verify_on):
    """A corrupt device record must not redirect the auth check somewhere
    arbitrary — an unknown op id falls back to the default."""
    execs = _Executor({SYSTEMREADY_OP: _systemready_ok(),
                       AUTH_CHECK_OP: _result(200, success=True)})
    rec = await _probe(_Catalog(), execs, device_info={
        "host": "192.0.2.1", PROBE_MARKER_KEY: {"auth_check_op": "evil.cgi:pwn"},
    })
    assert rec.status == DeviceHealthStatus.ONLINE
    assert _auth_calls(execs) == [AUTH_CHECK_OP]


@pytest.mark.asyncio
async def test_corroborated_path_reports_no_facts(_verify_on):
    """param.cgi's body is a parameter dump, so no identity facts come back —
    and empty facts must stay falsy so the sweep's flush is skipped entirely
    rather than blanking a stored model/serial."""
    execs = _Executor({SYSTEMREADY_OP: _systemready_ok(),
                       AUTH_CHECK_OP: _result(401),
                       CORROBORATION_OP: _param_ok()})
    rec = await _probe(_Catalog(), execs)
    assert rec.status == DeviceHealthStatus.ONLINE
    assert not rec.observed_facts


@pytest.mark.asyncio
async def test_sweep_persists_marker_without_touching_stored_facts(tmp_path):
    """The learned marker rides the observed_facts seam into the registry —
    and an empty facts payload leaves an existing model name alone."""
    registry = MagicMock()
    registry.list_devices.return_value = [
        {"device_id": "p8815", "host": "192.0.2.1", "model": "AXIS P8815-2"},
    ]
    registry.get_credentials.return_value = {"username": "root", "password": "pw"}
    store = DeviceHealthStore(str(tmp_path / "admz.db"))
    monitor = HealthMonitor(registry=registry, catalog=MagicMock(),
                            executors={"vapix": MagicMock()}, store=store)

    async def fake_probe(*, device_id, **kwargs):
        return DeviceHealthRecord(
            device_id=device_id, status=DeviceHealthStatus.ONLINE,
            last_check=time.time(), last_seen_online=time.time(),
            observed_facts=None,  # the corroborated path yields none
            learned_probe={"auth_check_op": CORROBORATION_OP},
        )

    with patch("admz.fleet.health.probe_device", side_effect=fake_probe):
        await monitor.sweep_once()

    registry.update_device_info.assert_called_once()
    did, payload = registry.update_device_info.call_args.args
    assert did == "p8815"
    assert payload == {PROBE_MARKER_KEY: {"auth_check_op": CORROBORATION_OP}}
    assert "model" not in payload  # the stored model name is untouched


@pytest.mark.asyncio
async def test_sweep_does_not_rewrite_an_unchanged_marker(tmp_path):
    """Delta-only, like the fact refresh — a marked device causes no write."""
    registry = MagicMock()
    registry.list_devices.return_value = [
        {"device_id": "p8815", "host": "192.0.2.1",
         PROBE_MARKER_KEY: {"auth_check_op": CORROBORATION_OP}},
    ]
    registry.get_credentials.return_value = {"username": "root", "password": "pw"}
    store = DeviceHealthStore(str(tmp_path / "admz.db"))
    monitor = HealthMonitor(registry=registry, catalog=MagicMock(),
                            executors={"vapix": MagicMock()}, store=store)

    async def fake_probe(*, device_id, **kwargs):
        return DeviceHealthRecord(
            device_id=device_id, status=DeviceHealthStatus.ONLINE,
            last_check=time.time(), last_seen_online=time.time(),
            learned_probe={"auth_check_op": CORROBORATION_OP},
        )

    with patch("admz.fleet.health.probe_device", side_effect=fake_probe):
        await monitor.sweep_once()

    registry.update_device_info.assert_not_called()


# ---------------------------------------------------------------------------
# Onboarding (GH #149) — the step that SAVES a password.
#
# onboarding.py's fleet-pair path stores credentials only on a True verdict,
# so on a P8815-2 it could previously never save a *correct* fleet password.
# ---------------------------------------------------------------------------


def test_onboarding_saves_fleet_creds_when_only_param_cgi_authenticates(monkeypatch):
    from admz.onboarding import onboard_device_credentials

    saved = {}

    class _Reg:
        def get_device_info(self, did):
            return {"host": "192.0.2.1", "model": "AXIS P8815-2"}

        def get_credentials(self, did):
            raise KeyError("no account")

        def update_device_info(self, did, changed):
            saved.setdefault("info", {}).update(changed)

    async def _tcp_up(host, port, timeout):
        return 5

    async def _not_needsetup(*a, **k):
        return {"needsetup": False}

    def _store_creds(registry, device_id, username, password, purpose=""):
        saved["creds"] = (username, password)

    monkeypatch.delenv("ADMZ_DISABLE_ONBOARDING_PROBES", raising=False)
    monkeypatch.setattr("admz.fleet.health._tcp_probe", _tcp_up)
    monkeypatch.setattr("admz.fleet.systemready.read_systemready", _not_needsetup)
    monkeypatch.setattr("admz.provisioning.store_provisioned_creds", _store_creds)
    monkeypatch.setattr(
        "admz.fleet_settings.fleet_settings.get",
        lambda key, *a, **k: {"default_password": "fleet-pw",
                              "default_username": "root"}.get(key),
    )

    # ADR-0061 / #411: a credential that authenticates is now used to CREATE
    # ADMZ's own account rather than being stored itself, and that write is
    # gated. Run under the same approval the factory-default path uses, and
    # stand in for the account write so this test stays about #149's subject:
    # the corroboration path accepting the credential.
    from admz.approval_context import approved

    adopted = {}

    async def _adopt(*a, **k):
        adopted["entry"] = k.get("entry")
        adopted["marker_already_persisted"] = PROBE_MARKER_KEY in saved.get("info", {})
        return {"success": True, "status": "admz_account_created",
                "username": "admz", "device_id": k.get("device_id")}

    monkeypatch.setattr("admz.provisioning.adopt_with_admz_account", _adopt)

    execs = _Executor({AUTH_CHECK_OP: _result(401), CORROBORATION_OP: _param_ok()})
    with approved("register_discovered_device", "tok-test"):
        out = asyncio.run(onboard_device_credentials(
            device_id="p8815", registry=_Reg(), catalog=_Catalog(),
            executors={"vapix": execs},
        ))

    assert out["status"] == "admz_account_created"
    # The corroborated credential is what ADMZ used to get in...
    assert adopted["entry"] == {"username": "root", "password": "fleet-pw"}
    # ...and onboarding learned to lead with param.cgi too — persisted BEFORE
    # the account write, so the write reaches the device the way the probe
    # did (the A1210 had a working credential and no profile, and read
    # auth_failed while the credential demonstrably worked).
    assert saved["info"][PROBE_MARKER_KEY] == {"auth_check_op": CORROBORATION_OP}
    assert adopted["marker_already_persisted"] is True
    assert "password" not in out  # the standing secrecy rule


def test_onboarding_still_rejects_a_genuinely_wrong_fleet_password(monkeypatch):
    """Both ops refuse → no credentials saved. The #149 fix must not turn
    onboarding into something that stores passwords it never verified."""
    from admz.onboarding import onboard_device_credentials

    saved = {}

    class _Reg:
        def get_device_info(self, did):
            return {"host": "192.0.2.1"}

        def get_credentials(self, did):
            raise KeyError("no account")

        def update_device_info(self, did, changed):
            saved.setdefault("info", {}).update(changed)

    async def _tcp_up(host, port, timeout):
        return 5

    async def _not_needsetup(*a, **k):
        return {"needsetup": False}

    def _store_creds(*a, **k):
        saved["creds"] = True

    monkeypatch.delenv("ADMZ_DISABLE_ONBOARDING_PROBES", raising=False)
    monkeypatch.setattr("admz.fleet.health._tcp_probe", _tcp_up)
    monkeypatch.setattr("admz.fleet.systemready.read_systemready", _not_needsetup)
    monkeypatch.setattr("admz.provisioning.store_provisioned_creds", _store_creds)
    monkeypatch.setattr(
        "admz.fleet_settings.fleet_settings.get",
        lambda key, *a, **k: {"default_password": "wrong-pw",
                              "default_username": "root"}.get(key),
    )

    execs = _Executor({AUTH_CHECK_OP: _result(401),
                       CORROBORATION_OP: _param_result(401)})
    out = asyncio.run(onboard_device_credentials(
        device_id="cam", registry=_Reg(), catalog=_Catalog(),
        executors={"vapix": execs},
    ))

    assert out["status"] == "credentials_needed"
    assert "creds" not in saved


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
