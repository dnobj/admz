"""A 401 must be *reported*, not merely *mentioned* (#291, guarding #149/#154).

`probe_device` used to decide auth-failure with a bare substring test:

    if status_code == 401 or "401" in str(getattr(result, "error", "")):

`error` carries **up to 500 characters of the device's own response body** for
any status >= 400 (`executor/vapix.py:1123`), so any body containing ``401``
anywhere — a request id, a byte count, an unrelated error number — classified
the device AUTH_FAILED. On a factory-defaulted unit that is exactly the
#149/#154 misclassification the health path exists to prevent: *needs setup*
read as *your credentials are wrong*, the P8815 mistake.

The loose form also had no true-positive value: every genuine 401 from the
VAPIX executor sets ``status_code=401`` (`vapix.py:1105-1114`), which the first
clause already catches. So it could only ever fire falsely.

**How this connects to the flake.** `test_needsetup_marks_needs_setup_not_auth_failed`
never set ``error`` on its mock, so ``str()`` of the auto-created child mock was
``<MagicMock name='mock.error' id='2868317770944'>`` — and roughly 1 address in
110 contains ``401``. Measured on the real code path: **182/20000 = 0.91%**, and
running the real test alone 3000 times gave 12 failures. That is why "20/20
alone" proved nothing (a 92% chance of showing all-passes) and why "ubuntu-only"
was coincidence rather than signal — with two failures total, both landing on
one leg is a coin flip.

**Vacuity note.** "a 401 is not detected" is trivially green if nothing is ever
detected, so `TestARealAuthFailureIsStillCaught` runs first and pins every shape
that must still classify AUTH_FAILED. The point of this change is to make the
signal *narrower*, not absent.
"""

from __future__ import annotations

import asyncio
import re
from unittest.mock import AsyncMock, MagicMock

import pytest

from admz.fleet.health import DeviceHealthStatus, probe_device

NEEDSETUP = {"systemready": "yes", "needsetup": "yes",
             "uptime": 100, "bootid": "boot-abc"}


def _catalog():
    catalog, op = MagicMock(), MagicMock()
    op.to_executor_dict.return_value = {"id": "systemready.cgi:systemReady"}
    catalog.get_operation.return_value = op
    return catalog


def _probe(result, corroborator=None):
    """Probe with ``result`` from every op.

    ``corroborator`` overrides what the *second* op answers. Since #150 a
    systemready 401 is only AUTH_FAILED once an independent auth-required op
    has also refused, so a test that wants the auth verdict must say what that
    second op said. Passing it explicitly rather than defaulting it keeps the
    two-op requirement visible at the call site — a default would hide exactly
    the thing #150 changed.
    """
    executor = MagicMock()
    if corroborator is None:
        executor.execute = AsyncMock(return_value=result)
    else:
        calls = {"n": 0}

        async def _execute(*_a, **_k):
            calls["n"] += 1
            return result if calls["n"] == 1 else corroborator

        executor.execute = _execute
    return asyncio.run(probe_device(
        device_id="cam-01", device_info={"host": "192.0.2.1"},
        credentials={"username": "root", "password": "x"},
        catalog=_catalog(), executor=executor))


#: What an independent auth-required op looks like when it also refuses.
REFUSED = dict(status_code=401, success=False, error="HTTP 401: Unauthorized")


def _result(**kw):
    base = dict(success=True, status_code=200, error=None, parsed_data=NEEDSETUP)
    base.update(kw)
    return MagicMock(**base)


# ── what must STILL be classified as an auth failure ─────────────────────────
class TestARealAuthFailureIsStillCaught:
    def test_a_401_status_code_is_auth_failed(self):
        """FIRST. Narrowing the error match must not touch the primary signal —
        and this is the path every genuine VAPIX 401 actually takes."""
        rec = _probe(_result(status_code=401, success=False,
                             error="Authentication failed (401). Check credentials."))
        assert rec.status == DeviceHealthStatus.AUTH_FAILED

    def test_the_executors_own_401_message_is_recognised(self):
        """`vapix.py:1112`'s exact string, with the status_code deliberately
        withheld so only the error branch can catch it. This is the
        belt-and-braces the substring match was there to provide, preserved."""
        rec = _probe(_result(status_code=None, success=False,
                             error="Authentication failed (401). Check credentials."),
                     corroborator=_result(**REFUSED))
        assert rec.status == DeviceHealthStatus.AUTH_FAILED

    def test_a_generic_http_401_envelope_is_recognised(self):
        """`vapix.py:1123`'s shape for a 401 that reached the generic branch:
        `f"HTTP {status_code}: {body[:500]}"`."""
        rec = _probe(_result(status_code=None, success=False,
                             error="HTTP 401: Unauthorized\n<html>...</html>"),
                     corroborator=_result(**REFUSED))
        assert rec.status == DeviceHealthStatus.AUTH_FAILED


# ── what must NOT be ─────────────────────────────────────────────────────────
class TestAMentionOf401IsNotAnAuthFailure:
    def test_a_factory_defaulted_device_whose_body_contains_401(self):
        """THE production defect, and the #149/#154 boundary. The device is
        reachable and factory-defaulted; its body merely happens to contain the
        digits. Before this it read as 'your credentials are wrong'."""
        rec = _probe(_result(
            error="HTTP 500: {\"error\":\"internal\",\"request_id\":\"8a401f2\"}"))
        assert rec.status == DeviceHealthStatus.NEEDS_SETUP, (
            "a needs-setup device was reported as auth_failed because an "
            "unrelated response body contained '401'")

    @pytest.mark.parametrize("body", [
        "HTTP 500: Error 1401: internal failure",
        "HTTP 404: not found (trace 40123)",
        "HTTP 503: retry after 4010ms",
        "HTTP 500: serial B8A44F401122",
        "Connection failed: [Errno 401] made-up",
    ])
    def test_incidental_digits_anywhere_in_the_body(self, body):
        """`error` carries 500 characters of device text; every one of these is
        a plausible thing to find in it."""
        assert _probe(_result(error=body)).status == DeviceHealthStatus.NEEDS_SETUP

    def test_the_flake_itself_cannot_recur(self):
        """THE regression test for #291, made deterministic by controlling the
        one variable that was random.

        This is the exact value the flaky test produced ~1 run in 110 — an
        unfaithful mock's repr with an unlucky address. Anchoring makes it
        unmatchable whatever the address, so the flake cannot come back even if
        someone writes another mock without `error`."""
        unlucky = "<MagicMock name='mock.error' id='140234014012345'>"
        assert "401" in unlucky, "the reproduction lost the thing it reproduces"
        rec = _probe(_result(error=unlucky))
        assert rec.status == DeviceHealthStatus.NEEDS_SETUP

    def test_an_absent_error_is_not_a_401(self):
        for empty in (None, "", 0):
            assert _probe(_result(error=empty)).status == \
                DeviceHealthStatus.NEEDS_SETUP


# ── the predicate on its own ─────────────────────────────────────────────────
class TestReports401:
    def test_it_anchors_rather_than_searching(self):
        from admz.fleet.health import _reports_401
        assert _reports_401("HTTP 401: Unauthorized")
        assert _reports_401("Authentication failed (401). Check credentials.")
        assert not _reports_401("HTTP 500: body mentioning 401 midway")
        assert not _reports_401("prefixed HTTP 401: not at the start")
        assert not _reports_401(None) and not _reports_401("")

    def test_it_does_not_match_a_longer_status_beginning_401(self):
        """`\\b` earns its keep: there is no HTTP 4011, but the anchor should
        not be the only thing standing between us and one."""
        from admz.fleet.health import _reports_401
        assert not _reports_401("HTTP 4011: invented")


# ── the mock-faithfulness lint ───────────────────────────────────────────────
def test_no_probe_result_mock_omits_error():
    """What actually caused #291: a mock that did not match the type it stands
    in for. `StepResult.error` is `Optional[str]` and always present
    (`executor/models.py:38`); an unset attribute on a MagicMock is a child mock
    whose `str()` embeds its memory address, which `probe_device` then reads.

    Anchoring the match already makes that harmless, so this is defence in
    depth — but it is the check that would have caught the flake at review time
    instead of after two red CI runs.
    """
    import ast
    import pathlib

    bad = []
    for path in sorted(pathlib.Path("tests").glob("test_fleet_health*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and getattr(node.func, "id", "") == "MagicMock"):
                continue
            kw = {k.arg for k in node.keywords}
            # Only results — identified by carrying the StepResult-ish fields
            # probe_device reads. A bare MagicMock() is a catalog/executor stub.
            if ("status_code" in kw or "parsed_data" in kw) and "error" not in kw:
                bad.append(f"{path}:{node.lineno}")
    assert not bad, (
        "MagicMock stands in for a StepResult but leaves `error` unset, so "
        "str(result.error) is '<MagicMock ... id=ADDRESS>' and any code "
        "reading that field sees a random string (#291):\n  "
        + "\n  ".join(bad))
