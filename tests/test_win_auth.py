"""Tests for admz.win_auth — Windows credential validation (ADR-0033).

The LogonUserW happy path needs a real password, which tests must never
hold — so success-path behavior is covered via the mocked backend tests
in test_windows_local_backend.py. Here we pin the pure helpers plus the
two live paths that are safe on a Windows runner: a definitively-bad
logon (returns None, never raises) and the platform guard.
"""

import sys

import pytest

from admz.win_auth import (
    WinAuthUnavailable,
    WindowsIdentity,
    _split_identity,
    _strip_authority,
    validate_windows_credentials,
)


class TestIdentityParsing:
    def test_bare_username_is_local(self):
        assert _split_identity("alice", None) == ("alice", ".")

    def test_backslash_domain(self):
        assert _split_identity("HOMELAB\\alice", None) == ("alice", "HOMELAB")

    def test_forward_slash_domain(self):
        assert _split_identity("HOMELAB/alice", None) == ("alice", "HOMELAB")

    def test_upn_form(self):
        assert _split_identity("alice@corp.local", None) == (
            "alice", "corp.local",
        )

    def test_explicit_domain_wins(self):
        assert _split_identity("alice", "CORP") == ("alice", "CORP")

    def test_strip_authority(self):
        assert _strip_authority("BUILTIN\\Administrators") == "Administrators"
        assert _strip_authority("Administrators") == "Administrators"
        assert _strip_authority("NT AUTHORITY\\INTERACTIVE") == "INTERACTIVE"


class TestValidate:
    def test_empty_credentials_return_none(self):
        if sys.platform != "win32":
            pytest.skip("Windows-only")
        assert validate_windows_credentials("", "x") is None
        assert validate_windows_credentials("alice", "") is None

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
    def test_bad_credentials_return_none_live(self):
        # A user that cannot exist + wrong password: LogonUserW returns
        # ERROR_LOGON_FAILURE and we map it to None (not an exception).
        result = validate_windows_credentials(
            "admz_test_no_such_user_xyz", "definitely-wrong",
        )
        assert result is None

    @pytest.mark.skipif(sys.platform == "win32", reason="non-Windows only")
    def test_unavailable_off_windows(self):
        with pytest.raises(WinAuthUnavailable):
            validate_windows_credentials("alice", "pw")

    def test_identity_dataclass_shape(self):
        ident = WindowsIdentity(
            username="alice", domain=None, groups=["Administrators"],
        )
        assert ident.username == "alice"
        assert ident.domain is None
        assert ident.groups == ["Administrators"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
class TestTokenGroupsLive:
    def test_current_process_token_groups_resolve(self):
        """Exercise the ctypes TOKEN_GROUPS layout against a real token
        (the current process's own) — no credentials involved."""
        import ctypes
        from ctypes import wintypes

        from admz.win_auth import _declare_prototypes, _groups_from_token

        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        _declare_prototypes(advapi32, kernel32)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        advapi32.OpenProcessToken.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE),
        ]
        advapi32.OpenProcessToken.restype = wintypes.BOOL

        token = wintypes.HANDLE()
        assert advapi32.OpenProcessToken(
            kernel32.GetCurrentProcess(), 0x0008, ctypes.byref(token)
        )
        try:
            groups = _groups_from_token(token, advapi32, kernel32)
        finally:
            kernel32.CloseHandle(token)
        assert isinstance(groups, list) and groups
        # Every interactive Windows token carries at least one of these.
        assert any(
            g in ("Users", "Administrators", "Everyone") for g in groups
        ), groups


class TestGroupMerging:
    def test_merge_strips_authority_and_dedupes(self):
        from admz.win_auth import merge_group_names

        merged = merge_group_names(
            ["Users", "docker-users"],
            ["BUILTIN\\Administrators", "BUILTIN\\Users", "Administrators"],
        )
        assert merged == ["Users", "docker-users", "Administrators"]

    def test_merge_preserves_token_order_first(self):
        from admz.win_auth import merge_group_names

        assert merge_group_names(["B", "A"], ["C"]) == ["B", "A", "C"]

    def test_enriched_groups_survives_lookup_failure(self, monkeypatch):
        """Directory lookup failing must never break a login."""
        import admz.win_auth as win_auth

        def boom(username, domain=None):
            raise RuntimeError("netapi32 unavailable")

        monkeypatch.setattr(win_auth, "local_group_memberships", boom)
        assert win_auth.enriched_groups(["Users"], "alice", None) == ["Users"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
class TestLocalGroupMembershipsLive:
    def test_current_user_memberships(self):
        """The UAC-filtering workaround (KL-AUTH-009): the directory view
        must include the local groups even when a network-logon token
        would carry them deny-only."""
        import os

        from admz.win_auth import local_group_memberships

        groups = local_group_memberships(os.environ["USERNAME"])
        assert isinstance(groups, list) and groups
        assert any(g in ("Users", "Administrators") for g in groups), groups

    def test_unknown_user_returns_empty(self):
        from admz.win_auth import local_group_memberships

        assert local_group_memberships("no-such-user-zzz-12345") == []
