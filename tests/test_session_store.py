"""Tests for admz.session_store — server-side web sessions (ADR-0033)."""

import time

import pytest

from admz.auth import Principal
from admz.session_store import SessionStore


@pytest.fixture
def store(tmp_path):
    return SessionStore(db_path=str(tmp_path / "admz.db"))


def _alice(groups=("Administrators", "Users")):
    return Principal(
        name="HOMELAB\\alice",
        display_name="alice",
        domain="HOMELAB",
        groups=list(groups),
        source="windows-local",
        is_anonymous=False,
    )


class TestSessionLifecycle:
    def test_create_and_resolve(self, store):
        token = store.create(_alice())
        assert token and len(token) > 30
        snap = store.resolve(token)
        assert snap is not None
        assert snap.name == "HOMELAB\\alice"
        assert snap.display_name == "alice"
        assert snap.domain == "HOMELAB"
        assert snap.groups == ["Administrators", "Users"]
        assert snap.source == "windows-local"

    def test_unknown_token_resolves_none(self, store):
        assert store.resolve("not-a-real-token") is None
        assert store.resolve("") is None

    def test_token_not_stored_in_plaintext(self, store, tmp_path):
        import sqlite3
        token = store.create(_alice())
        rows = sqlite3.connect(str(tmp_path / "admz.db")).execute(
            "SELECT token_hash, principal_json FROM web_sessions"
        ).fetchall()
        assert len(rows) == 1
        assert token not in rows[0][0]
        assert token not in rows[0][1]

    def test_revoke_kills_session(self, store):
        token = store.create(_alice())
        assert store.revoke(token) is True
        assert store.resolve(token) is None
        # Second revoke is a no-op.
        assert store.revoke(token) is False

    def test_expired_session_resolves_none(self, store, monkeypatch):
        monkeypatch.setenv("ADMZ_SESSION_TTL_SECONDS", "1")
        token = store.create(_alice())
        # Simulate the clock jumping past expiry.
        real_time = time.time
        monkeypatch.setattr(time, "time", lambda: real_time() + 10)
        assert store.resolve(token) is None

    def test_sliding_expiry_extends_session(self, store, monkeypatch, tmp_path):
        import sqlite3
        token = store.create(_alice())
        before = sqlite3.connect(str(tmp_path / "admz.db")).execute(
            "SELECT expires_at FROM web_sessions"
        ).fetchone()[0]
        real_time = time.time
        monkeypatch.setattr(time, "time", lambda: real_time() + 100)
        assert store.resolve(token) is not None
        after = sqlite3.connect(str(tmp_path / "admz.db")).execute(
            "SELECT expires_at FROM web_sessions"
        ).fetchone()[0]
        assert after > before

    def test_purge_expired_removes_rows(self, store, monkeypatch):
        monkeypatch.setenv("ADMZ_SESSION_TTL_SECONDS", "1")
        t1 = store.create(_alice())
        store.revoke(t1)
        real_time = time.time
        monkeypatch.setattr(time, "time", lambda: real_time() + 10)
        assert store.purge_expired() >= 1

    def test_create_requires_named_principal(self, store):
        with pytest.raises(ValueError):
            store.create(Principal(name="", display_name=""))
