"""AcsProExecutor — talks to an ACS Pro server's Facade/Operation HTTP-JSON API.

A new ``BaseExecutor`` family (``acs-pro``) so ACS ops flow through the same
spine as VAPIX. POSTs JSON to ``https://<server>:29204/Acs/Api/<Facade>/<Op>``,
authenticates with **Negotiate as the ADMZ process identity** (no stored
password), and tolerates ACS's self-signed cert **per connection only**.

``self_heals()`` is False: ACS authenticates per request, so the gate never
rewrites stored auth for this family (ADR-0039).

v1 is read-only; every wired op is ``risk_level: read``. The HTTP send is
isolated in :func:`_send` so unit tests can drive the executor without a live
server (the real Negotiate handshake needs an on-prem Windows/ACS box).
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional, Tuple

from admz.executor.base import BaseExecutor
from admz.executor.models import StepResult

_DEFAULT_TIMEOUT = 15.0


async def _send(
    client: Any,
    method: str,
    url: str,
    headers: Dict[str, str],
    json_body: Optional[Dict[str, Any]],
) -> Tuple[int, str, Dict[str, str], str]:
    """One HTTP request on a SHARED async client; returns
    (status_code, text, response_headers, reason_phrase).

    Async so it never blocks the uvicorn event loop. Isolated so tests
    monkeypatch it. NTLM is **connection-bound** — every leg of the handshake
    must reuse the *same* keep-alive connection — so the caller passes one
    ``httpx.AsyncClient`` for the whole exchange. ACS carries the error type in
    the HTTP reason phrase, so we surface it.
    """
    resp = await client.request(method, url, headers=headers, json=json_body)
    return resp.status_code, resp.text, dict(resp.headers), resp.reason_phrase


def _negotiate_challenge(www_authenticate: str) -> Optional[str]:
    """Extract the base64 token from a ``Negotiate <token>`` challenge.

    Tolerates a combined header like ``Negotiate <token>, Basic realm=""``.
    """
    for part in (www_authenticate or "").split(","):
        part = part.strip()
        if part.lower().startswith("negotiate ") and len(part.split(None, 1)) == 2:
            return part.split(None, 1)[1]
    return None


class AcsProExecutor(BaseExecutor):
    def __init__(self, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self._timeout = timeout

    @property
    def family(self) -> str:
        return "acs-pro"

    def self_heals(self) -> bool:
        return False

    async def execute(
        self,
        operation: Dict[str, Any],
        device: Dict[str, Any],
        credentials: Dict[str, Any],
        params: Dict[str, str],
    ) -> StepResult:
        op_id = operation.get("id") or operation.get("operation") or "acs-op"
        dev_id = device.get("device_id") or "acs-server"
        started = time.monotonic()

        base = (device.get("host") or "").rstrip("/")
        if not base:
            return StepResult(
                operation_id=op_id, device_id=dev_id, success=False,
                error="ACS Pro server is not configured (no host).",
            )

        path = operation.get("path") or (
            f"/Acs/Api/{operation.get('cgi', '')}/{operation.get('operation', '')}"
        )
        method = (operation.get("method") or "POST").upper()
        url = base + path
        verify = bool(device.get("verify_tls", False))
        timeout = operation.get("timeout_override") or self._timeout

        # GH #160: a caller may forbid authentication for this call. Used by
        # the "Test connection" probe against a host nobody has confirmed is
        # the ACS server — see the route for why that matters. When set we
        # never mint a token, never send Authorization, and never continue a
        # 401 challenge, so no credential material leaves this machine.
        no_auth = bool(device.get("no_negotiate"))

        # Negotiate as the process identity. Off Windows / SSPI failure → a
        # clean, gated error rather than a crash.
        from admz.modules.acs_pro import negotiate

        auth_header, neg_client = None, None
        try:
            if not no_auth:
                auth_header, neg_client = negotiate.initial_header(base)
        except Exception as exc:  # noqa: BLE001 — WinAuthUnavailable etc.
            return StepResult(
                operation_id=op_id, device_id=dev_id, success=False,
                error=(
                    "Negotiate authentication unavailable on this host "
                    f"({type(exc).__name__}: {exc}). ACS Pro requires Windows "
                    "Integrated Auth; ADMZ must run as a Windows user with "
                    "access to the ACS server."
                ),
            )

        reason = ""
        try:
            import httpx

            headers = {"Content-Type": "application/json"}
            if auth_header is not None:
                headers["Authorization"] = auth_header
            body = dict(params or {})
            # ONE keep-alive connection for the whole exchange — NTLM binds the
            # handshake to a single TCP connection (a new connection per leg
            # makes the server reject the type-3 token). Async so it never
            # blocks the event loop the web/voice surfaces run on.
            async with httpx.AsyncClient(verify=verify, timeout=timeout) as http:
                status, text, resp_headers, reason = await _send(
                    http, method, url, headers, body
                )
                # NTLM challenge leg: re-send the continued token on the SAME
                # connection. ACS challenges with HTTP 401 + WWW-Authenticate.
                if status == 401 and neg_client is not None:
                    token = _negotiate_challenge(
                        resp_headers.get("www-authenticate", "")
                    )
                    if token:
                        headers["Authorization"] = negotiate.continued_header(
                            neg_client, token
                        )
                        status, text, resp_headers, reason = await _send(
                            http, method, url, headers, body
                        )
        except Exception as exc:  # noqa: BLE001 — unreachable host / TLS / timeout
            return StepResult(
                operation_id=op_id, device_id=dev_id, success=False,
                error=(
                    f"Could not reach ACS Pro at {base} "
                    f"({type(exc).__name__}: {exc})."
                ),
                duration_ms=(time.monotonic() - started) * 1000.0,
            )
        finally:
            # None whenever `no_negotiate` was set — no context was ever
            # acquired. The blanket except below would have swallowed the
            # AttributeError, but relying on that reads like an accident.
            if neg_client is not None:
                try:
                    neg_client.close()
                except Exception:  # noqa: BLE001
                    pass

        dur = (time.monotonic() - started) * 1000.0

        if 200 <= status < 300:
            parsed: Any = None
            if text:
                try:
                    parsed = json.loads(text)
                except ValueError:
                    parsed = None
            return StepResult(
                operation_id=op_id, device_id=dev_id, success=True,
                status_code=status, response_body=text, parsed_data=parsed,
                duration_ms=dur,
            )

        # ACS carries the exception type in the HTTP reason phrase (e.g.
        # "UnauthorizedException", "ApiException"), often with an empty body.
        detail = reason or (text or "").strip()[:300] or "(no detail)"
        return StepResult(
            operation_id=op_id, device_id=dev_id, success=False,
            status_code=status, response_body=text,
            error=f"ACS Pro returned HTTP {status} ({detail}).",
            duration_ms=dur,
        )
