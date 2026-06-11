"""Tests for the production auth backends: ReverseProxyAuth, ApiKeyAuth,
CompositeAuth, plus the underlying ApiKeyStore. Phase 4B + 4B'.

Foundation-level tests (Principal, NoAuth, factory) live in
``test_web_auth.py``.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from admz.auth import (
    ApiKeyAuth,
    AuthBackend,
    CompositeAuth,
    NoAuth,
    Principal,
    ReverseProxyAuth,
)
from admz.api_keys import (
    ApiKey,
    ApiKeyStore,
    CreatedApiKey,
    looks_like_api_key,
    _generate_key,
    _hash_key,
    _verify_key,
)


def _mock_request(path="/api/devices", headers=None, client_host="127.0.0.1"):
    """Build a minimal fake Request for backend.authenticate()."""
    request = MagicMock()
    request.url.path = path
    request.headers = headers or {}
    request.client = MagicMock()
    request.client.host = client_host
    return request


@pytest.fixture
def api_key_store(tmp_path):
    return ApiKeyStore(db_path=str(tmp_path / "admz.db"))


# ---------------------------------------------------------------------------
# ReverseProxyAuth
# ---------------------------------------------------------------------------


class TestReverseProxyAuth:
    @pytest.mark.asyncio
    async def test_valid_header_from_localhost_succeeds(self):
        backend = ReverseProxyAuth()
        req = _mock_request(headers={"REMOTE_USER": "AXIS\\alice"})
        p = await backend.authenticate(req)
        assert p.display_name == "alice"
        assert p.domain == "AXIS"
        assert p.source == "windows"

    @pytest.mark.asyncio
    async def test_missing_header_raises_401(self):
        backend = ReverseProxyAuth()
        req = _mock_request(headers={})
        with pytest.raises(HTTPException) as exc:
            await backend.authenticate(req)
        assert exc.value.status_code == 401
        assert "REMOTE_USER" in exc.value.detail

    @pytest.mark.asyncio
    async def test_empty_header_raises_401(self):
        backend = ReverseProxyAuth()
        req = _mock_request(headers={"REMOTE_USER": "   "})
        with pytest.raises(HTTPException) as exc:
            await backend.authenticate(req)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_untrusted_source_ip_raises_401(self):
        backend = ReverseProxyAuth(trusted_proxies={"127.0.0.1"})
        req = _mock_request(
            headers={"REMOTE_USER": "AXIS\\alice"},
            client_host="10.0.0.42",
        )
        with pytest.raises(HTTPException) as exc:
            await backend.authenticate(req)
        assert exc.value.status_code == 401
        assert "trusted" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_custom_header_name(self):
        backend = ReverseProxyAuth(header="X-Forwarded-User")
        req = _mock_request(headers={"X-Forwarded-User": "alice@axis.local"})
        p = await backend.authenticate(req)
        assert p.display_name == "alice"
        assert p.domain == "axis.local"

    def test_from_env_defaults(self, monkeypatch):
        monkeypatch.delenv("ADMZ_AUTH_REMOTE_USER_HEADER", raising=False)
        monkeypatch.delenv("ADMZ_AUTH_TRUSTED_PROXIES", raising=False)
        backend = ReverseProxyAuth.from_env()
        assert backend.header == "REMOTE_USER"
        assert backend.trusted_proxies == {"127.0.0.1", "::1"}

    def test_from_env_overrides(self, monkeypatch):
        monkeypatch.setenv("ADMZ_AUTH_REMOTE_USER_HEADER", "X-Auth-User")
        monkeypatch.setenv("ADMZ_AUTH_TRUSTED_PROXIES", "10.0.0.5, 10.0.0.6")
        backend = ReverseProxyAuth.from_env()
        assert backend.header == "X-Auth-User"
        assert backend.trusted_proxies == {"10.0.0.5", "10.0.0.6"}


# ---------------------------------------------------------------------------
# ApiKey hashing primitives
# ---------------------------------------------------------------------------


class TestApiKeyHashing:
    def test_generate_key_has_expected_shape(self):
        k = _generate_key()
        assert k.startswith("admz_")
        # 32 random bytes -> ~43-char url-safe base64 -> ~48 total
        assert len(k) >= 45

    def test_two_generated_keys_are_different(self):
        a = _generate_key()
        b = _generate_key()
        assert a != b

    def test_hash_then_verify_succeeds(self):
        plaintext = _generate_key()
        h = _hash_key(plaintext)
        assert ":" in h
        assert _verify_key(plaintext, h) is True

    def test_wrong_key_fails_verify(self):
        h = _hash_key(_generate_key())
        assert _verify_key(_generate_key(), h) is False

    def test_malformed_hash_fails_verify_safely(self):
        assert _verify_key("admz_anything", "not-a-valid-hash") is False
        assert _verify_key("admz_anything", None) is False

    def test_looks_like_api_key(self):
        assert looks_like_api_key("admz_xxx") is True
        assert looks_like_api_key("Bearer admz_xxx") is False
        assert looks_like_api_key("") is False
        assert looks_like_api_key(None) is False


# ---------------------------------------------------------------------------
# ApiKeyStore
# ---------------------------------------------------------------------------


class TestApiKeyStore:
    def test_create_returns_plaintext_and_record(self, api_key_store):
        created = api_key_store.create(
            display_name="nightly-bot", created_by="AXIS\\alice"
        )
        assert isinstance(created, CreatedApiKey)
        assert created.plaintext.startswith("admz_")
        assert created.record.display_name == "nightly-bot"
        assert created.record.created_by == "AXIS\\alice"
        assert created.record.revoked is False
        assert created.record.id > 0

    def test_create_with_empty_display_name_raises(self, api_key_store):
        with pytest.raises(ValueError):
            api_key_store.create(display_name="", created_by="alice")
        with pytest.raises(ValueError):
            api_key_store.create(display_name="   ", created_by="alice")

    def test_create_without_created_by_raises(self, api_key_store):
        with pytest.raises(ValueError):
            api_key_store.create(display_name="bot", created_by="")

    def test_create_stores_groups_snapshot(self, api_key_store):
        created = api_key_store.create(
            display_name="bot",
            created_by="alice",
            groups=["admins", "operators"],
        )
        assert created.record.groups == ["admins", "operators"]
        fetched = api_key_store.get(created.record.id)
        assert fetched.groups == ["admins", "operators"]

    def test_list_excludes_revoked_by_default(self, api_key_store):
        a = api_key_store.create(display_name="a", created_by="alice")
        b = api_key_store.create(display_name="b", created_by="alice")
        api_key_store.revoke(a.record.id)
        names_active = {k.display_name for k in api_key_store.list()}
        names_all = {
            k.display_name for k in api_key_store.list(include_revoked=True)
        }
        assert names_active == {"b"}
        assert names_all == {"a", "b"}

    def test_authenticate_with_valid_key_returns_record(self, api_key_store):
        created = api_key_store.create(display_name="bot", created_by="alice")
        key = api_key_store.authenticate(created.plaintext)
        assert key is not None
        assert key.id == created.record.id
        assert key.last_used_at is not None

    def test_authenticate_with_invalid_key_returns_none(self, api_key_store):
        api_key_store.create(display_name="bot", created_by="alice")
        result = api_key_store.authenticate("admz_not-the-right-key")
        assert result is None

    def test_authenticate_revoked_key_returns_none(self, api_key_store):
        created = api_key_store.create(display_name="bot", created_by="alice")
        api_key_store.revoke(created.record.id)
        assert api_key_store.authenticate(created.plaintext) is None

    def test_authenticate_expired_key_returns_none(self, api_key_store):
        created = api_key_store.create(
            display_name="bot", created_by="alice", expires_at=0,
        )
        assert api_key_store.authenticate(created.plaintext) is None

    def test_authenticate_non_key_returns_none_without_hashing(
        self, api_key_store
    ):
        # Prefix short-circuit avoids the PBKDF2 cost on garbage input.
        result = api_key_store.authenticate("Bearer something-else")
        assert result is None

    def test_revoke_returns_true_only_for_active_key(self, api_key_store):
        created = api_key_store.create(display_name="bot", created_by="alice")
        assert api_key_store.revoke(created.record.id) is True
        assert api_key_store.revoke(created.record.id) is False
        assert api_key_store.revoke(99999) is False


# ---------------------------------------------------------------------------
# ApiKeyAuth backend
# ---------------------------------------------------------------------------


class TestApiKeyAuth:
    @pytest.mark.asyncio
    async def test_no_authorization_header_raises_401(self, api_key_store):
        backend = ApiKeyAuth(store=api_key_store)
        req = _mock_request(headers={})
        with pytest.raises(HTTPException) as exc:
            await backend.authenticate(req)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_non_bearer_authorization_raises_401(self, api_key_store):
        backend = ApiKeyAuth(store=api_key_store)
        req = _mock_request(headers={"Authorization": "Basic something"})
        with pytest.raises(HTTPException) as exc:
            await backend.authenticate(req)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_bearer_without_admz_prefix_raises_401(self, api_key_store):
        backend = ApiKeyAuth(store=api_key_store)
        req = _mock_request(headers={"Authorization": "Bearer foo"})
        with pytest.raises(HTTPException) as exc:
            await backend.authenticate(req)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_unknown_key_raises_401(self, api_key_store):
        backend = ApiKeyAuth(store=api_key_store)
        req = _mock_request(
            headers={"Authorization": "Bearer admz_unknown-key-value-here"}
        )
        with pytest.raises(HTTPException) as exc:
            await backend.authenticate(req)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_key_returns_principal(self, api_key_store):
        created = api_key_store.create(
            display_name="nightly-bot",
            created_by="AXIS\\alice",
            groups=["bot-operators"],
        )
        backend = ApiKeyAuth(store=api_key_store)
        req = _mock_request(
            headers={"Authorization": "Bearer " + created.plaintext}
        )
        p = await backend.authenticate(req)
        assert p.source == "api-key"
        assert p.display_name == "nightly-bot"
        assert p.groups == ["bot-operators"]
        assert p.name == "api-key:nightly-bot"


# ---------------------------------------------------------------------------
# CompositeAuth
# ---------------------------------------------------------------------------


class TestCompositeAuth:
    @pytest.mark.asyncio
    async def test_first_backend_succeeds_short_circuits(self, api_key_store):
        created = api_key_store.create(display_name="bot", created_by="alice")
        composite = CompositeAuth(
            [ApiKeyAuth(store=api_key_store), ReverseProxyAuth()]
        )
        req = _mock_request(
            headers={"Authorization": "Bearer " + created.plaintext}
        )
        p = await composite.authenticate(req)
        assert p.source == "api-key"

    @pytest.mark.asyncio
    async def test_falls_through_to_next_on_401(self, api_key_store):
        composite = CompositeAuth(
            [ApiKeyAuth(store=api_key_store), ReverseProxyAuth()]
        )
        req = _mock_request(headers={"REMOTE_USER": "AXIS\\alice"})
        p = await composite.authenticate(req)
        assert p.source == "windows"
        assert p.display_name == "alice"

    @pytest.mark.asyncio
    async def test_all_backends_fail_re_raises_last_401(self, api_key_store):
        composite = CompositeAuth(
            [ApiKeyAuth(store=api_key_store), ReverseProxyAuth()]
        )
        req = _mock_request(headers={})
        with pytest.raises(HTTPException) as exc:
            await composite.authenticate(req)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_non_401_error_propagates_immediately(self, api_key_store):
        class ServerErrorBackend(AuthBackend):
            async def authenticate(self, request):
                raise HTTPException(status_code=500, detail="boom")

        composite = CompositeAuth(
            [ServerErrorBackend(), ApiKeyAuth(store=api_key_store)]
        )
        with pytest.raises(HTTPException) as exc:
            await composite.authenticate(_mock_request())
        assert exc.value.status_code == 500

    def test_empty_backends_list_raises(self):
        with pytest.raises(ValueError):
            CompositeAuth([])

    def test_from_env_builds_api_key_then_session_then_windows(self):
        # ADR-0033: SessionAuth (browser login cookie) sits between the
        # explicit Bearer check and the trusted-header IWA check.
        from admz.auth import SessionAuth
        composite = CompositeAuth.from_env()
        assert isinstance(composite.backends[0], ApiKeyAuth)
        assert isinstance(composite.backends[1], SessionAuth)
        assert isinstance(composite.backends[2], ReverseProxyAuth)
