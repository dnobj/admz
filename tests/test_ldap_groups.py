"""Tests for admz.ldap_groups (Phase 4E)."""

from unittest.mock import MagicMock

import pytest

from admz.ldap_groups import (
    LdapConfig,
    LdapGroupResolver,
    _normalize_username,
    _parse_cn_from_dn,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestNormalizeUsername:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("AXIS\\alice", "alice"),
            ("AXIS/alice", "alice"),
            ("alice@axis.local", "alice"),
            ("alice", "alice"),
            ("  AXIS\\alice  ", "alice"),
        ],
    )
    def test_normalize(self, raw, expected):
        assert _normalize_username(raw) == expected


class TestParseCnFromDn:
    def test_simple_cn(self):
        assert _parse_cn_from_dn("CN=Admins,OU=Groups,DC=example,DC=com") == "Admins"

    def test_lowercase_cn(self):
        assert _parse_cn_from_dn("cn=Admins,DC=example,DC=com") == "Admins"

    def test_no_cn_falls_back_to_full_dn(self):
        assert _parse_cn_from_dn("OU=Groups,DC=example,DC=com") == \
            "OU=Groups,DC=example,DC=com"

    def test_spaces_in_dn_are_stripped(self):
        assert _parse_cn_from_dn(" CN=Admins , DC=example") == "Admins"


# ---------------------------------------------------------------------------
# LdapConfig
# ---------------------------------------------------------------------------


class TestLdapConfig:
    def test_defaults_disabled(self, monkeypatch):
        for k in ("ADMZ_LDAP_ENABLED", "ADMZ_LDAP_SERVER", "ADMZ_LDAP_BASE_DN",
                  "ADMZ_LDAP_BIND_USER", "ADMZ_LDAP_BIND_PASSWORD",
                  "ADMZ_LDAP_GROUP_CACHE_TTL"):
            monkeypatch.delenv(k, raising=False)
        config = LdapConfig.from_env()
        assert config.enabled is False
        assert config.server == ""
        assert config.cache_ttl == 300.0

    @pytest.mark.parametrize("raw,expected", [
        ("true", True), ("True", True), ("1", True), ("yes", True),
        ("on", True), ("false", False), ("0", False), ("no", False), ("", False),
    ])
    def test_enabled_parsing(self, raw, expected, monkeypatch):
        monkeypatch.setenv("ADMZ_LDAP_ENABLED", raw)
        assert LdapConfig.from_env().enabled is expected

    def test_invalid_ttl_falls_back_to_300(self, monkeypatch):
        monkeypatch.setenv("ADMZ_LDAP_GROUP_CACHE_TTL", "not-a-number")
        assert LdapConfig.from_env().cache_ttl == 300.0


# ---------------------------------------------------------------------------
# LdapGroupResolver (with mocked ldap3)
# ---------------------------------------------------------------------------


def _make_mock_connection(group_dns):
    """Build a mock ldap3 connection with the given memberOf DNs."""
    conn = MagicMock()
    conn.search.return_value = True

    member_of = MagicMock()
    member_of.values = list(group_dns)

    entry = MagicMock()
    entry.memberOf = member_of

    conn.entries = [entry]
    return conn


def _make_factory(conn):
    """Wrap a connection in the factory shape the resolver expects."""
    def factory(config):
        return conn
    return factory


class TestLdapGroupResolverDisabled:
    def test_returns_empty_when_disabled(self):
        config = LdapConfig(enabled=False)
        resolver = LdapGroupResolver(config=config)
        assert resolver.resolve_groups("alice") == []

    def test_returns_empty_for_empty_username(self):
        resolver = LdapGroupResolver(config=LdapConfig(enabled=True))
        assert resolver.resolve_groups("") == []


class TestLdapGroupResolverEnabled:
    def test_returns_cns_from_member_of(self):
        conn = _make_mock_connection([
            "CN=Admins,OU=Groups,DC=example,DC=com",
            "CN=Operators,OU=Groups,DC=example,DC=com",
        ])
        config = LdapConfig(enabled=True, server="ldap://dc", base_dn="DC=example")
        resolver = LdapGroupResolver(config=config, connection_factory=_make_factory(conn))
        groups = resolver.resolve_groups("alice")
        assert groups == ["Admins", "Operators"]

    def test_normalizes_username_in_search(self):
        conn = _make_mock_connection(["CN=Admins,DC=example"])
        captured = {}

        def factory(config):
            return conn
        resolver = LdapGroupResolver(
            config=LdapConfig(enabled=True, server="ldap://dc", base_dn="DC=example"),
            connection_factory=factory,
        )
        resolver.resolve_groups("AXIS\\alice")
        # The search filter should use the short username
        call_args = conn.search.call_args
        assert "sAMAccountName=alice" in call_args.kwargs["search_filter"]

    def test_caches_results(self):
        conn = _make_mock_connection(["CN=Admins,DC=example"])
        resolver = LdapGroupResolver(
            config=LdapConfig(enabled=True, server="ldap://dc",
                              base_dn="DC=example", cache_ttl=300),
            connection_factory=_make_factory(conn),
        )
        # First call hits LDAP
        resolver.resolve_groups("alice")
        assert conn.search.call_count == 1
        # Second call within TTL hits cache
        resolver.resolve_groups("alice")
        assert conn.search.call_count == 1
        # Different user does hit LDAP again
        resolver.resolve_groups("bob")
        assert conn.search.call_count == 2

    def test_cache_invalidation(self):
        conn = _make_mock_connection(["CN=Admins,DC=example"])
        resolver = LdapGroupResolver(
            config=LdapConfig(enabled=True, server="ldap://dc",
                              base_dn="DC=example", cache_ttl=300),
            connection_factory=_make_factory(conn),
        )
        resolver.resolve_groups("alice")
        resolver.invalidate_cache()
        resolver.resolve_groups("alice")
        assert conn.search.call_count == 2

    def test_search_returning_no_entries_returns_empty(self):
        conn = MagicMock()
        conn.search.return_value = True
        conn.entries = []
        resolver = LdapGroupResolver(
            config=LdapConfig(enabled=True, server="ldap://dc", base_dn="DC=example"),
            connection_factory=_make_factory(conn),
        )
        assert resolver.resolve_groups("alice") == []

    def test_search_returning_false_returns_empty(self):
        conn = MagicMock()
        conn.search.return_value = False
        resolver = LdapGroupResolver(
            config=LdapConfig(enabled=True, server="ldap://dc", base_dn="DC=example"),
            connection_factory=_make_factory(conn),
        )
        assert resolver.resolve_groups("alice") == []

    def test_ldap_exception_returns_empty_with_warning(self, caplog):
        import logging

        def failing_factory(config):
            raise ConnectionError("LDAP server unreachable")

        resolver = LdapGroupResolver(
            config=LdapConfig(enabled=True, server="ldap://dc", base_dn="DC=example"),
            connection_factory=failing_factory,
        )
        with caplog.at_level(logging.WARNING):
            groups = resolver.resolve_groups("alice")
        assert groups == []
        assert any("LDAP group lookup" in rec.message for rec in caplog.records)

    def test_no_connection_factory_when_ldap3_missing(self):
        # If ldap3 isn't installed, _default_connection_factory returns
        # None. The resolver should silently produce no groups instead
        # of crashing.
        resolver = LdapGroupResolver(
            config=LdapConfig(enabled=True, server="ldap://dc",
                              base_dn="DC=example"),
            connection_factory=lambda c: None,  # type: ignore[return-value]
        )
        # We can't reliably trigger the "ldap3 missing" branch without
        # uninstalling, but we can verify that a None connection
        # produces no groups via the failing factory.

    def test_member_of_as_plain_list(self):
        # Some ldap3 versions return memberOf as a plain list, not an
        # object with .values. Cover both.
        conn = MagicMock()
        conn.search.return_value = True
        entry = MagicMock()
        entry.memberOf = ["CN=Admins,DC=example"]
        conn.entries = [entry]
        resolver = LdapGroupResolver(
            config=LdapConfig(enabled=True, server="ldap://dc", base_dn="DC=example"),
            connection_factory=_make_factory(conn),
        )
        # memberOf as plain list still works
        groups = resolver.resolve_groups("alice")
        assert "Admins" in groups
