"""Tests for the audit log (Phase 4D).

Covers the AuditLog store, the record_event helper that integrates
with Principal, and the /api/audit read endpoint via TestClient.
"""

from types import SimpleNamespace

import pytest

from admz.audit import AuditLog, record_event
from admz.auth import Principal


@pytest.fixture
def audit_log(tmp_path):
    return AuditLog(db_path=str(tmp_path / "admz.db"))


# ---------------------------------------------------------------------------
# AuditLog store
# ---------------------------------------------------------------------------


class TestAuditLog:
    def test_record_and_list(self, audit_log):
        audit_log.record(
            requester="AXIS\\alice",
            auth_source="windows",
            action="get_credentials",
            resource="device:cam-01/account:default",
            details={"foo": "bar"},
            success=True,
        )
        entries = audit_log.list_recent()
        assert len(entries) == 1
        e = entries[0]
        assert e.requester == "AXIS\\alice"
        assert e.auth_source == "windows"
        assert e.action == "get_credentials"
        assert e.resource == "device:cam-01/account:default"
        assert e.details == {"foo": "bar"}
        assert e.success is True
        assert e.error_message == ""

    def test_record_failure(self, audit_log):
        audit_log.record(
            requester="api-key:bot",
            auth_source="api-key",
            action="get_credentials",
            success=False,
            error_message="disabled by fleet flag",
        )
        e = audit_log.list_recent()[0]
        assert e.success is False
        assert e.error_message == "disabled by fleet flag"

    def test_list_newest_first(self, audit_log):
        for i in range(5):
            audit_log.record(
                requester=f"user-{i}", action="op", auth_source="none"
            )
        entries = audit_log.list_recent(limit=3)
        assert len(entries) == 3
        # Newest (user-4) first
        assert entries[0].requester == "user-4"
        assert entries[1].requester == "user-3"
        assert entries[2].requester == "user-2"

    def test_filter_by_action(self, audit_log):
        audit_log.record(requester="a", action="get_credentials", auth_source="none")
        audit_log.record(requester="b", action="api_key.create", auth_source="none")
        audit_log.record(requester="c", action="get_credentials", auth_source="none")
        entries = audit_log.list_recent(action="get_credentials")
        assert len(entries) == 2
        assert all(e.action == "get_credentials" for e in entries)

    def test_filter_by_requester(self, audit_log):
        audit_log.record(requester="alice", action="x", auth_source="none")
        audit_log.record(requester="bob", action="x", auth_source="none")
        entries = audit_log.list_recent(requester="alice")
        assert len(entries) == 1
        assert entries[0].requester == "alice"

    def test_filter_by_since(self, audit_log):
        import time
        audit_log.record(requester="old", action="x", auth_source="none")
        cutoff = time.time()
        # Force a small gap so timestamps differ
        time.sleep(0.01)
        audit_log.record(requester="new", action="x", auth_source="none")
        entries = audit_log.list_recent(since=cutoff)
        assert len(entries) == 1
        assert entries[0].requester == "new"

    def test_details_round_trip(self, audit_log):
        complex_details = {
            "host": "192.168.1.10",
            "tags": ["lobby", "indoor"],
            "scopes": {"read": True, "write": False},
        }
        audit_log.record(
            requester="x", action="y", auth_source="none",
            details=complex_details,
        )
        e = audit_log.list_recent()[0]
        assert e.details == complex_details

    def test_non_serializable_details_falls_back_safely(self, audit_log):
        # The store uses default=str so e.g. dataclass instances become
        # their repr — no exception, just lossy.
        class Weird:
            def __repr__(self):
                return "<weird>"

        audit_log.record(
            requester="x", action="y", auth_source="none",
            details={"obj": Weird()},
        )
        e = audit_log.list_recent()[0]
        assert e.details == {"obj": "<weird>"}


# ---------------------------------------------------------------------------
# record_event helper
# ---------------------------------------------------------------------------


class TestRecordEvent:
    def test_pulls_requester_from_principal(self, audit_log):
        principal = Principal(
            name="AXIS\\alice",
            display_name="alice",
            domain="AXIS",
            source="windows",
        )
        record_event(
            principal, "get_credentials",
            resource="device:cam-01",
            log=audit_log,
        )
        e = audit_log.list_recent()[0]
        assert e.requester == "AXIS\\alice"
        assert e.auth_source == "windows"
        assert e.action == "get_credentials"

    def test_anonymous_principal_records_anonymous(self, audit_log):
        principal = Principal(
            name="anonymous", display_name="anonymous",
            source="none", is_anonymous=True,
        )
        record_event(principal, "op", log=audit_log)
        e = audit_log.list_recent()[0]
        assert e.requester == "anonymous"
        assert e.auth_source == "none"

    def test_none_principal_records_unknown(self, audit_log):
        record_event(None, "op", log=audit_log)
        e = audit_log.list_recent()[0]
        assert e.requester == "unknown"


# ---------------------------------------------------------------------------
# /api/audit endpoint
# ---------------------------------------------------------------------------


class TestAuditEndpoint:
    @pytest.fixture(autouse=True)
    def isolate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")
        monkeypatch.setenv(
            "ADMZ_AUTH_TRUSTED_PROXIES", "testclient,127.0.0.1,::1"
        )
        import admz.auth as auth_mod
        monkeypatch.setattr(auth_mod, "_ACTIVE_BACKEND", None)

    def test_list_empty(self, tmp_path):
        from fastapi.testclient import TestClient
        from admz.api.main import app

        with TestClient(app) as client:
            r = client.get("/api/audit")
            assert r.status_code == 200
            assert r.json() == []

    @staticmethod
    def _install_admin():
        # CR-3: POST /api/api-keys now refuses anonymous. Install a
        # stub authenticated backend so the test can mint.
        from admz.auth import (
            AuthBackend, Principal, set_active_backend,
        )

        class _Stub(AuthBackend):
            async def authenticate(self, request):
                return Principal(
                    name="test-admin",
                    display_name="test-admin",
                    source="windows",
                    is_anonymous=False,
                )

        set_active_backend(_Stub())

    @staticmethod
    def _restore_noauth():
        from admz.auth import NoAuth, set_active_backend
        set_active_backend(NoAuth())

    def test_records_appear_after_action(self, tmp_path):
        from fastapi.testclient import TestClient
        from admz.api.main import app

        with TestClient(app) as client:
            self._install_admin()
            try:
                # Create an API key (this records api_key.create)
                client.post("/api/api-keys", json={"display_name": "bot"})
            finally:
                self._restore_noauth()
            r = client.get("/api/audit")
            assert r.status_code == 200
            entries = r.json()
            assert any(e["action"] == "api_key.create" for e in entries)

    def test_filter_by_action(self, tmp_path):
        from fastapi.testclient import TestClient
        from admz.api.main import app

        with TestClient(app) as client:
            self._install_admin()
            try:
                client.post("/api/api-keys", json={"display_name": "bot-a"})
                client.post("/api/api-keys", json={"display_name": "bot-b"})
            finally:
                self._restore_noauth()
            r = client.get("/api/audit", params={"action": "api_key.create"})
            assert r.status_code == 200
            entries = r.json()
            # Two creates above; both should be present
            create_events = [e for e in entries if e["action"] == "api_key.create"]
            assert len(create_events) == 2
