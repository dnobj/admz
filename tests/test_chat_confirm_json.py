"""Tests for the JSON twin of the /confirm/{token} flow (Phase 5C).

The chat client uses /api/chat/confirm/{token} GET to fetch session
details and POST to submit approval. These tests verify that:

  - GET returns the correct shape and respects expired/completed
  - POST completes a pending session
  - Password gating works the same way as the HTML form
  - Per-token lockout still fires
  - Rate limiter still fires
  - 410/429/403 status codes match what the chat client expects
"""

import pytest
from fastapi.testclient import TestClient

from admz.rate_limit import rate_limiter as global_limiter


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")

    global_limiter.reset()
    # Don't let an exhausted bucket from a previous test cause a
    # spurious 429 — give the test plenty of headroom.
    global_limiter.configure("confirm", capacity=100, refill_per_s=100)

    import admz.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_ACTIVE_BACKEND", None)

    from admz.api.main import app

    try:
        with TestClient(app) as c:
            yield c
    finally:
        # Restore the rate-limit policy to defaults so subsequent
        # tests in other files don't see our tight 'rate_limited_per_ip'
        # bucket config. RateLimiter.reset() only clears buckets, not
        # policy — we have to reconfigure explicitly.
        global_limiter.configure("confirm", capacity=10, refill_per_s=1.0 / 6.0)
        global_limiter.reset()
        # Best-effort cleanup of the in-memory lockout tracker.
        from admz.api.routes.confirm import _PW_ATTEMPTS
        _PW_ATTEMPTS.clear()


def _make_session(confirmation_level="url_only", risk_level="dangerous"):
    """Create a confirm session and return its token."""
    from admz.api.confirm_store import confirm_store
    return confirm_store.create_session(
        device_id="cam-01",
        operation_id="factorydefault.cgi:factory-reset",
        family="vapix",
        params={},
        risk_level=risk_level,
        confirmation_level=confirmation_level,
        danger_description="Resets the device to factory defaults.",
    )


# ---------------------------------------------------------------------------
# GET /api/chat/confirm/{token}
# ---------------------------------------------------------------------------


class TestChatConfirmDetails:
    def test_returns_session_shape(self, client):
        session = _make_session()
        r = client.get(f"/api/chat/confirm/{session.token}")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "pending"
        assert body["device_id"] == "cam-01"
        assert body["operation_id"] == "factorydefault.cgi:factory-reset"
        assert body["risk_level"] == "dangerous"
        assert body["confirmation_level"] == "url_only"
        assert body["danger_description"].startswith("Resets")
        assert body["needs_password"] is False
        assert body["is_plan"] is False

    def test_needs_password_when_configured(self, client):
        from admz.api.confirm_store import hash_confirm_password
        from admz.fleet_settings import fleet_settings as fs
        fs.set("confirm_password_hash", hash_confirm_password("hunter2"))

        try:
            session = _make_session(confirmation_level="url_and_password")
            r = client.get(f"/api/chat/confirm/{session.token}")
            assert r.status_code == 200
            assert r.json()["needs_password"] is True
        finally:
            fs.delete("confirm_password_hash")

    def test_url_and_password_downgrades_when_no_password_set(self, client):
        # If url_and_password is requested but no password is in the
        # fleet store, treat as url_only so the operator isn't locked
        # out. Mirrors HTML form behavior.
        from admz.fleet_settings import fleet_settings as fs
        fs.delete("confirm_password_hash")

        session = _make_session(confirmation_level="url_and_password")
        r = client.get(f"/api/chat/confirm/{session.token}")
        assert r.status_code == 200
        assert r.json()["needs_password"] is False

    def test_unknown_token_returns_410(self, client):
        r = client.get("/api/chat/confirm/does-not-exist-token")
        assert r.status_code == 410
        assert r.json()["status"] == "expired_or_not_found"


# ---------------------------------------------------------------------------
# POST /api/chat/confirm/{token}
# ---------------------------------------------------------------------------


class TestChatConfirmSubmit:
    def test_approve_without_password(self, client):
        session = _make_session(confirmation_level="url_only")
        r = client.post(f"/api/chat/confirm/{session.token}")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "completed"
        assert body["device_id"] == "cam-01"

    def test_approve_with_correct_password(self, client):
        from admz.api.confirm_store import hash_confirm_password
        from admz.fleet_settings import fleet_settings as fs
        fs.set("confirm_password_hash", hash_confirm_password("hunter2"))

        try:
            session = _make_session(confirmation_level="url_and_password")
            r = client.post(
                f"/api/chat/confirm/{session.token}",
                data={"confirm_password": "hunter2"},
            )
            assert r.status_code == 200
            assert r.json()["status"] == "completed"
        finally:
            fs.delete("confirm_password_hash")

    def test_wrong_password_returns_403(self, client):
        from admz.api.confirm_store import hash_confirm_password
        from admz.fleet_settings import fleet_settings as fs
        fs.set("confirm_password_hash", hash_confirm_password("hunter2"))

        try:
            session = _make_session(confirmation_level="url_and_password")
            r = client.post(
                f"/api/chat/confirm/{session.token}",
                data={"confirm_password": "wrong"},
            )
            assert r.status_code == 403
            assert r.json()["status"] == "wrong_password"
        finally:
            fs.delete("confirm_password_hash")

    def test_already_completed_returns_410(self, client):
        session = _make_session()
        # First approval succeeds
        r1 = client.post(f"/api/chat/confirm/{session.token}")
        assert r1.status_code == 200
        # Second attempt against the same token: 410.
        r2 = client.post(f"/api/chat/confirm/{session.token}")
        assert r2.status_code == 410
        assert r2.json()["status"] == "expired_or_not_found"

    def test_lockout_after_five_wrong_passwords(self, client):
        from admz.api.confirm_store import hash_confirm_password
        from admz.fleet_settings import fleet_settings as fs
        fs.set("confirm_password_hash", hash_confirm_password("hunter2"))

        try:
            session = _make_session(confirmation_level="url_and_password")
            # 5 wrong tries → on the 5th, lockout kicks in
            for attempt in range(5):
                r = client.post(
                    f"/api/chat/confirm/{session.token}",
                    data={"confirm_password": "wrong"},
                )
                assert r.status_code in (403, 429), \
                    f"attempt {attempt}: status {r.status_code}"

            # 6th attempt with correct password should be locked
            r = client.post(
                f"/api/chat/confirm/{session.token}",
                data={"confirm_password": "hunter2"},
            )
            assert r.status_code == 429
            assert r.json()["status"] == "locked"
        finally:
            fs.delete("confirm_password_hash")

    def test_rate_limited_per_ip(self, client):
        # Configure a tiny bucket so the rate limit fires quickly.
        global_limiter.configure("confirm", capacity=2, refill_per_s=0.001)

        statuses = []
        for _ in range(8):
            r = client.post("/api/chat/confirm/no-such-token")
            statuses.append(r.status_code)

        # Expect 429s after the bucket drains. (Some will be 410
        # because the rate limit lets a few through, and unknown
        # token returns 410.)
        assert 429 in statuses, f"expected at least one 429, got {statuses}"
        # The 429 body should be JSON with status=rate_limited.
        for r in (client.post("/api/chat/confirm/no-such-token") for _ in range(3)):
            if r.status_code == 429:
                body = r.json()
                assert body["status"] in ("rate_limited", "locked")
                break


# ---------------------------------------------------------------------------
# Cross-check: HTML form route still works (we didn't break it)
# ---------------------------------------------------------------------------


class TestHtmlFormUnchanged:
    def test_get_form_still_renders(self, client):
        session = _make_session()
        r = client.get(f"/confirm/{session.token}")
        assert r.status_code == 200
        # HTML, not JSON.
        assert "text/html" in r.headers["content-type"]
        assert b"factory-reset" in r.content or b"factorydefault" in r.content


# ---------------------------------------------------------------------------
# H-5 (review 2026-06-10): url_* approvals must write audit rows
# ---------------------------------------------------------------------------


class TestConfirmAudit:
    """The web form and chat-widget approval paths are the riskiest
    executions in the system; both must leave an audit trail."""

    def _audit(self):
        from admz.audit import AuditLog
        return AuditLog()

    def test_chat_approval_writes_audit_row(self, client):
        session = _make_session()  # url_only
        r = client.post(f"/api/chat/confirm/{session.token}")
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

        rows = self._audit().list_recent(action="confirm.approve")
        assert len(rows) == 1
        row = rows[0]
        assert row.resource == "device:cam-01/op:factorydefault.cgi:factory-reset"
        assert row.details["confirmed_by"] == "chat"
        assert row.details["risk_level"] == "dangerous"
        assert row.details["confirmation_level"] == "url_only"
        assert row.details["is_plan"] is False
        # Execution fails (device not in registry) but the approval is
        # still audited - that is the point.
        assert row.success is False

    def test_web_form_approval_writes_audit_row(self, client):
        session = _make_session()  # url_only
        r = client.post(f"/confirm/{session.token}")
        assert r.status_code == 200

        rows = self._audit().list_recent(action="confirm.approve")
        assert len(rows) == 1
        assert rows[0].details["confirmed_by"] == "web"

    def test_wrong_password_writes_audit_row_without_password(self, client):
        from admz.api.confirm_store import hash_confirm_password
        from admz.fleet_settings import fleet_settings as fs
        fs.set("confirm_password_hash", hash_confirm_password("hunter2"))

        try:
            session = _make_session(confirmation_level="url_and_password")
            r = client.post(
                f"/api/chat/confirm/{session.token}",
                data={"confirm_password": "wrong-guess"},
            )
            assert r.status_code == 403

            rows = self._audit().list_recent(action="confirm.password_failed")
            assert len(rows) == 1
            row = rows[0]
            assert row.success is False
            assert row.details["confirmed_by"] == "chat"
            assert row.details["locked_out"] is False
            # The submitted password must never reach the audit log.
            import json as json_mod
            flat = json_mod.dumps(row.details) + row.error_message + row.resource
            assert "wrong-guess" not in flat
            assert "hunter2" not in flat

            # No approve row - the gate held.
            assert self._audit().list_recent(action="confirm.approve") == []
        finally:
            fs.delete("confirm_password_hash")

    def test_lockout_flag_recorded_on_final_attempt(self, client):
        from admz.api.confirm_store import hash_confirm_password
        from admz.fleet_settings import fleet_settings as fs
        fs.set("confirm_password_hash", hash_confirm_password("hunter2"))

        try:
            session = _make_session(confirmation_level="url_and_password")
            # _MAX_PW_ATTEMPTS is 5; the 5th failure trips the lockout.
            for _ in range(5):
                client.post(
                    f"/api/chat/confirm/{session.token}",
                    data={"confirm_password": "nope"},
                )

            rows = self._audit().list_recent(action="confirm.password_failed")
            assert len(rows) == 5
            # newest first - the final attempt carries locked_out=True
            assert rows[0].details["locked_out"] is True
            assert rows[-1].details["locked_out"] is False
        finally:
            fs.delete("confirm_password_hash")


# ---------------------------------------------------------------------------
# Identifying fields lifted off the execution outcome
#
# Without these, the confirm.approve row that records the *actual* creation of
# a rule carries device/approver/timestamp/success but not the rule id — so a
# drift row for rule 175 can only be joined back to its approval by correlating
# the rule *name* across two rows by time adjacency. Names are not unique and
# not stable under on-device rename, so that join is fuzzy. These pin the exact
# one.
# ---------------------------------------------------------------------------


class TestApproveOutcomeIdentityAudit:
    def _audit(self):
        from admz.audit import AuditLog
        return AuditLog()

    def _patch_outcome(self, monkeypatch, outcome):
        """Force execute_approved_session to return a chosen envelope.

        The real thing needs a reachable device; the shape of what it returns
        is what is under test here, not how it got there.
        """
        from admz import operations

        async def _fake(session, **kwargs):
            return outcome

        monkeypatch.setattr(operations, "execute_approved_session", _fake)

    def test_rule_id_reaches_the_audit_row(self, client, monkeypatch):
        self._patch_outcome(monkeypatch, {
            "success": True, "action": "create_action_rule",
            "device_id": "cam-01", "rule_id": "175", "config_id": "42",
            "rule_name": "AtlasRule",
        })
        session = _make_session()
        r = client.post(f"/api/chat/confirm/{session.token}")
        assert r.status_code == 200

        rows = self._audit().list_recent(action="confirm.approve")
        assert len(rows) == 1
        details = rows[0].details
        # The whole point: the approval that created rule 175 says so.
        assert details["rule_id"] == "175"
        assert details["config_id"] == "42"
        # ...without losing what the row already carried.
        assert details["confirmed_by"] == "chat"
        assert details["risk_level"] == "dangerous"

    def test_delete_path_records_the_removed_rule(self, client, monkeypatch):
        # Deletion has the same attribution problem as creation: a drift row
        # showing a rule vanished is just as unjoinable without the id.
        self._patch_outcome(monkeypatch, {
            "success": True, "action": "delete_action_rule",
            "removed_rule": "175", "removed_config": "42",
        })
        session = _make_session()
        client.post(f"/api/chat/confirm/{session.token}")

        details = self._audit().list_recent(action="confirm.approve")[0].details
        assert details["removed_rule"] == "175"
        assert details["removed_config"] == "42"

    def test_operation_without_identifiers_writes_todays_row(
        self, client, monkeypatch,
    ):
        """The no-rule-id path must be untouched — no empty key, no exception.

        This runs for every approved operation, not just rule creation, so the
        exact key set is asserted rather than just the absence of rule_id.
        """
        self._patch_outcome(monkeypatch, {
            "success": True, "operation_id": "factorydefault.cgi:factory-reset",
            "device_id": "cam-01", "status_code": 200, "duration_ms": 12.5,
        })
        session = _make_session()
        client.post(f"/api/chat/confirm/{session.token}")

        details = self._audit().list_recent(action="confirm.approve")[0].details
        assert details == {
            "confirmed_by": "chat",
            "risk_level": "dangerous",
            "confirmation_level": "url_only",
            "is_plan": False,
        }

    def test_null_rule_id_on_successful_create_is_omitted(
        self, client, monkeypatch,
    ):
        # rules/runner.py parses RuleID off the SOAP response without
        # validating it, so a successful create can still yield None. That must
        # not write rule_id=None into a durable row.
        self._patch_outcome(monkeypatch, {
            "success": True, "action": "create_action_rule",
            "rule_id": None, "config_id": "",
        })
        session = _make_session()
        r = client.post(f"/api/chat/confirm/{session.token}")
        assert r.status_code == 200

        details = self._audit().list_recent(action="confirm.approve")[0].details
        assert "rule_id" not in details
        assert "config_id" not in details

    def test_outcome_payload_never_reaches_the_audit_row(
        self, client, monkeypatch,
    ):
        """#217 guard: only the allow-list crosses into the row.

        The outcome envelope is not a fixed shape, and several handlers build
        theirs with ``**out`` spreads. A deny-list — or a bare ``**outcome`` —
        would carry device responses, SOAP traces and scheduled-job params into
        a durable, long-lived row.
        """
        self._patch_outcome(monkeypatch, {
            "success": True, "action": "create_action_rule", "rule_id": "175",
            # Every one of these is a real key some handler returns.
            "data": {"root.Network.Password": "s3cr3t-device-pw"},
            "steps": [{"op": "add", "error": "SOAP fault: user=admin pw=hunter2"}],
            "results": [{"error": "500 body: token=abcdef"}],
            "task": {"action_params": {"password": "task-secret"}},
            "added": [{"path": "root.Foo", "value": "live-config-value"}],
            "fragments": {"role": {"facets": {"body": "secret-body"}}},
            "demo": {"id": "d1", "rules": ["..."]},
            "message": "Rule 'AtlasRule' created on cam-01 (rule id 175).",
        })
        session = _make_session()
        client.post(f"/api/chat/confirm/{session.token}")

        row = self._audit().list_recent(action="confirm.approve")[0]
        details = row.details
        assert details["rule_id"] == "175"
        for leaked in (
            "data", "steps", "results", "task", "added", "fragments", "demo",
            "message",
        ):
            assert leaked not in details, f"{leaked} must not be audited"

        import json as json_mod
        flat = json_mod.dumps(details) + (row.error_message or "")
        for secret in (
            "s3cr3t-device-pw", "hunter2", "abcdef", "task-secret",
            "live-config-value", "secret-body",
        ):
            assert secret not in flat, f"{secret!r} reached the audit row"

    def test_non_scalar_identifier_is_dropped(self, client, monkeypatch):
        # A downstream shape change must not smuggle a blob in under an
        # allow-listed name; the audit store serializes with default=str and
        # would stringify it happily.
        self._patch_outcome(monkeypatch, {
            "success": True,
            "rule_id": {"nested": "unexpected-blob"},
        })
        session = _make_session()
        client.post(f"/api/chat/confirm/{session.token}")

        details = self._audit().list_recent(action="confirm.approve")[0].details
        assert "rule_id" not in details
