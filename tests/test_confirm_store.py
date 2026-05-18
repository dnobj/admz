"""
Tests for the multi-level confirmation gate.
"""

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
)


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
        """Test built-in defaults when no overrides are set."""
        from admz.fleet_settings import FleetSettings
        fs = FleetSettings(db_path=str(tmp_path / "test.db"))
        import admz.fleet_settings
        monkeypatch.setattr(admz.fleet_settings, "fleet_settings", fs)

        assert get_confirmation_level("dangerous") == "url_and_password"
        assert get_confirmation_level("service-affecting") == "llm_confirm"
        assert get_confirmation_level("normal") == "none"
        assert get_confirmation_level("read-only") == "none"

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
        """Unknown risk levels default to 'none'."""
        from admz.fleet_settings import FleetSettings
        fs = FleetSettings(db_path=str(tmp_path / "test.db"))
        import admz.fleet_settings
        monkeypatch.setattr(admz.fleet_settings, "fleet_settings", fs)

        assert get_confirmation_level("unknown_risk") == "none"


class TestProtectedKeys:
    """Test that PROTECTED_SETTING_KEYS covers the right keys."""

    def test_confirm_level_keys_protected(self):
        for risk in ("dangerous", "service-affecting", "normal", "read-only"):
            assert f"confirm_level_{risk}" in PROTECTED_SETTING_KEYS

    def test_password_hash_protected(self):
        assert "confirm_password_hash" in PROTECTED_SETTING_KEYS

    def test_valid_confirmation_levels(self):
        assert VALID_CONFIRMATION_LEVELS == {
            "url_and_password", "url_only", "llm_confirm", "none"
        }
