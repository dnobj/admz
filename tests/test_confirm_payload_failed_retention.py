"""GH #281: a failed write keeps the value that was requested — but not forever.

#266 stripped the four payload columns on completion. #270 put the *identifying*
information in the audit row first, so what was touched survives. What did not
survive is the **value requested** — fine for a successful write, since drift is
the source of truth (ADR-0056), but for a **failed** one there is no device
state to consult and the value is simply gone.

So the strip now waits for the outcome and fires only on success.

**Why the sweep is the substance, not a nicety.** `params_json` is written by
`json.dumps(params)` with no redaction, and `pwdgrp.cgi:update-user` is
`service-affecting` (so it gates) and takes a `pwd` param. Keeping failed
payloads *indefinitely* would therefore make `admz.db` a growing plaintext store
of rejected device passwords — one row per failed password change. The sweep in
`ConfirmStore._cleanup` is what makes the forensic window a window.

It is stated as an **invariant** — *no completed row keeps a payload past
`PAYLOAD_RETENTION_SECONDS`, for any reason* — rather than "a TTL on failures",
because two different things leave a payload behind:

1. a deliberately-retained failure, and
2. a **successful** write whose strip never ran because the process died between
   `complete_session` and `strip_payload`. #266 made that impossible by doing
   both in one statement; splitting them reintroduces it, and the same sweep
   closes it. `test_the_sweep_also_catches_a_successful_write_whose_strip_never_ran`
   is that case.

**The vacuity shape, and all three directions.** "we strip on success" is
trivially green for a store that strips everything, and "a failed payload
survives" is trivially green for a store that strips nothing. So each of the
three is pinned against the other two on the same fixture:

* a successful session is stripped **immediately**,
* a failed one **survives**,
* a failed one **older than the window** is stripped **by the sweep** — the one
  that would otherwise pass without any sweep existing at all.
"""

from __future__ import annotations

import json
import sqlite3
import time

import pytest

from admz.api.confirm_store import PAYLOAD_RETENTION_SECONDS, ConfirmStore

MARKER = "SYSLOG-MARKER-ZZ"
#: Shaped like the real hazard: a password on a gating operation.
PWD_MARKER = "Hunter2-NewDevicePassword-9f3a"


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    yield


@pytest.fixture
def store(tmp_path):
    return ConfirmStore(str(tmp_path / "confirm.db"))


def _mk(store, **kw):
    spec = dict(
        device_id="cam-01", operation_id="pwdgrp.cgi:update-user", family="vapix",
        params={"action": "update", "user": "root", "pwd": PWD_MARKER},
        risk_level="service-affecting", confirmation_level="url_only",
    )
    spec.update(kw)
    return store.create_session(**spec)


def _row(store, token):
    conn = sqlite3.connect(store._db_path)
    try:
        conn.row_factory = sqlite3.Row
        r = conn.execute(
            "SELECT * FROM confirm_sessions WHERE token=?", (token,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def _age_row(store, token, seconds):
    """Backdate a row's created_at, so the sweep can be exercised without
    sleeping for a day."""
    conn = sqlite3.connect(store._db_path)
    try:
        conn.execute("UPDATE confirm_sessions SET created_at=? WHERE token=?",
                     (time.time() - seconds, token))
        conn.commit()
    finally:
        conn.close()


# --- direction 1: a successful write is stripped immediately ---------------


def test_completion_alone_no_longer_strips(store):
    """The split itself. Completion happens BEFORE execution, so it cannot know
    the outcome — which is the whole reason the strip had to move."""
    s = _mk(store)
    assert store.complete_session(s.token) is True

    row = _row(store, s.token)
    assert PWD_MARKER in row["params_json"], (
        "completion stripped on its own; the outcome is not known yet")


def test_strip_payload_clears_all_four_columns(store):
    s = _mk(store, action_json=json.dumps({"a": MARKER}), plan_id="p1",
            plan_summary_json=json.dumps({"b": MARKER}),
            plan_steps_json=json.dumps([{"c": MARKER}]))
    store.complete_session(s.token)

    assert store.strip_payload(s.token) is True

    row = _row(store, s.token)
    assert row["params_json"] == "{}"
    assert row["action_json"] == ""
    assert row["plan_summary_json"] == ""
    assert row["plan_steps_json"] == ""
    assert PWD_MARKER not in json.dumps(row) and MARKER not in json.dumps(row)


def test_strip_payload_refuses_a_pending_row(store):
    """The #266 invariant that still matters. `plan_steps_json` is the
    cross-process transport — the approving uvicorn process reconstructs the
    plan from this row — so stripping before completion breaks execution
    outright. #266 got this from the atomic UPDATE; the split has to state it."""
    s = _mk(store, plan_id="p1",
            plan_steps_json=json.dumps([{"op": "x", "params": {"k": MARKER}}]))

    assert store.strip_payload(s.token) is False, "it stripped a PENDING row"
    assert MARKER in json.dumps(_row(store, s.token))


def test_the_receipt_survives_the_strip(store):
    """FIRST-class control: if the row were deleted, every 'no payload'
    assertion here would pass for the wrong reason."""
    s = _mk(store)
    store.complete_session(s.token, confirmed_by="AXIS\\dnich")
    store.strip_payload(s.token)

    row = _row(store, s.token)
    assert row is not None, "the receipt row was deleted, not stripped"
    assert row["status"] == "completed"
    assert row["confirmed_by"] == "AXIS\\dnich"
    assert row["operation_id"] == "pwdgrp.cgi:update-user"


# --- direction 2: a failed write keeps its payload -------------------------


def test_a_failed_session_keeps_its_payload(store):
    """The point of #281. Nothing calls strip_payload, so the requested value
    is still recoverable — there is no device state to consult for a write that
    did not land."""
    s = _mk(store)
    store.complete_session(s.token)
    # (no strip_payload — the outcome was a failure)

    row = _row(store, s.token)
    assert PWD_MARKER in row["params_json"], (
        "a failed write lost the value that was requested")


def test_the_sweep_leaves_a_recent_failure_alone(store):
    """The forensic window has to actually be open, or #281 delivers nothing."""
    s = _mk(store)
    store.complete_session(s.token)

    store._cleanup()

    assert PWD_MARKER in _row(store, s.token)["params_json"], (
        "the sweep stripped a failure inside the retention window")


# --- direction 3: the sweep closes the window ------------------------------


def test_the_sweep_strips_a_failure_older_than_the_window(store):
    """THE assertion that would otherwise be trivially green.

    Without a sweep, "a failed payload survives" passes forever — which is
    precisely the indefinite plaintext-credential retention this must not
    create.
    """
    s = _mk(store)
    store.complete_session(s.token)
    _age_row(store, s.token, PAYLOAD_RETENTION_SECONDS + 60)

    # Control: still present before the sweep, or the assertion below is empty.
    assert PWD_MARKER in _row(store, s.token)["params_json"]

    store._cleanup()

    row = _row(store, s.token)
    assert row is not None, "the sweep DELETED the receipt; it must only strip"
    assert row["params_json"] == "{}"
    assert PWD_MARKER not in json.dumps(row), (
        "a rejected device password survived the retention window")


def test_the_sweep_also_catches_a_successful_write_whose_strip_never_ran(store):
    """The regression the split introduces, closed by the same mechanism.

    #266 stripped in the same statement as the status flip, so a successful
    write could not keep its payload. Splitting them means a process death
    between `complete_session` and `strip_payload` leaves one behind — and
    `_cleanup` never deletes completed rows, so it would be forever.

    One sweep, one invariant: no completed row keeps a payload past the window,
    for any reason.
    """
    s = _mk(store)
    store.complete_session(s.token)      # ...and then the process dies here
    _age_row(store, s.token, PAYLOAD_RETENTION_SECONDS + 60)

    store._cleanup()

    assert PWD_MARKER not in json.dumps(_row(store, s.token))


def test_the_sweep_never_deletes_a_completed_row(store):
    """It strips; it does not reap. The row is the approval receipt (#266)."""
    s = _mk(store)
    store.complete_session(s.token, confirmed_by="AXIS\\dnich")
    _age_row(store, s.token, PAYLOAD_RETENTION_SECONDS * 10)

    store._cleanup()

    row = _row(store, s.token)
    assert row is not None and row["confirmed_by"] == "AXIS\\dnich"


def test_the_sweep_is_idempotent(store):
    s = _mk(store)
    store.complete_session(s.token)
    _age_row(store, s.token, PAYLOAD_RETENTION_SECONDS + 60)

    store._cleanup()
    once = _row(store, s.token)
    store._cleanup()
    assert _row(store, s.token) == once


# --- the states that were never in scope -----------------------------------


def test_a_denied_session_is_deleted_wholesale_not_merely_stripped(store):
    """Denial carries no forensic value — nothing was attempted — and the
    existing `status != 'completed'` predicate already removes the whole row,
    which is stronger than stripping. Pinned so a later change to that
    predicate does not silently turn denials into retained payloads.
    """
    s = _mk(store, ttl=1)
    assert store.deny_session(s.token) is True
    _age_row(store, s.token, 3600)

    store._cleanup()

    assert _row(store, s.token) is None, "a denied session was retained"


def test_an_expired_session_is_deleted_wholesale(store):
    """Same predicate, same reasoning: never acted on, nothing to keep."""
    s = _mk(store, ttl=1)
    _age_row(store, s.token, 3600)

    store._cleanup()

    assert _row(store, s.token) is None


# --- both doors, both outcomes ---------------------------------------------
#
# Everything above tests ConfirmStore. But #281's actual behaviour change is at
# the CALL SITES — "strip only if the outcome succeeded" — and there are exactly
# two callers of `complete_session`:
#
#   * `routes/confirm.py::_approve_session`  — the web form and the in-chat twin
#   * `operations.py::consume_confirmation`  — the MCP / JSON-REST path
#
# A mutation check found this: making either door strip *unconditionally*, or
# never strip, left the store tests entirely green. A door that never strips
# keeps every successful payload for the full retention window; a door that
# strips unconditionally silently undoes #281 for its callers. Neither is
# visible from the store's side, so both doors are pinned here in both
# directions.


def _step_result(success: bool):
    from admz.executor.models import StepResult
    return StepResult(operation_id="pwdgrp.cgi:update-user", device_id="cam-01",
                      success=success, status_code=200 if success else 500,
                      error=None if success else "device refused")


def _run(coro):
    import asyncio
    return asyncio.run(coro)


def _consume(store, token, *, success, monkeypatch):
    """Drive the MCP/REST door for real, with only the device call faked."""
    import admz.operations as ops

    async def _tail(**kw):
        # The payload must still be readable AT EXECUTION TIME, whatever the
        # outcome — the strip happens after this returns, never before.
        assert kw["params"]["pwd"] == PWD_MARKER
        return _step_result(success)

    monkeypatch.setattr(ops, "run_execution_tail", _tail)
    return _run(ops.consume_confirmation(
        token, catalog=None, registry=None, executors={}, store=store,
        confirmed_by="mcp", enforce_url_flow_block=False))


def test_mcp_door_strips_a_successful_write(store, monkeypatch):
    s = _mk(store)
    out = _consume(store, s.token, success=True, monkeypatch=monkeypatch)

    assert out["success"] is True
    assert PWD_MARKER not in json.dumps(_row(store, s.token)), (
        "a successful write kept its payload at the MCP door")


def test_mcp_door_keeps_a_failed_writes_payload(store, monkeypatch):
    """The #281 case at this door. Same fixture as the test above — so neither
    can pass by stripping everything or stripping nothing."""
    s = _mk(store)
    out = _consume(store, s.token, success=False, monkeypatch=monkeypatch)

    assert out["success"] is False
    assert PWD_MARKER in _row(store, s.token)["params_json"], (
        "a failed write lost the requested value at the MCP door")


def _approve(store, token, *, success, monkeypatch):
    """Drive the web door for real, with only execution and auth faked."""
    from admz.api.routes import confirm as C
    import admz.auth as auth
    import admz.operations as ops

    monkeypatch.setattr(C, "confirm_store", store)

    async def _exec(session, **kw):
        assert session.params["pwd"] == PWD_MARKER      # readable at exec time
        return {"success": success, "error": None if success else "refused"}

    monkeypatch.setattr(ops, "execute_approved_session", _exec)
    monkeypatch.setattr(C.rate_limiter, "check", lambda *a, **k: True)
    monkeypatch.setattr(C, "_is_locked", lambda t: False)
    monkeypatch.setattr(C, "_note_resolution_to_chat", lambda *a, **k: None)

    async def _cur(request):
        from types import SimpleNamespace as NS
        return NS(name="AXIS\\dnich", groups=["Administrators"],
                  is_anonymous=False, auth_source="windows-local")

    monkeypatch.setattr(auth, "get_current_principal", _cur)

    from types import SimpleNamespace as NS
    ctx = NS(catalog=None, registry=NS(), executors={}, plan_engine=None,
             git_repo=None)
    return _run(C._approve_session(NS(client=None, headers={}), token, None,
                                   ctx, "web"))


def test_web_door_strips_a_successful_write(store, monkeypatch):
    s = _mk(store)
    _approve(store, s.token, success=True, monkeypatch=monkeypatch)

    assert PWD_MARKER not in json.dumps(_row(store, s.token)), (
        "a successful write kept its payload at the web door")


def test_web_door_keeps_a_failed_writes_payload(store, monkeypatch):
    """The #281 case at the web door — the one an operator actually watches
    fail, and then wants to know what was submitted."""
    s = _mk(store)
    _approve(store, s.token, success=False, monkeypatch=monkeypatch)

    row = _row(store, s.token)
    assert row["status"] == "completed", "the session was not completed"
    assert PWD_MARKER in row["params_json"], (
        "a failed write lost the requested value at the web door")


# --- the window itself -----------------------------------------------------


def test_the_retention_window_is_a_day():
    """A number in one place, asserted so changing it is a decision (#303)."""
    assert PAYLOAD_RETENTION_SECONDS == 24 * 60 * 60
