"""Owner-only DACLs for secret files on Windows (ADR-0010, issue #207).

``os.chmod`` is the POSIX mechanism for "only the owner may read this
file". On Windows it is **not a weaker version of that — it is nothing
at all**. ``os.chmod(path, 0o600)`` never touches the DACL; the only
thing it can affect is the ``FILE_ATTRIBUTE_READONLY`` bit, and because
``0o600`` *has* the owner-write bit it clears that attribute rather than
setting it. Measured on Windows 11: the DACL is byte-identical before
and after, ``os.stat().st_mode & 0o777`` reads back ``0o666``, and
``os.access(path, os.W_OK)`` stays ``True``.

So a file written under ``C:\\ProgramData\\admz`` simply inherits its
parent's ACL. ``C:\\ProgramData`` grants ``BUILTIN\\Users:(OI)(CI)(RX)``,
which a freshly-created ``ADMZ_HOME`` inherits — meaning every local
user can read the Fernet master key that encrypts the whole fleet's
device credentials. ADR-0042 hardens ``ADMZ_HOME`` via a *setup script*;
this module is the code-level equivalent, so a deployment that never ran
that script is not silently unprotected.

**Mechanism: ctypes, not pywin32.** ADR-0033 established the house
pattern for Win32 work ("ctypes ``advapi32.LogonUserW`` … *no new
dependencies*") and ``admz/win_auth.py`` is the precedent. ``pywin32``
*is* importable in the dev venv, but only incidentally — it arrives as
``mcp``'s transitive dependency (``mcp -> pywin32>=310; sys_platform ==
'win32'``) and is declared in neither ``requirements.txt`` nor
``setup.py``. Depending on it would mean an ``mcp`` minor release could
drop it and turn this guard into a silent ``ImportError`` on
``windows-latest`` — precisely the false-green that #207 exists to kill.

**Everything here compares SIDs, never names.** ``BUILTIN\\Administrators``
is ``Administratoren`` on a German install; ``S-1-5-32-544`` is
``S-1-5-32-544`` everywhere. That is also what makes the tests portable
across the CI runner and the operator's box, which have entirely
different accounts.

The module imports cleanly on POSIX — deliberately. It uses plain
``ctypes`` types rather than ``ctypes.wintypes``, which is *not*
importable off-Windows (``VARIANT_BOOL``'s ``"v"`` type code is
Windows-only), so the ubuntu CI leg can still import this module and
exercise :func:`build_secret_file_sddl`. Only the calls that need
``WinDLL`` raise, and they raise :class:`WinAclUnavailable`.
"""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Union

__all__ = [
    "Ace",
    "FileDacl",
    "WinAclError",
    "WinAclUnavailable",
    "build_secret_file_sddl",
    "current_user_sid",
    "harden_secret_file",
    "lookup_account_sid",
    "read_file_dacl",
    "SID_ADMINISTRATORS",
    "SID_AUTHENTICATED_USERS",
    "SID_EVERYONE",
    "SID_SYSTEM",
    "SID_USERS",
]


class WinAclError(RuntimeError):
    """A Win32 security call failed."""


class WinAclUnavailable(WinAclError):
    """Windows ACL manipulation isn't possible here (non-Windows host)."""


# --------------------------------------------------------------------------
# Well-known SIDs (winnt.h). Locale-invariant, unlike the display names.
# --------------------------------------------------------------------------
SID_SYSTEM = "S-1-5-18"
SID_ADMINISTRATORS = "S-1-5-32-544"
SID_EVERYONE = "S-1-1-0"
SID_USERS = "S-1-5-32-545"
SID_AUTHENTICATED_USERS = "S-1-5-11"

# SECURITY_INFORMATION bits (winnt.h)
_DACL_SECURITY_INFORMATION = 0x00000004
_PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000

# SE_OBJECT_TYPE (accctrl.h)
_SE_FILE_OBJECT = 1

# SECURITY_DESCRIPTOR_CONTROL (winnt.h). The bit that says "this DACL is
# NOT inherited from the parent" — the one assertion that cannot be true
# by accident, and therefore the load-bearing one in the tests.
_SE_DACL_PROTECTED = 0x1000

# TOKEN_INFORMATION_CLASS + access rights (winnt.h)
_TOKEN_USER = 1
_TOKEN_QUERY = 0x0008

# sddl.h
_SDDL_REVISION_1 = 1

# ACE types (winnt.h)
ACCESS_ALLOWED_ACE_TYPE = 0x0
ACCESS_DENIED_ACE_TYPE = 0x1

# Access-mask bits that confer the ability to read the file's CONTENTS.
# FILE_ALL_ACCESS (0x1F01FF) and GENERIC_ALL both contain FILE_READ_DATA;
# MAXIMUM_ALLOWED resolves at access time to whatever the principal can
# get, so it has to count as read too.
_FILE_READ_DATA = 0x00000001
_GENERIC_READ = 0x80000000
_GENERIC_ALL = 0x10000000
_MAXIMUM_ALLOWED = 0x02000000
_READ_BITS = _FILE_READ_DATA | _GENERIC_READ | _GENERIC_ALL | _MAXIMUM_ALLOWED


# --------------------------------------------------------------------------
# Structures — plain ctypes types so this module imports on POSIX too.
#   c_ubyte  == BYTE      c_uint16 == WORD
#   c_uint32 == DWORD     c_void_p == HANDLE / PSID / PSECURITY_DESCRIPTOR
# --------------------------------------------------------------------------


class _ACL(ctypes.Structure):
    _fields_ = [
        ("AclRevision", ctypes.c_ubyte),
        ("Sbz1", ctypes.c_ubyte),
        ("AclSize", ctypes.c_uint16),
        ("AceCount", ctypes.c_uint16),
        ("Sbz2", ctypes.c_uint16),
    ]


class _ACE_HEADER(ctypes.Structure):
    _fields_ = [
        ("AceType", ctypes.c_ubyte),
        ("AceFlags", ctypes.c_ubyte),
        ("AceSize", ctypes.c_uint16),
    ]


class _ACCESS_ALLOWED_ACE(ctypes.Structure):
    """ACCESS_DENIED_ACE has an identical layout, so this parses both."""

    _fields_ = [
        ("Header", _ACE_HEADER),
        ("Mask", ctypes.c_uint32),
        ("SidStart", ctypes.c_uint32),
    ]


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", ctypes.c_uint32)]


@dataclass(frozen=True)
class Ace:
    """One access-control entry, with its trustee as a SID *string*."""

    type: int
    flags: int
    mask: int
    sid: str

    @property
    def is_allow(self) -> bool:
        return self.type == ACCESS_ALLOWED_ACE_TYPE

    @property
    def grants_read(self) -> bool:
        """True when this is an ALLOW ace conferring read of the contents."""
        return self.is_allow and bool(self.mask & _READ_BITS)


@dataclass(frozen=True)
class FileDacl:
    """A file's DACL: whether it is protected, and its ACEs."""

    protected: bool
    aces: List[Ace]

    def read_trustees(self) -> List[str]:
        """SIDs of every principal this DACL lets read the file."""
        return sorted({a.sid for a in self.aces if a.grants_read})


# --------------------------------------------------------------------------
# ctypes plumbing
# --------------------------------------------------------------------------


def _require_windows() -> None:
    if sys.platform != "win32":
        raise WinAclUnavailable(
            "Windows ACL manipulation requires Windows (advapi32)."
        )


def _load():
    """Load advapi32/kernel32 and declare prototypes.

    Prototypes are declared explicitly for the same reason ADR-0033 gives
    for ``win_auth.py``: ctypes' default ``c_int`` marshaling truncates
    64-bit pointers and handles.
    """
    _require_windows()
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    advapi32.GetNamedSecurityInfoW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_int,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.POINTER(_ACL)),
        ctypes.POINTER(ctypes.POINTER(_ACL)),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.GetNamedSecurityInfoW.restype = ctypes.c_uint32

    advapi32.SetNamedSecurityInfoW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_int,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    advapi32.SetNamedSecurityInfoW.restype = ctypes.c_uint32

    advapi32.GetSecurityDescriptorControl.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint16),
        ctypes.POINTER(ctypes.c_uint32),
    ]
    advapi32.GetSecurityDescriptorControl.restype = ctypes.c_int

    advapi32.GetSecurityDescriptorDacl.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_int),
    ]
    advapi32.GetSecurityDescriptorDacl.restype = ctypes.c_int

    advapi32.GetAce.argtypes = [
        ctypes.POINTER(_ACL),
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.GetAce.restype = ctypes.c_int

    advapi32.ConvertSidToStringSidW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_wchar_p),
    ]
    advapi32.ConvertSidToStringSidW.restype = ctypes.c_int

    advapi32.LookupAccountNameW.argtypes = [
        ctypes.c_wchar_p,                    # lpSystemName
        ctypes.c_wchar_p,                    # lpAccountName
        ctypes.c_void_p,                     # Sid (out)
        ctypes.POINTER(ctypes.c_uint32),     # cbSid
        ctypes.c_wchar_p,                    # ReferencedDomainName (out)
        ctypes.POINTER(ctypes.c_uint32),     # cchReferencedDomainName
        ctypes.POINTER(ctypes.c_int),        # peUse (SID_NAME_USE)
    ]
    advapi32.LookupAccountNameW.restype = ctypes.c_int

    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_uint32),
    ]
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = (
        ctypes.c_int
    )

    advapi32.OpenProcessToken.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.OpenProcessToken.restype = ctypes.c_int

    advapi32.GetTokenInformation.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    advapi32.GetTokenInformation.restype = ctypes.c_int

    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int

    return advapi32, kernel32


def _sid_to_string(advapi32, kernel32, psid) -> str:
    out = ctypes.c_wchar_p()
    if not advapi32.ConvertSidToStringSidW(psid, ctypes.byref(out)):
        raise WinAclError(
            f"ConvertSidToStringSidW failed: {ctypes.get_last_error()}"
        )
    try:
        return out.value or ""
    finally:
        kernel32.LocalFree(ctypes.cast(out, ctypes.c_void_p))


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def current_user_sid() -> str:
    """SID string of the account this process is running as.

    Under the ``admz`` Windows service (which runs as LocalSystem, see
    ADR-0042) this is :data:`SID_SYSTEM`.
    """
    advapi32, kernel32 = _load()
    token = ctypes.c_void_p()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(token)
    ):
        raise WinAclError(
            f"OpenProcessToken failed: {ctypes.get_last_error()}"
        )
    try:
        size = ctypes.c_uint32()
        advapi32.GetTokenInformation(
            token, _TOKEN_USER, None, 0, ctypes.byref(size)
        )
        buf = ctypes.create_string_buffer(size.value)
        if not advapi32.GetTokenInformation(
            token, _TOKEN_USER, buf, size, ctypes.byref(size)
        ):
            raise WinAclError(
                f"GetTokenInformation(TokenUser) failed: "
                f"{ctypes.get_last_error()}"
            )
        info = ctypes.cast(buf, ctypes.POINTER(_SID_AND_ATTRIBUTES)).contents
        return _sid_to_string(advapi32, kernel32, info.Sid)
    finally:
        kernel32.CloseHandle(token)


def lookup_account_sid(name: str) -> str:
    """Resolve an account or group *name* to its SID string.

    The inverse of the constants above, for names this module cannot know in
    advance — an operator's own ``ADMZ-Admins``, or the localised display name
    of a built-in group as reported by ``NetUserGetLocalGroups`` (issue #274:
    ``Administratoren`` on a German install is ``S-1-5-32-544`` all the same).

    ``lpSystemName=None`` means "this machine, then its domain", which is the
    same resolution order the gates' existing name comparison implicitly
    assumed.

    Raises :class:`WinAclUnavailable` off-Windows and :class:`WinAclError` if
    the name does not resolve — callers that must not fail closed should catch
    both. See ``admz/authz.py``, which treats an unresolvable name as "compare
    by name instead", never as "deny".
    """
    advapi32, kernel32 = _load()
    if not name:
        raise WinAclError("lookup_account_sid requires a non-empty name")

    sid_size = ctypes.c_uint32(0)
    dom_size = ctypes.c_uint32(0)
    use = ctypes.c_int(0)
    # First call sizes the buffers; it is EXPECTED to fail with
    # ERROR_INSUFFICIENT_BUFFER (122). Any other failure is the real answer —
    # in particular ERROR_NONE_MAPPED (1332) for a name that does not exist.
    advapi32.LookupAccountNameW(
        None, name, None, ctypes.byref(sid_size),
        None, ctypes.byref(dom_size), ctypes.byref(use),
    )
    if sid_size.value == 0:
        raise WinAclError(
            f"LookupAccountNameW({name!r}) failed: {ctypes.get_last_error()}"
        )
    sid_buf = ctypes.create_string_buffer(sid_size.value)
    dom_buf = ctypes.create_unicode_buffer(dom_size.value)
    if not advapi32.LookupAccountNameW(
        None, name, sid_buf, ctypes.byref(sid_size),
        dom_buf, ctypes.byref(dom_size), ctypes.byref(use),
    ):
        raise WinAclError(
            f"LookupAccountNameW({name!r}) failed: {ctypes.get_last_error()}"
        )
    return _sid_to_string(advapi32, kernel32, ctypes.cast(sid_buf, ctypes.c_void_p))


def build_secret_file_sddl(owner_sid: str) -> str:
    """Return the SDDL for an owner-only secret file.

    ``D:P`` is the whole point: **P** = ``SE_DACL_PROTECTED``, i.e. this
    DACL does not inherit from the parent directory. Without it the
    permissive ``C:\\ProgramData`` ACEs come straight back.

    ``FA`` = FILE_ALL_ACCESS, ``FRFW`` = FILE_GENERIC_READ|WRITE.

    SYSTEM and Administrators are granted unconditionally so that the
    service (LocalSystem) and the operator (an Administrator) both retain
    access regardless of which of them created the file. When the owner
    is already one of those, the redundant third ACE is omitted.

    Pure string construction, deliberately — it is the one part of this
    module the POSIX CI leg can assert on.
    """
    if not owner_sid or not owner_sid.startswith("S-"):
        raise ValueError(f"not a SID string: {owner_sid!r}")
    aces = [
        f"(A;;FA;;;{SID_SYSTEM})",
        f"(A;;FA;;;{SID_ADMINISTRATORS})",
    ]
    if owner_sid not in (SID_SYSTEM, SID_ADMINISTRATORS):
        aces.append(f"(A;;FRFW;;;{owner_sid})")
    return "D:P" + "".join(aces)


def read_file_dacl(path: Union[str, Path]) -> FileDacl:
    """Read a file's DACL: the protected flag plus every ACE.

    Used by the tests to assert the *property* that must hold in both CI
    and production, rather than a literal ACL string that would only ever
    be right in one environment.
    """
    advapi32, kernel32 = _load()
    pdacl = ctypes.POINTER(_ACL)()
    psd = ctypes.c_void_p()
    rc = advapi32.GetNamedSecurityInfoW(
        str(path),
        _SE_FILE_OBJECT,
        _DACL_SECURITY_INFORMATION,
        None,
        None,
        ctypes.byref(pdacl),
        None,
        ctypes.byref(psd),
    )
    if rc != 0:
        raise WinAclError(f"GetNamedSecurityInfoW failed on {path}: rc={rc}")
    try:
        control = ctypes.c_uint16()
        revision = ctypes.c_uint32()
        if not advapi32.GetSecurityDescriptorControl(
            psd, ctypes.byref(control), ctypes.byref(revision)
        ):
            raise WinAclError(
                f"GetSecurityDescriptorControl failed: "
                f"{ctypes.get_last_error()}"
            )
        protected = bool(control.value & _SE_DACL_PROTECTED)

        aces: List[Ace] = []
        if pdacl:
            for index in range(pdacl.contents.AceCount):
                pace = ctypes.c_void_p()
                if not advapi32.GetAce(pdacl, index, ctypes.byref(pace)):
                    raise WinAclError(
                        f"GetAce({index}) failed: {ctypes.get_last_error()}"
                    )
                header = ctypes.cast(
                    pace, ctypes.POINTER(_ACE_HEADER)
                ).contents
                body = ctypes.cast(
                    pace, ctypes.POINTER(_ACCESS_ALLOWED_ACE)
                ).contents
                # The SID is inline at the end of the ACE, not a pointer.
                psid = ctypes.c_void_p(
                    pace.value + _ACCESS_ALLOWED_ACE.SidStart.offset
                )
                aces.append(
                    Ace(
                        type=header.AceType,
                        flags=header.AceFlags,
                        mask=body.Mask,
                        sid=_sid_to_string(advapi32, kernel32, psid),
                    )
                )
        return FileDacl(protected=protected, aces=aces)
    finally:
        kernel32.LocalFree(psd)


def harden_secret_file(path: Union[str, Path]) -> str:
    """Replace *path*'s DACL with a protected, owner-only one.

    Returns the SDDL applied, for logging. Raises :class:`WinAclError` on
    failure and :class:`WinAclUnavailable` off-Windows — callers decide
    whether that is fatal.

    Requires WRITE_DAC, which the creator of a file always holds as its
    owner; verified to work from a non-elevated process.
    """
    advapi32, kernel32 = _load()
    sddl = build_secret_file_sddl(current_user_sid())

    psd = ctypes.c_void_p()
    if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        sddl, _SDDL_REVISION_1, ctypes.byref(psd), None
    ):
        raise WinAclError(
            f"ConvertStringSecurityDescriptorToSecurityDescriptorW failed "
            f"for {sddl!r}: {ctypes.get_last_error()}"
        )
    try:
        present = ctypes.c_int()
        defaulted = ctypes.c_int()
        pdacl = ctypes.c_void_p()
        if not advapi32.GetSecurityDescriptorDacl(
            psd,
            ctypes.byref(present),
            ctypes.byref(pdacl),
            ctypes.byref(defaulted),
        ):
            raise WinAclError(
                f"GetSecurityDescriptorDacl failed: "
                f"{ctypes.get_last_error()}"
            )
        rc = advapi32.SetNamedSecurityInfoW(
            str(path),
            _SE_FILE_OBJECT,
            # PROTECTED_DACL_SECURITY_INFORMATION is what actually breaks
            # inheritance. Without it the parent's ACEs are merged back in
            # and the file stays readable by BUILTIN\\Users.
            _DACL_SECURITY_INFORMATION
            | _PROTECTED_DACL_SECURITY_INFORMATION,
            None,
            None,
            pdacl,
            None,
        )
        if rc != 0:
            raise WinAclError(
                f"SetNamedSecurityInfoW failed on {path}: rc={rc}"
            )
        return sddl
    finally:
        kernel32.LocalFree(psd)
