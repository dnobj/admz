"""LDAP / Active Directory group enrichment for Windows-authenticated
principals (Phase 4E).

IIS forwards the authenticated username via ``REMOTE_USER`` but does NOT
forward group membership by default. To populate ``Principal.groups``
for future role-based access control, ADMZ queries LDAP at auth time.

Configuration is env-driven and entirely **opt-in**::

    ADMZ_LDAP_ENABLED=true
    ADMZ_LDAP_SERVER=ldap://dc.example.com
    ADMZ_LDAP_BASE_DN=DC=example,DC=com
    ADMZ_LDAP_BIND_USER=CN=svc-admz,OU=Service Accounts,DC=example,DC=com
    ADMZ_LDAP_BIND_PASSWORD=...
    ADMZ_LDAP_GROUP_CACHE_TTL=300   # seconds

Workgroup deployments (no domain controller) leave it disabled; groups
stay empty, RBAC isn't available yet, no fallback issue.

Failures are non-fatal — if LDAP is unreachable, malformed, or slow,
the user still authenticates (via REMOTE_USER) but with empty groups
and a logged warning. Auth must not break on a transient LDAP outage.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_username(raw: str) -> str:
    """Reduce ``DOMAIN\\user`` / ``user@domain`` / bare ``user`` to the
    short username for the LDAP search filter."""
    raw = raw.strip()
    if "\\" in raw or "/" in raw:
        return raw.replace("/", "\\").rsplit("\\", 1)[-1]
    if "@" in raw:
        return raw.split("@", 1)[0]
    return raw


def _parse_cn_from_dn(dn: str) -> str:
    """Pull the CN out of a DN like ``CN=Admins,OU=Groups,DC=...``.
    Returns the raw DN if no CN= prefix found."""
    for rdn in dn.split(","):
        rdn = rdn.strip()
        if rdn.lower().startswith("cn="):
            return rdn[3:]
    return dn


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


@dataclass
class _CacheEntry:
    groups: List[str]
    expires_at: float


class _GroupCache:
    """Thread-safe TTL cache keyed by normalized username."""

    def __init__(self, ttl: float):
        self.ttl = ttl
        self._lock = threading.Lock()
        self._entries: Dict[str, _CacheEntry] = {}

    def get(self, key: str) -> Optional[List[str]]:
        now = time.time()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._entries.pop(key, None)
                return None
            return list(entry.groups)

    def put(self, key: str, groups: List[str]) -> None:
        with self._lock:
            self._entries[key] = _CacheEntry(
                groups=list(groups),
                expires_at=time.time() + self.ttl,
            )

    def invalidate(self) -> None:
        with self._lock:
            self._entries.clear()


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


@dataclass
class LdapConfig:
    enabled: bool = False
    server: str = ""
    base_dn: str = ""
    bind_user: str = ""
    bind_password: str = ""
    cache_ttl: float = 300.0

    @classmethod
    def from_env(cls) -> "LdapConfig":
        raw_enabled = os.getenv("ADMZ_LDAP_ENABLED", "false").strip().lower()
        enabled = raw_enabled in ("1", "true", "yes", "on")
        try:
            ttl = float(os.getenv("ADMZ_LDAP_GROUP_CACHE_TTL", "300"))
        except ValueError:
            ttl = 300.0
        return cls(
            enabled=enabled,
            server=os.getenv("ADMZ_LDAP_SERVER", ""),
            base_dn=os.getenv("ADMZ_LDAP_BASE_DN", ""),
            bind_user=os.getenv("ADMZ_LDAP_BIND_USER", ""),
            bind_password=os.getenv("ADMZ_LDAP_BIND_PASSWORD", ""),
            cache_ttl=ttl,
        )


class LdapGroupResolver:
    """Resolve a username -> list of AD group CNs.

    Cheap in the common case (cache hit). On miss, opens a fresh
    connection, search-binds as the service account, queries
    ``(&(objectClass=user)(sAMAccountName=<user>))`` for ``memberOf``,
    closes the connection.
    """

    def __init__(self, config: Optional[LdapConfig] = None, connection_factory=None):
        self.config = config or LdapConfig.from_env()
        self._cache = _GroupCache(ttl=self.config.cache_ttl)
        # Injection seam for tests — defaults to ldap3 if available.
        self._connection_factory = connection_factory

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def invalidate_cache(self) -> None:
        self._cache.invalidate()

    def resolve_groups(self, username: str) -> List[str]:
        """Look up the user's group CNs.

        Returns an empty list on any error / disabled state — never
        raises. The caller is expected to attach the result to the
        Principal without treating "no groups" as a failure.
        """
        if not self.config.enabled:
            return []
        if not username:
            return []

        key = _normalize_username(username)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        try:
            groups = self._lookup(key)
        except Exception as exc:
            logger.warning(
                "LDAP group lookup for %r failed: %s — returning empty groups",
                username, exc,
            )
            return []

        self._cache.put(key, groups)
        return groups

    # -- internal -------------------------------------------------------

    def _lookup(self, sam_account_name: str) -> List[str]:
        """Open a connection, query, return CN list. Caller wraps in
        try/except for resilience."""
        factory = self._connection_factory or self._default_connection_factory()
        if factory is None:
            return []
        conn = factory(self.config)
        try:
            search_filter = (
                f"(&(objectClass=user)(sAMAccountName={sam_account_name}))"
            )
            ok = conn.search(
                search_base=self.config.base_dn,
                search_filter=search_filter,
                attributes=["memberOf"],
            )
            if not ok:
                logger.info(
                    "LDAP search for %r returned no entries", sam_account_name
                )
                return []
            entries = list(getattr(conn, "entries", []) or [])
            if not entries:
                return []
            member_of = entries[0].memberOf
            # ldap3 returns either a list or a single value depending on the
            # underlying attribute. Normalize.
            if hasattr(member_of, "values"):
                raw_dns = list(member_of.values)
            elif isinstance(member_of, list):
                raw_dns = member_of
            else:
                raw_dns = [str(member_of)] if member_of else []
            return [_parse_cn_from_dn(str(dn)) for dn in raw_dns]
        finally:
            try:
                conn.unbind()
            except Exception:
                pass

    @staticmethod
    def _default_connection_factory():
        """Returns a callable(config) -> bound connection, or None if
        ldap3 is not installed (LDAP is optional)."""
        try:
            from ldap3 import Server, Connection, ALL  # noqa: F401
        except ImportError:
            logger.warning(
                "ldap3 package not installed; LDAP enrichment unavailable. "
                "Install with: pip install ldap3"
            )
            return None

        def factory(config: LdapConfig):
            server = Server(config.server, get_info="ALL")
            conn = Connection(
                server,
                user=config.bind_user or None,
                password=config.bind_password or None,
                auto_bind=True,
            )
            return conn

        return factory


# ---------------------------------------------------------------------------
# Module-level resolver (built lazily, env-driven)
# ---------------------------------------------------------------------------


_resolver: Optional[LdapGroupResolver] = None
_resolver_lock = threading.Lock()


def get_resolver() -> LdapGroupResolver:
    """Module-level lazy singleton matching the rest of the ADMZ store pattern."""
    global _resolver
    if _resolver is None:
        with _resolver_lock:
            if _resolver is None:
                _resolver = LdapGroupResolver()
    return _resolver


def reset_resolver() -> None:
    """Reset the singleton — used by tests after env changes."""
    global _resolver
    with _resolver_lock:
        _resolver = None
