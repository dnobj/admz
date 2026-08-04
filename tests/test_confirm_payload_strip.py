"""A completed confirm session keeps its receipt and loses its payload (#266).

`_cleanup` deletes `WHERE status != 'completed'`, so approved sessions are never
reaped — every gated action's arguments (device parameters, rule definitions,
webhook URLs, whole restore plans) persisted in `admz.db` indefinitely, in the
same file as the device registry, with nothing redacting them. The row now
survives as a **receipt** and the payload is cleared on the transition.

Two properties this file exists to pin, because both are load-bearing and neither
is obvious from reading `complete_session` alone:

* **The strip is safe only because of caller ordering.** Every payload consumer
  works from the `ConfirmSession` fetched *before* completion
  (`routes/confirm.py`: get_session -> complete_session ->
  execute_approved_session). `complete_session` touches only the database. A
  refactor that re-fetched after completion would silently execute against an
  empty payload — `test_execution_still_sees_the_payload...` fails loudly if so.
* **It must not fire early.** `plan_steps_json` is the cross-process transport:
  the approving uvicorn process may not be the MCP subprocess that built the
  plan, and reconstructs it from that column.

Vacuity note: "no payload in completed rows" is trivially green when there are no
completed rows, or when the payload was empty to begin with. Every test below
plants a distinctive marker and asserts the receipt fields survive, so an empty
row or a deleted row cannot pass.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from types import SimpleNamespace as NS

import pytest

MARKER = "ZZ-PAYLOAD-MARKER-ZZ"
_PAYLOAD_COLS = ("params_json", "action_json", "plan_summary_json", "plan_steps_json")


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture
def store(tmp_path):
    from admz.api.confirm_store import ConfirmStore
    return ConfirmStore(str(tmp_path / "confirm.db"))


def _mk(store, **kw):
    base = dict(device_id="cam-01", operation_id="param.cgi:update", family="vapix",
                params={}, risk_level="dangerous", confirmation_level="url_only",
                danger_description="does a dangerous thing", ttl=300.0)
    base.update(kw)
    return store.create_session(**base)


def _row(store, token):
    conn = sqlite3.connect(store._db_path)
    try:
        cur = conn.execute(
            "SELECT token, status, confirmed_by, operation_id, device_id, "
            "created_at, ttl, params_json, action_json, plan_summary_json, "
            "plan_steps_json FROM confirm_sessions WHERE token=?", (token,))
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else None
    finally:
        conn.close()


class TestTheReceiptSurvives:
    def test_a_completed_row_exists_with_its_receipt_intact(self, store):
        """FIRST: if the row were deleted, every 'no payload' assertion below
        would pass for the wrong reason."""
        s = _mk(store, params={"root.RemoteSyslog.Server": MARKER})
        assert store.complete_session(s.token, confirmed_by="AXIS\\dnich") is True

        row = _row(store, s.token)
        assert row is not None, "the receipt row was deleted, not stripped"
        assert row["token"] == s.token
        assert row["status"] == "completed"
        assert row["confirmed_by"] == "AXIS\\dnich"
        assert row["operation_id"] == "param.cgi:update"
        assert row["device_id"] == "cam-01"
        assert row["created_at"] > 0 and row["ttl"] == 300.0

    def test_all_four_payload_columns_are_cleared(self, store):
        s = _mk(store,
                params={"root.RemoteSyslog.Server": MARKER},
                action_json=json.dumps({"action": "create_task", "url": MARKER}),
                plan_id="p1",
                plan_summary_json=json.dumps({"step_count": 1, "note": MARKER}),
                plan_steps_json=json.dumps([{"op": "x", "params": {"k": MARKER}}]))
        store.complete_session(s.token)

        row = _row(store, s.token)
        assert row["params_json"] == "{}"          # still valid JSON
        assert row["action_json"] == ""
        assert row["plan_summary_json"] == ""
        assert row["plan_steps_json"] == ""

    def test_the_marker_is_gone_from_the_whole_row(self, store):
        """The blunt check: nothing anywhere in the persisted row."""
        s = _mk(store, params={"a": MARKER},
                action_json=json.dumps({"action": "x", "b": MARKER}),
                plan_id="p1", plan_summary_json=json.dumps({"c": MARKER}),
                plan_steps_json=json.dumps([{"d": MARKER}]))
        # Present before — otherwise this test proves nothing.
        assert MARKER in json.dumps(_row(store, s.token))
        store.complete_session(s.token)
        assert MARKER not in json.dumps(_row(store, s.token))

    def test_the_stripped_row_still_reads_back_cleanly(self, store):
        """Accessors must not raise on emptied columns."""
        s = _mk(store, params={"a": MARKER},
                action_json=json.dumps({"action": "x"}), plan_id="p1")
        store.complete_session(s.token)
        got = store.get_session(s.token)
        assert got.params == {} and got.action == {} and got.plan_summary == {}
        assert got.is_plan is True                 # plan_id is NOT cleared


class TestItCannotFireEarly:
    def test_a_pending_session_keeps_its_payload(self, store):
        """`plan_steps_json` is the cross-process transport — the approving
        process reconstructs the plan from it. Stripping before approval would
        break execution outright."""
        s = _mk(store, plan_id="p1",
                plan_steps_json=json.dumps([{"op": "param.cgi:update"}]))
        _mk(store, device_id="cam-02")             # another create → runs _cleanup
        store.get_session(s.token)                 # a read must not strip either

        row = _row(store, s.token)
        assert row["status"] == "pending"
        assert json.loads(row["plan_steps_json"]) == [{"op": "param.cgi:update"}]

    def test_a_second_completion_does_not_report_success(self, store):
        """The `status='pending'` guard is what makes the strip fire exactly
        once, on the transition."""
        s = _mk(store, params={"a": MARKER})
        assert store.complete_session(s.token) is True
        assert store.complete_session(s.token) is False


class TestExistingRetentionIsUnchanged:
    def test_abandoned_sessions_are_still_reaped(self, store):
        """The behaviour that already worked must not regress."""
        keep = _mk(store, params={"a": MARKER})
        drop = _mk(store, device_id="cam-02", params={"b": MARKER})
        store.complete_session(keep.token)

        conn = sqlite3.connect(store._db_path)
        conn.execute("UPDATE confirm_sessions SET created_at = created_at - 100000")
        conn.commit()
        conn.close()
        store._cleanup()

        assert _row(store, drop.token) is None, "abandoned row survived cleanup"
        assert _row(store, keep.token) is not None, "the receipt was reaped"


# ── the ordering the strip depends on ────────────────────────────────────────
class TestCallerOrderingIsPinned:
    def test_execution_still_sees_the_payload_after_the_row_is_stripped(
            self, monkeypatch, tmp_path):
        """THE load-bearing property. `_approve_session` fetches the session,
        completes it (which strips the DB row), then executes from the object it
        already holds. If anyone refactors it to re-fetch after completion, the
        executor gets an empty payload and this goes red.
        """
        from admz.api.confirm_store import ConfirmStore
        from admz.api.routes import confirm as C

        real = ConfirmStore(str(tmp_path / "c.db"))
        monkeypatch.setattr(C, "confirm_store", real)
        s = real.create_session(
            device_id="cam-01", operation_id="action:create_task", family="admz",
            params={}, risk_level="dangerous", confirmation_level="url_only",
            danger_description="d",
            action_json=json.dumps({"action": "create_task", "url": MARKER}))

        seen = {}

        async def _exec(session, **kw):
            # What the executor actually receives, at execution time.
            seen["action"] = dict(session.action)
            seen["row_at_exec"] = _row(real, s.token)
            return {"success": True}

        import admz.operations as ops
        monkeypatch.setattr(ops, "execute_approved_session", _exec)
        monkeypatch.setattr(C.rate_limiter, "check", lambda *a, **k: True)
        monkeypatch.setattr(C, "_is_locked", lambda t: False)
        monkeypatch.setattr(C, "_note_resolution_to_chat", lambda *a, **k: None)

        import admz.auth as auth

        async def _cur(request):
            return NS(name="AXIS\\dnich", groups=["Administrators"],
                      is_anonymous=False, auth_source="windows-local")
        monkeypatch.setattr(auth, "get_current_principal", _cur)

        ctx = NS(catalog=None, registry=NS(), executors={}, plan_engine=None,
                 git_repo=None)
        result = _run(C._approve_session(NS(client=None, headers={}), s.token,
                                         None, ctx, "web"))

        assert result.status == "completed"
        # 1. Execution saw the real payload...
        assert seen["action"]["url"] == MARKER, (
            "the executor got an empty payload — the session was re-fetched "
            "AFTER completion, which the strip makes unsafe")
        # 2. ...while the persisted row was already stripped by then.
        assert seen["row_at_exec"]["action_json"] == ""
        # 3. And it stays stripped afterwards.
        assert MARKER not in json.dumps(_row(real, s.token))

    def test_the_approve_audit_row_still_describes_the_work(
            self, monkeypatch, tmp_path):
        """#270's key-only record is built from the same in-memory session, so
        the strip must not blank it. Together they are the whole receipt."""
        from admz.api.confirm_store import ConfirmStore
        from admz.api.routes import confirm as C

        real = ConfirmStore(str(tmp_path / "c2.db"))
        monkeypatch.setattr(C, "confirm_store", real)
        s = real.create_session(
            device_id="cam-01", operation_id="param.cgi:update", family="vapix",
            params={"root.RemoteSyslog.Server": MARKER}, risk_level="dangerous",
            confirmation_level="url_only", danger_description="d")

        async def _exec(*a, **k):
            return {"success": True}
        import admz.operations as ops
        monkeypatch.setattr(ops, "execute_approved_session", _exec)
        monkeypatch.setattr(C.rate_limiter, "check", lambda *a, **k: True)
        monkeypatch.setattr(C, "_is_locked", lambda t: False)
        monkeypatch.setattr(C, "_note_resolution_to_chat", lambda *a, **k: None)

        import admz.auth as auth

        async def _cur(request):
            return NS(name="AXIS\\dnich", groups=["Administrators"],
                      is_anonymous=False, auth_source="windows-local")
        monkeypatch.setattr(auth, "get_current_principal", _cur)

        ctx = NS(catalog=None, registry=NS(), executors={}, plan_engine=None,
                 git_repo=None)
        _run(C._approve_session(NS(client=None, headers={}), s.token, None,
                                ctx, "web"))

        from admz.audit import AuditLog
        row = AuditLog().list_recent(action="confirm.approve")[0]
        assert row.details["param_keys"] == ["root.RemoteSyslog.Server"]
        assert row.details["confirm_token"] == s.token      # joins to the receipt
        assert MARKER not in json.dumps(row.details)        # ...key-only, still
