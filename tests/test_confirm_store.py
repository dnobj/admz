"""
Tests for the multi-level confirmation gate.
"""

import asyncio
import json
import time
import tempfile
import os

import pytest

from admz.api.confirm_store import (
    ConfirmStore,
    ConfirmSession,
    ConfirmStatus,
    hash_confirm_password,
    verify_confirm_password,
    get_confirmation_level,
    PROTECTED_SETTING_KEYS,
    VALID_CONFIRMATION_LEVELS,
    _DEFAULT_CONFIRMATION_LEVELS,
    confirm_level_key,
    is_confirm_level_key,
)
from admz.fleet_settings import is_protected_setting


@pytest.fixture
def store(tmp_path):
    """Create a ConfirmStore with a temp database."""
    db = str(tmp_path / "test.db")
    return ConfirmStore(db_path=db)


class TestConfirmStore:
    """Test ConfirmStore CRUD operations."""

    def test_create_session(self, store):
        session = store.create_session(
            device_id="cam-01",
            operation_id="firmwaremanagement.cgi:upgrade",
            family="vapix",
            params={"file": "/tmp/fw.bin"},
            risk_level="dangerous",
            confirmation_level="url_and_password",
            danger_description="Firmware upgrade may brick the device.",
        )

        assert session.token
        assert session.device_id == "cam-01"
        assert session.operation_id == "firmwaremanagement.cgi:upgrade"
        assert session.family == "vapix"
        assert session.params == {"file": "/tmp/fw.bin"}
        assert session.risk_level == "dangerous"
        assert session.confirmation_level == "url_and_password"
        assert session.danger_description == "Firmware upgrade may brick the device."
        assert session.status == ConfirmStatus.PENDING
        assert session.effective_status == ConfirmStatus.PENDING

    def test_get_session(self, store):
        session = store.create_session(
            device_id="cam-01",
            operation_id="param.cgi:update",
            family="vapix",
            params={"root.Time.ObtainFromDHCP": "no"},
            risk_level="service-affecting",
            confirmation_level="llm_confirm",
        )

        retrieved = store.get_session(session.token)
        assert retrieved is not None
        assert retrieved.token == session.token
        assert retrieved.device_id == "cam-01"
        assert retrieved.params == {"root.Time.ObtainFromDHCP": "no"}

    def test_get_session_not_found(self, store):
        assert store.get_session("nonexistent-token") is None

    def test_complete_session(self, store):
        session = store.create_session(
            device_id="cam-01",
            operation_id="test.cgi:action",
            family="vapix",
            params={},
            risk_level="dangerous",
            confirmation_level="url_only",
        )

        result = store.complete_session(session.token, confirmed_by="web")
        assert result is True

        completed = store.get_session(session.token)
        assert completed is not None
        assert completed.status == ConfirmStatus.COMPLETED
        assert completed.effective_status == ConfirmStatus.COMPLETED
        assert completed.confirmed_by == "web"

    def test_complete_session_idempotent(self, store):
        """Completing an already-completed session returns False."""
        session = store.create_session(
            device_id="cam-01",
            operation_id="test.cgi:action",
            family="vapix",
            params={},
            risk_level="dangerous",
            confirmation_level="url_only",
        )

        assert store.complete_session(session.token) is True
        assert store.complete_session(session.token) is False

    def test_session_expiry(self, store):
        session = store.create_session(
            device_id="cam-01",
            operation_id="test.cgi:action",
            family="vapix",
            params={},
            risk_level="dangerous",
            confirmation_level="url_only",
            ttl=0.01,  # 10ms
        )

        time.sleep(0.05)
        assert store.get_session(session.token) is None

    def test_completed_session_survives_expiry(self, store):
        """A completed session should be retrievable even after TTL."""
        session = store.create_session(
            device_id="cam-01",
            operation_id="test.cgi:action",
            family="vapix",
            params={},
            risk_level="dangerous",
            confirmation_level="url_only",
            ttl=1.0,  # long enough to complete before expiry
        )

        # Complete while still valid
        assert store.complete_session(session.token) is True

        # Now manually set a very short TTL in the DB to simulate expiry
        import sqlite3
        conn = sqlite3.connect(store._db_path)
        conn.execute(
            "UPDATE confirm_sessions SET ttl=0.01 WHERE token=?",
            (session.token,),
        )
        conn.commit()
        conn.close()

        time.sleep(0.05)

        retrieved = store.get_session(session.token)
        assert retrieved is not None
        assert retrieved.effective_status == ConfirmStatus.COMPLETED

    def test_complete_expired_session_fails(self, store):
        session = store.create_session(
            device_id="cam-01",
            operation_id="test.cgi:action",
            family="vapix",
            params={},
            risk_level="dangerous",
            confirmation_level="url_only",
            ttl=0.01,
        )

        time.sleep(0.05)
        assert store.complete_session(session.token) is False

    def test_get_session_by_plan(self, store):
        session = store.create_session(
            device_id="cam-01",
            operation_id="plan:abc123",
            family="vapix",
            params={},
            risk_level="dangerous",
            confirmation_level="url_and_password",
            plan_id="abc123",
        )

        found = store.get_session_by_plan("abc123")
        assert found is not None
        assert found.token == session.token
        assert found.plan_id == "abc123"

    def test_get_session_by_plan_not_found(self, store):
        assert store.get_session_by_plan("nonexistent") is None

    def test_params_json_roundtrip(self, store):
        params = {"key1": "value1", "key2": "value2"}
        session = store.create_session(
            device_id="cam-01",
            operation_id="test.cgi:action",
            family="vapix",
            params=params,
            risk_level="normal",
            confirmation_level="none",
        )

        retrieved = store.get_session(session.token)
        assert retrieved.params == params

    def test_plan_summary_json_roundtrip(self, store):
        """Plan summary JSON is stored and retrieved correctly."""
        plan_summary = {
            "plan_id": "plan-abc123",
            "description": "Upgrade firmware on 3 cameras",
            "step_count": 3,
            "risk_summary": {"dangerous": 3},
            "on_failure": "stop",
            "steps": [
                {"step": 1, "device": "cam-01", "operation": "firmwaremanagement.cgi:upgrade", "risk": "dangerous"},
                {"step": 2, "device": "cam-02", "operation": "firmwaremanagement.cgi:upgrade", "risk": "dangerous"},
                {"step": 3, "device": "cam-03", "operation": "firmwaremanagement.cgi:upgrade", "risk": "dangerous"},
            ],
        }
        session = store.create_session(
            device_id="cam-01",
            operation_id="plan:plan-abc123",
            family="vapix",
            params={},
            risk_level="dangerous",
            confirmation_level="url_and_password",
            plan_id="plan-abc123",
            plan_summary_json=json.dumps(plan_summary),
        )

        retrieved = store.get_session(session.token)
        assert retrieved is not None
        assert retrieved.plan_summary_json == json.dumps(plan_summary)
        assert retrieved.plan_summary == plan_summary
        assert retrieved.is_plan is True
        assert retrieved.plan_summary["step_count"] == 3
        assert len(retrieved.plan_summary["steps"]) == 3

    def test_plan_summary_empty_for_non_plan(self, store):
        """Non-plan sessions have empty plan_summary."""
        session = store.create_session(
            device_id="cam-01",
            operation_id="test.cgi:action",
            family="vapix",
            params={},
            risk_level="dangerous",
            confirmation_level="url_only",
        )

        retrieved = store.get_session(session.token)
        assert retrieved.is_plan is False
        assert retrieved.plan_summary == {}
        assert retrieved.plan_summary_json == ""

    def test_is_plan_property(self, store):
        """is_plan is True when plan_id is set."""
        session = store.create_session(
            device_id="cam-01",
            operation_id="plan:xyz",
            family="vapix",
            params={},
            risk_level="dangerous",
            confirmation_level="url_and_password",
            plan_id="xyz",
        )
        assert session.is_plan is True

        session2 = store.create_session(
            device_id="cam-01",
            operation_id="test.cgi:action",
            family="vapix",
            params={},
            risk_level="normal",
            confirmation_level="none",
        )
        assert session2.is_plan is False

    def test_secret_fields_roundtrip(self, store):
        """#334: secret_fields holds NAMES only — the caller (execute_gated_
        operation) must have already stripped the corresponding values out
        of params before calling create_session; this just persists and
        returns the name list."""
        session = store.create_session(
            device_id="cam-01",
            operation_id="pwdgrp.cgi:update-user",
            family="vapix",
            params={"user": "root"},
            secret_fields=["password"],
            risk_level="service-affecting",
            confirmation_level="url_only",
        )
        assert session.secret_fields == ["password"]
        assert "password" not in session.params

        retrieved = store.get_session(session.token)
        assert retrieved is not None
        assert retrieved.secret_fields == ["password"]
        assert retrieved.params == {"user": "root"}

    def test_secret_fields_defaults_to_empty_list(self, store):
        """Pin the other direction: a session created without secret_fields
        (the overwhelming majority of ops) must not spuriously report any —
        an implementation that always returned a non-empty list would fail
        every downstream check requiring the secret-entry page."""
        session = store.create_session(
            device_id="cam-01",
            operation_id="test.cgi:action",
            family="vapix",
            params={"a": "1"},
            risk_level="normal",
            confirmation_level="none",
        )
        assert session.secret_fields == []

        retrieved = store.get_session(session.token)
        assert retrieved.secret_fields == []
        assert retrieved.params == {"a": "1"}

    def test_plan_summary_json_via_get_session_by_plan(self, store):
        """Plan summary is also available via get_session_by_plan."""
        plan_summary = {
            "plan_id": "plan-def456",
            "description": "Factory reset 2 devices",
            "step_count": 2,
            "risk_summary": {"dangerous": 2},
            "on_failure": "continue",
            "steps": [
                {"step": 1, "device": "cam-01", "operation": "factorydefault.cgi:set", "risk": "dangerous"},
                {"step": 2, "device": "cam-02", "operation": "factorydefault.cgi:set", "risk": "dangerous"},
            ],
        }
        store.create_session(
            device_id="cam-01",
            operation_id="plan:plan-def456",
            family="vapix",
            params={},
            risk_level="dangerous",
            confirmation_level="url_and_password",
            plan_id="plan-def456",
            plan_summary_json=json.dumps(plan_summary),
        )

        found = store.get_session_by_plan("plan-def456")
        assert found is not None
        assert found.plan_summary == plan_summary
        assert found.is_plan is True


class TestPasswordHashing:
    """Test password hashing helpers."""

    def test_hash_and_verify(self):
        password = "my-secret-password"
        hashed = hash_confirm_password(password)

        assert ":" in hashed
        assert verify_confirm_password(password, hashed)

    def test_wrong_password(self):
        hashed = hash_confirm_password("correct")
        assert not verify_confirm_password("wrong", hashed)

    def test_empty_password(self):
        hashed = hash_confirm_password("")
        assert verify_confirm_password("", hashed)
        assert not verify_confirm_password("notempty", hashed)

    def test_different_hashes(self):
        """Two calls with the same password produce different hashes (different salt)."""
        h1 = hash_confirm_password("password")
        h2 = hash_confirm_password("password")
        assert h1 != h2
        # But both verify
        assert verify_confirm_password("password", h1)
        assert verify_confirm_password("password", h2)

    def test_verify_invalid_hash(self):
        assert not verify_confirm_password("password", "invalid")
        assert not verify_confirm_password("password", "")
        assert not verify_confirm_password("password", None)


class TestConfirmationLevel:
    """Test get_confirmation_level with default and overridden values."""

    def test_defaults(self, monkeypatch, tmp_path):
        """Every risk in the policy table resolves to its declared default.

        Derived from the table, not a hand-written list: the previous version
        asserted four of the six entries and so said nothing about the ACS Pro
        ``action`` / ``read`` classes added later (GH #152).
        """
        from admz.fleet_settings import FleetSettings
        fs = FleetSettings(db_path=str(tmp_path / "test.db"))
        import admz.fleet_settings
        monkeypatch.setattr(admz.fleet_settings, "fleet_settings", fs)

        for risk, expected in _DEFAULT_CONFIRMATION_LEVELS.items():
            assert get_confirmation_level(risk) == expected, risk

        # Spot-check the two the old test could not see, so a regression names
        # itself in the failure output rather than showing up as a loop index.
        assert get_confirmation_level("action") == "url_only"
        assert get_confirmation_level("read") == "none"

    def test_override(self, monkeypatch, tmp_path):
        """Test that fleet_settings overrides work."""
        from admz.fleet_settings import FleetSettings
        fs = FleetSettings(db_path=str(tmp_path / "test.db"))
        fs.set("confirm_level_dangerous", "url_only")
        import admz.fleet_settings
        monkeypatch.setattr(admz.fleet_settings, "fleet_settings", fs)

        assert get_confirmation_level("dangerous") == "url_only"

    def test_invalid_override_ignored(self, monkeypatch, tmp_path):
        """Invalid override values should be ignored, falling back to default."""
        from admz.fleet_settings import FleetSettings
        fs = FleetSettings(db_path=str(tmp_path / "test.db"))
        fs.set("confirm_level_dangerous", "bogus_value")
        import admz.fleet_settings
        monkeypatch.setattr(admz.fleet_settings, "fleet_settings", fs)

        assert get_confirmation_level("dangerous") == "url_and_password"

    def test_unknown_risk_level(self, monkeypatch, tmp_path):
        """An unknown risk class fails CLOSED (#397).

        This test previously asserted ``== "none"`` — it pinned the fail-open
        default as though it were the intended design. It was not; it was the
        behaviour of ``dict.get(risk, "none")``, and the test made the gap look
        deliberate to everyone who read it afterwards.
        """
        from admz.confirm_policy import UNKNOWN_RISK_CONFIRMATION
        from admz.fleet_settings import FleetSettings
        fs = FleetSettings(db_path=str(tmp_path / "test.db"))
        import admz.fleet_settings
        monkeypatch.setattr(admz.fleet_settings, "fleet_settings", fs)

        assert get_confirmation_level("unknown_risk") == UNKNOWN_RISK_CONFIRMATION
        assert get_confirmation_level("unknown_risk") != "none"


class TestProtectedKeys:
    """Test that PROTECTED_SETTING_KEYS covers the right keys."""

    def test_confirm_level_keys_protected(self):
        """Every risk class in the policy table has a protected override key.

        Iterates the *real* table. The previous version iterated a hardcoded
        four-tuple, so when the table grew ``action`` (default ``url_only``,
        governing 68 live ACS Pro operations) and ``read``, this guard kept
        passing over the hole it exists to detect (GH #152).

        The transferable rule: a literal is fine as an *expectation*, never as
        the *iteration source* for a coverage claim — growth in the real source
        can then only ever be missed.
        """
        for risk in _DEFAULT_CONFIRMATION_LEVELS:
            key = confirm_level_key(risk)
            assert key in PROTECTED_SETTING_KEYS, key
            assert is_protected_setting(key), key

    def test_confirm_level_namespace_protected(self):
        """A risk class absent from the table is protected by the namespace rule.

        ``get_confirmation_level`` interpolates whatever risk string the
        catalog hands it, so protection is scoped to the ``confirm_level_*``
        namespace rather than to today's six keys — which is also what the
        glossary and both personas have always documented.
        """
        assert is_protected_setting("confirm_level_totally_new")
        assert is_protected_setting("confirm_level_action")
        assert is_protected_setting("confirm_level_read")

        # The rule is a namespace, not a substring match: a key that merely
        # mentions the words is not matched *by this rule*.
        #
        # Asserted against is_confirm_level_key rather than
        # is_protected_setting since ADR-0053. The claim under test is that the
        # namespace rule is prefix-anchored, and that is still true and still
        # worth locking. What changed is that being outside the namespace no
        # longer implies writable: fleet settings are deny-by-default, so
        # `my_confirm_level_thing` is now protected for the ordinary reason —
        # nobody declared it writable. Testing the anchoring through the
        # protection predicate would silently stop testing anchoring at all.
        assert not is_confirm_level_key("my_confirm_level_thing")
        assert not is_confirm_level_key("default_username")

        # The allow-set, meanwhile, is exactly the fleet credential pair.
        assert not is_protected_setting("default_username")
        assert is_protected_setting("my_confirm_level_thing")

    def test_password_hash_protected(self):
        assert "confirm_password_hash" in PROTECTED_SETTING_KEYS
        assert is_protected_setting("confirm_password_hash")

    def test_valid_confirmation_levels(self):
        # Exact equality on a *closed* vocabulary is the correct shape: it
        # fails loudly if a level is added or removed. Contrast the coverage
        # guards above, which must derive their iteration source.
        assert VALID_CONFIRMATION_LEVELS == {
            "url_and_password", "url_only", "llm_confirm", "none"
        }


class TestMcpCannotRelaxConfirmationGates:
    """The MCP write path itself must refuse every confirmation-level key.

    This drives ``_set_fleet_setting`` rather than the predicate, because the
    predicate was never the thing that was broken: ``server.py`` tested
    ``key in PROTECTED_SETTING_KEYS`` directly, so a fix applied only to
    ``is_protected_setting`` would have reviewed as correct and changed
    nothing. This is the test that would have caught GH #152.
    """

    @pytest.mark.parametrize("risk", sorted(_DEFAULT_CONFIRMATION_LEVELS))
    def test_refuses_every_confirm_level_key(self, risk):
        from admz.mcp.server import ADMZMCPServer

        out = asyncio.run(
            ADMZMCPServer._set_fleet_setting(None, confirm_level_key(risk), "none")
        )
        assert out["success"] is False, risk
        assert "protected" in out["error"].lower()

    def test_refuses_the_key_from_the_report(self):
        """The exact call from the issue: relax the ACS Pro action gate."""
        from admz.mcp.server import ADMZMCPServer

        out = asyncio.run(
            ADMZMCPServer._set_fleet_setting(None, "confirm_level_action", "none")
        )
        assert out["success"] is False
        assert "protected" in out["error"].lower()

    def test_refuses_a_risk_class_not_in_the_table(self):
        from admz.mcp.server import ADMZMCPServer

        out = asyncio.run(
            ADMZMCPServer._set_fleet_setting(None, "confirm_level_invented", "none")
        )
        assert out["success"] is False

    def test_refusal_is_selective(self, monkeypatch, tmp_path):
        """Positive control: an ordinary key still writes.

        Without this, a ``_set_fleet_setting`` that refused *everything* would
        satisfy the assertions above. Uses an isolated FleetSettings bound to
        tmp_path — nothing here may reach a real database.
        """
        from admz.fleet_settings import FleetSettings
        import admz.mcp.server as mcp_server

        fs = FleetSettings(db_path=str(tmp_path / "test.db"))
        monkeypatch.setattr(mcp_server, "fleet_settings", fs)

        out = asyncio.run(
            mcp_server.ADMZMCPServer._set_fleet_setting(
                None, "default_username", "admin"
            )
        )
        assert out["success"] is True
        assert fs.get("default_username") == "admin"
