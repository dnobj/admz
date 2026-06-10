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
from xml.etree import ElementTree

import httpx

from admz.executor.base import BaseExecutor
from admz.executor.models import ExecutionRequest, StepResult
from admz.ssl_config import verify_ssl_default

logger = logging.getLogger(__name__)

# H-3 (review 2026-06-10): file uploads may only read from the firmware
# cache. The upload path reaches the executor via caller-supplied operation
# params (e.g. a chatbot tool call), so an unconstrained path would let a
# caller read ANY host file (~/.admz/admz.key, the SQLite DB, ...) and
# exfiltrate it to a device it controls. Mirrors
# admz.firmware.downloader._DEFAULT_FIRMWARE_DIR (not imported — the
# executor stays a leaf module).
_UPLOAD_ROOT = Path.home() / ".admz" / "firmware"


def _upload_path_allowed(file_path: str) -> bool:
    """True if ``file_path`` resolves to inside the firmware cache.

    Resolves symlinks and ``..`` segments before comparing, so neither
    traversal nor a symlink planted in the cache can escape the root.
    """
    try:
        resolved = Path(file_path).resolve()
        root = _UPLOAD_ROOT.resolve()
    except (OSError, ValueError):
        return False
    return resolved == root or root in resolved.parents


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
    ):
        self._timeout = timeout
        # If caller didn't pin a value, honor ADMZ_VERIFY_SSL (default False).
        self._verify_ssl = (
            verify_ssl_default() if verify_ssl is None else bool(verify_ssl)
        )
        self._retries = retries

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

            # Determine scheme from device auth profile
            auth_info = device.get("auth")
            if auth_info and isinstance(auth_info, dict):
                scheme = auth_info.get("scheme", "http")
            else:
                scheme = "http"
            port = device.get("port", 443 if scheme == "https" else 80)
            url = f"{scheme}://{host}:{port}{request.path}"

            # Resolve auth from device profile (protocol-aware)
            auth = self._resolve_auth(device, credentials, scheme)

            # Per-operation timeout override (e.g., firmware upload)
            effective_timeout = request.timeout_override or self._timeout

            transport = httpx.AsyncHTTPTransport(
                retries=self._retries, verify=self._verify_ssl
            )
            async with httpx.AsyncClient(
                transport=transport, timeout=effective_timeout
            ) as client:
                if request.file_path:
                    # H-3: refuse uploads from outside the firmware cache.
                    if not _upload_path_allowed(request.file_path):
                        return StepResult(
                            operation_id=op_id,
                            device_id=device_id,
                            success=False,
                            error=(
                                "Upload file_path must be inside the firmware "
                                f"cache ({_UPLOAD_ROOT}); got: {request.file_path}. "
                                "Use download_firmware or import_firmware to "
                                "stage the file first."
                            ),
                        )
                    # Multipart/form-data with file upload
                    with open(request.file_path, "rb") as f:
                        files = {
                            request.file_field_name: (
                                os.path.basename(request.file_path),
                                f,
                                "application/octet-stream",
                            )
                        }
                        response = await client.request(
                            method=request.method,
                            url=url,
                            data=request.form_data or {},
                            files=files,
                            auth=auth,
                        )
                elif request.raw_body is not None:
                    # SOAP XML or other pre-built body
                    response = await client.request(
                        method=request.method,
                        url=url,
                        content=request.raw_body,
                        auth=auth,
                        headers={"Content-Type": request.content_type}
                        if request.content_type
                        else None,
                    )
                else:
                    response = await client.request(
                        method=request.method,
                        url=url,
                        params=request.query_params,
                        json=request.json_body,
                        auth=auth,
                        headers={"Content-Type": request.content_type}
                        if request.content_type
                        and request.content_type != "multipart/form-data"
                        else None,
                    )

            elapsed = (time.monotonic() - start) * 1000

            # Parse response
            return self._parse_response(
                operation, response, op_id, device_id, elapsed
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

    @staticmethod
    def _resolve_auth(
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
        auth_info = device.get("auth")
        if auth_info and isinstance(auth_info, dict):
            method = auth_info.get(scheme, "digest")
        else:
            # Legacy fallback
            method = device.get("auth_method", "digest")

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

        # Backward compat: if template resolution didn't produce a "params"
        # key but user provided params, put them there (e.g., operations
        # with no typed placeholders yet)
        if "params" not in body and params:
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

        # Substitute path parameters
        for k, v in params.items():
            placeholder = "{" + k + "}"
            if placeholder in full_path:
                full_path = full_path.replace(placeholder, v)

        request_spec = operation.get("request", {})
        timeout_val = request_spec.get("timeout")
        timeout_override = float(timeout_val) if timeout_val else None

        return ExecutionRequest(
            method=operation.get("method", "GET"),
            path=full_path,
            json_body=params if params else None,
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
        the same _resolve_template logic as other generations.
        """
        request_spec = operation.get("request", {})
        body_xml = request_spec.get("body_xml", "")

        # Resolve placeholders in XML body
        if body_xml and params:
            resolved = self._resolve_template(body_xml, params)
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
