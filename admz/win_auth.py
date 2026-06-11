"""Windows credential validation against the local box (ADR-0033).

Validates a username + password against Windows itself via the Win32
``LogonUserW`` API — local SAM accounts on a workgroup machine (e.g.
Windows 11 Home), domain accounts automatically when the host is
domain-joined. This is the same account model Axis Camera Station Pro
uses (Windows users/groups, local or domain), without requiring IIS or
a reverse proxy (ADR-0021's path) or an LDAP server (ADR-0023).

On success the logon token's group memberships are read via
``GetTokenInformation(TokenGroups)`` and resolved to names
(``Administrators``, ``Users``, …) so the existing group-based gates
(``ADMZ_REVEAL_GROUPS`` — default includes ``Administrators``) work for
local accounts exactly as they would for AD groups. Group resolution is
best-effort: a failure yields empty groups, never a failed login
(mirrors FR-AUTH-006's LDAP posture).

The password exists only for the duration of the ``LogonUserW`` call —
it is never stored, logged, or echoed (the same invariant as device
passwords).

Windows-only: every entry point raises :class:`WinAuthUnavailable` on
other platforms. Tests mock :func:`validate_windows_credentials`.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class WinAuthUnavailable(RuntimeError):
    """Raised when Windows credential validation isn't possible here."""


# LogonUserW constants (winbase.h)
_LOGON32_LOGON_NETWORK = 3
_LOGON32_LOGON_INTERACTIVE = 2
_LOGON32_PROVIDER_DEFAULT = 0

# GetTokenInformation classes (winnt.h)
_TOKEN_GROUPS = 2

# Group SID attribute flags worth keeping (winnt.h). SE_GROUP_ENABLED
# marks groups active in the token; logon-id / integrity SIDs are noise.
_SE_GROUP_ENABLED = 0x00000004
_SE_GROUP_LOGON_ID = 0xC0000000
_SE_GROUP_INTEGRITY = 0x00000020

# SID_NAME_USE values that represent real groups.
_SID_TYPE_GROUP = 2
_SID_TYPE_WELL_KNOWN_GROUP = 5
_SID_TYPE_ALIAS = 4  # local groups like BUILTIN\Administrators


@dataclass
class WindowsIdentity:
    """The outcome of a successful credential validation."""

    username: str           # account name as validated (no domain prefix)
    domain: Optional[str]   # domain, or None/"." for a local account
    groups: List[str] = field(default_factory=list)


def _strip_authority(name: str) -> str:
    """``BUILTIN\\Administrators`` -> ``Administrators`` — matches how the
    reveal gate strips ``DOMAIN\\`` prefixes before comparing."""
    return name.split("\\")[-1].strip()


def validate_windows_credentials(
    username: str, password: str, domain: Optional[str] = None
) -> Optional[WindowsIdentity]:
    """Validate credentials against Windows. Returns a
    :class:`WindowsIdentity` on success, ``None`` on bad credentials.

    ``username`` may be bare (``alice`` → local account, domain ``.``),
    ``DOMAIN\\alice``, or ``alice@domain.local`` — parsing mirrors
    :func:`admz.auth.parse_windows_identity`.

    Raises :class:`WinAuthUnavailable` off-Windows or if the Win32 call
    itself cannot be made (NOT for wrong passwords — those return None).
    """
    if sys.platform != "win32":  # pragma: no cover — exercised via mock
        raise WinAuthUnavailable(
            "Windows credential validation requires Windows (LogonUserW)."
        )
    if not username or not password:
        return None

    user, dom = _split_identity(username, domain)

    import ctypes
    from ctypes import wintypes

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _declare_prototypes(advapi32, kernel32)

    token = wintypes.HANDLE()
    ok = False
    # NETWORK logon is the cheap "are these credentials valid" check and
    # doesn't require the 'log on locally' right. Some lockdown policies
    # deny network logon — fall back to INTERACTIVE in that case.
    for logon_type in (_LOGON32_LOGON_NETWORK, _LOGON32_LOGON_INTERACTIVE):
        ok = bool(
            advapi32.LogonUserW(
                user,
                dom,
                password,
                logon_type,
                _LOGON32_PROVIDER_DEFAULT,
                ctypes.byref(token),
            )
        )
        if ok:
            break
        err = ctypes.get_last_error()
        # 1326 = ERROR_LOGON_FAILURE (bad username/password) — definitive,
        # don't retry with another logon type.
        if err == 1326:
            logger.info("Windows logon failed for %r (bad credentials)", user)
            return None
    if not ok:
        err = ctypes.get_last_error()
        logger.warning(
            "LogonUserW failed for %r with winerror %s", user, err
        )
        return None

    try:
        groups = _groups_from_token(token, advapi32, kernel32)
    except Exception:  # pragma: no cover — best effort
        logger.warning(
            "could not read token groups for %r", user, exc_info=True
        )
        groups = []
    finally:
        kernel32.CloseHandle(token)

    return WindowsIdentity(
        username=user,
        domain=None if dom in (".", None) else dom,
        groups=groups,
    )


def _declare_prototypes(advapi32, kernel32) -> None:
    """Declare Win32 argtypes/restypes. Without these, 64-bit HANDLE and
    pointer values get truncated through ctypes' default c_int marshaling
    (symptom: ERROR_INVALID_HANDLE from perfectly valid handles)."""
    import ctypes
    from ctypes import wintypes

    advapi32.LogonUserW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
        wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.LogonUserW.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.LookupAccountSidW.argtypes = [
        wintypes.LPCWSTR, ctypes.c_void_p,
        wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.LookupAccountSidW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL


def _split_identity(
    username: str, domain: Optional[str]
) -> Tuple[str, str]:
    """Resolve (user, domain) for LogonUserW. ``.`` means the local SAM."""
    if domain:
        return username, domain
    if "\\" in username:
        dom, user = username.split("\\", 1)
        return user, (dom or ".")
    if "/" in username:
        dom, user = username.split("/", 1)
        return user, (dom or ".")
    if "@" in username:
        # UPN form: LogonUserW accepts the full UPN with domain=None,
        # but passing the split keeps behavior uniform.
        user, dom = username.split("@", 1)
        return user, dom
    return username, "."


def _groups_from_token(token, advapi32, kernel32) -> List[str]:
    """Resolve the logon token's group SIDs to bare group names."""
    import ctypes
    from ctypes import wintypes

    # First call gets the needed buffer size.
    needed = wintypes.DWORD(0)
    advapi32.GetTokenInformation(
        token, _TOKEN_GROUPS, None, 0, ctypes.byref(needed)
    )
    if needed.value == 0:
        return []
    buf = ctypes.create_string_buffer(needed.value)
    if not advapi32.GetTokenInformation(
        token, _TOKEN_GROUPS, buf, needed, ctypes.byref(needed)
    ):
        return []

    class SID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [
            ("Sid", ctypes.c_void_p),
            ("Attributes", wintypes.DWORD),
        ]

    group_count = ctypes.cast(
        buf, ctypes.POINTER(wintypes.DWORD)
    ).contents.value
    # TOKEN_GROUPS = DWORD GroupCount + SID_AND_ATTRIBUTES Groups[...]
    # The array starts after the (aligned) count field.
    offset = ctypes.sizeof(ctypes.c_void_p)  # alignment padding incl. count
    array_type = SID_AND_ATTRIBUTES * group_count
    entries = ctypes.cast(
        ctypes.byref(buf, offset), ctypes.POINTER(array_type)
    ).contents

    names: List[str] = []
    for entry in entries:
        attrs = entry.Attributes
        if attrs & _SE_GROUP_LOGON_ID or attrs & _SE_GROUP_INTEGRITY:
            continue
        if not (attrs & _SE_GROUP_ENABLED):
            continue
        resolved = _lookup_sid(entry.Sid, advapi32)
        if resolved is None:
            continue
        name, sid_type = resolved
        if sid_type not in (
            _SID_TYPE_GROUP, _SID_TYPE_WELL_KNOWN_GROUP, _SID_TYPE_ALIAS
        ):
            continue
        bare = _strip_authority(name)
        if bare and bare not in names:
            names.append(bare)
    return names


def _lookup_sid(sid_ptr, advapi32) -> Optional[Tuple[str, int]]:
    import ctypes
    from ctypes import wintypes

    name_len = wintypes.DWORD(0)
    dom_len = wintypes.DWORD(0)
    sid_type = wintypes.DWORD(0)
    advapi32.LookupAccountSidW(
        None, sid_ptr, None, ctypes.byref(name_len),
        None, ctypes.byref(dom_len), ctypes.byref(sid_type),
    )
    if name_len.value == 0:
        return None
    name_buf = ctypes.create_unicode_buffer(name_len.value)
    dom_buf = ctypes.create_unicode_buffer(max(dom_len.value, 1))
    if not advapi32.LookupAccountSidW(
        None, sid_ptr, name_buf, ctypes.byref(name_len),
        dom_buf, ctypes.byref(dom_len), ctypes.byref(sid_type),
    ):
        return None
    return name_buf.value, sid_type.value
