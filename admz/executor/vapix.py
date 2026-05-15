"""
VAPIX executor — builds and sends HTTP requests for VAPIX operations.

Handles all three VAPIX generations:
  - legacy-cgi: GET with query parameters
  - json-rpc: POST with JSON body
  - config-rest: REST methods with JSON body
"""

import logging
import time
from typing import Any, Dict, Optional

import httpx

from admz.executor.base import BaseExecutor
from admz.executor.models import ExecutionRequest, StepResult

logger = logging.getLogger(__name__)


class VapixExecutor(BaseExecutor):
    """Executor for VAPIX operations on Axis cameras/devices."""

    def __init__(self, timeout: float = 15.0, verify_ssl: bool = False):
        self._timeout = timeout
        self._verify_ssl = verify_ssl

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

            # Determine scheme
            scheme = "https" if device.get("https", True) else "http"
            port = device.get("port", 443 if scheme == "https" else 80)
            url = f"{scheme}://{host}:{port}{request.path}"

            # Build httpx auth
            auth = httpx.DigestAuth(
                credentials.get("username", ""),
                credentials.get("password", ""),
            )

            async with httpx.AsyncClient(
                verify=self._verify_ssl, timeout=self._timeout
            ) as client:
                response = await client.request(
                    method=request.method,
                    url=url,
                    params=request.query_params,
                    json=request.json_body,
                    auth=auth,
                    headers={"Content-Type": request.content_type}
                    if request.content_type
                    else None,
                )

            elapsed = (time.monotonic() - start) * 1000

            # Parse response
            return self._parse_response(
                operation, response, op_id, device_id, elapsed
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
            return StepResult(
                operation_id=op_id,
                device_id=device_id,
                success=False,
                error=f"Request timed out after {self._timeout}s",
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

    def build_request(
        self, operation: Dict[str, Any], params: Dict[str, str]
    ) -> ExecutionRequest:
        """
        Build an HTTP request from an operation spec and user params.

        Routes to the correct builder based on the operation's generation.
        """
        # Generation comes from _cgi.yaml, enriched by loader/resolver
        generation = (
            operation.get("_generation")
            or operation.get("generation")
            or "legacy-cgi"
        )
        endpoint = (
            operation.get("_endpoint")
            or operation.get("endpoint", "")
        )

        if generation == "legacy-cgi":
            return self._build_legacy_cgi(operation, endpoint, params)
        elif generation == "json-rpc":
            return self._build_json_rpc(operation, endpoint, params)
        elif generation == "config-rest":
            return self._build_config_rest(operation, params)
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

        # Start with template params (like action=update)
        query: Dict[str, str] = {}
        for k, v in query_template.items():
            # Skip template placeholders that aren't filled
            if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
                placeholder = v[1:-1]
                if placeholder in params:
                    query[k] = params[placeholder]
            else:
                query[k] = str(v)

        # Add user params (for param.cgi, these are the key=value pairs)
        for k, v in params.items():
            if k not in query:
                query[k] = str(v)

        return ExecutionRequest(
            method=operation.get("method", "GET"),
            path=endpoint,
            query_params=query if query else None,
        )

    def _build_json_rpc(
        self,
        operation: Dict[str, Any],
        endpoint: str,
        params: Dict[str, str],
    ) -> ExecutionRequest:
        """Build a JSON-RPC request (POST with JSON body)."""
        request_spec = operation.get("request", {})
        body_template = request_spec.get("body", {})

        body: Dict[str, Any] = {}
        for k, v in body_template.items():
            body[k] = v

        # Add user params to the body
        if params:
            body["params"] = params

        return ExecutionRequest(
            method="POST",
            path=endpoint,
            json_body=body,
            content_type="application/json",
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

        return ExecutionRequest(
            method=operation.get("method", "GET"),
            path=full_path,
            json_body=params if params else None,
            content_type="application/json"
            if operation.get("method", "GET") != "GET"
            else None,
        )

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
        body = response.text
        warnings = []

        # Check for service impact
        if operation.get("service_impact"):
            warnings.append(operation["service_impact"])

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
