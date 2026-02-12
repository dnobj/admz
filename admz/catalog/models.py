"""
Data models for the operations catalog.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CgiMetadata:
    """Metadata for a CGI endpoint (_cgi.yaml)."""

    endpoint: str
    generation: str  # "legacy-cgi" | "json-rpc" | "config-rest"
    auth: str  # "digest" | "basic" | "none"
    min_firmware: Optional[str] = None
    api_id: Optional[str] = None
    description: str = ""


@dataclass
class ParameterInfo:
    """A single parameter within a parameter group."""

    name: str
    type: str  # "enum" | "integer" | "boolean" | "string"
    description: str = ""
    valid_values: Optional[List[str]] = None
    valid_values_from: Optional[str] = None
    example_values: Optional[List[str]] = None
    range: Optional[List[int]] = None
    default: Optional[Any] = None
    auth_level: str = "admin"


@dataclass
class ParameterGroup:
    """A param.cgi parameter group (e.g., root.Image)."""

    group: str
    cgi: str
    read_action: str = "list"
    write_action: str = "update"
    description: str = ""
    channel_indexed: bool = False
    channel_key: Optional[str] = None
    parameters: Dict[str, ParameterInfo] = field(default_factory=dict)
    service_impact: Optional[str] = None


@dataclass
class RollbackSpec:
    """How to undo an operation."""

    strategy: str  # "revert-params" | "delete" | "none"
    description: str = ""
    read_action: Optional[str] = None
    operation_id: Optional[str] = None
    params: Optional[Dict[str, str]] = None


@dataclass
class Operation:
    """A single catalog operation."""

    id: str
    cgi: str
    method: str  # "GET" | "POST" | "PUT" | "DELETE"
    risk_level: str  # "read-only" | "normal" | "service-affecting" | "dangerous"
    request: Dict[str, Any] = field(default_factory=dict)
    response: Dict[str, Any] = field(default_factory=dict)
    rollback: Optional[RollbackSpec] = None
    requires: Dict[str, Any] = field(default_factory=dict)
    min_api_version: Optional[str] = None
    danger_description: Optional[str] = None
    service_impact: Optional[str] = None

    # Populated by loader from _cgi.yaml
    endpoint: Optional[str] = None
    generation: Optional[str] = None
    auth: Optional[str] = None


@dataclass
class ResolverResult:
    """Result of a catalog query — filtered docs for the LLM."""

    operations: List[Dict[str, Any]]
    parameter_groups: List[Dict[str, Any]]
    device: Dict[str, Any]
    risk_summary: Dict[str, int]
    notes: List[str] = field(default_factory=list)
