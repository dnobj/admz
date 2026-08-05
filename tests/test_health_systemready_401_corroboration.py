"""GH #150: a systemready 401 is not proof the stored credentials are bad.

`probe_device` had two places where a 401 became a fleet-visible `auth_failed`.
#149 corroborated the second (the `basicdeviceinfo` credential check) after a
real AXIS P8815-2 disproved the single-op inference — per-op authorization
differences are real on Axis firmware. #300 fixed this issue's *other* half (the
`"401" in str(...)` substring). The first branch was still single-op:

    if status_code == 401 or _reports_401(...):
        return DeviceHealthRecord(status=AUTH_FAILED, ...)

This file covers acceptance criteria 2 and 3. Criterion 1 (an error containing
`401` with a non-401 status code is not `auth_failed`) is already met and tested
in `test_health_401_classification.py`; it is not re-litigated here.

**What is deliberately NOT claimed.** Whether `systemready` *can* 401 while
another op authenticates has never been observed on a real device — that is why
#150 was split out of #149. Nothing here asserts it happens. What is asserted is
that ADMZ no longer *concludes* the password is wrong from that one op, which is
a claim about ADMZ's reasoning, not about Axis firmware.

**The vacuity shape.** "a 401 does not produce auth_failed" is trivially green
if the probe never reaches the 401 branch at all — an executor that errors, a
catalog with no op, a device with no host all produce a non-`auth_failed`
record for reasons that have nothing to do with corroboration. So every negative
case below asserts the *positive* status it should have instead AND that the
corroborating op was actually called, and `test_both_ops_refusing_still_condemns`
pins that the verdict is still reachable.
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock

import pytest

from admz.fleet.health import (
    AUTH_CHECK_OP,
    CORROBORATION_OP,
    SYSTEMREADY_OP,
    DeviceHealthStatus,
    probe_device,
)


@pytest.fixture(autouse=True)
def _isolate_admz_home(monkeypatch):
    """No test here may touch the operator's real data directory.

    `probe_device` reads `health_verify_credentials` from fleet_settings, which
    resolves its DB under ADMZ_HOME at call time.
    """
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setenv("ADMZ_HOME", d)
        monkeypatch.setenv("ADMZ_DB_PATH", os.path.join(d, "admz.db"))
        yield d


# --- fixtures --------------------------------------------------------------


def _r(**kw):
    """A StepResult-shaped mock. Explicit about every field the probe reads, so
    no auto-created child mock can decide a branch (the #291 flake)."""
    base = dict(success=True, status_code=200, error=None, parsed_data={})
    base.update(kw)
    return MagicMock(**base)


REFUSED = dict(success=False, status_code=401, error="HTTP 401: Unauthorized")
AUTHENTICATED = dict(success=True, status_code=200,
                     parsed_data={"data": {"propertyList": {"ProdNbr": "P3245"}}})


def _probe_with(op_results, *, host="192.0.2.1"):
    """Drive `probe_device` with a per-op result map.

    Keyed by op id, so a test says what *each* op answered rather than relying
    on call order — which is what makes "the corroborating op was consulted"
    assertable rather than assumed.
    """
    seen = []

    def _get_operation(_family, op_id):
        if op_id not in op_results:
            return None
        op = MagicMock()
        op.to_executor_dict.return_value = {"id": op_id}
        return op

    catalog = MagicMock()
    catalog.get_operation.side_effect = _get_operation

    async def _execute(op_dict, *_a, **_k):
        op_id = op_dict["id"]
        seen.append(op_id)
        outcome = op_results[op_id]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    executor = MagicMock()
    executor.execute = _execute
    return catalog, executor, seen


@pytest.fixture(autouse=True)
def _no_real_sockets(monkeypatch):
    """`_tcp_probe` opens a real socket. Left unmocked these tests spent ~26s
    in connect timeouts against TEST-NET-1 and every fall-through read
    `unreachable` for that reason rather than the one under test — a false
    negative that looks exactly like a real failure. Default: the host answers.
    """
    async def _connects(*_a, **_k):
        return 5

    monkeypatch.setattr("admz.fleet.health._tcp_probe", _connects)


async def _probe(op_results, **kw):
    catalog, executor, seen = _probe_with(op_results, **kw)
    rec = await probe_device(
        device_id="cam-01",
        device_info={"host": kw.get("host", "192.0.2.1")},
        credentials={"username": "root", "password": "x"},
        catalog=catalog,
        executor=executor,
    )
    return rec, seen


# --- acceptance criterion 3: a corroborated 401 still condemns --------------


@pytest.mark.asyncio
async def test_both_ops_refusing_still_condemns():
    """FIRST, and the anti-vacuity anchor for everything below.

    If this stops passing, the negative cases prove nothing — they would be
    green for a probe that could never say `auth_failed` at all.
    """
    rec, seen = await _probe({
        SYSTEMREADY_OP: _r(**REFUSED),
        CORROBORATION_OP: _r(**REFUSED),
    })

    assert rec.status == DeviceHealthStatus.AUTH_FAILED
    assert rec.consecutive_failures == 1
    assert CORROBORATION_OP in seen, "condemned without consulting a second op"
    # The message must say what the verdict actually rests on — "HTTP 401 from
    # device" was the old single-op wording and is no longer accurate.
    assert SYSTEMREADY_OP in rec.last_error and CORROBORATION_OP in rec.last_error


# --- acceptance criterion 2: an uncorroborated 401 does not condemn ---------


@pytest.mark.asyncio
async def test_corroborator_authenticates_so_credentials_are_not_condemned():
    """The #150 defect. systemready 401s; an independent auth-required op
    answers an authenticated 2xx. The stored password is demonstrably fine."""
    rec, seen = await _probe({
        SYSTEMREADY_OP: _r(**REFUSED),
        CORROBORATION_OP: _r(**AUTHENTICATED),
    })

    assert rec.status != DeviceHealthStatus.AUTH_FAILED, (
        "one op's 401 still condemned the credentials")
    # ...and not merely "something other than auth_failed": the device answered
    # HTTP and authenticated, so it is up and this is an attention state.
    assert rec.status == DeviceHealthStatus.REACHABLE_NO_API
    assert rec.last_seen_online is not None, "it answered — reachability advances"
    assert rec.consecutive_failures == 0, "a settled state, not a failed probe"
    assert CORROBORATION_OP in seen


@pytest.mark.asyncio
async def test_the_not_condemned_error_message_says_credentials_look_valid():
    """An operator reading `REACHABLE_NO_API` + a bare "HTTP 401" would go and
    check the password — the exact wrong action this issue exists to prevent."""
    rec, _ = await _probe({
        SYSTEMREADY_OP: _r(**REFUSED),
        CORROBORATION_OP: _r(**AUTHENTICATED),
    })
    assert "credentials look valid" in rec.last_error
    assert CORROBORATION_OP in rec.last_error


@pytest.mark.asyncio
async def test_a_transient_corroborator_error_does_not_condemn():
    """The corroborating op blew up. That proves nothing in either direction,
    so the credentials keep the benefit of the doubt rather than flapping."""
    rec, seen = await _probe({
        SYSTEMREADY_OP: _r(**REFUSED),
        CORROBORATION_OP: RuntimeError("connection reset"),
    })

    assert rec.status != DeviceHealthStatus.AUTH_FAILED
    assert rec.status == DeviceHealthStatus.REACHABLE_NO_API
    assert "NOT condemned" in rec.last_error
    assert CORROBORATION_OP in seen


@pytest.mark.asyncio
async def test_an_inconclusive_corroborator_answer_does_not_condemn():
    """The corroborator answered, but not with an authenticated 2xx and not
    with a refusal — a 500, say. Says nothing about the password."""
    rec, _ = await _probe({
        SYSTEMREADY_OP: _r(**REFUSED),
        CORROBORATION_OP: _r(success=False, status_code=500, error="HTTP 500: boom"),
    })

    assert rec.status != DeviceHealthStatus.AUTH_FAILED
    assert rec.status == DeviceHealthStatus.REACHABLE_NO_API


@pytest.mark.asyncio
async def test_403_from_the_corroborator_also_condemns():
    """`_corroborate_rejection` treats 403 as a refusal too. Pinned so the
    corroborating branch is not narrowed to 401 by a later tidy-up."""
    rec, _ = await _probe({
        SYSTEMREADY_OP: _r(**REFUSED),
        CORROBORATION_OP: _r(success=False, status_code=403, error="HTTP 403"),
    })
    assert rec.status == DeviceHealthStatus.AUTH_FAILED


# --- the deliberate fallback: no corroborator in the catalog ---------------


@pytest.mark.asyncio
async def test_missing_corroborating_op_keeps_the_pre_149_verdict():
    """`_corroborate_rejection` returns False when the corroborating op is not
    in the catalog, on purpose: a genuinely stale password must not read as
    healthy merely because the second op is unavailable. Pinned here because it
    is the one path where #150 deliberately does NOT relax the verdict, and a
    future reader would otherwise reasonably assume it should.
    """
    rec, seen = await _probe({SYSTEMREADY_OP: _r(**REFUSED)})  # no CORROBORATION_OP

    assert rec.status == DeviceHealthStatus.AUTH_FAILED
    assert CORROBORATION_OP not in seen


# --- the ordering decision -------------------------------------------------


@pytest.mark.asyncio
async def test_a_401_carries_no_needsetup_signal_at_all():
    """Why #150's ordering concern cannot be fixed by reordering.

    `needsetup` is read out of systemready's own parsed body. A 401 has no
    body, so there is no needsetup signal to reach — moving the branch would
    evaluate `needsetup = False` against empty `parsed_data` and fall through
    to the same place. This test pins the *reason*: even with a body that would
    say needsetup=yes, a 401 result cannot produce NEEDS_SETUP, because the
    device never told us that on an authenticated-refusal response.
    """
    rec, _ = await _probe({
        SYSTEMREADY_OP: _r(success=False, status_code=401,
                           error="HTTP 401: Unauthorized",
                           parsed_data={"data": {"needsetup": "yes"}}),
        CORROBORATION_OP: _r(**AUTHENTICATED),
    })

    # Not NEEDS_SETUP — and, critically, not AUTH_FAILED either. The old code
    # returned AUTH_FAILED here, which is the misclassification that put a
    # device out of reach of the #70/#71 deferred-recovery triggers.
    assert rec.status == DeviceHealthStatus.REACHABLE_NO_API


@pytest.mark.asyncio
async def test_an_uncondemned_401_on_an_unreachable_host_is_unreachable(monkeypatch):
    """The other half of the fall-through: if the host does not accept a TCP
    connection either, it is UNREACHABLE, not an attention state. Pins that the
    `REACHABLE_NO_API` verdict above rests on actual reachability evidence
    rather than being a constant.
    """
    async def _refuses(*_a, **_k):
        return None

    monkeypatch.setattr("admz.fleet.health._tcp_probe", _refuses)

    rec, _ = await _probe({
        SYSTEMREADY_OP: _r(**REFUSED),
        CORROBORATION_OP: _r(**AUTHENTICATED),
    })

    assert rec.status == DeviceHealthStatus.UNREACHABLE
    assert rec.status != DeviceHealthStatus.AUTH_FAILED


@pytest.mark.asyncio
async def test_a_genuine_needsetup_200_is_untouched():
    """The path that actually produces NEEDS_SETUP still does. Without this,
    the test above passes for a probe that lost the classification entirely."""
    rec, seen = await _probe({
        SYSTEMREADY_OP: _r(parsed_data={"data": {
            "systemready": "yes", "needsetup": "yes",
            "uptime": 100, "bootid": "boot-abc"}}),
    })

    assert rec.status == DeviceHealthStatus.NEEDS_SETUP
    assert rec.uptime_seconds == 100
    assert CORROBORATION_OP not in seen, "a 200 must not trigger corroboration"


# --- no regression on the ordinary paths -----------------------------------


@pytest.mark.asyncio
async def test_a_healthy_device_never_pays_for_the_corroborating_call():
    """The extra op runs only on a path that already failed."""
    rec, seen = await _probe({
        SYSTEMREADY_OP: _r(parsed_data={"data": {
            "systemready": "yes", "needsetup": "no",
            "uptime": 42, "bootid": "b"}}),
        AUTH_CHECK_OP: _r(**AUTHENTICATED),
    })

    assert rec.status == DeviceHealthStatus.ONLINE
    assert seen.count(CORROBORATION_OP) == 0
