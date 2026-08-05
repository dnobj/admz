"""
Tests for temporary credentials and get_credentials toggle.
"""

import time
import pytest

from admz.mcp.temp_credentials import (
    TempCredential,
    TempCredentialManager,
)
from admz.api.confirm_store import PROTECTED_SETTING_KEYS


@pytest.fixture(autouse=True)
def _isolated_temp_cred_db(tmp_path, monkeypatch):
    """Every manager in this file gets its own database.

    Since #314 the manager is SQLite-backed, so a bare
    ``TempCredentialManager()`` resolves the shared ADMZ database at call time
    and every test in this file would see the previous test's rows — six of
    them failed that way on the first run. ``ADMZ_HOME`` and ``ADMZ_DB_PATH``
    are both redirected so nothing can reach a real database even if a test
    constructs a manager with no explicit path.
    """
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    yield


# ── TempCredential dataclass ─────────────────────────────────────────────


class TestTempCredential:

    def test_not_expired_within_ttl(self):
        cred = TempCredential(
            device_id="cam-01",
            username="at_abc12345",
            password="secret",
            group="users",
            ttl_seconds=300,
        )
        assert not cred.is_expired

    def test_expired_after_ttl(self):
        cred = TempCredential(
            device_id="cam-01",
            username="at_abc12345",
            password="secret",
            group="users",
            created_at=time.time() - 400,
            ttl_seconds=300,
        )
        assert cred.is_expired

    def test_expires_at_iso_format(self):
        cred = TempCredential(
            device_id="cam-01",
            username="at_abc12345",
            password="secret",
            group="users",
        )
        iso = cred.expires_at_iso
        assert iso.endswith("Z")
        assert "T" in iso

    def test_should_retry_cleanup(self):
        cred = TempCredential(
            device_id="cam-01",
            username="at_abc12345",
            password="secret",
            group="users",
        )
        assert cred.should_retry_cleanup
        cred.cleanup_attempts = 5
        assert not cred.should_retry_cleanup


# ── TempCredentialManager ────────────────────────────────────────────────


class TestTempCredentialManager:

    def test_generate_username_format(self):
        mgr = TempCredentialManager()
        name = mgr.generate_username()
        assert name.startswith("at_")
        assert len(name) == 11  # "at_" + 8 hex chars

    def test_generate_username_uniqueness(self):
        mgr = TempCredentialManager()
        names = {mgr.generate_username() for _ in range(50)}
        assert len(names) == 50

    def test_generate_password_length(self):
        mgr = TempCredentialManager()
        pw = mgr.generate_password()
        assert len(pw) == 16

    def test_register_and_list(self):
        mgr = TempCredentialManager()
        cred = TempCredential(
            device_id="cam-01",
            username="at_aabbccdd",
            password="secret",
            group="users",
        )
        mgr.register(cred)
        active = mgr.list_active()
        assert len(active) == 1
        assert active[0]["username"] == "at_aabbccdd"
        # Password must never appear in list output
        assert "password" not in active[0]

    def test_list_active_filters_by_device(self):
        mgr = TempCredentialManager()
        mgr.register(TempCredential("cam-01", "at_11111111", "pw1", "users"))
        mgr.register(TempCredential("cam-02", "at_22222222", "pw2", "users"))
        assert len(mgr.list_active("cam-01")) == 1
        assert len(mgr.list_active("cam-02")) == 1
        assert len(mgr.list_active()) == 2

    def test_count_active_for_device(self):
        mgr = TempCredentialManager()
        mgr.register(TempCredential("cam-01", "at_11111111", "pw", "users"))
        mgr.register(TempCredential("cam-01", "at_22222222", "pw", "users"))
        mgr.register(TempCredential("cam-02", "at_33333333", "pw", "users"))
        assert mgr.count_active_for_device("cam-01") == 2
        assert mgr.count_active_for_device("cam-02") == 1

    def test_count_excludes_expired(self):
        mgr = TempCredentialManager()
        mgr.register(TempCredential(
            "cam-01", "at_11111111", "pw", "users",
            created_at=time.time() - 400, ttl_seconds=300,
        ))
        mgr.register(TempCredential("cam-01", "at_22222222", "pw", "users"))
        assert mgr.count_active_for_device("cam-01") == 1

    def test_remove(self):
        mgr = TempCredentialManager()
        cred = TempCredential("cam-01", "at_aabbccdd", "pw", "users")
        mgr.register(cred)
        removed = mgr.remove("cam-01", "at_aabbccdd")

        # Identity (`is cred`) was the pre-#314 assertion and a store cannot
        # honour it: the row is reconstructed, not handed back. Assert the
        # identifying fields instead — those are what cleanup uses.
        assert removed is not None
        assert (removed.device_id, removed.username) == ("cam-01", "at_aabbccdd")
        assert removed.group == "users"
        # And the deliberate omission: the temp password is never persisted, so
        # a stolen database yields no live device credential. Cleanup
        # authenticates as the admin from the registry, never as the temp user.
        assert removed.password == "", "the temp password was written to the DB"
        assert len(mgr.list_active()) == 0

    def test_remove_nonexistent(self):
        mgr = TempCredentialManager()
        assert mgr.remove("cam-01", "at_nope") is None

    def test_get_expired(self):
        mgr = TempCredentialManager()
        mgr.register(TempCredential(
            "cam-01", "at_expired", "pw", "users",
            created_at=time.time() - 400, ttl_seconds=300,
        ))
        mgr.register(TempCredential("cam-01", "at_active", "pw", "users"))
        expired = mgr.get_expired()
        assert len(expired) == 1
        assert expired[0].username == "at_expired"

    def test_get_all(self):
        mgr = TempCredentialManager()
        mgr.register(TempCredential("cam-01", "at_11111111", "pw", "users"))
        mgr.register(TempCredential("cam-02", "at_22222222", "pw", "root"))
        assert len(mgr.get_all()) == 2

    def test_max_per_device(self):
        mgr = TempCredentialManager()
        assert mgr.max_per_device == 3


# ── Protected setting key ────────────────────────────────────────────────


class TestGetCredentialsToggle:

    def test_tool_toggle_key_is_protected(self):
        assert "tool_get_credentials_enabled" in PROTECTED_SETTING_KEYS
