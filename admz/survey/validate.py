"""
Validation runner -- turn *cataloged-but-untested* ops into real evidence.

Survey installs can confirm that catalog ops actually work on real hardware. This
is risk-gated, matching the catalog's own ``risk_level``:

* **Tier 0 (read-only)** -- executes GET / json-rpc *query* ops only. Safe to run
  anywhere the operator opted in. Records: reachable, HTTP status, response
  *shape* (keys + types, never values), latency, error code. Fully implemented.

* **Tier 1 (service-affecting)** -- lab-designated devices only, per-op opt-in,
  read-modify-restore. Implemented as a **guarded skeleton**: a write is attempted
  only when (a) the device is tagged lab/test, (b) the tier is 1, and (c) an
  explicit safe test-value is supplied for that op. Otherwise the op is recorded
  ``skipped`` with a reason -- never an accidental write.

* **Tier 2 (dangerous)** -- never executed here. Hard-blocked.

The runner is synchronous (so it composes with the sync collector and runs fine
in a scheduler worker thread) and its HTTP layer is injectable for testing.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import yaml

logger = logging.getLogger(__name__)

TIER0_RISK = {"read-only"}
TIER1_RISK = {"service-affecting"}
NEVER_RISK = {"dangerous"}

LAB_TAGS = {"lab", "test", "lab/test"}


# ---------------------------------------------------------------------------
# op specs loaded from the installed atlas
# ---------------------------------------------------------------------------


@dataclass
class OpSpec:
    op_id: str
    method: str
    risk_level: str
    generation: str                       # config-rest | json-rpc | legacy-cgi | soap
    cgi: str = ""
    base_path: str = ""
    path: str = ""
    request: Dict[str, Any] = field(default_factory=dict)
    response: Dict[str, Any] = field(default_factory=dict)


def _atlas_root(data_path: Optional[str]) -> Path:
    if data_path is None:
        data_path = os.getenv("ADMZ_CATALOG_PATH")
    if data_path is None:
        import axis_api_atlas
        data_path = axis_api_atlas.default_data_path()
    return Path(data_path)


def _norm(s: str) -> str:
    return s.lower().replace(".cgi", "").replace("-", "")


def load_ops_for_apis(api_ids: Sequence[str], *, data_path: Optional[str] = None) -> List[OpSpec]:
    """Load every op spec whose API matches one of ``api_ids`` (device-reported)."""
    root = _atlas_root(data_path)
    wanted = {_norm(a) for a in api_ids}
    ops: List[OpSpec] = []
    for sub, generation_default in (("rest", "config-rest"), ("cgi", "json-rpc")):
        base = root / "vapix" / sub
        if not base.is_dir():
            continue
        for api_dir in base.iterdir():
            if not api_dir.is_dir() or _norm(api_dir.name) not in wanted:
                continue
            api_meta = _load_api_meta(api_dir)
            for op_file in api_dir.rglob("*.yaml"):
                if op_file.name == "_api.yaml":
                    continue
                try:
                    data = yaml.safe_load(op_file.read_text(encoding="utf-8")) or {}
                except Exception:  # noqa: BLE001
                    continue
                if not isinstance(data, dict) or "id" not in data:
                    continue
                ops.append(OpSpec(
                    op_id=data["id"],
                    method=str(data.get("method", "GET")).upper(),
                    risk_level=data.get("risk_level", "normal"),
                    generation=api_meta.get("generation", generation_default),
                    cgi=data.get("cgi", api_dir.name),
                    base_path=data.get("base_path", api_meta.get("endpoint", "")),
                    path=data.get("path", ""),
                    request=data.get("request", {}) or {},
                    response=data.get("response", {}) or {},
                ))
    return ops


def _load_api_meta(api_dir: Path) -> Dict[str, Any]:
    f = api_dir / "_api.yaml"
    if f.is_file():
        try:
            return yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            return {}
    return {}


# ---------------------------------------------------------------------------
# response shape (keys + types, never values)
# ---------------------------------------------------------------------------


def response_shape(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return "..."
    if isinstance(value, dict):
        return {k: response_shape(v, depth + 1) for k, v in list(value.items())[:50]}
    if isinstance(value, list):
        return [response_shape(value[0], depth + 1)] if value else []
    return type(value).__name__


# ---------------------------------------------------------------------------
# HTTP layer (injectable)
# ---------------------------------------------------------------------------

# http(method, url, json) -> (status_code:int|None, parsed_json:Any|None, latency_ms:float)
HttpFn = Callable[..., Any]


def _default_http(user: str, password: str, verify: bool) -> HttpFn:
    """HTTP closure that caches the working auth scheme to avoid auth storms.

    Axis devices throttle/lock out after many rapid failed auth attempts, so once
    a scheme (Basic vs Digest) succeeds we stick with it instead of re-trying both
    on every op.
    """
    import time

    import httpx

    state = {"scheme": None}  # "basic" | "digest" | None (unknown)

    def _auth(scheme):
        return httpx.BasicAuth(user, password) if scheme == "basic" \
            else httpx.DigestAuth(user, password)

    def call(method: str, url: str, json: Optional[Dict] = None):
        order = [state["scheme"]] if state["scheme"] else ["basic", "digest"]
        for scheme in order:
            start = time.monotonic()
            try:
                with httpx.Client(verify=verify, timeout=30, auth=_auth(scheme)) as c:
                    r = c.request(method, url, json=json)
                latency = (time.monotonic() - start) * 1000
                if r.status_code in (401, 403):
                    if state["scheme"] == scheme:
                        state["scheme"] = None   # cached scheme stopped working; relearn
                    continue
                state["scheme"] = scheme          # remember what worked
                try:
                    parsed = r.json()
                except Exception:  # noqa: BLE001
                    parsed = None
                return r.status_code, parsed, latency
            except Exception:  # noqa: BLE001
                continue
        return None, None, 0.0

    return call


# ---------------------------------------------------------------------------
# the runner
# ---------------------------------------------------------------------------


def _build_readonly_request(op: OpSpec, host: str):
    """Return (method, url, json_body) for a read-only op, or None if unsupported."""
    if op.generation == "config-rest":
        url = f"{host}{op.base_path}{op.path}"
        return "GET", url, None
    if op.generation == "json-rpc":
        body = (op.request or {}).get("body")
        cgi = op.cgi if op.cgi.endswith(".cgi") else f"{op.cgi}.cgi"
        url = f"{host}/axis-cgi/{cgi}"
        return "POST", url, body
    return None  # legacy-cgi / soap not auto-validated read-only here


@dataclass
class ValidationRunner:
    host: str
    user: str
    password: str
    verify: bool = False
    http: Optional[HttpFn] = None

    def __post_init__(self):
        if not self.host.startswith("http"):
            self.host = f"https://{self.host}"
        if self.http is None:
            self.http = _default_http(self.user, self.password, self.verify)

    def validate_write_back(self, op: OpSpec) -> Dict[str, Any]:
        """Tier-1 read-modify-restore via **idempotent write-back**.

        Reads the current value, writes the *same* value back, and confirms it
        took -- proving the write path works with zero net change. If the read-
        back differs (shouldn't, since we wrote the original), we attempt to
        restore and flag a mismatch. config-rest scalar/sub-resource ops only;
        json-rpc writes are skipped (no generic safe write-back).
        """
        if op.generation != "config-rest":
            return self._result(op, ok=False,
                                skipped="tier-1 write-back supported for config-rest ops only")
        url = f"{self.host}{op.base_path}{op.path}"
        # 1. read current value
        status, parsed, _ = self.http("GET", url, json=None)
        if status is None or not (200 <= status < 300) or not isinstance(parsed, dict):
            return self._result(op, ok=False, http_status=status,
                                skipped="could not read current value for write-back")
        original = parsed.get("data") if "data" in parsed else parsed
        # 2. write the same value back
        pstatus, _pp, latency = self.http(op.method, url, json=original)
        patch_ok = pstatus is not None and 200 <= pstatus < 300
        # 3. read back + compare
        rstatus, rparsed, _ = self.http("GET", url, json=None)
        readback = rparsed.get("data") if isinstance(rparsed, dict) and "data" in rparsed else rparsed
        mismatch = patch_ok and readback != original
        if mismatch:
            # best-effort restore (we only ever wrote the original, so this is belt-and-braces)
            self.http(op.method, url, json=original)
        return self._result(
            op, ok=bool(patch_ok and not mismatch), http_status=pstatus,
            latency_ms=round(latency, 1),
            error_code="readback-mismatch" if mismatch else None,
            method=op.method, path=op.base_path + op.path,
            shape=response_shape(original))

    def validate_readonly(self, op: OpSpec) -> Dict[str, Any]:
        built = _build_readonly_request(op, self.host)
        if built is None:
            return self._result(op, ok=False, skipped="unsupported generation for read-only validation")
        method, url, body = built
        status, parsed, latency = self.http(method, url, json=body)
        ok = status is not None and 200 <= status < 300
        # json-rpc returns 200 even on method errors; detect the error envelope
        error_code = None
        if isinstance(parsed, dict):
            err = parsed.get("error")
            if isinstance(err, dict):
                ok = False
                error_code = err.get("code") or err.get("errorCode")
            elif "Unknown method" in str(parsed.get("method", "")):
                ok = False
        return self._result(
            op, ok=ok, http_status=status, latency_ms=round(latency, 1),
            error_code=error_code,
            shape=response_shape(parsed.get("data") if isinstance(parsed, dict) and "data" in parsed
                                 else parsed) if parsed is not None else None,
            method=method, path=op.base_path + op.path if op.generation == "config-rest" else op.cgi)

    @staticmethod
    def _result(op: OpSpec, *, ok: bool, http_status=None, latency_ms=None,
                error_code=None, shape=None, skipped=None, method=None, path=None) -> Dict[str, Any]:
        r = {
            "op_id": op.op_id,
            "method": method or op.method,
            "path": path,
            "risk_level": op.risk_level,
            "http_status": http_status,
            "ok": ok,
            "latency_ms": latency_ms,
            "error_code": error_code,
            "response_shape": shape,
        }
        if skipped:
            r["skipped"] = skipped
            r["ok"] = None
        return r


def is_lab_device(device_info: Dict[str, Any]) -> bool:
    tags = {str(t).lower() for t in (device_info.get("tags") or [])}
    if tags & LAB_TAGS:
        return True
    return bool(device_info.get("lab") or device_info.get("is_lab"))


def run_validation(
    runner: ValidationRunner,
    ops: Sequence[OpSpec],
    *,
    tier: int = 0,
    lab: bool = False,
    write_back_ops: Optional[Sequence[str]] = None,
    pace_seconds: float = 0.0,
) -> List[Dict[str, Any]]:
    """Validate ``ops`` at the given tier. Returns one result dict per attempted op.

    Tier 0: read-only ops only. Tier 1: + service-affecting ops, but only on a lab
    device AND only for op ids the operator explicitly opted into via
    ``write_back_ops`` (read-modify-restore by idempotent write-back). Dangerous
    ops are never executed.

    ``pace_seconds`` inserts a delay between executed ops to stay under device auth/
    rate throttling (recommended for live runs against a single device).
    """
    import time

    opted_in = set(write_back_ops or ())
    results: List[Dict[str, Any]] = []
    for op in ops:
        if op.risk_level in NEVER_RISK:
            continue  # never validate dangerous ops in survey mode
        if op.risk_level in TIER0_RISK:
            if results and pace_seconds:
                time.sleep(pace_seconds)
            results.append(runner.validate_readonly(op))
        elif op.risk_level in TIER1_RISK:
            if tier < 1 or not lab:
                continue  # not eligible; don't even record (keeps Tier-0 bundles read-only)
            if op.op_id not in opted_in:
                results.append(ValidationRunner._result(
                    op, ok=False,
                    skipped="tier-1 write not opted in (add op id to write_back_ops to validate via write-back)"))
            else:
                if results and pace_seconds:
                    time.sleep(pace_seconds)
                results.append(runner.validate_write_back(op))
    return results
