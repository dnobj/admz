"""Outbound HTTP Negotiate (SPNEGO) for talking to an ACS Pro server.

ACS Pro authenticates with Windows Integrated Auth (Kerberos/NTLM). ADMZ
authenticates as **its own process identity** — in the single-operator local
deploy that is the logged-in operator (ADR-0039). No ACS password is ever
stored: we ask Windows SSPI for a token via ``InitializeSecurityContext`` and
put it in ``Authorization: Negotiate <base64>``, exactly mirroring the
acceptor side in :mod:`admz.win_sspi` (ADR-0035) and its loopback test client.

``NegotiateClient`` drives the (possibly multi-leg, for NTLM) handshake; the
executor feeds back any ``WWW-Authenticate: Negotiate <challenge>`` and retries.
Off Windows / when SSPI is unavailable it raises ``WinAuthUnavailable`` so the
executor can return a clean, gated error instead of crashing.
"""

from __future__ import annotations

import base64
from typing import Optional, Tuple

from admz import win_sspi
from admz.win_auth import WinAuthUnavailable


def negotiate_available() -> bool:
    """Whether outbound Negotiate can be attempted on this host (Windows)."""
    import sys

    return sys.platform == "win32"


def spn_for(host: str) -> str:
    """HTTP service principal name for an ACS host (``HTTP/<host>``)."""
    h = (host or "").strip()
    # Strip scheme/port if a URL or host:port slipped through.
    if "://" in h:
        h = h.split("://", 1)[1]
    h = h.split("/", 1)[0].split(":", 1)[0]
    return f"HTTP/{h}"


class NegotiateClient:
    """One outbound Negotiate security context (the initiator/client side).

    ``step(in_blob)`` runs ``InitializeSecurityContext`` and returns
    ``(done, out_blob)``:
      * first call with ``in_blob=None`` produces the initial token,
      * if the server challenged, pass its decoded token back in,
      * ``done`` is True once SSPI reports the context complete.
    """

    def __init__(self, target_spn: str) -> None:
        (self._ct, self._wt, self._secur32, _a, _k,
         self._structs) = win_sspi._sspi()
        SecHandle = self._structs["SecHandle"]
        self._cred = SecHandle()
        self._ctxt = SecHandle()
        self._have_cred = False
        self._have_ctxt = False
        self._target = target_spn
        self._max_token = win_sspi._max_token_size(
            self._ct, self._secur32, self._structs
        )
        expiry = self._structs["TimeStamp"]()
        status = self._secur32.AcquireCredentialsHandleW(
            None, win_sspi._PACKAGE, win_sspi._SECPKG_CRED_OUTBOUND,
            None, None, None, None,
            self._ct.byref(self._cred), self._ct.byref(expiry),
        )
        if status != win_sspi.SEC_E_OK:
            raise WinAuthUnavailable(
                f"AcquireCredentialsHandleW(Negotiate, outbound) failed: "
                f"0x{status & 0xFFFFFFFF:08X}"
            )
        self._have_cred = True

    def step(self, in_blob: Optional[bytes]) -> Tuple[bool, bytes]:
        ct = self._ct
        in_ref = None
        if in_blob is not None:
            in_desc, _b, _back = win_sspi._token_buffer(
                ct, self._structs, in_blob
            )
            in_ref = ct.byref(in_desc)
        out_desc, out_buf, out_backing = win_sspi._token_buffer(
            ct, self._structs, None, self._max_token
        )
        attr = ct.c_ulong(0)
        expiry = self._structs["TimeStamp"]()
        status = self._secur32.InitializeSecurityContextW(
            ct.byref(self._cred),
            ct.byref(self._ctxt) if self._have_ctxt else None,
            self._target,
            win_sspi._ASC_REQ_CONNECTION,  # ISC_REQ_CONNECTION (same bit)
            0,
            win_sspi._SECURITY_NATIVE_DREP,
            in_ref,
            0,
            ct.byref(self._ctxt),
            ct.byref(out_desc),
            ct.byref(attr),
            ct.byref(expiry),
        )
        self._have_ctxt = True
        if status in (
            win_sspi.SEC_I_COMPLETE_NEEDED,
            win_sspi.SEC_I_COMPLETE_AND_CONTINUE,
        ):
            self._secur32.CompleteAuthToken(
                ct.byref(self._ctxt), ct.byref(out_desc)
            )
            status = (
                win_sspi.SEC_I_CONTINUE_NEEDED
                if status == win_sspi.SEC_I_COMPLETE_AND_CONTINUE
                else win_sspi.SEC_E_OK
            )
        out_blob = bytes(out_backing.raw[: out_buf.cbBuffer])
        done = status == win_sspi.SEC_E_OK
        return done, out_blob

    def close(self) -> None:
        if self._have_ctxt:
            self._secur32.DeleteSecurityContext(self._ct.byref(self._ctxt))
            self._have_ctxt = False
        if self._have_cred:
            self._secur32.FreeCredentialsHandle(self._ct.byref(self._cred))
            self._have_cred = False


def initial_header(host: str) -> Tuple[str, "NegotiateClient"]:
    """Build the first ``Authorization: Negotiate <b64>`` header for ``host``.

    Returns the header value plus the live client, so the caller can continue a
    multi-leg (NTLM) handshake by feeding back the server's challenge. Raises
    ``WinAuthUnavailable`` off Windows / on SSPI failure.
    """
    client = NegotiateClient(spn_for(host))
    _done, token = client.step(None)
    return "Negotiate " + base64.b64encode(token).decode("ascii"), client


def continued_header(client: "NegotiateClient", challenge_b64: str) -> str:
    """Next leg: feed the server's base64 challenge back, return the header."""
    challenge = base64.b64decode(challenge_b64)
    _done, token = client.step(challenge)
    return "Negotiate " + base64.b64encode(token).decode("ascii")
