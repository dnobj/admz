"""Approving a gated session records WHAT was approved — keys, never values (#270).

MCP tool calls are audited with their arguments (`server.py`: `_sanitize_tool_args`
-> `redact_structure`). Gated sessions created from the **web API** never pass
through an MCP tool call — roughly 13 call sites across 8 route modules
(`/catalog/execute`, `/plans/{id}/execute`, `/snapshot/revert`, the
`gate_task_write` and `gate_demo_write` routes, ...) — so nothing recorded what
they asked for. `confirm.approve` carried identifiers only.

It now also carries a **value-free** description. Values are deliberately absent:
`redact_structure` masks by key *name*, so `root.RemoteSyslog.Server` and a
webhook `upload_url` would pass straight into an audit log that is **never
pruned** (no DELETE in `audit.py`), while the confirm row mirroring them is about
to be stripped (#266). That would be strictly worse than the leak being fixed.

Vacuity note: "no values in the row" is trivially green if no row is written or
the payload was empty. `test_a_web_origin_approval_now_produces_a_record` and the
key assertions run first and pin that a row exists with real content; the
no-values test plants a distinctive marker so an empty payload cannot pass.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace as NS

import pytest

MARKER = "ZZ-DISTINCTIVE-VALUE-ZZ"


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _session(**kw):
    """A ConfirmSession-shaped stub. Uses the real accessors' semantics:
    `is_action` iff action_json, `is_plan` iff plan_id."""
    action_json = kw.pop("action_json", "")
    plan_summary_json = kw.pop("plan_summary_json", "")
    params_json = kw.pop("params_json", "{}")
    base = dict(token="tok-abc123", device_id="cam-01",
                operation_id="param.cgi:update", plan_id="",
                risk_level="service-affecting", confirmation_level="url_only",
                confirmed_by="",
                # #334 — _approve_session reads this before it reads
                # anything else on the session; the stub must carry it like
                # every other real accessor above, or it fails before the
                # behavior this file actually tests is even reached.
                secret_fields=[])
    base.update(kw)
    s = NS(**base)
    s.action_json = action_json
    s.params = json.loads(params_json) if params_json else {}
    s.action = json.loads(action_json) if action_json else {}
    s.plan_summary = json.loads(plan_summary_json) if plan_summary_json else {}
    s.is_action = bool(action_json)
    s.is_plan = bool(base["plan_id"])
    return s


def _fields(session):
    from admz.api.routes.confirm import _approved_work_fields
    return _approved_work_fields(session)


# ── the record exists, and has real content ──────────────────────────────────
class TestOperationSessions:
    """`/catalog/execute` and `/api/acs/action` — payload lands in params_json."""

    def test_a_web_origin_approval_now_produces_a_record(self):
        """FIRST: the thing that does not happen today. If this is empty, every
        'no values' assertion below is vacuous."""
        f = _fields(_session(params_json=json.dumps(
            {"root.RemoteSyslog.Server": MARKER, "root.Network.HTTPS.Enabled": "yes"})))
        assert f["param_keys"] == ["root.Network.HTTPS.Enabled", "root.RemoteSyslog.Server"]
        assert f["operation_id"] == "param.cgi:update"
        assert f["device_id"] == "cam-01"

    def test_it_carries_no_values(self):
        f = _fields(_session(params_json=json.dumps(
            {"root.RemoteSyslog.Server": MARKER})))
        assert MARKER not in json.dumps(f)

    def test_the_token_joins_the_row_to_the_surviving_receipt(self):
        """#266 strips the payload but keeps the row; the token is what still
        ties the audit entry to that receipt."""
        assert _fields(_session())["confirm_token"] == "tok-abc123"


class TestActionSessions:
    """`gate_task_write` / `gate_demo_write` — payload lands in action_json."""

    def test_keys_are_recorded_and_nested_payloads_are_not_walked(self):
        f = _fields(_session(action_json=json.dumps({
            "action": "create_task", "device_id": "cam-01",
            "action_params": {"url": MARKER, "secret_token": MARKER},
            "tag_filter": MARKER, "interval": MARKER})))
        assert f["action_keys"] == ["action_params", "device_id", "interval", "tag_filter"]
        assert f["action"] == "create_task"
        assert MARKER not in json.dumps(f)

    def test_the_identifiers_attribution_consumes_are_kept(self):
        """ADR-0056's join reads rule_id and rule_name and nothing else — without
        them a web-origin rule write cannot be attributed at all."""
        f = _fields(_session(action_json=json.dumps({
            "action": "delete_action_rule", "rule_id": "175",
            "rule_name": "Motion record", "param_choices": {"x": MARKER}})))
        assert f["rule_id"] == "175" and f["rule_name"] == "Motion record"
        assert f["action_keys"] == ["param_choices"]      # identifiers not duplicated
        assert MARKER not in json.dumps(f)

    def test_non_scalar_identifiers_are_dropped(self):
        """Mirrors outcome_identity_fields: the audit store serialises with
        default=str and would stringify whatever it was handed."""
        f = _fields(_session(action_json=json.dumps({
            "action": "x", "rule_id": {"nested": MARKER}, "rule_name": ["a"]})))
        assert "rule_id" not in f and "rule_name" not in f
        assert MARKER not in json.dumps(f)


class TestPlanSessions:
    """`/plans/{id}/execute`, `/snapshot/revert`, demo prepare/end — the richest
    web-origin payload, and the one with no MCP row at all."""

    def test_operations_and_count_recorded_without_step_params(self):
        f = _fields(_session(plan_id="p1", plan_summary_json=json.dumps({
            "step_count": 2,
            "steps": [
                {"step": 1, "operation": "param.cgi:update", "device": "cam-01",
                 "description": f"set syslog to {MARKER}"},
                {"step": 2, "operation": "factorydefault.cgi:soft", "device": "cam-01"},
            ]})))
        assert f["plan_steps"] == 2
        assert f["plan_operations"] == ["factorydefault.cgi:soft", "param.cgi:update"]
        # per-step `description` is free text that can quote a value — excluded
        assert MARKER not in json.dumps(f)


class TestAllowListDiscipline:
    """#246: 'Allow-listed identifiers only — never **outcome'. Same rule here."""

    def test_the_identity_list_stays_minimal_and_justified(self):
        from admz.api.routes.confirm import _ACTION_IDENTITY_KEYS
        assert _ACTION_IDENTITY_KEYS == ("action", "rule_id", "rule_name")

    def test_an_unknown_payload_key_contributes_its_name_only(self):
        """The guard against someone widening this to **action later."""
        f = _fields(_session(action_json=json.dumps(
            {"action": "x", "some_future_field": MARKER})))
        assert f["action_keys"] == ["some_future_field"]
        assert MARKER not in json.dumps(f)


# ── through the real approve path ────────────────────────────────────────────
@pytest.fixture
def approve(monkeypatch):
    """Drive the REAL `_approve_session` and read the REAL audit log back."""
    from admz.api.routes import confirm as C

    def go(session):
        session.effective_status = C.ConfirmStatus.PENDING
        monkeypatch.setattr(C.confirm_store, "get_session", lambda t: session)
        monkeypatch.setattr(C.confirm_store, "complete_session",
                            lambda t, confirmed_by="": True)
        monkeypatch.setattr(C.rate_limiter, "check", lambda *a, **k: True)
        monkeypatch.setattr(C, "_is_locked", lambda t: False)
        monkeypatch.setattr(C, "_note_resolution_to_chat", lambda *a, **k: None)

        async def _exec(*a, **k):
            return {"success": True}          # success: no error string to muddy it
        import admz.operations as ops
        monkeypatch.setattr(ops, "execute_approved_session", _exec)

        import admz.auth as auth

        async def _cur(request):
            return NS(name="AXIS\\dnich", groups=["Administrators"],
                      is_anonymous=False, auth_source="windows-local")
        monkeypatch.setattr(auth, "get_current_principal", _cur)

        ctx = NS(catalog=None, registry=NS(), executors={}, plan_engine=None,
                 git_repo=None)
        result = _run(C._approve_session(NS(client=None, headers={}), "t", None,
                                         ctx, "web"))
        from admz.audit import AuditLog
        rows = AuditLog().list_recent(action="confirm.approve")
        return result, rows[0]
    return go


class TestThroughTheRealApprovePath:
    def test_a_web_origin_operation_is_recorded_keys_only(self, approve):
        result, row = approve(_session(params_json=json.dumps(
            {"root.RemoteSyslog.Server": MARKER})))
        assert result.status == "completed"
        # THE DEFECT, stated behaviourally: today this row says a dangerous
        # operation was approved and nothing about what it touched.
        assert "root.RemoteSyslog.Server" in json.dumps(row.details), (
            "the confirm.approve row records nothing about WHAT was approved")
        assert row.details["param_keys"] == ["root.RemoteSyslog.Server"]
        assert row.details["confirm_token"] == "tok-abc123"
        # The whole row, not just details — resource and error_message too.
        assert MARKER not in json.dumps(
            {"d": row.details, "r": row.resource, "e": row.error_message})

    def test_a_web_origin_task_write_is_recorded_keys_only(self, approve):
        """`gate_task_write` — the most common web origin (7 of the ~13 sites)."""
        result, row = approve(_session(action_json=json.dumps({
            "action": "create_task", "task_id": "nightly",
            "tag_filter": MARKER, "action_params": {"url": MARKER}})))
        assert result.status == "completed"
        assert "action_params" in json.dumps(row.details), (
            "the confirm.approve row records nothing about WHAT was approved")
        assert row.details["action"] == "create_task"
        assert row.details["action_keys"] == ["action_params", "tag_filter", "task_id"]
        assert MARKER not in json.dumps(
            {"d": row.details, "r": row.resource, "e": row.error_message})

    def test_the_mcp_tool_argument_audit_is_untouched(self):
        """MCP origins keep their own arguments row; this change adds nothing to
        and removes nothing from `_sanitize_tool_args`."""
        from admz.mcp.server import _sanitize_tool_args
        args = {"device_id": "cam-01", "params": {"root.X": MARKER},
                "password": "hunter2"}
        out = _sanitize_tool_args(args)
        assert out["params"] == {"root.X": MARKER}      # values still recorded there
        assert out["password"] == "***"                 # redaction still applied
