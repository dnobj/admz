"""
Redaction -- the trust boundary between a surveyed device and a submitted bundle.

Everything that leaves the site passes through here. The rule is **allow-list,
not deny-list**: we copy only known-safe identity/API fields and drop everything
else, so a future firmware that adds a new (possibly sensitive) field defaults to
*not* being shipped.

What's safe to ship:
  - product identity (model, firmware, SoC, hardware id, part number, prod type);
  - the API surface (api ids, versions, state, REST paths, OpenAPI **schemas**);
  - capability snapshot structure (which api at which version).

What is dropped or transformed:
  - serial / MAC -> HMAC under the ``hash-serial`` profile (kept only on opt-in);
  - everything network/site (hostname, IP, DNS, NTP, gateway, VLAN);
  - geolocation, privacy-mask coordinates, overlay text, user/account names;
  - any live response body (we keep schemas, never values) -- e.g. param model.json
    or a GET response is never shipped, only its shape if part of validation.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any, Dict, List, Optional

# basicdeviceinfo property names that are safe to ship verbatim.
IDENTITY_WHITELIST = {
    "Architecture", "ProdNbr", "ProdFullName", "ProdShortName", "ProdType",
    "ProdVariant", "Soc", "Brand", "Version", "HardwareID", "BuildDate",
}

# Identity properties that are serial-like and must be hashed/dropped.
_SERIAL_FIELDS = {"SerialNumber", "SocSerialNumber"}


def hash_serial(serial: str, key: bytes) -> str:
    """Stable, non-reversible device id (HMAC-SHA256, truncated)."""
    if not serial:
        return ""
    digest = hmac.new(key, serial.encode(), hashlib.sha256).hexdigest()
    return "h:" + digest[:16]


def redact_identity(identity: Dict[str, Any], *, profile: str, key: bytes) -> Dict[str, Any]:
    """Whitelist identity fields; hash/drop serials per profile."""
    out: Dict[str, Any] = {k: v for k, v in identity.items() if k in IDENTITY_WHITELIST}
    raw_serial = identity.get("SerialNumber") or identity.get("serial") or ""
    if profile == "keep-serial":
        if raw_serial:
            out["SerialNumber"] = raw_serial
    else:  # hash-serial (default)
        if raw_serial:
            out["device_hash"] = hash_serial(raw_serial, key)
    return out


def redact_snapshot(snapshot: Dict[str, Any], *, profile: str, key: bytes) -> Dict[str, Any]:
    """Redact a capability snapshot produced by the atlas refresh tool.

    The snapshot already contains only API-shape data (firmware, api_count,
    apis, apis_detail) plus a ``device_id`` (the raw serial). We replace the
    serial per profile and pass the API structure through untouched.
    """
    out: Dict[str, Any] = {
        "firmware": snapshot.get("firmware"),
        "discovered": snapshot.get("discovered"),
        "api_count": snapshot.get("api_count"),
        "apis": dict(snapshot.get("apis", {})),
        "apis_detail": _strip_specs(snapshot.get("apis_detail", {})),
    }
    raw_serial = str(snapshot.get("device_id") or "")
    if profile == "keep-serial":
        out["device_id"] = raw_serial
    else:
        out["device_id"] = hash_serial(raw_serial, key)
    return out


def _strip_specs(apis_detail: Dict[str, Any]) -> Dict[str, Any]:
    """apis_detail holds versions + spec *links* (paths), not bodies -> safe.

    We keep it as-is; OpenAPI spec *bodies* are handled separately (only the
    schema-bearing openapi.json is shipped, never model.json / live values).
    """
    return apis_detail


def is_safe_openapi(api_id: str, spec_path: str) -> bool:
    """OpenAPI schema docs are safe; param ``model.json`` mirrors live values."""
    p = (spec_path or "").lower()
    if p.endswith("model.json"):
        return False
    if api_id == "param":
        return False
    return p.endswith("openapi.json") or "openapi" in p


def redact_validation_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Keep op id, status, latency, error code, response *shape* -- never values."""
    return {
        "op_id": result.get("op_id"),
        "method": result.get("method"),
        "path": result.get("path"),
        "http_status": result.get("http_status"),
        "ok": result.get("ok"),
        "latency_ms": result.get("latency_ms"),
        "error_code": result.get("error_code"),
        "response_shape": result.get("response_shape"),  # keys/types only, no values
    }


def build_preview(redacted_snapshots: List[Dict[str, Any]],
                  *, profile: str, included_specs: List[str],
                  validation: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """The exact "what will be sent" object the UI renders before submission."""
    return {
        "redaction_profile": profile,
        "snapshots": redacted_snapshots,
        "openapi_specs_included": sorted(included_specs),
        "validation_results": validation or [],
        "note": (
            "This is the complete payload that would be submitted. It contains no "
            "credentials, network/site config, geolocation, overlay text, or user "
            "names. Serials are "
            + ("included (keep-serial profile)." if profile == "keep-serial"
               else "hashed (hash-serial profile).")
        ),
    }
