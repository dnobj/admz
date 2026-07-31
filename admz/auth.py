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

A fourth, **test auth**, is not an ``ADMZ_AUTH_BACKEND`` value at all: it
is the ``dev.test_auth`` advanced capability (GH #140), enabled only by
``ADMZ_TEST_AUTH=1``, which appends :class:`TestAuth` to whatever chain is
configured so an unattended agent resolves to a fixed synthetic principal
instead of a sign-in page. The server refuses to start with it active on a
non-loopback bind.

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

    Default in dev/test. The startup-safety check in
    :func:`admz.__main__._check_bind_safety` refuses to bind to
    non-localhost when ``ADMZ_AUTH_BACKEND in (windows, composite)`` —
    i.e. when reverse-proxy auth would otherwise be trusting a header
    that could be spoofed.

    Under ``NoAuth`` itself, the localhost-bind default
    (``--host 127.0.0.1``) is what bounds the exposure. The lifespan
    in :mod:`admz.api.main` emits a one-time WARNING when this
    backend is active so operators are reminded that the
    anonymous principal has full write access (and audit rows
    will attribute every mutation to ``anonymous``). The five most
    destructive endpoints (mint API key, write protected fleet
    settings, delete device, restore device, execute plan) refuse
    the anonymous principal via :func:`admz.authz.require_authenticated_principal`.
    """

    async def authenticate(self, request: Request) -> Principal:
        return Principal(
            name="anonymous",
            display_name="anonymous",
            domain=None,
            source="none",
            is_anonymous=True,
        )


#: The synthetic identity :class:`TestAuth` hands out. Deliberately not a
#: shape any real directory produces — a ``test\\`` domain does not exist, so
#: an audit row or a "Signed in as" badge reading ``test\agent`` is
#: unmistakable at a glance.
TEST_AUTH_DEFAULT_NAME = "test\\agent"

#: Default group membership: **none**, deliberately.
#:
#: A principal is all an unattended verification run needs — the surfaces it
#: exercises require *authentication*, not *administration*. Granting reveal
#: groups by default would let a synthetic, unauthenticated-by-design caller
#: read plaintext device credentials, and a staging instance typically carries
#: a copy of the real ones. Least privilege is the right default precisely
#: because the cases needing more are not known in advance.
#:
#: Grant membership explicitly with ``ADMZ_TEST_AUTH_GROUPS`` when a specific
#: authz path has to be exercised. See ``test_reveal_denied_by_default``.
TEST_AUTH_DEFAULT_GROUPS: tuple = ()


def _is_loopback(host: Optional[str]) -> bool:
    """True iff ``host`` is a loopback address (or the literal ``localhost``).

    Deliberately stricter than a ``in ("127.0.0.1", "::1")`` membership test:
    the whole ``127.0.0.0/8`` block is loopback, and an address that does not
    parse at all is *not* trusted. Shared by the per-request check below and
    the startup refusal in :mod:`admz.__main__`.
    """
    if not host:
        return False
    host = host.strip().strip("[]")
    if host.lower() == "localhost":
        return True
    try:
        import ipaddress

        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class TestAuth(AuthBackend):
    """Authenticates every request as a fixed synthetic principal (GH #140).

    **Registered as the ``dev.test_auth`` advanced capability**, danger class
    ``dev-only`` and env-only per the registry's asymmetry rule — it can never
    be flipped from a browser. :func:`build_auth_backend` appends it to the
    configured chain only while :func:`admz.capabilities.is_active` says so.

    Why it exists: ADMZ deployments authenticate with ``windows-local``
    (ADR-0035 Negotiate SSO), which a headless client cannot complete, so an
    agent verifying the UI lands on the sign-in page and stops.
    ``ADMZ_AUTH_BACKEND=none`` is not a workaround — its principal is
    ``is_anonymous``, and every :func:`admz.authz.require_authenticated_principal`
    surface (demo CRUD, the inference endpoints, capability listing) refuses
    it. This backend yields a **real** :class:`Principal` of exactly the shape
    :class:`SessionAuth` produces, so those surfaces behave normally.

    What it is not: a security boundary, and not a way around the
    confirmation gate. ADR-0034 is untouched — a ``url_only`` operation still
    returns ``blocked: true`` under test auth. This changes *who the principal
    is*, never *whether approval is required*.

    Two things bound the exposure, and they are the reason this is safe enough
    to ship:

    * ``admz/__main__.py::_check_test_auth_bind`` **refuses to start** when
      the capability is active and the bind address is not loopback. No
      override — unlike ``ADMZ_AUTH_INSECURE_BIND_OK``, there is no legitimate
      reason to expose a synthetic principal off-box.
    * :meth:`authenticate` re-checks the *client* address on every request, so
      the bypass cannot be reached from off-box even if the server was started
      some other way (a bare ``uvicorn`` invocation, an embedding host). Same
      reasoning as NFR-AUTH-005 for the trusted-proxies check: a startup check
      alone goes stale the moment the network does.
    """

    #: Not a test case. pytest collects any class named ``Test*`` that a test
    #: module imports; this is the same opt-out Starlette's ``TestClient``
    #: uses for exactly the same reason.
    __test__ = False

    def __init__(
        self,
        name: str = TEST_AUTH_DEFAULT_NAME,
        groups: Optional[List[str]] = None,
    ):
        self.name = name or TEST_AUTH_DEFAULT_NAME
        self.groups = (
            list(TEST_AUTH_DEFAULT_GROUPS) if groups is None else list(groups)
        )

    @classmethod
    def from_env(cls) -> "TestAuth":
        """Read the two companion vars declared on the capability row.

        ``ADMZ_TEST_AUTH_GROUPS`` distinguishes *unset* (defaults apply) from
        *set-but-empty* (a principal with no groups), because "authenticated
        but unprivileged" is a case worth being able to test.
        """
        name = os.getenv("ADMZ_TEST_AUTH_USER", "").strip() or TEST_AUTH_DEFAULT_NAME
        raw_groups = os.getenv("ADMZ_TEST_AUTH_GROUPS")
        if raw_groups is None:
            groups = list(TEST_AUTH_DEFAULT_GROUPS)
        else:
            groups = [g.strip() for g in raw_groups.split(",") if g.strip()]
        return cls(name=name, groups=groups)

    def principal(self) -> Principal:
        """The synthetic principal, built the same way a real one is.

        Reuses :func:`parse_windows_identity` for the ``DOMAIN\\user`` split
        rather than inventing a parallel representation, then overrides
        ``source`` so the audit log can tell a test principal from a real
        Windows one at a glance.
        """
        try:
            principal = parse_windows_identity(self.name)
        except ValueError:  # pragma: no cover — name is never empty
            principal = Principal(name=TEST_AUTH_DEFAULT_NAME, display_name="agent")
        principal.groups = list(self.groups)
        principal.source = "test"
        principal.is_anonymous = False
        return principal

    async def authenticate(self, request) -> Principal:
        client_host = getattr(getattr(request, "client", None), "host", None)
        if not _is_loopback(client_host):
            logger.warning(
                "TestAuth: refusing a non-loopback request from %r. "
                "dev.test_auth is active but the synthetic principal is only "
                "ever handed to a caller on this box.",
                client_host,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Test auth (dev.test_auth) only authenticates requests "
                    "originating from loopback."
                ),
            )
        return self.principal()


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
            principal = parse_windows_identity(raw)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Could not parse {self.header} header: {e}",
            )

        # Phase 4E: enrich with AD groups when LDAP is configured.
        # Failures are non-fatal — empty groups, logged warning.
        try:
            from admz.ldap_groups import get_resolver
            resolver = get_resolver()
            if resolver.enabled:
                principal.groups = resolver.resolve_groups(principal.name)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "LDAP group enrichment failed for %r: %s",
                principal.name, exc,
            )

        return principal


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


class SessionAuth(AuthBackend):
    """Authenticates browser requests via the ``admz_session`` cookie.

    The session is minted by the ``/login`` flow (ADR-0033: Windows
    credentials validated in-process via ``LogonUserW``) and stored
    server-side (:mod:`admz.session_store`) — the cookie carries only a
    random bearer token. Works for plain HTTP requests AND WebSocket
    upgrades: both Starlette objects expose ``.cookies`` from the
    handshake headers.
    """

    @classmethod
    def from_env(cls) -> "SessionAuth":
        return cls()

    async def authenticate(self, request) -> Principal:
        from admz.session_store import SESSION_COOKIE, get_session_store

        token = (request.cookies or {}).get(SESSION_COOKIE, "")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not signed in.",
            )
        snapshot = get_session_store().resolve(token)
        if snapshot is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired or revoked — sign in again.",
            )
        return Principal(
            name=snapshot.name,
            display_name=snapshot.display_name,
            domain=snapshot.domain,
            groups=list(snapshot.groups),
            source=snapshot.source,
            is_anonymous=False,
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
        # Default composite: API key first (explicit signal, cheap when
        # absent), then session cookie (browser logins), then Windows IWA
        # headers. Operators can opt out by selecting a bare backend.
        return cls([
            ApiKeyAuth.from_env(),
            SessionAuth.from_env(),
            ReverseProxyAuth.from_env(),
        ])

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
    # The login flow must be reachable unauthenticated (it's where you
    # BECOME authenticated). /logout is exempt so an expired session can
    # still clear its cookie; the route reads the cookie itself.
    "/login",
    "/logout",
    # ACS Pro "Send HTTP Notification" webhook — ACS can't do Negotiate, so this
    # endpoint authenticates itself via a shared secret token (see acs_pro.webhook).
    "/api/acs/rule-fired",
    # GitHub App OAuth callbacks — top-level cross-site GET redirects from GitHub
    # arrive without an ADMZ session; they self-authenticate via an HMAC-signed,
    # short-lived `state` param (see routes/github_app.py).
    "/api/github/setup/callback",
    "/api/github/install/callback",
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


_VALID_BACKENDS = {"none", "windows", "api-key", "composite", "windows-local"}


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


def _apply_test_auth(backend: AuthBackend) -> AuthBackend:
    """Append :class:`TestAuth` to ``backend`` when ``dev.test_auth`` is on.

    Off by default and structurally invisible when off: absent the capability
    this returns the configured backend unchanged, so behaviour is identical
    to an installation that has never heard of test auth.

    When on, the rule is **last resort, never override**:

    * a real credential still wins — ``TestAuth`` goes at the *end* of the
      chain, so an API key or a session cookie authenticates as itself and the
      audit log keeps saying who actually called;
    * under ``ADMZ_AUTH_BACKEND=none`` it *replaces* :class:`NoAuth` rather
      than following it. ``NoAuth`` never fails, so appending would be dead
      code — and the anonymous principal it returns is precisely the thing
      this capability exists to stop handing out (#140: anonymous mode is not
      a workaround because it has no principal).
    """
    from admz import capabilities

    if not capabilities.is_active("dev.test_auth"):
        return backend
    test = TestAuth.from_env()
    if isinstance(backend, NoAuth):
        return test
    if isinstance(backend, CompositeAuth):
        return CompositeAuth([*backend.backends, test])
    return CompositeAuth([backend, test])


def build_auth_backend(name: Optional[str] = None) -> AuthBackend:
    """Construct the configured backend.

    ``name`` defaults to the ``ADMZ_AUTH_BACKEND`` env var (or
    ``"none"``). The ``windows`` / ``api-key`` / ``composite`` options
    will land in Phases 4B and 4B′; calling them here falls back to
    NoAuth with a warning so partial deploys don't break.

    The ``dev.test_auth`` capability (GH #140) layers on top of whatever is
    configured — see :func:`_apply_test_auth`. It is deliberately **not** an
    ``ADMZ_AUTH_BACKEND`` value: a dev-only bypass belongs in the capability
    registry, where it is loud, audited, and impossible to select by accident.
    """
    return _apply_test_auth(_build_configured_backend(name))


def _build_configured_backend(name: Optional[str] = None) -> AuthBackend:
    """The backend ``ADMZ_AUTH_BACKEND`` selects, with no capability layering."""
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
        if resolved == "windows-local":
            # ADR-0033: browsers sign in with Windows credentials at
            # /login (LogonUserW) and carry a session cookie; agents
            # keep Bearer API keys. No trusted-header backend in the
            # chain, so no reverse proxy / bind restriction applies.
            return CompositeAuth([
                ApiKeyAuth.from_env(),
                SessionAuth.from_env(),
            ])
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

    On :class:`HTTPException` (typically 401): browser page loads (the
    request prefers HTML and isn't an ``/api/`` call) are redirected to
    the ``/login`` form with a ``next`` return path; API/agent requests
    get the JSON 401 with the exception's headers
    (``WWW-Authenticate: Negotiate`` / ``Bearer realm="ADMZ"``).
    """
    from fastapi.responses import JSONResponse, RedirectResponse

    if is_exempt(request.url.path):
        return await call_next(request)

    backend = get_active_backend()
    try:
        principal = await backend.authenticate(request)
    except HTTPException as exc:
        path = request.url.path
        accepts_html = "text/html" in request.headers.get("accept", "")
        if (
            exc.status_code == status.HTTP_401_UNAUTHORIZED
            and accepts_html
            and not path.startswith("/api/")
        ):
            from urllib.parse import quote
            nxt = quote(path or "/", safe="/")
            return RedirectResponse(
                url=f"/login?next={nxt}", status_code=303
            )
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
    "SessionAuth",
    "CompositeAuth",
    "TestAuth",
    "TEST_AUTH_DEFAULT_NAME",
    "TEST_AUTH_DEFAULT_GROUPS",
    "parse_windows_identity",
    "exempt_paths",
    "is_exempt",
    "build_auth_backend",
    "set_active_backend",
    "get_active_backend",
    "get_current_principal",
    "auth_middleware",
]
