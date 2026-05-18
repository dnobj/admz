"""Authentication for the ADMZ web/REST surface.

ADMZ has multiple trust boundaries; this module covers exactly one:
the **web/REST client → ADMZ HTTP server** boundary. Device auth
(digest/basic/bearer over VAPIX), Vault auth, MCP-over-stdio, and
at-rest credential encryption are unchanged.

Two production auth methods are supported, plus a development-only
no-auth mode:

  * **windows** — Windows Integrated Authentication via a reverse
    proxy (IIS, nginx-with-spnego, etc.). The proxy negotiates with
    the client and forwards the authenticated username in a header
    (``REMOTE_USER`` by default). Used by browsers.

  * **api-key** — ``Authorization: Bearer admz_<random>`` header.
    Keys are minted in the web UI by Windows-authenticated operators
    and given to programmatic agents.

  * **none** — every request is mapped to a synthetic ``anonymous``
    principal. Default for dev / single-user local installs. Tests
    rely on this so that ~600 existing tests keep working without
    standing up IIS.

The two production methods can be enabled together (``CompositeAuth``)
so that ``/api/...`` endpoints accept either browser cookies (Windows
IWA via AJAX) or a Bearer token (a separate agent). Each ``Principal``
carries a ``source`` field so the audit log can tell them apart.

Configuration is env-driven::

    ADMZ_AUTH_BACKEND               none | windows | api-key | composite
    ADMZ_AUTH_REMOTE_USER_HEADER    default: REMOTE_USER
    ADMZ_AUTH_TRUSTED_PROXIES       default: 127.0.0.1,::1 (comma list)

Routes opt into auth by depending on :func:`get_current_principal`.
:func:`exempt_paths` lists endpoints that bypass auth (health probes).
"""

from __future__ import annotations

import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Set

from fastapi import HTTPException, Request, status


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------


@dataclass
class Principal:
    """The authenticated identity behind a request.

    Built by an :class:`AuthBackend`; consumed by route handlers via
    :func:`get_current_principal`. Carries enough info for audit
    logging and (future) role lookup.
    """

    name: str
    """Raw identity string from the auth source.

    For Windows IWA this is typically ``DOMAIN\\user`` or
    ``user@domain.local``. For API keys this is the human-readable
    ``display_name`` set when the key was minted.
    """

    display_name: str
    """Short human-friendly name shown in the UI (e.g. ``alice``)."""

    domain: Optional[str] = None
    """Domain component when meaningful (Windows only)."""

    groups: List[str] = field(default_factory=list)
    """Group memberships. Empty in Phase 4A; populated by LDAP
    enrichment in Phase 4E."""

    source: str = "none"
    """Which backend authenticated this principal. One of
    ``none``, ``windows``, ``api-key``."""

    is_anonymous: bool = False
    """True for the synthetic principal returned by :class:`NoAuth`."""


# Parse ``DOMAIN\\user``, ``DOMAIN/user``, or ``user@domain`` shapes that
# Windows IWA / IIS commonly produces in ``REMOTE_USER``.
_DOMAIN_BACKSLASH = re.compile(r"^(?P<domain>[^\\/@]+)[\\/](?P<user>[^\\/@]+)$")
_USER_AT_DOMAIN = re.compile(r"^(?P<user>[^@\\/]+)@(?P<domain>[^@\\/]+)$")


def parse_windows_identity(raw: str) -> Principal:
    """Split a ``REMOTE_USER`` value into display_name + domain."""
    raw = raw.strip()
    if not raw:
        raise ValueError("empty REMOTE_USER")

    m = _DOMAIN_BACKSLASH.match(raw)
    if m:
        return Principal(
            name=raw,
            display_name=m.group("user"),
            domain=m.group("domain"),
            source="windows",
        )

    m = _USER_AT_DOMAIN.match(raw)
    if m:
        return Principal(
            name=raw,
            display_name=m.group("user"),
            domain=m.group("domain"),
            source="windows",
        )

    # No domain part — just use the raw value as the display name.
    return Principal(name=raw, display_name=raw, domain=None, source="windows")


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------


class AuthBackend(ABC):
    """Resolve a :class:`Principal` for an incoming request, or raise.

    Backends raise :class:`fastapi.HTTPException` with 401 to indicate
    "this caller is not authenticated by this method." A composite
    backend swallows 401 from one method to try the next.
    """

    @abstractmethod
    async def authenticate(self, request: Request) -> Principal:
        ...


class NoAuth(AuthBackend):
    """Returns a synthetic ``anonymous`` principal for every request.

    Default in dev/test. Never selected for production deployments;
    the startup-safety check (Phase 4C) refuses to bind to non-localhost
    when this backend is in use combined with a wider bind address.
    """

    async def authenticate(self, request: Request) -> Principal:
        return Principal(
            name="anonymous",
            display_name="anonymous",
            domain=None,
            source="none",
            is_anonymous=True,
        )


class ReverseProxyAuth(AuthBackend):
    """Trusts a username header forwarded by a reverse proxy (IIS / nginx).

    The proxy is expected to perform the actual authentication (Windows
    Integrated / Negotiate / Kerberos / NTLM) and forward the resulting
    username to ADMZ in a header. ADMZ never sees the Negotiate
    handshake itself — keeps Python-side Windows dependencies at zero.

    Trust model: the header is only honored when the request originates
    from one of the configured ``trusted_proxies`` IP addresses. uvicorn
    is expected to bind to localhost only (the default in production
    mode) so the only path to setting the header is via the local
    reverse proxy.

    The header value is parsed by :func:`parse_windows_identity`.
    Missing / empty header → 401. Untrusted source IP → 401.
    """

    def __init__(
        self,
        header: str = "REMOTE_USER",
        trusted_proxies: Optional[Set[str]] = None,
    ):
        self.header = header
        self.trusted_proxies = trusted_proxies or {"127.0.0.1", "::1"}

    @classmethod
    def from_env(cls) -> "ReverseProxyAuth":
        header = os.getenv("ADMZ_AUTH_REMOTE_USER_HEADER", "REMOTE_USER")
        raw_proxies = os.getenv("ADMZ_AUTH_TRUSTED_PROXIES", "127.0.0.1,::1")
        proxies = {p.strip() for p in raw_proxies.split(",") if p.strip()}
        return cls(header=header, trusted_proxies=proxies)

    async def authenticate(self, request: Request) -> Principal:
        client_host = request.client.host if request.client else None
        if client_host not in self.trusted_proxies:
            logger.warning(
                "ReverseProxyAuth: request from untrusted source %r; "
                "trusted_proxies=%s",
                client_host,
                sorted(self.trusted_proxies),
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Request did not originate from a trusted reverse proxy. "
                    "ADMZ refuses to honor the auth header when uvicorn is "
                    "reachable from outside the reverse proxy."
                ),
            )

        # FastAPI's Headers is case-insensitive on lookup.
        raw = request.headers.get(self.header, "").strip()
        if not raw:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    f"Missing or empty {self.header} header. The reverse "
                    "proxy must be configured to forward the authenticated "
                    "username."
                ),
                headers={"WWW-Authenticate": "Negotiate"},
            )

        try:
            return parse_windows_identity(raw)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Could not parse {self.header} header: {e}",
            )


class ApiKeyAuth(AuthBackend):
    """Authenticate via ``Authorization: Bearer admz_<...>`` header.

    Keys are minted in the web UI (or via CLI in a future iteration) by
    a Windows-authenticated operator. Stored hashed at rest in the
    ``api_keys`` SQLite table; see :mod:`admz.api_keys` for the store.

    The principal's ``name`` is the key's ``display_name`` (e.g.
    ``"nightly-snapshot-bot"``) and ``groups`` is the snapshot of the
    creator's AD groups (so RBAC can fire on either humans or agents
    that have been granted equivalent group membership).
    """

    def __init__(self, store=None):
        # Build a fresh ApiKeyStore reading the current env each time
        # from_env() is called. The module-level api_key_store singleton
        # is created at import time, which doesn't pick up env changes
        # (e.g. when tests redirect ADMZ_DB_PATH after import). Building
        # fresh keeps the auth backend correct under those conditions
        # without changing the broader singleton pattern.
        if store is None:
            from admz.api_keys import ApiKeyStore
            store = ApiKeyStore()
        self._store = store

    @classmethod
    def from_env(cls) -> "ApiKeyAuth":
        return cls()

    async def authenticate(self, request: Request) -> Principal:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or malformed Authorization header.",
                headers={"WWW-Authenticate": 'Bearer realm="ADMZ"'},
            )

        token = auth_header[len("Bearer "):].strip()
        from admz.api_keys import looks_like_api_key
        if not looks_like_api_key(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer token is not an ADMZ API key.",
                headers={"WWW-Authenticate": 'Bearer realm="ADMZ"'},
            )

        api_key = self._store.authenticate(token)
        if api_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid, expired, or revoked API key.",
                headers={"WWW-Authenticate": 'Bearer realm="ADMZ"'},
            )

        return Principal(
            name=f"api-key:{api_key.display_name}",
            display_name=api_key.display_name,
            domain=None,
            groups=list(api_key.groups),
            source="api-key",
        )


class CompositeAuth(AuthBackend):
    """Try multiple backends in order; succeed if any succeeds.

    Order matters: ``Authorization: Bearer ...`` is checked before
    Windows IWA because (a) it's a more explicit signal of intent, and
    (b) a browser making AJAX calls won't include a Bearer header so
    the API-key check is cheap when irrelevant.

    Each backend raises HTTPException(401) on failure; the composite
    swallows 401s from earlier backends to try the next. The last
    backend's exception (or a synthesized "no method matched") is
    re-raised.
    """

    def __init__(self, backends: List[AuthBackend]):
        if not backends:
            raise ValueError("CompositeAuth requires at least one backend")
        self.backends = backends

    @classmethod
    def from_env(cls) -> "CompositeAuth":
        # Default composite: API key first, then Windows IWA.
        # Operators can opt out of either side by selecting the bare
        # ``api-key`` or ``windows`` backend instead.
        return cls([ApiKeyAuth.from_env(), ReverseProxyAuth.from_env()])

    async def authenticate(self, request: Request) -> Principal:
        last_exc: Optional[HTTPException] = None
        for backend in self.backends:
            try:
                return await backend.authenticate(request)
            except HTTPException as exc:
                if exc.status_code != status.HTTP_401_UNAUTHORIZED:
                    raise
                last_exc = exc
        # All backends rejected; surface the last one's detail so the
        # client at least sees *some* WWW-Authenticate header.
        raise last_exc or HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No auth method matched.",
        )


# ---------------------------------------------------------------------------
# Exempt paths
# ---------------------------------------------------------------------------


# Paths the auth middleware bypasses entirely. Health probes need to be
# reachable by the reverse proxy without credentials so it can detect
# when uvicorn is down. Static assets and the OpenAPI/Swagger UIs are
# exempt for usability — they expose no business data.
_EXEMPT_PATH_PREFIXES = (
    "/health",
    "/api/health",
    "/static/",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
)


def exempt_paths() -> tuple:
    """Tuple of URL path prefixes that bypass authentication."""
    return _EXEMPT_PATH_PREFIXES


def is_exempt(path: str) -> bool:
    """True if ``path`` is in the auth-bypass list."""
    return any(path == p or path.startswith(p) for p in _EXEMPT_PATH_PREFIXES)


# ---------------------------------------------------------------------------
# Factory + env-var configuration
# ---------------------------------------------------------------------------


_VALID_BACKENDS = {"none", "windows", "api-key", "composite"}


def _resolve_backend_name(env_value: Optional[str] = None) -> str:
    raw = env_value if env_value is not None else os.getenv(
        "ADMZ_AUTH_BACKEND", "none"
    )
    norm = (raw or "none").strip().lower()
    if norm in _VALID_BACKENDS:
        return norm
    logger.warning(
        "ADMZ_AUTH_BACKEND=%r is not recognized — falling back to 'none'. "
        "Valid: %s",
        raw,
        sorted(_VALID_BACKENDS),
    )
    return "none"


def build_auth_backend(name: Optional[str] = None) -> AuthBackend:
    """Construct the configured backend.

    ``name`` defaults to the ``ADMZ_AUTH_BACKEND`` env var (or
    ``"none"``). The ``windows`` / ``api-key`` / ``composite`` options
    will land in Phases 4B and 4B′; calling them here falls back to
    NoAuth with a warning so partial deploys don't break.
    """
    resolved = _resolve_backend_name(name)
    if resolved == "none":
        return NoAuth()

    # 4B / 4B′ implementations are wired in below as those phases land.
    # Stub fallthrough keeps 4A useful on its own.
    try:
        if resolved == "windows":
            return ReverseProxyAuth.from_env()
        if resolved == "api-key":
            return ApiKeyAuth.from_env()
        if resolved == "composite":
            return CompositeAuth.from_env()
    except NameError:  # pragma: no cover — phase-gated
        logger.warning(
            "ADMZ_AUTH_BACKEND=%s requested but its implementation isn't "
            "wired in yet; falling back to NoAuth.",
            resolved,
        )
        return NoAuth()

    return NoAuth()  # pragma: no cover — unreachable given _VALID_BACKENDS


# ---------------------------------------------------------------------------
# FastAPI integration
# ---------------------------------------------------------------------------


# Singleton built at app-startup; tests override via dependency_overrides.
_ACTIVE_BACKEND: Optional[AuthBackend] = None


def set_active_backend(backend: AuthBackend) -> None:
    """Install ``backend`` as the process-wide active backend."""
    global _ACTIVE_BACKEND
    _ACTIVE_BACKEND = backend


def get_active_backend() -> AuthBackend:
    """Return the active backend, building from env if not yet set."""
    global _ACTIVE_BACKEND
    if _ACTIVE_BACKEND is None:
        _ACTIVE_BACKEND = build_auth_backend()
    return _ACTIVE_BACKEND


async def get_current_principal(request: Request) -> Principal:
    """FastAPI dependency: return the principal authenticated by the
    middleware.

    The actual auth work happens in :func:`auth_middleware` so each
    request authenticates once and routes can grab the principal off
    ``request.state`` without re-running the backend. This dependency
    just exposes the stashed principal to handlers that want to read
    it (e.g. for audit logging).

    Exempt paths short-circuit to a synthetic anonymous principal so
    the same dependency can sit on health endpoints.
    """
    if is_exempt(request.url.path):
        return Principal(
            name="anonymous",
            display_name="anonymous",
            source="none",
            is_anonymous=True,
        )

    principal = getattr(request.state, "principal", None)
    if principal is None:
        # The middleware didn't run, or the route is reached via a
        # path the middleware didn't cover. Authenticate now as a
        # safety net.
        backend = get_active_backend()
        principal = await backend.authenticate(request)
        request.state.principal = principal
    return principal


async def auth_middleware(request: Request, call_next):
    """ASGI middleware: authenticate every non-exempt request once.

    On success, stashes the principal on ``request.state.principal``
    so :func:`get_current_principal` can return it without re-running
    the backend.

    On :class:`HTTPException` (typically 401), returns a JSON response
    with the exception's headers (``WWW-Authenticate: Negotiate`` /
    ``Bearer realm="ADMZ"``) so the browser knows to prompt.
    """
    from fastapi.responses import JSONResponse

    if is_exempt(request.url.path):
        return await call_next(request)

    backend = get_active_backend()
    try:
        principal = await backend.authenticate(request)
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers or {},
        )

    request.state.principal = principal
    return await call_next(request)


__all__ = [
    "Principal",
    "AuthBackend",
    "NoAuth",
    "ReverseProxyAuth",
    "ApiKeyAuth",
    "CompositeAuth",
    "parse_windows_identity",
    "exempt_paths",
    "is_exempt",
    "build_auth_backend",
    "set_active_backend",
    "get_active_backend",
    "get_current_principal",
    "auth_middleware",
]
