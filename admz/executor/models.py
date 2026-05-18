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
