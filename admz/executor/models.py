"""
Data models for operation execution.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionRequest:
    """An HTTP request built from an operation spec."""

    method: str
    path: str
    query_params: Optional[Dict[str, str]] = None
    json_body: Optional[Dict[str, Any]] = None
    content_type: Optional[str] = None
    # Multipart/form-data support (firmware upgrade, ACAP upload)
    form_data: Optional[Dict[str, str]] = None
    file_path: Optional[str] = None
    file_field_name: str = "file"
    # Pre-built body string (for SOAP XML)
    raw_body: Optional[str] = None
    # Per-operation timeout override (seconds)
    timeout_override: Optional[float] = None
    # Extra request headers from the operation spec (GH #245). SOAP's
    # ``SOAPAction`` is the only current user; ``Content-Type`` stays separate
    # because the send path already derives it per body kind.
    headers_extra: Optional[Dict[str, str]] = None


@dataclass
class StepResult:
    """Result of executing a single operation."""

    operation_id: str
    device_id: str
    success: bool
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    parsed_data: Optional[Any] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    duration_ms: Optional[float] = None
    # For rollback: values read before the write
    rollback_data: Optional[Dict[str, str]] = None
    # Connectivity self-healing: when the executor had to fall back to a
    # different scheme/auth method than the stored profile (because the
    # configured one connect-refused or used the wrong auth), it records the
    # corrected ``auth`` profile here. ``run_execution_tail`` persists it to
    # the registry so the next call uses the right values directly.
    learned_auth: Optional[Dict[str, str]] = None
