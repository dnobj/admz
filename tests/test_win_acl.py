"""Tests for admz.win_acl (issue #207).

Note the platform split, which is the point of the module:

* :func:`build_secret_file_sddl` and the ``Ace`` predicates are pure and
  run on **every** platform — so the ubuntu CI leg exercises the new code
  rather than skipping all of it. That also pins the "module imports on
  POSIX" property, which is why ``win_acl`` uses plain ctypes types
  instead of ``ctypes.wintypes`` (the latter is not importable off
  Windows: ``VARIANT_BOOL``'s ``"v"`` type code is Windows-only).
* The calls that need ``advapi32`` are Windows-only and raise
  :class:`WinAclUnavailable` elsewhere, asserted below on POSIX.
"""

import sys

import pytest

from admz.win_acl import (
    ACCESS_ALLOWED_ACE_TYPE,
    ACCESS_DENIED_ACE_TYPE,
    Ace,
    FileDacl,
    SID_ADMINISTRATORS,
    SID_AUTHENTICATED_USERS,
    SID_EVERYONE,
    SID_SYSTEM,
    SID_USERS,
    WinAclUnavailable,
    build_secret_file_sddl,
)


class TestSddl:
    """Pure — runs on every platform, including the ubuntu CI leg."""

    def test_dacl_is_protected(self):
        """``D:P`` is the whole fix — without P the parent ACEs come back."""
        sddl = build_secret_file_sddl("S-1-5-21-1-2-3-1001")
        assert sddl.startswith("D:P")

    def test_grants_system_and_administrators_and_owner(self):
        sddl = build_secret_file_sddl("S-1-5-21-1-2-3-1001")
        assert f"(A;;FA;;;{SID_SYSTEM})" in sddl
        assert f"(A;;FA;;;{SID_ADMINISTRATORS})" in sddl
        assert "(A;;FRFW;;;S-1-5-21-1-2-3-1001)" in sddl

    def test_grants_nothing_broader(self):
        sddl = build_secret_file_sddl("S-1-5-21-1-2-3-1001")
        for broad in (SID_EVERYONE, SID_USERS, SID_AUTHENTICATED_USERS):
            assert broad not in sddl

    def test_localsystem_owner_is_not_duplicated(self):
        """The admz service runs as LocalSystem (ADR-0042), so this is
        the shape a service-created key actually gets."""
        sddl = build_secret_file_sddl(SID_SYSTEM)
        assert sddl.count(SID_SYSTEM) == 1
        assert SID_ADMINISTRATORS in sddl

    def test_rejects_a_non_sid(self):
        with pytest.raises(ValueError):
            build_secret_file_sddl("DNLT\\dnich")


class TestAcePredicates:
    """Pure — the read-detection logic the assertions depend on."""

    def test_file_all_access_grants_read(self):
        ace = Ace(ACCESS_ALLOWED_ACE_TYPE, 0, 0x001F01FF, SID_USERS)
        assert ace.grants_read

    def test_generic_read_grants_read(self):
        ace = Ace(ACCESS_ALLOWED_ACE_TYPE, 0, 0x80000000, SID_USERS)
        assert ace.grants_read

    def test_read_execute_grants_read(self):
        """0x1200A9 is what BUILTIN\\Users inherits from C:\\ProgramData."""
        ace = Ace(ACCESS_ALLOWED_ACE_TYPE, 0, 0x001200A9, SID_USERS)
        assert ace.grants_read

    def test_write_only_does_not_grant_read(self):
        ace = Ace(ACCESS_ALLOWED_ACE_TYPE, 0, 0x00000002, SID_USERS)
        assert not ace.grants_read

    def test_deny_ace_is_not_a_grant(self):
        ace = Ace(ACCESS_DENIED_ACE_TYPE, 0, 0x001F01FF, SID_USERS)
        assert not ace.grants_read

    def test_read_trustees_dedupes_and_sorts(self):
        dacl = FileDacl(
            protected=True,
            aces=[
                Ace(ACCESS_ALLOWED_ACE_TYPE, 0, 0x001F01FF, SID_SYSTEM),
                Ace(ACCESS_ALLOWED_ACE_TYPE, 0, 0x001F01FF, SID_SYSTEM),
                Ace(ACCESS_ALLOWED_ACE_TYPE, 0, 0x00000002, SID_USERS),
                Ace(ACCESS_DENIED_ACE_TYPE, 0, 0x001F01FF, SID_EVERYONE),
            ],
        )
        assert dacl.read_trustees() == [SID_SYSTEM]


@pytest.mark.skipif(sys.platform == "win32", reason="non-Windows only")
class TestUnavailableOffWindows:
    """The Windows path must be inert on the ubuntu leg, not merely unused."""

    def test_harden_raises(self, tmp_path):
        from admz.win_acl import harden_secret_file

        p = tmp_path / "admz.key"
        p.write_bytes(b"x")
        with pytest.raises(WinAclUnavailable):
            harden_secret_file(p)

    def test_read_dacl_raises(self, tmp_path):
        from admz.win_acl import read_file_dacl

        p = tmp_path / "admz.key"
        p.write_bytes(b"x")
        with pytest.raises(WinAclUnavailable):
            read_file_dacl(p)

    def test_current_user_sid_raises(self):
        from admz.win_acl import current_user_sid

        with pytest.raises(WinAclUnavailable):
            current_user_sid()

    def test_posix_creation_path_does_not_touch_win_acl(
        self, tmp_path, monkeypatch
    ):
        """Belt-and-braces on the ubuntu leg: key creation must reach
        chmod, never the Windows branch."""
        import admz.win_acl as win_acl
        from admz.backends.sqlite_backend import SQLiteDeviceRegistry

        def _boom(*a, **kw):  # pragma: no cover - must not be called
            raise AssertionError("win_acl was reached on a POSIX host")

        monkeypatch.setattr(win_acl, "harden_secret_file", _boom)

        key_path = tmp_path / "admz.key"
        SQLiteDeviceRegistry(
            db_path=str(tmp_path / "admz.db"), key_path=str(key_path)
        )
        assert key_path.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
class TestOnWindows:
    def test_current_user_sid_looks_like_a_sid(self):
        from admz.win_acl import current_user_sid

        sid = current_user_sid()
        assert sid.startswith("S-1-")

    def test_harden_then_read_roundtrip(self, tmp_path):
        from admz.win_acl import (
            current_user_sid,
            harden_secret_file,
            read_file_dacl,
        )

        p = tmp_path / "secret.bin"
        p.write_bytes(b"topsecret")
        assert read_file_dacl(p).protected is False

        harden_secret_file(p)
        dacl = read_file_dacl(p)

        assert dacl.protected is True
        assert set(dacl.read_trustees()) <= {
            SID_SYSTEM,
            SID_ADMINISTRATORS,
            current_user_sid(),
        }
        # The owning process must not lock itself out.
        assert p.read_bytes() == b"topsecret"

    def test_missing_file_raises_rather_than_passing_silently(self, tmp_path):
        from admz.win_acl import WinAclError, harden_secret_file

        with pytest.raises((WinAclError, OSError)):
            harden_secret_file(tmp_path / "does-not-exist.key")
