"""In-process HTTP Negotiate (SPNEGO) SSO via Windows SSPI (ADR-0035).

Lets a browser sign in as the **currently logged-in Windows user** with no
password typed — the "Current user" option Axis Camera Station Pro offers.
The browser and Windows complete a Kerberos/NTLM handshake over the HTTP
``Negotiate`` scheme; ADMZ shuttles the opaque token blobs between the
browser and the OS's own ``AcceptSecurityContext`` (secur32.dll), exactly
the way IIS does. There is **no SPNEGO parsing in Python** and no new
dependency: Windows owns the protocol state machine, this module owns
buffer plumbing only — same ctypes posture as :mod:`admz.win_auth`
(explicit prototypes; default int marshaling truncates 64-bit handles).

On a workgroup box Negotiate selects NTLM; if the host is domain-joined it
selects Kerberos automatically. Either way the completed security context
yields a real Windows access token, from which the username and group
memberships are read with the same helpers the form login uses — so the
``ADMZ_REVEAL_GROUPS`` / ``Administrators`` gates behave identically for
both sign-in methods.

NTLM is a multi-leg handshake bound to one TCP connection; partial
contexts are parked in :class:`PendingHandshakes` keyed by the client's
(host, port) between legs.

Windows-only: entry points raise :class:`~admz.win_auth.WinAuthUnavailable`
elsewhere. Route tests mock :class:`NegotiateHandshake`; the real SSPI path
is exercised by a loopback client↔server handshake test on Windows.
"""

from __future__ import annotations

import base64
import logging
import os
import sys
import threading
import time
from typing import Dict, Optional, Tuple

from admz.win_auth import (
    WinAuthUnavailable,
    WindowsIdentity,
    _declare_prototypes,
    _groups_from_token,
    _lookup_sid,
)

logger = logging.getLogger(__name__)

# SECURITY_STATUS values (signed; errors are negative as c_long).
SEC_E_OK = 0
SEC_I_CONTINUE_NEEDED = 0x00090312
SEC_I_COMPLETE_NEEDED = 0x00090313
SEC_I_COMPLETE_AND_CONTINUE = 0x00090314

# AcquireCredentialsHandleW
_SECPKG_CRED_INBOUND = 1
_SECPKG_CRED_OUTBOUND = 2  # used by the loopback test client

# Accept/InitializeSecurityContext
_ASC_REQ_CONNECTION = 0x00000800
_SECURITY_NATIVE_DREP = 0x00000010

# SecBuffer
_SECBUFFER_VERSION = 0
_SECBUFFER_TOKEN = 2

# GetTokenInformation class
_TOKEN_USER = 1

_PACKAGE = "Negotiate"

# Handshake step outcomes.
CONTINUE = "continue"
COMPLETE = "complete"
FAILED = "failed"


def sso_available() -> bool:
    """Whether the "continue as the signed-in Windows user" path can work
    here: Windows only, and not explicitly disabled via env."""
    if sys.platform != "win32":
        return False
    raw = (os.getenv("ADMZ_SSO_NEGOTIATE", "") or "").strip().lower()
    return raw not in ("0", "false", "no", "off")


# ---------------------------------------------------------------------------
# ctypes scaffolding (lazy — module must import cleanly off-Windows)
# ---------------------------------------------------------------------------


def _sspi():
    """Return (ctypes, wintypes, secur32, advapi32, kernel32, structs)."""
    if sys.platform != "win32":  # pragma: no cover — exercised via mock
        raise WinAuthUnavailable(
            "Negotiate SSO requires Windows (SSPI / secur32.dll)."
        )
    import ctypes
    from ctypes import wintypes

    secur32 = ctypes.WinDLL("secur32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _declare_prototypes(advapi32, kernel32)

    ULONG_PTR = ctypes.c_size_t

    class SecHandle(ctypes.Structure):
        _fields_ = [("dwLower", ULONG_PTR), ("dwUpper", ULONG_PTR)]

    class SecBuffer(ctypes.Structure):
        _fields_ = [
            ("cbBuffer", ctypes.c_ulong),
            ("BufferType", ctypes.c_ulong),
            ("pvBuffer", ctypes.c_void_p),
        ]

    class SecBufferDesc(ctypes.Structure):
        _fields_ = [
            ("ulVersion", ctypes.c_ulong),
            ("cBuffers", ctypes.c_ulong),
            ("pBuffers", ctypes.POINTER(SecBuffer)),
        ]

    class SecPkgInfoW(ctypes.Structure):
        _fields_ = [
            ("fCapabilities", ctypes.c_ulong),
            ("wVersion", ctypes.c_ushort),
            ("wRPCID", ctypes.c_ushort),
            ("cbMaxToken", ctypes.c_ulong),
            ("Name", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
        ]

    TimeStamp = ctypes.c_longlong
    STATUS = ctypes.c_long  # SECURITY_STATUS is a signed LONG

    secur32.QuerySecurityPackageInfoW.argtypes = [
        wintypes.LPCWSTR, ctypes.POINTER(ctypes.POINTER(SecPkgInfoW)),
    ]
    secur32.QuerySecurityPackageInfoW.restype = STATUS
    secur32.FreeContextBuffer.argtypes = [ctypes.c_void_p]
    secur32.FreeContextBuffer.restype = STATUS
    secur32.AcquireCredentialsHandleW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_ulong,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.POINTER(SecHandle), ctypes.POINTER(TimeStamp),
    ]
    secur32.AcquireCredentialsHandleW.restype = STATUS
    secur32.AcceptSecurityContext.argtypes = [
        ctypes.POINTER(SecHandle), ctypes.POINTER(SecHandle),
        ctypes.POINTER(SecBufferDesc), ctypes.c_ulong, ctypes.c_ulong,
        ctypes.POINTER(SecHandle), ctypes.POINTER(SecBufferDesc),
        ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(TimeStamp),
    ]
    secur32.AcceptSecurityContext.restype = STATUS
    secur32.InitializeSecurityContextW.argtypes = [
        ctypes.POINTER(SecHandle), ctypes.POINTER(SecHandle),
        wintypes.LPCWSTR, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong,
        ctypes.POINTER(SecBufferDesc), ctypes.c_ulong,
        ctypes.POINTER(SecHandle), ctypes.POINTER(SecBufferDesc),
        ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(TimeStamp),
    ]
    secur32.InitializeSecurityContextW.restype = STATUS
    secur32.CompleteAuthToken.argtypes = [
        ctypes.POINTER(SecHandle), ctypes.POINTER(SecBufferDesc),
    ]
    secur32.CompleteAuthToken.restype = STATUS
    secur32.QuerySecurityContextToken.argtypes = [
        ctypes.POINTER(SecHandle), ctypes.POINTER(wintypes.HANDLE),
    ]
    secur32.QuerySecurityContextToken.restype = STATUS
    secur32.DeleteSecurityContext.argtypes = [ctypes.POINTER(SecHandle)]
    secur32.DeleteSecurityContext.restype = STATUS
    secur32.FreeCredentialsHandle.argtypes = [ctypes.POINTER(SecHandle)]
    secur32.FreeCredentialsHandle.restype = STATUS

    structs = {
        "SecHandle": SecHandle,
        "SecBuffer": SecBuffer,
        "SecBufferDesc": SecBufferDesc,
        "SecPkgInfoW": SecPkgInfoW,
        "TimeStamp": TimeStamp,
    }
    return ctypes, wintypes, secur32, advapi32, kernel32, structs


def _max_token_size(ctypes_mod, secur32, structs) -> int:
    info = ctypes_mod.POINTER(structs["SecPkgInfoW"])()
    status = secur32.QuerySecurityPackageInfoW(
        _PACKAGE, ctypes_mod.byref(info)
    )
    if status != SEC_E_OK or not info:
        return 65536  # generous fallback (Kerberos tokens can be large)
    try:
        return int(info.contents.cbMaxToken) or 65536
    finally:
        secur32.FreeContextBuffer(info)


def _token_buffer(ctypes_mod, structs, data: Optional[bytes], size: int = 0):
    """Build a single-token SecBufferDesc (and keep the backing buffer
    alive by returning it alongside)."""
    SecBuffer = structs["SecBuffer"]
    SecBufferDesc = structs["SecBufferDesc"]
    if data is not None:
        backing = ctypes_mod.create_string_buffer(data, len(data))
        length = len(data)
    else:
        backing = ctypes_mod.create_string_buffer(size)
        length = size
    buf = SecBuffer(
        length, _SECBUFFER_TOKEN,
        ctypes_mod.cast(backing, ctypes_mod.c_void_p),
    )
    desc = SecBufferDesc(_SECBUFFER_VERSION, 1, ctypes_mod.pointer(buf))
    return desc, buf, backing


# ---------------------------------------------------------------------------
# Server-side handshake
# ---------------------------------------------------------------------------


class NegotiateHandshake:
    """One browser's Negotiate handshake (server/acceptor side).

    ``step(in_blob)`` feeds the browser's ``Authorization: Negotiate``
    token to Windows and returns ``(status, out_blob, identity)``:

    * ``CONTINUE`` — send ``out_blob`` back as a 401 challenge and keep
      this object for the next leg (NTLM is multi-leg).
    * ``COMPLETE`` — ``identity`` is the authenticated
      :class:`~admz.win_auth.WindowsIdentity`; the context is cleaned up.
    * ``FAILED`` — authentication failed; the context is cleaned up.
    """

    def __init__(self) -> None:
        (self._ct, self._wt, self._secur32, self._advapi32,
         self._kernel32, self._structs) = _sspi()
        SecHandle = self._structs["SecHandle"]
        self._cred = SecHandle()
        self._ctxt = SecHandle()
        self._have_cred = False
        self._have_ctxt = False
        self._max_token = _max_token_size(
            self._ct, self._secur32, self._structs
        )

        expiry = self._structs["TimeStamp"]()
        status = self._secur32.AcquireCredentialsHandleW(
            None, _PACKAGE, _SECPKG_CRED_INBOUND,
            None, None, None, None,
            self._ct.byref(self._cred), self._ct.byref(expiry),
        )
        if status != SEC_E_OK:
            raise WinAuthUnavailable(
                f"AcquireCredentialsHandleW(Negotiate) failed: 0x{status & 0xFFFFFFFF:08X}"
            )
        self._have_cred = True

    def step(
        self, in_blob: bytes
    ) -> Tuple[str, bytes, Optional[WindowsIdentity]]:
        ct = self._ct
        in_desc, _in_buf, _in_backing = _token_buffer(
            ct, self._structs, in_blob
        )
        out_desc, out_buf, _out_backing = _token_buffer(
            ct, self._structs, None, self._max_token
        )
        attr = ct.c_ulong(0)
        expiry = self._structs["TimeStamp"]()

        status = self._secur32.AcceptSecurityContext(
            ct.byref(self._cred),
            ct.byref(self._ctxt) if self._have_ctxt else None,
            ct.byref(in_desc),
            _ASC_REQ_CONNECTION,
            _SECURITY_NATIVE_DREP,
            ct.byref(self._ctxt),
            ct.byref(out_desc),
            ct.byref(attr),
            ct.byref(expiry),
        )
        self._have_ctxt = True

        if status in (SEC_I_COMPLETE_NEEDED, SEC_I_COMPLETE_AND_CONTINUE):
            self._secur32.CompleteAuthToken(
                ct.byref(self._ctxt), ct.byref(out_desc)
            )
            status = (
                SEC_I_CONTINUE_NEEDED
                if status == SEC_I_COMPLETE_AND_CONTINUE else SEC_E_OK
            )

        out_blob = bytes(_out_backing.raw[: out_buf.cbBuffer])

        if status == SEC_I_CONTINUE_NEEDED:
            return CONTINUE, out_blob, None
        if status == SEC_E_OK:
            identity = self._identity_from_context()
            self.close()
            if identity is None:
                return FAILED, b"", None
            return COMPLETE, out_blob, identity
        logger.info(
            "Negotiate handshake failed: 0x%08X", status & 0xFFFFFFFF
        )
        self.close()
        return FAILED, b"", None

    def _identity_from_context(self) -> Optional[WindowsIdentity]:
        """Read user + groups from the completed context's access token —
        the same token-based extraction the form login uses."""
        ct, wt = self._ct, self._wt
        token = wt.HANDLE()
        status = self._secur32.QuerySecurityContextToken(
            ct.byref(self._ctxt), ct.byref(token)
        )
        if status != SEC_E_OK:
            logger.warning(
                "QuerySecurityContextToken failed: 0x%08X",
                status & 0xFFFFFFFF,
            )
            return None
        try:
            user, domain = self._token_user(token)
            if not user:
                return None
            try:
                groups = _groups_from_token(
                    token, self._advapi32, self._kernel32
                )
            except Exception:  # pragma: no cover — best effort, like form
                logger.warning(
                    "could not read token groups for %r", user, exc_info=True
                )
                groups = []
            # A local account resolves with the machine name as its
            # "domain" — normalize to None so SSO and form sign-ins of the
            # same local account yield the same principal name.
            machine = os.environ.get("COMPUTERNAME", "")
            if domain and machine and domain.upper() == machine.upper():
                domain = None
            return WindowsIdentity(
                username=user, domain=domain or None, groups=groups
            )
        finally:
            self._kernel32.CloseHandle(token)

    def _token_user(self, token) -> Tuple[str, str]:
        """TokenUser SID → (account name, domain) via LookupAccountSidW."""
        ct, wt = self._ct, self._wt

        needed = wt.DWORD(0)
        self._advapi32.GetTokenInformation(
            token, _TOKEN_USER, None, 0, ct.byref(needed)
        )
        if needed.value == 0:
            return "", ""
        buf = ct.create_string_buffer(needed.value)
        if not self._advapi32.GetTokenInformation(
            token, _TOKEN_USER, buf, needed, ct.byref(needed)
        ):
            return "", ""
        # TOKEN_USER is a single SID_AND_ATTRIBUTES; Sid is its first field.
        sid_ptr = ct.cast(buf, ct.POINTER(ct.c_void_p)).contents

        name_len = wt.DWORD(0)
        dom_len = wt.DWORD(0)
        sid_type = wt.DWORD(0)
        self._advapi32.LookupAccountSidW(
            None, sid_ptr, None, ct.byref(name_len),
            None, ct.byref(dom_len), ct.byref(sid_type),
        )
        if name_len.value == 0:
            return "", ""
        name_buf = ct.create_unicode_buffer(name_len.value)
        dom_buf = ct.create_unicode_buffer(max(dom_len.value, 1))
        if not self._advapi32.LookupAccountSidW(
            None, sid_ptr, name_buf, ct.byref(name_len),
            dom_buf, ct.byref(dom_len), ct.byref(sid_type),
        ):
            return "", ""
        return name_buf.value, dom_buf.value

    def close(self) -> None:
        """Release the SSPI context and credentials (idempotent)."""
        if self._have_ctxt:
            self._secur32.DeleteSecurityContext(self._ct.byref(self._ctxt))
            self._have_ctxt = False
        if self._have_cred:
            self._secur32.FreeCredentialsHandle(self._ct.byref(self._cred))
            self._have_cred = False

    def __del__(self):  # pragma: no cover — backstop only
        try:
            self.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Pending-handshake parking (NTLM multi-leg, keyed by TCP connection)
# ---------------------------------------------------------------------------


class PendingHandshakes:
    """Park partial handshakes between an NTLM exchange's HTTP legs.

    Keyed by the client's (host, port) — the browser performs all legs on
    one TCP connection, so the ephemeral port identifies it. Entries are
    short-lived: a browser answers a challenge immediately or not at all.
    """

    def __init__(self, ttl_s: float = 30.0, max_entries: int = 64) -> None:
        self._ttl = ttl_s
        self._max = max_entries
        self._lock = threading.Lock()
        self._entries: Dict[tuple, Tuple[object, float]] = {}

    def pop(self, key: tuple):
        """Remove and return the parked handshake for ``key``, or None."""
        with self._lock:
            self._evict_locked()
            entry = self._entries.pop(key, None)
        return entry[0] if entry else None

    def put(self, key: tuple, handshake) -> None:
        with self._lock:
            self._evict_locked()
            old = self._entries.pop(key, None)
            self._entries[key] = (handshake, time.monotonic() + self._ttl)
        if old:
            self._close_quietly(old[0])

    def _evict_locked(self) -> None:
        now = time.monotonic()
        expired = [k for k, (_, dl) in self._entries.items() if dl <= now]
        for k in expired:
            hs, _ = self._entries.pop(k)
            self._close_quietly(hs)
        while len(self._entries) >= self._max:
            # Oldest deadline first.
            oldest = min(self._entries, key=lambda k: self._entries[k][1])
            hs, _ = self._entries.pop(oldest)
            self._close_quietly(hs)

    @staticmethod
    def _close_quietly(handshake) -> None:
        try:
            handshake.close()
        except Exception:  # pragma: no cover
            pass

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


#: Process-wide parking lot used by the /login/sso route.
pending_handshakes = PendingHandshakes()


def decode_negotiate_header(authorization: str) -> Optional[bytes]:
    """Extract the token blob from an ``Authorization: Negotiate <b64>``
    header value; None if the header isn't a usable Negotiate token."""
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "negotiate":
        return None
    try:
        return base64.b64decode(parts[1], validate=True)
    except Exception:
        return None
