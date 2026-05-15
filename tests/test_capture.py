"""Tests for the out-of-band credential capture flow."""

import time

import pytest

from admz.api.capture import CaptureSession, CaptureStatus, CaptureStore


class TestCaptureSession:

    def test_initial_status_is_pending(self):
        s = CaptureSession(token="t", device_id="d", account_id="a")
        assert s.effective_status == CaptureStatus.PENDING

    def test_expired_when_past_ttl(self):
        s = CaptureSession(
            token="t",
            device_id="d",
            account_id="a",
            ttl=0.01,
        )
        time.sleep(0.02)
        assert s.is_expired is True
        assert s.effective_status == CaptureStatus.EXPIRED

    def test_completed_overrides_expiry(self):
        """A completed session stays completed even if its TTL elapsed."""
        s = CaptureSession(
            token="t",
            device_id="d",
            account_id="a",
            ttl=0.01,
        )
        s.status = CaptureStatus.COMPLETED
        time.sleep(0.02)
        assert s.effective_status == CaptureStatus.COMPLETED


class TestCaptureStore:

    def test_create_session_returns_unique_tokens(self):
        store = CaptureStore()
        s1 = store.create_session("cam-01", "default")
        s2 = store.create_session("cam-02", "default")
        assert s1.token != s2.token

    def test_token_is_url_safe(self):
        store = CaptureStore()
        s = store.create_session("cam-01")
        # Should be base64url — no / or +
        assert "/" not in s.token
        assert "+" not in s.token
        # Reasonable length
        assert len(s.token) > 30

    def test_get_session_returns_session(self):
        store = CaptureStore()
        created = store.create_session("cam-01", "default")
        fetched = store.get_session(created.token)
        assert fetched is not None
        assert fetched.device_id == "cam-01"

    def test_get_session_unknown_token_returns_none(self):
        store = CaptureStore()
        assert store.get_session("does-not-exist") is None

    def test_complete_session(self):
        store = CaptureStore()
        s = store.create_session("cam-01")
        assert store.complete_session(s.token) is True
        fetched = store.get_session(s.token)
        assert fetched.effective_status == CaptureStatus.COMPLETED

    def test_complete_unknown_session_returns_false(self):
        store = CaptureStore()
        assert store.complete_session("nope") is False

    def test_complete_already_completed_returns_false(self):
        store = CaptureStore()
        s = store.create_session("cam-01")
        store.complete_session(s.token)
        # Second completion fails (single-use)
        assert store.complete_session(s.token) is False

    def test_expired_session_lookup_returns_none(self):
        store = CaptureStore()
        s = store.create_session("cam-01", ttl=0.01)
        time.sleep(0.02)
        assert store.get_session(s.token) is None

    def test_default_ttl_is_10_minutes(self):
        store = CaptureStore()
        s = store.create_session("cam-01")
        assert s.ttl == 600.0

    def test_custom_ttl_honored(self):
        store = CaptureStore()
        s = store.create_session("cam-01", ttl=30.0)
        assert s.ttl == 30.0

    def test_purpose_and_account_type_stored(self):
        store = CaptureStore()
        s = store.create_session(
            "cam-01",
            account_id="aoa-agent",
            account_type="service",
            purpose="AOA agent access",
        )
        fetched = store.get_session(s.token)
        assert fetched.purpose == "AOA agent access"
        assert fetched.account_type == "service"
