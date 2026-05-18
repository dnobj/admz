"""
On-demand credential probing for Axis devices.

Tests authentication against a device using no-auth, legacy defaults,
and/or user-supplied credentials.  This is separate from discovery —
discovery only *observes* (headers, open ports), while the probe
actively *tries* credentials.

The probe also detects the device's authentication method by parsing
the ``WWW-Authenticate`` header on 401 responses.  This is stored in
``ProbeResult.auth_method`` and should be persisted in the device
profile so the executor can use the correct auth handler.

Usage::

    from admz.discovery.credential_probe import probe_credentials

    result = await probe_credentials("192.168.1.100")
    print(result.status, result.auth_method, result.detail)
"""

import enum
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from admz.ssl_config import verify_ssl_default

logger = logging.getLogger(__name__)

# Built-in legacy Axis default credentials.
LEGACY_DEFAULTS: List[Tuple[str, str]] = [("root", "pass")]

# Max user-supplied credential pairs (no-auth + legacy are additional).
MAX_USER_CREDENTIALS = 5


class ProbeStatus(enum.Enum):
    """Outcome of a credential probe."""

    FACTORY_DEFAULT = "factory_default"
    AUTHENTICATED = "authenticated"
    AUTH_FAILED = "auth_failed"
    UNREACHABLE = "unreachable"


@dataclass
class ProbeResult:
    """Result of probing a single host."""

    status: ProbeStatus
    host: str
    username: Optional[str] = None
    password: Optional[str] = None
    device_info: Optional[Dict] = field(default_factory=dict)
    detail: str = ""
    auth_method: Optional[str] = None  # "none", "digest", "basic"
    auth: Optional[Dict[str, str]] = None  # {"http": "digest", "https": "basic", "scheme": "http"}

    def to_dict(self, include_credentials: bool = False) -> Dict:
        """Serialize the result.

        By default credentials are omitted to preserve the ADMZ
        principle of keeping secrets out of the LLM context.
        """
        d: Dict = {
            "status": self.status.value,
            "host": self.host,
            "detail": self.detail,
        }
        if self.auth_method:
            d["auth_method"] = self.auth_method
        if self.auth:
            d["auth"] = self.auth
        if self.device_info:
            d["device_info"] = self.device_info
        if include_credentials and self.username is not None:
            d["username"] = self.username
            d["password"] = self.password
        return d


def _parse_device_info(body: str) -> Dict:
    """Parse VAPIX basicdeviceinfo response (JSON or key=value)."""
    try:
        data = json.loads(body)
        props = data.get("data", {}).get("properties", data)
    except (json.JSONDecodeError, AttributeError):
        props = {}
        for line in body.splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                props[k.strip()] = v.strip()

    return {
        "model": props.get("ProdNbr") or props.get("model"),
        "serial_number": props.get("SerialNumber") or props.get("serialnumber"),
        "firmware_version": props.get("Version") or props.get("firmware"),
        "friendly_name": props.get("ProdFullName"),
    }


def _parse_www_authenticate(headers) -> str:
    """Parse WWW-Authenticate header to determine auth method.

    Returns ``"basic"`` or ``"digest"`` (default).
    """
    www_auth = headers.get("www-authenticate", "")
    if www_auth.lower().startswith("basic"):
        return "basic"
    return "digest"


async def _detect_auth_schemes(host: str, timeout: float = 5.0) -> Dict[str, str]:
    """Probe HTTP and HTTPS to detect per-protocol auth methods.

    Sends unauthenticated requests to trigger 401 responses, then
    parses ``WWW-Authenticate`` headers to determine the auth method
    for each protocol.  Also determines the preferred scheme based
    on which protocols are reachable.

    Returns a dict like::

        {"http": "digest", "https": "basic", "scheme": "http"}
    """
    import httpx as _httpx

    result: Dict[str, str] = {}
    reachable: List[str] = []

    for scheme in ("http", "https"):
        url = f"{scheme}://{host}/axis-cgi/basicdeviceinfo.cgi"
        try:
            async with _httpx.AsyncClient(
                verify=verify_ssl_default(), timeout=timeout
            ) as client:
                resp = await client.post(
                    url,
                    content=json.dumps(
                        {"apiVersion": "1.0", "method": "getAllProperties"}
                    ),
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 401:
                    result[scheme] = _parse_www_authenticate(resp.headers)
                    reachable.append(scheme)
                elif resp.status_code == 200:
                    # No auth required on this scheme
                    result[scheme] = "none"
                    reachable.append(scheme)
                else:
                    # Reachable but unexpected status
                    result[scheme] = "digest"  # safe default
                    reachable.append(scheme)
        except Exception:
            # Scheme not reachable — skip it
            logger.debug("%s not reachable on %s", scheme.upper(), host)

    # Prefer HTTP (digest is more universally supported than basic)
    if "http" in reachable:
        result["scheme"] = "http"
    elif "https" in reachable:
        result["scheme"] = "https"
    else:
        result["scheme"] = "http"  # fallback

    return result


async def probe_credentials(
    host: str,
    *,
    credentials_list: Optional[List[Tuple[str, str]]] = None,
    try_no_auth: bool = True,
    try_legacy_defaults: bool = True,
    timeout: float = 10.0,
) -> ProbeResult:
    """
    Test credentials against a device's basicdeviceinfo endpoint.

    Progression (stops on first success):
      1. No auth       -> if 200, device is FACTORY_DEFAULT
      2. root/pass     -> if 200, AUTHENTICATED (legacy default)
      3. User-supplied -> if 200, AUTHENTICATED
      4. All 401s      -> AUTH_FAILED
      5. Connection error -> UNREACHABLE

    The device's authentication method is detected from the
    ``WWW-Authenticate`` header on the first 401 response and used
    for all subsequent credential attempts.  After a successful probe,
    both HTTP and HTTPS are tested to build a per-protocol auth map.

    Args:
        host: IP address or hostname to probe.
        credentials_list: Optional list of (username, password) tuples (max 5).
        try_no_auth: Whether to attempt unauthenticated access first.
        try_legacy_defaults: Whether to try built-in legacy defaults.
        timeout: HTTP request timeout in seconds.

    Returns:
        ProbeResult with status, auth_method, auth dict, and optional device info.
    """
    result = await _probe_credentials_core(
        host,
        credentials_list=credentials_list,
        try_no_auth=try_no_auth,
        try_legacy_defaults=try_legacy_defaults,
        timeout=timeout,
    )

    # Enrich successful results with per-protocol auth detection
    if result.status in (ProbeStatus.FACTORY_DEFAULT, ProbeStatus.AUTHENTICATED):
        try:
            auth_schemes = await _detect_auth_schemes(host, timeout=timeout)
            if auth_schemes:
                result.auth = auth_schemes
        except Exception:
            logger.debug("Auth scheme detection failed for %s", host)

    return result


async def _probe_credentials_core(
    host: str,
    *,
    credentials_list: Optional[List[Tuple[str, str]]] = None,
    try_no_auth: bool = True,
    try_legacy_defaults: bool = True,
    timeout: float = 10.0,
) -> ProbeResult:
    """Core probe logic — tests credentials without auth scheme detection."""
    try:
        import httpx
    except ImportError:
        return ProbeResult(
            status=ProbeStatus.UNREACHABLE,
            host=host,
            detail="httpx library not installed",
        )

    # Enforce max user credentials
    user_creds = list(credentials_list or [])[:MAX_USER_CREDENTIALS]

    url = f"http://{host}/axis-cgi/basicdeviceinfo.cgi"
    # param.cgi always requires auth on configured devices, so we use
    # it as a second check to distinguish "truly factory default" from
    # "configured but basicdeviceinfo is publicly accessible".
    param_url = f"http://{host}/axis-cgi/param.cgi?action=list&group=root.Brand"

    # Mutable context shared across attempts.  _try_request populates
    # "auth_method" from the first 401's WWW-Authenticate header.
    ctx: Dict = {}

    async with httpx.AsyncClient(
        timeout=timeout, verify=verify_ssl_default(), follow_redirects=True
    ) as client:
        # Step 1: No auth
        if try_no_auth:
            result = await _try_request(client, url, host, auth=None, ctx=ctx)
            if result is not None:
                if result.status == ProbeStatus.UNREACHABLE:
                    return result
                if result.status == ProbeStatus.FACTORY_DEFAULT:
                    # basicdeviceinfo returned 200 without auth, but
                    # newer firmware exposes this endpoint publicly even
                    # on configured devices.  Confirm by checking param.cgi
                    # which always requires auth when a password is set.
                    try:
                        param_resp = await client.get(param_url)
                        if param_resp.status_code == 200:
                            return result  # truly factory default
                        # On AXIS OS 12+, factory-default devices return
                        # 401 with Axis-Setup: vapix on ALL endpoints.
                        if param_resp.status_code == 401:
                            axis_setup = param_resp.headers.get("axis-setup", "")
                            if axis_setup.lower() == "vapix":
                                return result  # confirmed factory default
                        # param.cgi returned 401 without Axis-Setup —
                        # device is configured, continue trying credentials
                    except Exception:
                        return result  # can't reach param.cgi, trust the first result

        # Step 2: Legacy defaults
        if try_legacy_defaults:
            for username, password in LEGACY_DEFAULTS:
                result = await _try_request(
                    client, url, host, auth=(username, password), ctx=ctx,
                )
                if result is not None:
                    if result.status in (
                        ProbeStatus.AUTHENTICATED,
                        ProbeStatus.UNREACHABLE,
                    ):
                        return result

        # Step 3: User-supplied credentials
        for username, password in user_creds:
            result = await _try_request(
                client, url, host, auth=(username, password), ctx=ctx,
            )
            if result is not None:
                if result.status in (
                    ProbeStatus.AUTHENTICATED,
                    ProbeStatus.UNREACHABLE,
                ):
                    return result

    # All attempts returned 401
    return ProbeResult(
        status=ProbeStatus.AUTH_FAILED,
        host=host,
        detail="All credential attempts returned 401 Unauthorized",
        auth_method=ctx.get("auth_method", "digest"),
    )


def _is_valid_device_info(body: str) -> bool:
    """Check that a 200 response actually contains device info, not an API error.

    AXIS OS 12+ returns HTTP 200 with a JSON error body for unsupported
    methods (e.g. GET on a POST-only endpoint).  We must not treat that
    as a successful probe.
    """
    try:
        data = json.loads(body)
        if "error" in data and "data" not in data:
            return False  # API error response
        return True
    except (json.JSONDecodeError, TypeError):
        # key=value format or non-JSON — these are always real responses
        return bool(body.strip())


def _build_auth(auth_method: str, username: str, password: str):
    """Build the correct httpx auth handler for the detected method."""
    from httpx import BasicAuth, DigestAuth

    if auth_method == "basic":
        return BasicAuth(username, password)
    return DigestAuth(username, password)


async def _try_request(
    client, url: str, host: str, *, auth, ctx: Dict,
) -> Optional[ProbeResult]:
    """
    Try to authenticate against basicdeviceinfo.cgi.

    Uses POST first (AXIS OS 12+), falls back to GET (older firmware).
    Validates the response body to avoid false positives from API error
    responses that return HTTP 200.

    The ``ctx`` dict is used to share state between attempts:
    - ``ctx["auth_method"]`` is set from the first 401's WWW-Authenticate
      header and reused for subsequent credential attempts.

    Returns:
        ProbeResult on successful auth or connection error, None on 401.
    """
    try:
        # Build auth handler
        kwargs = {}
        if auth is not None:
            # Use previously detected auth method, default to digest
            method = ctx.get("auth_method", "digest")
            kwargs["auth"] = _build_auth(method, auth[0], auth[1])

        # Try POST first (required by AXIS OS 12+)
        post_body = json.dumps({"apiVersion": "1.0", "method": "getAllProperties"})
        resp = await client.post(
            url, content=post_body,
            headers={"Content-Type": "application/json"},
            **kwargs,
        )

        # If POST returns 405 or other method error, fall back to GET
        if resp.status_code in (405, 404):
            resp = await client.get(url, **kwargs)

        if resp.status_code == 200:
            if not _is_valid_device_info(resp.text):
                # 200 but body is an API error (e.g. wrong HTTP method)
                # — treat as if endpoint is unreachable for this method
                return None

            device_info = _parse_device_info(resp.text)
            if auth is None:
                return ProbeResult(
                    status=ProbeStatus.FACTORY_DEFAULT,
                    host=host,
                    device_info=device_info,
                    detail="Device responded without authentication (factory default)",
                    auth_method="none",
                )
            else:
                return ProbeResult(
                    status=ProbeStatus.AUTHENTICATED,
                    host=host,
                    username=auth[0],
                    password=auth[1],
                    device_info=device_info,
                    detail=f"Authenticated as '{auth[0]}'",
                    auth_method=ctx.get("auth_method", "digest"),
                )

        if resp.status_code == 401:
            # Detect auth method from WWW-Authenticate header (first time only)
            if "auth_method" not in ctx:
                ctx["auth_method"] = _parse_www_authenticate(resp.headers)

            # Factory-default devices on AXIS OS 12+ return 401 for POST
            # even without a password set, but include Axis-Setup: vapix.
            # GET basicdeviceinfo still works without auth.
            if auth is None:
                axis_setup = resp.headers.get("axis-setup", "")
                if axis_setup.lower() == "vapix":
                    try:
                        get_resp = await client.get(url)
                        if get_resp.status_code == 200 and _is_valid_device_info(
                            get_resp.text
                        ):
                            return ProbeResult(
                                status=ProbeStatus.FACTORY_DEFAULT,
                                host=host,
                                device_info=_parse_device_info(get_resp.text),
                                detail="Device is factory default (Axis-Setup header)",
                                auth_method="none",
                            )
                    except Exception:
                        pass
                    # Header present but GET failed — still factory default
                    return ProbeResult(
                        status=ProbeStatus.FACTORY_DEFAULT,
                        host=host,
                        detail="Device is factory default (Axis-Setup header)",
                        auth_method="none",
                    )
            return None  # Signal to try next credentials

        # Unexpected status code — treat as auth failure for this attempt
        logger.debug("Unexpected status %d from %s", resp.status_code, host)
        return None

    except Exception as e:
        logger.debug("Connection error probing %s: %s", host, e)
        return ProbeResult(
            status=ProbeStatus.UNREACHABLE,
            host=host,
            detail=f"Connection error: {e}",
        )
