"""Tests for admz.win_sspi — in-process Negotiate SSO (ADR-0035).

The HTTP route flow is covered with a mocked handshake in
test_windows_local_backend.py. This file covers the module itself:
platform guard, header parsing, the pending-handshake parking lot, and —
on Windows only — a REAL SSPI handshake: a client security context
(InitializeSecurityContextW, the browser's role) driven against
NegotiateHandshake (the server role), asserting the resulting identity
names the user running the tests. That exercises every SSPI call the
production path uses, with no browser involved.
"""

from __future__ import annotations

import sys

import pytest

import admz.win_sspi as win_sspi
from admz.win_auth import WinAuthUnavailable


class TestSsoAvailable:
    def test_disabled_by_env(self, monkeypatch):
        monkeypatch.setenv("ADMZ_SSO_NEGOTIATE", "0")
        assert win_sspi.sso_available() is False

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_default_on_windows(self, monkeypatch):
        monkeypatch.delenv("ADMZ_SSO_NEGOTIATE", raising=False)
        assert win_sspi.sso_available() is True

    @pytest.mark.skipif(sys.platform == "win32", reason="non-Windows only")
    def test_never_available_off_windows(self, monkeypatch):
        monkeypatch.delenv("ADMZ_SSO_NEGOTIATE", raising=False)
        assert win_sspi.sso_available() is False


@pytest.mark.skipif(sys.platform == "win32", reason="non-Windows only")
class TestOffWindowsGuard:
    def test_handshake_raises_unavailable(self):
        with pytest.raises(WinAuthUnavailable):
            win_sspi.NegotiateHandshake()


class TestDecodeNegotiateHeader:
    def test_valid(self):
        import base64
        blob = b"\x01\x02negotiate-token"
        header = f"Negotiate {base64.b64encode(blob).decode()}"
        assert win_sspi.decode_negotiate_header(header) == blob

    def test_case_insensitive_scheme(self):
        import base64
        header = f"negotiate {base64.b64encode(b'x').decode()}"
        assert win_sspi.decode_negotiate_header(header) == b"x"

    @pytest.mark.parametrize("header", [
        "",
        "Negotiate",                      # no token
        "Bearer abc123",                  # wrong scheme
        "Negotiate not-base64!!!",        # invalid b64
        "Basic dXNlcjpwYXNz",
    ])
    def test_rejects(self, header):
        assert win_sspi.decode_negotiate_header(header) is None


class _DummyHandshake:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class TestPendingHandshakes:
    def test_put_pop_roundtrip(self):
        store = win_sspi.PendingHandshakes(ttl_s=60)
        hs = _DummyHandshake()
        store.put(("127.0.0.1", 5000), hs)
        assert store.pop(("127.0.0.1", 5000)) is hs
        assert store.pop(("127.0.0.1", 5000)) is None  # gone after pop

    def test_expired_entry_is_closed_and_dropped(self):
        store = win_sspi.PendingHandshakes(ttl_s=-1.0)  # born expired
        hs = _DummyHandshake()
        store.put(("127.0.0.1", 5000), hs)
        assert store.pop(("127.0.0.1", 5000)) is None
        assert hs.closed is True

    def test_cap_evicts_oldest_and_closes_it(self):
        store = win_sspi.PendingHandshakes(ttl_s=60, max_entries=2)
        first = _DummyHandshake()
        store.put(("c", 1), first)
        store.put(("c", 2), _DummyHandshake())
        store.put(("c", 3), _DummyHandshake())
        assert len(store) == 2
        assert first.closed is True
        assert store.pop(("c", 1)) is None
        assert store.pop(("c", 3)) is not None

    def test_replacing_a_key_closes_the_old_handshake(self):
        store = win_sspi.PendingHandshakes(ttl_s=60)
        old = _DummyHandshake()
        store.put(("c", 1), old)
        store.put(("c", 1), _DummyHandshake())
        assert old.closed is True
        assert len(store) == 1


# ---------------------------------------------------------------------------
# The real thing — Windows only: full loopback SSPI handshake
# ---------------------------------------------------------------------------


class _SspiClient:
    """The browser's role: an outbound Negotiate security context."""

    def __init__(self, target: str | None = None):
        (self._ct, self._wt, self._secur32, _a, _k,
         self._structs) = win_sspi._sspi()
        SecHandle = self._structs["SecHandle"]
        self._cred = SecHandle()
        self._ctxt = SecHandle()
        self._have_ctxt = False
        self._target = target
        self._max_token = win_sspi._max_token_size(
            self._ct, self._secur32, self._structs
        )
        expiry = self._structs["TimeStamp"]()
        status = self._secur32.AcquireCredentialsHandleW(
            None, win_sspi._PACKAGE, win_sspi._SECPKG_CRED_OUTBOUND,
            None, None, None, None,
            self._ct.byref(self._cred), self._ct.byref(expiry),
        )
        assert status == win_sspi.SEC_E_OK, f"client creds: 0x{status & 0xFFFFFFFF:08X}"

    def step(self, in_blob: bytes | None):
        ct = self._ct
        if in_blob is not None:
            in_desc, _b, _back = win_sspi._token_buffer(
                ct, self._structs, in_blob
            )
            in_ref = ct.byref(in_desc)
        else:
            in_ref = None
        out_desc, out_buf, out_backing = win_sspi._token_buffer(
            ct, self._structs, None, self._max_token
        )
        attr = ct.c_ulong(0)
        expiry = self._structs["TimeStamp"]()
        status = self._secur32.InitializeSecurityContextW(
            ct.byref(self._cred),
            ct.byref(self._ctxt) if self._have_ctxt else None,
            self._target,
            win_sspi._ASC_REQ_CONNECTION,  # ISC_REQ_CONNECTION, same bit
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
        return status, out_blob

    def close(self):
        if self._have_ctxt:
            self._secur32.DeleteSecurityContext(self._ct.byref(self._ctxt))
            self._have_ctxt = False
        self._secur32.FreeCredentialsHandle(self._ct.byref(self._cred))


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only (SSPI)")
class TestRealLoopbackHandshake:
    def test_full_handshake_yields_current_user(self):
        import os

        server = win_sspi.NegotiateHandshake()
        client = _SspiClient()
        try:
            status, client_blob = client.step(None)
            identity = None
            for _ in range(6):  # NTLM: 2 client legs; Kerberos: 1
                result, server_blob, identity = server.step(client_blob)
                if result == win_sspi.FAILED:
                    pytest.fail("server side failed the handshake")
                if result == win_sspi.COMPLETE:
                    break
                status, client_blob = client.step(server_blob)
                assert client_blob, "client produced no token to continue"
            else:
                pytest.fail("handshake did not converge")

            assert identity is not None
            assert identity.username.lower() == os.environ["USERNAME"].lower()
            # Local account on a workgroup box → machine domain normalized
            # away; on a domain account this would be the domain name.
            machine = os.environ.get("COMPUTERNAME", "").upper()
            if identity.domain:
                assert identity.domain.upper() != machine
        finally:
            client.close()
            server.close()

    def test_garbage_token_fails_cleanly(self):
        server = win_sspi.NegotiateHandshake()
        result, blob, identity = server.step(b"\x00garbage-not-a-token")
        assert result == win_sspi.FAILED
        assert identity is None
