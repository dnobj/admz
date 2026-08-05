"""
VAPIX executor — builds and sends HTTP requests for VAPIX operations.

Handles all four VAPIX generations:
  - legacy-cgi: GET with query parameters
  - json-rpc: POST with JSON body
  - config-rest: REST methods with JSON body
  - soap: POST XML to /vapix/services
"""

import json as json_module
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote
from xml.etree import ElementTree

import httpx

from admz.executor.base import BaseExecutor
from admz.executor.models import ExecutionRequest, StepResult
from admz.ssl_config import verify_ssl_default

logger = logging.getLogger(__name__)

# H-3 (review 2026-06-10): file uploads may only read from the firmware
# cache. The upload path reaches the executor via caller-supplied operation
# params (e.g. a chatbot tool call), so an unconstrained path would let a
# caller read ANY host file (the Fernet key, the SQLite DB, ...) and
# exfiltrate it to a device it controls. Resolved at CALL time via
# admz.paths (ADR-0042) so ADMZ_HOME set after import is honored; admz.paths
# imports only stdlib, so the executor stays a leaf module.
def _upload_root() -> Path:
    from admz.paths import firmware_dir
    return firmware_dir()


def _auth_method_from_challenge(header: Optional[str]) -> Optional[str]:
    """Parse a ``WWW-Authenticate`` header into ``"basic"`` / ``"digest"``.

    Used by the connectivity self-healing path to relearn a device's auth
    method when the configured one was wrong. Prefers Digest when a device
    offers both. Returns None if the header is absent/unrecognized.
    """
    if not header:
        return None
    low = header.lower()
    if "digest" in low:
        return "digest"
    if "basic" in low:
        return "basic"
    return None


def _is_plaintext_channel(scheme: str) -> bool:
    """True unless this channel is TLS.

    Deliberately expressed as "not https" rather than "== http" so an absent,
    malformed or unexpected scheme is treated as plaintext. This is a security
    predicate, and the mistake it must never make is calling a plaintext
    channel encrypted; over-refusing is recoverable, under-refusing spends a
    password. See ``_send_self_healing`` and GH #171.
    """
    return (scheme or "").strip().lower() != "https"


def _upload_path_allowed(file_path: str) -> bool:
    """True if ``file_path`` resolves to inside the firmware cache.

    Resolves symlinks and ``..`` segments before comparing, so neither
    traversal nor a symlink planted in the cache can escape the root.
    """
    try:
        resolved = Path(file_path).resolve()
        root = _upload_root().resolve()
    except (OSError, ValueError):
        return False
    return resolved == root or root in resolved.parents


class PathParamRejected(ValueError):
    """A config-rest path parameter would have changed the request's shape.

    Raised rather than silently stripping or encoding the offending value:
    the caller (an MCP tool call, a chat turn, a REST body) asked for
    something that would retarget the request, and should be told so —
    both for the audit trail and so it doesn't chase a confusing 404.
    """


# Issue #10: config-rest is the ONLY generation that interpolates
# caller-supplied params into the URL *path* (legacy-cgi puts them in
# ``params=`` and json-rpc in a JSON body, both of which httpx encodes for
# us). Those params reach the executor from untrusted surfaces — the same
# provenance the H-3 note above describes — so a raw substitution is a live
# injection sink, not a theoretical one.
#
# These constructs change the SHAPE of the request rather than its content,
# and httpx 0.28 actively cooperates with each: it RESOLVES "." / ".."
# dot-segments client-side before sending (so traversal succeeds), and it
# honours "?" and "#" as query/fragment starts (config-rest passes
# ``params=None``, so an injected query survives to the wire).
_PATH_PARAM_FORBIDDEN: Tuple[Tuple[str, str], ...] = (
    ("/", "path separator"),
    ("\\", "path separator"),
    ("?", "query separator"),
    ("#", "fragment separator"),
)

# A value may hide a forbidden construct behind percent-encoding ("%2e%2e")
# or behind two layers of it ("%252e%252e"). Three rounds is well past any
# legitimate value while staying bounded.
_MAX_DECODE_ROUNDS = 3


def _reject_shape_changing(name: str, text: str, origin: str = "") -> None:
    """Raise ``PathParamRejected`` if ``text`` is not a single, inert segment."""
    via = f" (percent-decoded from {origin!r})" if origin else ""

    for ch, why in _PATH_PARAM_FORBIDDEN:
        if ch in text:
            raise PathParamRejected(
                f"Path parameter {name!r} contains a {why} ({ch!r}){via}: "
                f"{text!r}. Path parameters name a single resource and may "
                "not add or retarget URL segments."
            )

    if text == ".":
        raise PathParamRejected(
            f"Path parameter {name!r} is a bare '.' path segment{via}. "
            "It would be resolved away before the request is sent."
        )

    if ".." in text:
        raise PathParamRejected(
            f"Path parameter {name!r} contains '..'{via}: {text!r}. "
            "Parent-directory segments are resolved by the HTTP client "
            "before sending, which would escape the operation's endpoint."
        )

    for ch in text:
        if ord(ch) < 0x20 or ord(ch) == 0x7F:
            raise PathParamRejected(
                f"Path parameter {name!r} contains a control character "
                f"({ch!r}){via}: {text!r}."
            )


def _sanitize_path_param(name: str, value: Any) -> str:
    """Return ``value`` percent-encoded for use as ONE URL path segment.

    Rejects anything that would change the request's shape, then encodes
    what survives with ``safe=""`` — the default ``safe="/"`` would leave a
    separator intact and preserve the very exposure this closes.

    Only the *value* is encoded, never the assembled path template: several
    catalogued operations have literal templates that percent-encoding would
    break (``param:exportParams`` is ``path: '/$export'``).
    """
    text = str(value)

    if not text:
        raise PathParamRejected(
            f"Path parameter {name!r} is empty; an empty value collapses a "
            "URL path segment and would retarget the request."
        )

    _reject_shape_changing(name, text)

    # Re-run the same check against each decoding layer, so the guard cannot
    # be bypassed by spelling the construct as "%2f" or "%252e".
    probe = text
    for _ in range(_MAX_DECODE_ROUNDS):
        decoded = unquote(probe)
        if decoded == probe:
            break
        _reject_shape_changing(name, decoded, origin=text)
        probe = decoded

    return quote(text, safe="")


# Issue #144: soap is the other generation that interpolates caller-supplied
# params into a *structured* payload without the transport encoding them for
# us. The four generations differ, and only two ever had a problem:
#
#   legacy-cgi   -> query_params -> httpx ``params=``   encoded by the client
#   json-rpc     -> JSON body                           escaped by serialisation
#   config-rest  -> URL path                            #10, fixed in PR #146
#   soap         -> raw XML body                        THIS
#
# json-rpc is safe by accident of ``json.dumps``, not by design — the same
# ``_resolve_template`` helper feeds both. So the escape belongs HERE, in the
# SOAP builder, and NOT in ``_resolve_template``: that helper is shared with
# legacy-cgi and json-rpc, where XML-escaping a value would corrupt it
# (a query param would go on the wire as ``a&amp;b``).
#
# ESCAPE, don't reject. Legitimate SOAP values contain nearly every
# metacharacter a reject-list would want to ban: ``&`` in a recipient query
# string (``camera=entrance&event=motion``), ``/`` and ``:`` in a topic
# expression (``tns1:Device/tnsaxis:IO/VirtualInput``), quotes and brackets in
# an XPath filter, spaces in rule names. Escaping preserves all of them —
# ``&amp;`` decodes back to ``&`` at the device — where a reject-list would
# break real operations. That is the #10 lesson applied to a different sink.
#
# Ampersand MUST be replaced first: doing it later would re-escape the "&"
# that the other rows introduce ("<" -> "&lt;" -> "&amp;lt;").
_XML_ESCAPES: Tuple[Tuple[str, str], ...] = (
    ("&", "&amp;"),
    ("<", "&lt;"),
    (">", "&gt;"),
    ('"', "&quot;"),
    ("'", "&apos;"),
)


def _xml_escape_param(value: Any) -> str:
    """Return ``value`` as XML text that cannot escape its element.

    Every catalogued placeholder sits in element *text*, so ``&``, ``<`` and
    ``>`` are strictly sufficient today — verified mechanically against all 30
    ``ws/`` op templates at the pinned atlas SHA. The two quote forms are
    escaped anyway so that a future template which puts a placeholder inside an
    *attribute* is correct on arrival rather than silently under-escaped; in
    text content they round-trip identically, which the accept table asserts.

    Deliberately NOT handled: XML 1.0 forbids most C0 control characters even
    in escaped form, so a value containing ``\\x00`` yields a body the device's
    parser rejects outright. That is a malformed request, not an injection —
    no escaping can express those characters, and rejecting them here would be
    the reject-list this function exists to avoid. Left alone knowingly.
    """
    text = str(value)
    for ch, replacement in _XML_ESCAPES:
        text = text.replace(ch, replacement)
    return text


class _BearerAuth(httpx.Auth):
    """Bearer token authentication for httpx."""

    def __init__(self, token: str):
        self._token = token

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {self._token}"
        yield request


class VapixExecutor(BaseExecutor):
    """Executor for VAPIX operations on Axis cameras/devices."""

    def __init__(
        self,
        timeout: float = 15.0,
        verify_ssl: Optional[bool] = None,
        retries: int = 1,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self._timeout = timeout
        # If caller didn't pin a value, honor ADMZ_VERIFY_SSL (default False).
        self._verify_ssl = (
            verify_ssl_default() if verify_ssl is None else bool(verify_ssl)
        )
        self._retries = retries
        # Test seam: when set, all requests go through this transport (e.g.
        # httpx.MockTransport). Production leaves it None and builds a real one.
        self._transport = transport

    def _make_transport(self) -> httpx.AsyncBaseTransport:
        return self._transport or httpx.AsyncHTTPTransport(
            retries=self._retries, verify=self._verify_ssl
        )

    @property
    def family(self) -> str:
        return "vapix"

    async def execute(
        self,
        operation: Dict[str, Any],
        device: Dict[str, Any],
        credentials: Dict[str, Any],
        params: Dict[str, str],
    ) -> StepResult:
        """Execute a VAPIX operation."""
        op_id = operation.get("id", "unknown")
        device_id = device.get("device_id", "unknown")
        host = device.get("host", "")
        start = time.monotonic()

        if not host:
            return StepResult(
                operation_id=op_id,
                device_id=device_id,
                success=False,
                error="No host address for device",
            )

        try:
            # Build the HTTP request from operation spec
            request = self.build_request(operation, params)

            # H-3: refuse uploads from outside the firmware cache
            # (scheme-independent, so check once up front).
            if request.file_path and not _upload_path_allowed(request.file_path):
                return StepResult(
                    operation_id=op_id,
                    device_id=device_id,
                    success=False,
                    error=(
                        "Upload file_path must be inside the firmware "
                        f"cache ({_upload_root()}); got: {request.file_path}. "
                        "Use download_firmware or import_firmware to "
                        "stage the file first."
                    ),
                )

            # Determine scheme from device auth profile
            auth_info = device.get("auth")
            if auth_info and isinstance(auth_info, dict):
                scheme = auth_info.get("scheme", "http")
            else:
                scheme = "http"
            port = device.get("port", 443 if scheme == "https" else 80)

            # Per-operation timeout override (e.g., firmware upload)
            effective_timeout = request.timeout_override or self._timeout

            # Send with connectivity self-healing: on a connection refusal,
            # retry the other scheme; on a 401 whose challenge names a
            # different auth method, retry with that method. Any correction is
            # returned as ``learned_auth`` for the caller to persist.
            response, learned_auth = await self._send_self_healing(
                request=request, host=host, device=device,
                credentials=credentials, scheme=scheme, port=port,
                timeout=effective_timeout,
            )

            elapsed = (time.monotonic() - start) * 1000

            # Parse response
            result = self._parse_response(
                operation, response, op_id, device_id, elapsed
            )
            if learned_auth:
                result.learned_auth = learned_auth
            return result

        except PathParamRejected as e:
            # A deliberate refusal, not a surprise — log it at WARNING with
            # the operation and device so the attempt is attributable, and
            # hand the caller the reason verbatim. Must precede the catch-all
            # below, which would file this under "Unexpected error".
            elapsed = (time.monotonic() - start) * 1000
            logger.warning(
                "Refused %s on %s: %s", op_id, device_id, e
            )
            return StepResult(
                operation_id=op_id,
                device_id=device_id,
                success=False,
                error=str(e),
                duration_ms=elapsed,
            )
        except FileNotFoundError:
            elapsed = (time.monotonic() - start) * 1000
            return StepResult(
                operation_id=op_id,
                device_id=device_id,
                success=False,
                error=f"File not found: {getattr(request, 'file_path', 'unknown')}",
                duration_ms=elapsed,
            )
        except httpx.ConnectError as e:
            elapsed = (time.monotonic() - start) * 1000
            return StepResult(
                operation_id=op_id,
                device_id=device_id,
                success=False,
                error=f"Connection failed: {e}",
                duration_ms=elapsed,
            )
        except httpx.TimeoutException:
            elapsed = (time.monotonic() - start) * 1000
            effective_timeout = getattr(request, 'timeout_override', None) or self._timeout
            # Operations like factory-reset/restart cause the device to
            # reboot — the timeout is the *expected* outcome.
            if operation.get("response", {}).get("expect_timeout"):
                return StepResult(
                    operation_id=op_id,
                    device_id=device_id,
                    success=True,
                    warnings=[
                        f"Request timed out after {effective_timeout}s "
                        "(expected — device is rebooting)"
                    ],
                    duration_ms=elapsed,
                )
            return StepResult(
                operation_id=op_id,
                device_id=device_id,
                success=False,
                error=f"Request timed out after {effective_timeout}s",
                duration_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            logger.exception("Unexpected error executing %s on %s", op_id, device_id)
            return StepResult(
                operation_id=op_id,
                device_id=device_id,
                success=False,
                error=str(e),
                duration_ms=elapsed,
            )

    async def _open_and_send(
        self,
        scheme: str,
        host: str,
        port: int,
        request: ExecutionRequest,
        auth: Optional[httpx.Auth],
        timeout: float,
    ) -> httpx.Response:
        """Open a client and send the request once for one scheme/port/auth.

        Propagates httpx.ConnectError / httpx.TimeoutException / FileNotFoundError
        to the caller; returns the httpx.Response otherwise.
        """
        url = f"{scheme}://{host}:{port}{request.path}"
        async with httpx.AsyncClient(
            transport=self._make_transport(), timeout=timeout
        ) as client:
            if request.file_path:
                with open(request.file_path, "rb") as f:
                    files = {
                        request.file_field_name: (
                            os.path.basename(request.file_path),
                            f,
                            "application/octet-stream",
                        )
                    }
                    return await client.request(
                        method=request.method, url=url,
                        data=request.form_data or {}, files=files, auth=auth,
                    )
            if request.raw_body is not None:
                return await client.request(
                    method=request.method, url=url, content=request.raw_body,
                    auth=auth,
                    headers={"Content-Type": request.content_type}
                    if request.content_type else None,
                )
            return await client.request(
                method=request.method, url=url, params=request.query_params,
                json=request.json_body, auth=auth,
                headers={"Content-Type": request.content_type}
                if request.content_type
                and request.content_type != "multipart/form-data" else None,
            )

    async def _send_self_healing(
        self,
        *,
        request: ExecutionRequest,
        host: str,
        device: Dict[str, Any],
        credentials: Dict[str, Any],
        scheme: str,
        port: int,
        timeout: float,
    ) -> Tuple[httpx.Response, Optional[Dict[str, str]]]:
        """Send the request, healing connectivity issues as it goes:

          - on ``httpx.ConnectError`` (e.g. the configured scheme's port is
            refused), retry the *other* scheme on its default port;
          - on a ``401`` whose ``WWW-Authenticate`` names a different auth
            method than we used, retry with that method — *except* Basic on a
            plaintext channel, which is refused (GH #171; see the comment at
            the check). The refusal blocks only *learning* Basic over HTTP; a
            device whose stored profile already says ``{"http": "basic"}``
            keeps working untouched, because the first attempt then uses Basic
            directly and no challenge-driven relearn occurs. That is the
            operator's escape hatch until the pin of D2 lands.

        Returns ``(response, learned_auth)`` where ``learned_auth`` is a profile
        fragment like ``{"scheme": "https", "https": "basic"}`` when a
        correction was applied (else ``None``). Re-raises ``ConnectError`` only
        when *every* scheme refuses the connection. Uploads (``file_path``) are
        never scheme-flipped — a firmware push targets one endpoint.
        """
        method = self._method_for_scheme(device, scheme)
        learned: Optional[Dict[str, str]] = None

        try:
            response = await self._open_and_send(
                scheme, host, port, request,
                self._auth_for_method(method, credentials), timeout,
            )
        except httpx.ConnectError:
            if request.file_path:
                raise  # don't scheme-flip a multipart upload
            alt_scheme = "https" if scheme == "http" else "http"
            alt_port = 443 if alt_scheme == "https" else 80
            alt_method = self._method_for_scheme(device, alt_scheme)
            response = await self._open_and_send(  # may re-raise ConnectError
                alt_scheme, host, alt_port, request,
                self._auth_for_method(alt_method, credentials), timeout,
            )
            scheme, port, method = alt_scheme, alt_port, alt_method
            learned = {"scheme": scheme, scheme: method}

        # Relearn the auth method if the 401 challenge names a different one
        # than we used (profile says digest, device offers basic, ...).
        if response.status_code == 401:
            offered = _auth_method_from_challenge(
                response.headers.get("www-authenticate")
            )
            if offered and offered in ("basic", "digest") and offered != method:
                # GH #171. Refuse to LEARN Basic on a plaintext channel.
                #
                # `WWW-Authenticate` is attacker-controlled: anything answering
                # at the device's address can offer `Basic realm="x"` and, but
                # for this branch, ADMZ would immediately retry with
                # httpx.BasicAuth — which sends `Authorization: Basic
                # base64(user:pass)` PREEMPTIVELY on the first request. Under
                # Digest the password never crosses the wire at all, so this is
                # a real escalation, not a restatement of network access.
                #
                # The check must sit HERE, before the retry is issued. It was
                # measured that the credential is sent before the
                # `retry.status_code != 401` test below, so a defence at
                # persistence time is already too late.
                #
                # Narrow ON PURPOSE — this is not a "protection may only
                # increase" ratchet. Such a rule would strand a camera
                # legitimately reconfigured downward, break the safe
                # Digest->Basic-over-HTTPS relearn that
                # test_method_relearn_digest_to_basic covers, and still not
                # stop the leak. ADR-0007 records that Axis's "Recommended"
                # policy mandates digest-over-HTTP and basic-over-HTTPS, so
                # Basic-over-plaintext is the one combination that is both
                # dangerous and abnormal.
                #
                # A CALLER NOW DEPENDS ON THIS, not just on the general
                # principle (GH #193). `discovery/reconcile.py` verifies that a
                # claimed new address really is the device by authenticating to
                # it with that device's stored credentials — i.e. it sends
                # credentials to an address chosen by an UNAUTHENTICATED mDNS
                # claim, on purpose, because Digest never puts the password on
                # the wire. Relax this branch and that verification becomes a
                # plaintext credential disclosure to whoever won the mDNS race.
                # Pinned by
                # tests/test_reconcile_requires_proof.py::TestThisDependsOnTheBasicDowngradeRefusal
                # so the breakage names its caller rather than only failing
                # this module's own tests.
                #
                # Refusal proceeds WITHOUT learning rather than raising: the
                # request genuinely did 401, which every caller (health
                # monitor, plan engine, MCP, REST) already handles. Raising
                # would invent a failure mode in paths that today only expect
                # ConnectError/TimeoutException.
                if offered == "basic" and _is_plaintext_channel(scheme):
                    # `offered` is one of two known constants, never the raw
                    # header — the challenge is attacker-controlled and does
                    # not belong in the log verbatim.
                    logger.warning(
                        "Refusing to relearn Basic auth over a plaintext %s "
                        "channel for device %s (%s): the challenge asked for "
                        "Basic, which would put the stored password on the "
                        "wire in base64. Keeping %s and returning the 401. "
                        "If this device genuinely requires Basic over HTTP, "
                        "set its stored auth profile explicitly. (GH #171)",
                        scheme, device.get("device_id") or "?", host, method,
                    )
                else:
                    retry = await self._open_and_send(
                        scheme, host, port, request,
                        self._auth_for_method(offered, credentials), timeout,
                    )
                    if retry.status_code != 401:
                        response, method = retry, offered
                        learned = {
                            **(learned or {}), "scheme": scheme, scheme: method
                        }

        return response, learned

    @staticmethod
    def _method_for_scheme(device: Dict[str, Any], scheme: str) -> str:
        """The configured auth method for a scheme (basic/digest/bearer/none)."""
        auth_info = device.get("auth")
        if auth_info and isinstance(auth_info, dict):
            return auth_info.get(scheme, "digest")
        return device.get("auth_method", "digest")  # legacy fallback

    @staticmethod
    def _auth_for_method(
        method: str, credentials: Dict[str, Any]
    ) -> Optional[httpx.Auth]:
        """Build an httpx auth object for a method + credentials."""
        username = credentials.get("username", "")
        password = credentials.get("password", "")
        if method == "none":
            return None
        elif method == "basic":
            return httpx.BasicAuth(username, password)
        elif method == "bearer":
            token = credentials.get("token", password)
            return _BearerAuth(token)
        else:  # "digest" or unknown
            return httpx.DigestAuth(username, password)

    @classmethod
    def _resolve_auth(
        cls,
        device: Dict[str, Any],
        credentials: Dict[str, Any],
        scheme: str = "http",
    ) -> Optional[httpx.Auth]:
        """Resolve HTTP auth from device profile, protocol-aware.

        Axis devices have per-protocol auth policies controlled by
        ``Network.HTTP.AuthenticationPolicy``.  The default policy
        (``Recommended``) uses Digest over HTTP and Basic over HTTPS.

        The structured ``auth`` dict in device info maps each protocol
        to its auth method.  Falls back to the legacy ``auth_method``
        field for backward compatibility.
        """
        return cls._auth_for_method(
            cls._method_for_scheme(device, scheme), credentials
        )

    # Matches {name}, {name:type}, {name=default}, or {name:type=default}
    # placeholders in YAML templates. Group 1 = name, 2 = type hint (optional),
    # 3 = default literal (optional).
    _PLACEHOLDER_RE = re.compile(r"\{(\w+)(?::(\w+))?(?:=([^{}]*))?\}")

    @staticmethod
    def _coerce_value(value: Any, type_hint: str) -> Any:
        """Coerce a value to the type specified by a placeholder hint.

        Supports: int, float, bool, array, object.  Default is str.

        Values arrive either as strings (legacy query params) OR as native
        JSON types — the LLM passes real ints / lists / bools straight
        through the ``execute_operation`` params object. Be tolerant of
        both so a placeholder like ``{colors:array}`` works whether the
        caller sent ``["white"]`` or the string ``'["white"]'``.
        """
        if type_hint == "int":
            return int(value)
        elif type_hint == "float":
            return float(value)
        elif type_hint == "bool":
            if isinstance(value, bool):
                return value
            return str(value).lower() in ("true", "1", "yes")
        elif type_hint in ("array", "object"):
            if isinstance(value, str):
                return json_module.loads(value)
            return value  # already a parsed list/dict
        return value  # "str" or default

    def _resolve_template(
        self, template: Any, params: Dict[str, str]
    ) -> Any:
        """Resolve placeholders in a YAML template recursively.

        Handles three patterns:
          - Whole-value: "{name}", "{name:type}", "{name=default}",
            or "{name:type=default}" — resolved + type-coerced
          - Embedded: "{a},{b}" or "prefix-{x}" — string interpolation
          - Nested dicts/lists: walked recursively

        Default syntax: a placeholder may declare a fallback literal after
        ``=`` (e.g. ``{opticsId=0}``). When the param is absent the default
        is used (and type-coerced) instead of omitting the key — so a
        single-valued device field stays present without the caller having
        to supply it, while still being overridable.
        """
        if isinstance(template, str):
            # Case 1: Whole-value placeholder (optionally typed / defaulted)
            m = re.fullmatch(r"\{(\w+)(?::(\w+))?(?:=([^{}]*))?\}", template)
            if m:
                name, type_hint, default = m.group(1), m.group(2) or "str", m.group(3)
                if name in params:
                    return self._coerce_value(params[name], type_hint)
                if default is not None:
                    return self._coerce_value(default, type_hint)
                return None  # param not provided and no default — omit key

            # Case 2: Embedded placeholders "{a},{b}" or "prefix-{x}-suffix"
            if "{" in template:
                def _replace(m: re.Match) -> str:
                    name, default = m.group(1), m.group(3)
                    if name in params:
                        return str(params[name])
                    if default is not None:
                        return default
                    return m.group(0)
                result = self._PLACEHOLDER_RE.sub(_replace, template)
                if result == template:
                    return template  # nothing resolved
                return result

            return template  # literal string, no placeholders

        elif isinstance(template, dict):
            if not template:
                # An authored empty object is a literal (e.g. the /vapix/call
                # command bodies {"axcall:GetSIPConfiguration": {}}) — dropping
                # it would delete the command key itself.
                return {}
            resolved = {}
            for k, v in template.items():
                val = self._resolve_template(v, params)
                if val is not None:
                    resolved[k] = val
            return resolved if resolved else None

        elif isinstance(template, list):
            return [self._resolve_template(item, params) for item in template]

        # Numbers, booleans from YAML — pass through as-is
        return template

    @staticmethod
    def _flatten_params(params: Any) -> Any:
        """Lift nested scalar leaves into the flat param namespace.

        Placeholder resolution looks up names in the *flat* top-level params,
        but LLMs frequently pass params that mirror the body template's nested
        shape instead — e.g. for ``opticscontrol.cgi:setMagnification`` the doc
        shows ``params.optics[0].magnification``, so the model calls
        ``execute_operation(params={"optics":[{"opticsId":0,"magnification":1.5}]})``
        instead of the flat ``{"magnification":1.5}``. Without this, the nested
        ``magnification`` is never found and the device rejects the request
        (2103 "Required parameter missing" / 2104 "Invalid parameter value").

        We merge nested scalar leaves up by their leaf name. Existing top-level
        keys always win (never overwritten), so flat calls are unchanged.
        """
        if not isinstance(params, dict):
            return params
        flat = dict(params)

        def walk(obj: Any) -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, (dict, list)):
                        walk(v)
                    elif k not in flat:
                        flat[k] = v
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        for v in params.values():
            if isinstance(v, (dict, list)):
                walk(v)
        return flat

    def build_request(
        self, operation: Dict[str, Any], params: Dict[str, str]
    ) -> ExecutionRequest:
        """
        Build an HTTP request from an operation spec and user params.

        Routes to the correct builder based on content-type first,
        then the operation's generation.
        """
        # LLMs often pass params in the body's nested shape rather than flat
        # scalars; lift nested leaves so placeholder resolution finds them.
        params = self._flatten_params(params)

        endpoint = (
            operation.get("_endpoint")
            or operation.get("endpoint", "")
        )

        # Check content_type first — multipart overrides generation
        request_spec = operation.get("request", {})
        content_type = request_spec.get("content_type", "")
        if content_type == "multipart/form-data":
            return self._build_multipart(operation, endpoint, params)

        # Generation comes from _api.yaml, enriched by loader/resolver
        generation = (
            operation.get("_generation")
            or operation.get("generation")
            or "legacy-cgi"
        )

        if generation == "legacy-cgi":
            return self._build_legacy_cgi(operation, endpoint, params)
        elif generation == "json-rpc":
            return self._build_json_rpc(operation, endpoint, params)
        elif generation == "config-rest":
            return self._build_config_rest(operation, params)
        elif generation == "soap":
            return self._build_soap(operation, params)
        else:
            raise ValueError(f"Unknown VAPIX generation: {generation}")

    def _build_legacy_cgi(
        self,
        operation: Dict[str, Any],
        endpoint: str,
        params: Dict[str, str],
    ) -> ExecutionRequest:
        """Build a legacy CGI request (GET with query params)."""
        request_spec = operation.get("request", {})
        query_template = request_spec.get("query", {})

        # Resolve template values (handles whole-value, embedded, compound)
        query: Dict[str, str] = {}
        for k, v in query_template.items():
            resolved = self._resolve_template(v, params)
            if resolved is not None:
                query[k] = str(resolved)

        # Add user params not already in query (for param.cgi key=value pairs)
        for k, v in params.items():
            if k not in query:
                query[k] = str(v)

        timeout_val = request_spec.get("timeout")
        timeout_override = float(timeout_val) if timeout_val else None

        return ExecutionRequest(
            method=operation.get("method", "GET"),
            path=endpoint,
            query_params=query if query else None,
            timeout_override=timeout_override,
        )

    def _build_json_rpc(
        self,
        operation: Dict[str, Any],
        endpoint: str,
        params: Dict[str, str],
    ) -> ExecutionRequest:
        """Build a JSON-RPC request (POST with JSON body).

        Resolves typed placeholders in the body template recursively,
        coercing values to native JSON types (int, bool, array, etc.).
        Falls back to putting params under "params" key if the template
        has no placeholders (backward compat with param.cgi-style ops).
        """
        request_spec = operation.get("request", {})
        body_template = request_spec.get("body", {})

        # Resolve the entire body template recursively
        body = self._resolve_template(body_template, params) or {}

        # Backward compat: JSON-RPC envelope bodies ({apiVersion, method, ...})
        # get leftover params under a "params" key (operations with no typed
        # placeholders yet). Command-keyed bodies (the /vapix/call service:
        # {"axcall:GetSIPConfiguration": {}}) have no "method" envelope and
        # reject stray keys — never inject there.
        if (
            "params" not in body
            and params
            and (not body_template or "method" in body)
        ):
            body["params"] = params

        timeout_val = request_spec.get("timeout")
        timeout_override = float(timeout_val) if timeout_val else None

        return ExecutionRequest(
            method="POST",
            path=endpoint,
            json_body=body,
            content_type="application/json",
            timeout_override=timeout_override,
        )

    def _build_config_rest(
        self,
        operation: Dict[str, Any],
        params: Dict[str, str],
    ) -> ExecutionRequest:
        """Build a config-rest request (REST method + JSON body)."""
        base_path = operation.get("base_path", "")
        sub_path = operation.get("path", "")
        full_path = base_path + sub_path

        # Substitute path parameters. A param consumed by the path must NOT
        # also ride in the JSON body (PATCH /schedules/{id1} with body
        # {"id1": ..., "data": ...} confuses strict config-rest handlers).
        #
        # Every substituted value goes through _sanitize_path_param, which
        # refuses shape-changing values and percent-encodes the rest. This
        # applies uniformly to all placeholders — including the ones in a
        # middle segment (cert:generateCSR is /certificates/{alias}/get_csr)
        # and the two-placeholder siren-and-light:startFunctionPattern —
        # because a stray separator there retargets the request entirely.
        body_params = dict(params)
        for k, v in params.items():
            placeholder = "{" + k + "}"
            if placeholder in full_path:
                full_path = full_path.replace(
                    placeholder, _sanitize_path_param(k, v)
                )
                body_params.pop(k, None)

        request_spec = operation.get("request", {})
        timeout_val = request_spec.get("timeout")
        timeout_override = float(timeout_val) if timeout_val else None

        return ExecutionRequest(
            method=operation.get("method", "GET"),
            path=full_path,
            json_body=body_params if body_params else None,
            content_type="application/json"
            if operation.get("method", "GET") != "GET"
            else None,
            timeout_override=timeout_override,
        )

    def _build_soap(
        self,
        operation: Dict[str, Any],
        params: Dict[str, str],
    ) -> ExecutionRequest:
        """Build a SOAP request (POST XML to /vapix/services).

        Resolves {placeholder} values in the body_xml template using
        the same _resolve_template logic as other generations, with every
        caller-supplied value XML-escaped first (#144).

        Escaping the *params* rather than the rendered body is what makes this
        correct: the template itself is authored catalog content and must stay
        live XML, and a placeholder's authored default (``{limit=100}``) is
        equally trusted — neither passes through ``_xml_escape_param``. Only
        values that came from a caller do.

        No operation is exempt. ``AddActionConfiguration.parameters`` and
        ``AddRecipientConfiguration.parameters`` are authored as raw-XML
        fragment slots, so a carve-out was considered and then measured away:
        the only in-repo consumer of those ops is ``admz.rules.runner``, which
        supplies a pre-rendered ``body_override`` and forces ``params={}``
        (runner.py:180-185), so it never reaches this substitution at all. The
        sole route that *does* reach it is the generic execute surface — MCP
        ``execute_operation``, ``POST /api/catalog/execute``, plan steps —
        which is precisely the untrusted caller this escape defends against.
        An exemption for a caller that does not exist is the worst kind.
        """
        request_spec = operation.get("request", {})
        body_xml = request_spec.get("body_xml", "")

        # Resolve placeholders in XML body
        if body_xml and params:
            escaped = {k: _xml_escape_param(v) for k, v in params.items()}
            resolved = self._resolve_template(body_xml, escaped)
            if isinstance(resolved, str):
                body_xml = resolved

        timeout_val = request_spec.get("timeout")
        timeout_override = float(timeout_val) if timeout_val else None

        headers_extra = {}
        soap_action = operation.get("soap_action")
        if soap_action:
            headers_extra["SOAPAction"] = soap_action

        return ExecutionRequest(
            method="POST",
            path="/vapix/services",
            raw_body=body_xml,
            content_type="application/xml",
            timeout_override=timeout_override,
        )

    def _build_multipart(
        self,
        operation: Dict[str, Any],
        endpoint: str,
        params: Dict[str, str],
    ) -> ExecutionRequest:
        """Build a multipart/form-data request (firmware upgrade, ACAP upload)."""
        request_spec = operation.get("request", {})
        body_template = request_spec.get("body", {})

        form_data: Dict[str, str] = {}
        file_path = None

        for key, value in body_template.items():
            if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
                # Placeholder like "{firmware_file}" — resolve from params
                placeholder = value[1:-1]
                resolved = params.get(placeholder) or params.get("firmware_file") or params.get("file")
                if resolved:
                    file_path = resolved
            elif isinstance(value, dict):
                # Nested dict (e.g., the JSON envelope) — serialize + merge user params
                merged = dict(value)
                extra_params = {
                    k: v for k, v in params.items()
                    if k not in ("firmware_file", "file")
                }
                if extra_params:
                    merged["params"] = extra_params
                form_data[key] = json_module.dumps(merged)
            else:
                form_data[key] = str(value)

        timeout_val = request_spec.get("timeout")
        timeout_override = float(timeout_val) if timeout_val else None

        return ExecutionRequest(
            method="POST",
            path=endpoint,
            content_type="multipart/form-data",
            form_data=form_data if form_data else None,
            file_path=file_path,
            timeout_override=timeout_override,
        )

    @staticmethod
    def _content_type_extension(content_type: str) -> str:
        """Map a content type to a file extension for binary responses."""
        mapping = {
            "application/x-tar": ".tar",
            "application/gzip": ".tar.gz",
            "application/zip": ".zip",
            "application/octet-stream": ".bin",
            "image/jpeg": ".jpg",
            "image/png": ".png",
        }
        return mapping.get(content_type, ".bin")

    @staticmethod
    def _strip_ns(tag: str) -> str:
        """Strip XML namespace URI from a tag name."""
        if tag.startswith("{"):
            return tag.split("}", 1)[1]
        return tag

    @classmethod
    def _xml_to_dict(cls, element: ElementTree.Element) -> Any:
        """Convert an ElementTree element to a dict recursively.

        Conventions:
          - Attributes are prefixed with ``@``
          - Text content stored under ``#text``
          - Repeated child tags become lists
          - Leaf text elements become plain strings
          - Namespace URIs are stripped from tags and attributes
        """
        tag = cls._strip_ns(element.tag)
        result: Dict[str, Any] = {}

        # Attributes
        for attr_name, attr_val in element.attrib.items():
            result[f"@{cls._strip_ns(attr_name)}"] = attr_val

        # Children
        children: Dict[str, List[Any]] = {}
        for child in element:
            child_tag = cls._strip_ns(child.tag)
            child_val = cls._xml_to_dict(child)
            # Unwrap single-key dicts where key matches the tag
            if isinstance(child_val, dict) and list(child_val.keys()) == [child_tag]:
                child_val = child_val[child_tag]
            children.setdefault(child_tag, []).append(child_val)

        for child_tag, vals in children.items():
            result[child_tag] = vals if len(vals) > 1 else vals[0]

        # Text content
        text = (element.text or "").strip()
        if text:
            if result:
                result["#text"] = text
            else:
                # Leaf element with only text — return plain string
                return {tag: text}

        if not result and not text:
            return {tag: None}

        return {tag: result}

    def _parse_response(
        self,
        operation: Dict[str, Any],
        response: httpx.Response,
        op_id: str,
        device_id: str,
        elapsed: float,
    ) -> StepResult:
        """Parse an HTTP response according to the operation spec."""
        resp_spec = operation.get("response", {})
        fmt = resp_spec.get("format", "text")
        warnings = []

        # Check for service impact
        if operation.get("service_impact"):
            warnings.append(operation["service_impact"])

        # For binary format, avoid decoding response body as text
        if fmt == "binary" and response.status_code < 400:
            return self._parse_binary_response(
                resp_spec, response, op_id, device_id, elapsed, warnings
            )

        body = response.text

        if response.status_code == 401:
            return StepResult(
                operation_id=op_id,
                device_id=device_id,
                success=False,
                status_code=401,
                response_body=body,
                error="Authentication failed (401). Check credentials.",
                duration_ms=elapsed,
            )

        if response.status_code >= 400:
            return StepResult(
                operation_id=op_id,
                device_id=device_id,
                success=False,
                status_code=response.status_code,
                response_body=body,
                error=f"HTTP {response.status_code}: {body[:500]}",
                duration_ms=elapsed,
            )

        # Format-specific parsing
        parsed_data = None
        success = True
        error = None

        if fmt == "json":
            try:
                json_data = response.json()
                # Check for JSON-RPC errors
                if "error" in json_data:
                    err = json_data["error"]
                    success = False
                    error = f"{err.get('code', '')}: {err.get('message', str(err))}"
                else:
                    # Extract data at the specified path
                    data_path = resp_spec.get("data_path", "data")
                    parsed_data = json_data
                    for key in data_path.split("."):
                        if isinstance(parsed_data, dict):
                            parsed_data = parsed_data.get(key, parsed_data)
            except Exception as e:
                success = False
                error = f"Failed to parse JSON response: {e}"
        elif fmt == "xml":
            try:
                root = ElementTree.fromstring(body)
                parsed_data = self._xml_to_dict(root)
                # Unwrap single root element for convenience
                if isinstance(parsed_data, dict) and len(parsed_data) == 1:
                    parsed_data = next(iter(parsed_data.values()))
            except ElementTree.ParseError as e:
                logger.warning("XML parse failed for %s: %s", op_id, e)
                parsed_data = body.strip()
                warnings.append(f"XML parse failed, returning raw text: {e}")
        else:
            # Text format — check success/error patterns
            success_pattern = resp_spec.get("success")
            error_prefix = resp_spec.get("error_prefix")

            if error_prefix and body.strip().startswith(error_prefix):
                success = False
                error = body.strip()
            elif success_pattern and not body.strip().startswith(success_pattern):
                # If there's a success pattern and body doesn't match,
                # it might still be OK (some CGIs return data directly)
                parsed_data = body.strip()
            else:
                parsed_data = body.strip()

        return StepResult(
            operation_id=op_id,
            device_id=device_id,
            success=success,
            status_code=response.status_code,
            response_body=body,
            parsed_data=parsed_data,
            error=error,
            warnings=warnings,
            duration_ms=elapsed,
        )

    def _parse_binary_response(
        self,
        resp_spec: Dict[str, Any],
        response: httpx.Response,
        op_id: str,
        device_id: str,
        elapsed: float,
        warnings: List[str],
    ) -> StepResult:
        """Handle binary response format — save to temp file, return path."""
        import tempfile

        content_type = resp_spec.get(
            "content_type", "application/octet-stream"
        )
        suffix = self._content_type_extension(content_type)
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=suffix, prefix=f"{op_id}_"
        ) as f:
            f.write(response.content)
            file_path = f.name

        size = len(response.content)
        return StepResult(
            operation_id=op_id,
            device_id=device_id,
            success=True,
            status_code=response.status_code,
            response_body=f"<binary {size} bytes saved to {file_path}>",
            parsed_data={"file_path": file_path, "size_bytes": size},
            warnings=warnings,
            duration_ms=elapsed,
        )
