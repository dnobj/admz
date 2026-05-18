"""Tests for admz.auth — the web/REST authentication layer.

Disambiguation: ``test_auth.py`` tests **device-side** auth
(per-protocol detection of digest/basic for VAPIX calls). This file
tests **server-side** auth — Windows IWA via reverse proxy + API keys
+ the foundation. Phase 4.
"""

from unittest.mock import MagicMock

import pytest

from admz.auth import (
    AuthBackend,
    NoAuth,
    Principal,
    build_auth_backend,
    exempt_paths,
    get_active_backend,
    get_current_principal,
    is_exempt,
    parse_windows_identity,
    set_active_backend,
    _resolve_backend_name,
)


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------


class TestPrincipal:
    def test_defaults(self):
        p = Principal(name="alice", display_name="alice")
        assert p.name == "alice"
        assert p.display_name == "alice"
        assert p.domain is None
        assert p.groups == []
        assert p.source == "none"
        assert p.is_anonymous is False

    def test_groups_independent_per_instance(self):
        # Regression: dataclass default_factory should give each
        # principal its own groups list (not a shared class-level list).
        a = Principal(name="a", display_name="a")
        b = Principal(name="b", display_name="b")
        a.groups.append("admins")
        assert b.groups == []


# ---------------------------------------------------------------------------
# parse_windows_identity
# ---------------------------------------------------------------------------


class TestParseWindowsIdentity:
    def test_domain_backslash_user(self):
        p = parse_windows_identity("AXIS\\alice")
        assert p.domain == "AXIS"
        assert p.display_name == "alice"
        assert p.name == "AXIS\\alice"
        assert p.source == "windows"

    def test_domain_forward_slash_user(self):
        p = parse_windows_identity("AXIS/alice")
        assert p.domain == "AXIS"
        assert p.display_name == "alice"

    def test_user_at_domain(self):
        p = parse_windows_identity("alice@axis.local")
        assert p.domain == "axis.local"
        assert p.display_name == "alice"
        assert p.name == "alice@axis.local"

    def test_bare_username(self):
        # No domain part — workgroup / local account
        p = parse_windows_identity("alice")
        assert p.domain is None
        assert p.display_name == "alice"
        assert p.name == "alice"

    def test_strips_whitespace(self):
        p = parse_windows_identity("  AXIS\\alice  ")
        assert p.display_name == "alice"
        assert p.domain == "AXIS"

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_windows_identity("")

    def test_only_whitespace_raises(self):
        with pytest.raises(ValueError):
            parse_windows_identity("   ")


# ---------------------------------------------------------------------------
# NoAuth
# ---------------------------------------------------------------------------


class TestNoAuth:
    @pytest.mark.asyncio
    async def test_returns_anonymous_regardless_of_request(self):
        backend = NoAuth()
        request = MagicMock()
        request.url.path = "/api/devices"
        request.headers = {"REMOTE_USER": "AXIS\\alice"}  # ignored

        p = await backend.authenticate(request)
        assert p.name == "anonymous"
        assert p.is_anonymous is True
        assert p.source == "none"
        assert p.groups == []


# ---------------------------------------------------------------------------
# Exempt paths
# ---------------------------------------------------------------------------


class TestExemptPaths:
    @pytest.mark.parametrize(
        "path",
        ["/health", "/api/health", "/static/css/style.css",
         "/api/docs", "/api/redoc", "/api/openapi.json"],
    )
    def test_exempt_paths_match(self, path):
        assert is_exempt(path) is True

    @pytest.mark.parametrize(
        "path",
        ["/", "/api/devices", "/device/cam-01", "/api/catalog/execute",
         "/capture/abc123", "/confirm/abc123"],
    )
    def test_non_exempt_paths_do_not_match(self, path):
        assert is_exempt(path) is False

    def test_exempt_list_is_tuple(self):
        # Immutable shape so a caller can't accidentally mutate the
        # auth-bypass list at runtime.
        assert isinstance(exempt_paths(), tuple)


# ---------------------------------------------------------------------------
# Backend factory + env
# ---------------------------------------------------------------------------


class TestBuildAuthBackend:
    def test_default_is_noauth(self, monkeypatch):
        monkeypatch.delenv("ADMZ_AUTH_BACKEND", raising=False)
        backend = build_auth_backend()
        assert isinstance(backend, NoAuth)

    def test_explicit_none(self):
        backend = build_auth_backend("none")
        assert isinstance(backend, NoAuth)

    def test_unknown_value_falls_back_to_noauth(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            backend = build_auth_backend("magic-beans")
        assert isinstance(backend, NoAuth)
        assert any("magic-beans" in rec.message for rec in caplog.records)

    def test_env_value_is_read(self, monkeypatch):
        monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")
        assert isinstance(build_auth_backend(), NoAuth)

    def test_case_insensitive_and_strips(self):
        assert _resolve_backend_name("  NONE  ") == "none"

    def test_phase_gated_options_dont_crash(self):
        # 4B / 4B' implementations may not be wired yet; asking for
        # them should never raise — fall back to NoAuth.
        for name in ("windows", "api-key", "composite"):
            backend = build_auth_backend(name)
            assert isinstance(backend, AuthBackend), (
                f"{name} should produce an AuthBackend (may be NoAuth fallback)"
            )


# ---------------------------------------------------------------------------
# Active backend management
# ---------------------------------------------------------------------------


class TestActiveBackend:
    def test_set_and_get_active_backend(self):
        backend = NoAuth()
        set_active_backend(backend)
        assert get_active_backend() is backend

    def test_get_lazy_builds_from_env(self, monkeypatch):
        import admz.auth as auth_mod
        monkeypatch.setattr(auth_mod, "_ACTIVE_BACKEND", None)
        monkeypatch.delenv("ADMZ_AUTH_BACKEND", raising=False)
        backend = get_active_backend()
        assert isinstance(backend, NoAuth)


# ---------------------------------------------------------------------------
# get_current_principal dependency
# ---------------------------------------------------------------------------


class TestGetCurrentPrincipal:
    @pytest.mark.asyncio
    async def test_exempt_path_short_circuits(self):
        set_active_backend(NoAuth())
        request = MagicMock()
        request.url.path = "/health"
        p = await get_current_principal(request)
        assert p.is_anonymous is True

    @pytest.mark.asyncio
    async def test_non_exempt_path_invokes_backend(self):
        # When request.state.principal isn't set (the middleware didn't
        # run), the dependency falls back to running the backend
        # directly. Use a real SimpleNamespace for state so MagicMock
        # doesn't auto-create a truthy .principal attribute.
        from types import SimpleNamespace

        set_active_backend(NoAuth())
        request = MagicMock()
        request.url.path = "/api/devices"
        request.state = SimpleNamespace()
        p = await get_current_principal(request)
        # NoAuth still returns anonymous; the point is the backend
        # was consulted rather than short-circuiting.
        assert p.is_anonymous is True
        assert p.source == "none"
        # And the principal got stashed for future calls
        assert request.state.principal is p

    @pytest.mark.asyncio
    async def test_reads_from_state_when_middleware_ran(self):
        # If middleware already ran, the dependency returns the stashed
        # principal without re-invoking the backend.
        from types import SimpleNamespace

        set_active_backend(NoAuth())
        cached = Principal(
            name="cached", display_name="cached", source="windows"
        )
        request = MagicMock()
        request.url.path = "/api/devices"
        request.state = SimpleNamespace(principal=cached)
        p = await get_current_principal(request)
        assert p is cached
