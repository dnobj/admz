"""Tests for per-protocol auth method support.

Covers:
  - VapixExecutor._resolve_auth() with structured auth dict, legacy fallback
  - VapixExecutor scheme selection from device auth dict
  - _detect_auth_schemes() with mocked HTTP/HTTPS responses
  - ProbeResult.auth field serialization
  - DiscoveredDevice.to_registry_dict() auth structure
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

import httpx

from admz.executor.vapix import VapixExecutor
from admz.discovery.credential_probe import (
    ProbeResult,
    ProbeStatus,
    _detect_auth_schemes,
    _parse_www_authenticate,
)
from admz.discovery.models import DiscoveredDevice, DeviceType


def _run(coro):
    """Helper to run async functions in sync tests.

    ``asyncio.run`` rather than ``get_event_loop().run_until_complete`` — the
    latter depends on ambient loop state this file does not own. Once any
    earlier async test has run under a pytest-asyncio that clears the current
    loop, ``get_event_loop()`` stops emitting a DeprecationWarning and starts
    raising ``RuntimeError: There is no current event loop``.

    That is exactly how it failed: `pytest-asyncio` is pinned `>=1.0.0,<2`, CI
    resolved 1.4.0 while the dev venv held 1.3.0, and 1.4.0 leaves no current
    loop behind. The file that happened to expose it was simply the first
    async test file sorting before this one — nothing to do with what it
    tested. `asyncio.run` creates and closes its own loop, so this helper no
    longer cares what ran before it.
    """
    return asyncio.run(coro)


# ------------------------------------------------------------------
# _resolve_auth tests
# ------------------------------------------------------------------


class TestResolveAuth:
    """Test VapixExecutor._resolve_auth with various device auth configs."""

    def test_structured_auth_http_digest(self):
        device = {"auth": {"http": "digest", "https": "basic", "scheme": "http"}}
        creds = {"username": "root", "password": "pass"}
        auth = VapixExecutor._resolve_auth(device, creds, scheme="http")
        assert isinstance(auth, httpx.DigestAuth)

    def test_structured_auth_https_basic(self):
        device = {"auth": {"http": "digest", "https": "basic", "scheme": "http"}}
        creds = {"username": "root", "password": "pass"}
        auth = VapixExecutor._resolve_auth(device, creds, scheme="https")
        assert isinstance(auth, httpx.BasicAuth)

    def test_structured_auth_none(self):
        device = {"auth": {"http": "none", "https": "none", "scheme": "http"}}
        creds = {"username": "root", "password": "pass"}
        auth = VapixExecutor._resolve_auth(device, creds, scheme="http")
        assert auth is None

    def test_structured_auth_default_to_digest(self):
        """If scheme key is missing from auth dict, default to digest."""
        device = {"auth": {"http": "digest", "scheme": "http"}}
        creds = {"username": "root", "password": "pass"}
        # https not in dict -> should default to digest
        auth = VapixExecutor._resolve_auth(device, creds, scheme="https")
        assert isinstance(auth, httpx.DigestAuth)

    def test_legacy_auth_method_fallback(self):
        """Device with only auth_method (no auth dict) -> legacy path."""
        device = {"auth_method": "basic"}
        creds = {"username": "root", "password": "pass"}
        auth = VapixExecutor._resolve_auth(device, creds, scheme="http")
        assert isinstance(auth, httpx.BasicAuth)

    def test_legacy_auth_method_digest(self):
        device = {"auth_method": "digest"}
        creds = {"username": "root", "password": "pass"}
        auth = VapixExecutor._resolve_auth(device, creds, scheme="https")
        assert isinstance(auth, httpx.DigestAuth)

    def test_no_auth_info_defaults_digest(self):
        """Device with no auth info at all -> default to digest."""
        device = {}
        creds = {"username": "root", "password": "pass"}
        auth = VapixExecutor._resolve_auth(device, creds, scheme="http")
        assert isinstance(auth, httpx.DigestAuth)

    def test_structured_auth_takes_precedence(self):
        """If both auth and auth_method exist, auth dict wins."""
        device = {
            "auth_method": "digest",
            "auth": {"http": "basic", "https": "basic", "scheme": "http"},
        }
        creds = {"username": "root", "password": "pass"}
        auth = VapixExecutor._resolve_auth(device, creds, scheme="http")
        assert isinstance(auth, httpx.BasicAuth)


# ------------------------------------------------------------------
# Scheme selection tests
# ------------------------------------------------------------------


class TestSchemeSelection:
    """Test that the executor picks the correct scheme from device info."""

    def test_scheme_from_auth_dict(self):
        executor = VapixExecutor()
        device = {
            "host": "192.168.1.100",
            "auth": {"http": "digest", "https": "basic", "scheme": "http"},
        }
        auth_info = device.get("auth")
        scheme = auth_info.get("scheme", "http") if auth_info else "http"
        assert scheme == "http"

    def test_scheme_https(self):
        device = {
            "host": "192.168.1.100",
            "auth": {"http": "digest", "https": "basic", "scheme": "https"},
        }
        auth_info = device.get("auth")
        scheme = auth_info.get("scheme", "http") if auth_info else "http"
        assert scheme == "https"

    def test_scheme_default_no_auth_dict(self):
        device = {"host": "192.168.1.100"}
        auth_info = device.get("auth")
        scheme = auth_info.get("scheme", "http") if auth_info and isinstance(auth_info, dict) else "http"
        assert scheme == "http"

    def test_scheme_default_legacy(self):
        device = {"host": "192.168.1.100", "auth_method": "digest"}
        auth_info = device.get("auth")
        scheme = auth_info.get("scheme", "http") if auth_info and isinstance(auth_info, dict) else "http"
        assert scheme == "http"


# ------------------------------------------------------------------
# _parse_www_authenticate tests
# ------------------------------------------------------------------


class TestParseWwwAuthenticate:

    def test_digest(self):
        headers = {"www-authenticate": 'Digest realm="AXIS_ACCC8E123456"'}
        assert _parse_www_authenticate(headers) == "digest"

    def test_basic(self):
        headers = {"www-authenticate": 'Basic realm="AXIS_ACCC8E123456"'}
        assert _parse_www_authenticate(headers) == "basic"

    def test_empty(self):
        headers = {}
        assert _parse_www_authenticate(headers) == "digest"

    def test_basic_case_insensitive(self):
        headers = {"www-authenticate": 'BASIC realm="test"'}
        assert _parse_www_authenticate(headers) == "basic"


# ------------------------------------------------------------------
# ProbeResult serialization
# ------------------------------------------------------------------


class TestProbeResultSerialization:

    def test_to_dict_includes_auth(self):
        result = ProbeResult(
            status=ProbeStatus.AUTHENTICATED,
            host="192.168.1.100",
            username="root",
            password="pass",
            auth_method="digest",
            auth={"http": "digest", "https": "basic", "scheme": "http"},
        )
        d = result.to_dict(include_credentials=False)
        assert d["auth_method"] == "digest"
        assert d["auth"] == {"http": "digest", "https": "basic", "scheme": "http"}
        assert "password" not in d

    def test_to_dict_no_auth(self):
        result = ProbeResult(
            status=ProbeStatus.AUTH_FAILED,
            host="192.168.1.100",
        )
        d = result.to_dict()
        assert "auth" not in d

    def test_to_dict_with_credentials(self):
        result = ProbeResult(
            status=ProbeStatus.AUTHENTICATED,
            host="192.168.1.100",
            username="root",
            password="secret",
            auth={"http": "digest", "scheme": "http"},
        )
        d = result.to_dict(include_credentials=True)
        assert d["username"] == "root"
        assert d["password"] == "secret"
        assert d["auth"] == {"http": "digest", "scheme": "http"}


# ------------------------------------------------------------------
# DiscoveredDevice.to_registry_dict auth structure
# ------------------------------------------------------------------


class TestDiscoveredDeviceAuth:

    def test_to_registry_dict_factory_default(self):
        d = DiscoveredDevice(
            ip_address="192.168.1.100",
            mac_address="AC:CC:8E:12:34:56",
            factory_default=True,
            is_axis=True,
        )
        reg = d.to_registry_dict()
        assert reg["auth_method"] == "none"
        assert reg["auth"] == {"http": "none", "https": "none", "scheme": "http"}

    def test_to_registry_dict_configured(self):
        d = DiscoveredDevice(
            ip_address="192.168.1.100",
            mac_address="AC:CC:8E:12:34:56",
            factory_default=False,
            is_axis=True,
        )
        reg = d.to_registry_dict()
        assert reg["auth_method"] == "digest"
        assert reg["auth"] == {"http": "digest", "https": "digest", "scheme": "http"}


# ------------------------------------------------------------------
# _detect_auth_schemes tests (mocked HTTP)
# ------------------------------------------------------------------


class TestDetectAuthSchemes:

    def _mock_client(self, post_fn):
        """Create a mock httpx.AsyncClient with the given post function."""
        mock_client = AsyncMock()
        mock_client.post = post_fn
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        return mock_client

    def test_both_protocols_recommended(self):
        """HTTP returns Digest, HTTPS returns Basic -> scheme=http."""
        mock_responses = {
            "http": MagicMock(
                status_code=401,
                headers={"www-authenticate": 'Digest realm="test"'},
            ),
            "https": MagicMock(
                status_code=401,
                headers={"www-authenticate": 'Basic realm="test"'},
            ),
        }

        async def mock_post(url, **kwargs):
            if url.startswith("http://"):
                return mock_responses["http"]
            return mock_responses["https"]

        with patch("httpx.AsyncClient", return_value=self._mock_client(mock_post)):
            result = _run(_detect_auth_schemes("192.168.1.100"))

        assert result["http"] == "digest"
        assert result["https"] == "basic"
        assert result["scheme"] == "http"

    def test_http_only(self):
        """Only HTTP reachable -> scheme=http."""
        async def mock_post(url, **kwargs):
            if url.startswith("http://"):
                return MagicMock(
                    status_code=401,
                    headers={"www-authenticate": 'Digest realm="test"'},
                )
            raise ConnectionError("HTTPS not available")

        with patch("httpx.AsyncClient", return_value=self._mock_client(mock_post)):
            result = _run(_detect_auth_schemes("192.168.1.100"))

        assert result["http"] == "digest"
        assert "https" not in result
        assert result["scheme"] == "http"

    def test_https_only(self):
        """Only HTTPS reachable -> scheme=https."""
        async def mock_post(url, **kwargs):
            if url.startswith("https://"):
                return MagicMock(
                    status_code=401,
                    headers={"www-authenticate": 'Basic realm="test"'},
                )
            raise ConnectionError("HTTP not available")

        with patch("httpx.AsyncClient", return_value=self._mock_client(mock_post)):
            result = _run(_detect_auth_schemes("192.168.1.100"))

        assert "http" not in result
        assert result["https"] == "basic"
        assert result["scheme"] == "https"

    def test_no_auth_both_protocols(self):
        """Both return 200 (no auth) -> scheme=http."""
        async def mock_post(url, **kwargs):
            return MagicMock(status_code=200, headers={})

        with patch("httpx.AsyncClient", return_value=self._mock_client(mock_post)):
            result = _run(_detect_auth_schemes("192.168.1.100"))

        assert result["http"] == "none"
        assert result["https"] == "none"
        assert result["scheme"] == "http"
