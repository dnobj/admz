"""Refresh ``catalog/capabilities/models/<model>.yaml`` from a live Axis device.

Queries BOTH API-discovery mechanisms on the device and records a
firmware-stamped snapshot of every API it exposes — version, state
(released/beta/alpha), and (for the newer RESTful APIs) the OpenAPI spec
link:

  - Legacy : POST /axis-cgi/apidiscovery.cgi  getApiList   (CGI / JSON-RPC APIs)
  - DCA    : GET  /config/discover/apis                    (RESTful APIs incl. beta;
             AXIS OS >= 12.3 — the "Device Configuration API" framework)

Device identity (model + firmware + serial) comes from basicdeviceinfo.cgi.

The snapshot preserves the existing back-compat ``apis: {id: version}`` map
(consumed by admz.capabilities) and ADDS an ``apis_detail`` map that records,
per API, what each discovery source reported (so a single API that exists as
both a legacy CGI v1 and a DCA REST v2beta is captured in full). The capability
loader ignores unknown keys, so this is additive.

Read-only: this tool only performs discovery GET/getList calls. It never
mutates device state.

Usage:
  python tools/refresh_capabilities.py --device-id B8A44FB0BDA1
  python tools/refresh_capabilities.py --host 192.168.1.220 --user root --password pass
  python tools/refresh_capabilities.py --device-id B8A44FB0BDA1 --dry-run
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx
import yaml

# Repo root: tools/ is one level under the repo root.
ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog"
MODELS_DIR = CATALOG / "capabilities" / "models"

sys.path.insert(0, str(ROOT))
from admz.knowledge.loader import normalize_model  # noqa: E402


def _client(host: str, user: str, password: str) -> Tuple[str, httpx.Client]:
    base = host if host.startswith("http") else f"http://{host}"
    return base, httpx.Client(auth=httpx.DigestAuth(user, password), timeout=12.0)


def get_identity(base: str, c: httpx.Client) -> Dict[str, str]:
    """Model / firmware / serial via basicdeviceinfo.cgi."""
    r = c.post(
        base + "/axis-cgi/basicdeviceinfo.cgi",
        json={"apiVersion": "1.0", "method": "getAllProperties"},
    )
    r.raise_for_status()
    props = r.json().get("data", {}).get("propertyList", {}) or r.json().get("data", {})
    return {
        "model": props.get("ProdNbr") or props.get("ProdShortName", "").replace("AXIS ", ""),
        "firmware": props.get("Version", ""),
        "serial": props.get("SerialNumber", ""),
        "product_full": props.get("ProdFullName", ""),
        "product_type": props.get("ProdType", ""),
    }


def get_legacy_apis(base: str, c: httpx.Client) -> Dict[str, Dict[str, str]]:
    """Legacy apidiscovery.cgi getApiList -> {id: {version, status}}."""
    out: Dict[str, Dict[str, str]] = {}
    try:
        r = c.post(
            base + "/axis-cgi/apidiscovery.cgi",
            json={"apiVersion": "1.0", "method": "getApiList"},
        )
        if r.status_code == 200:
            for a in r.json().get("data", {}).get("apiList", []):
                out[a["id"]] = {
                    "version": str(a.get("version", "")),
                    "status": a.get("status", ""),
                }
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] legacy apidiscovery failed: {e}", file=sys.stderr)
    return out


def get_dca_apis(base: str, c: httpx.Client) -> Dict[str, Dict[str, Any]]:
    """DCA /config/discover/apis -> {id: {major, version, state, rest_api, openapi}}.

    Older AXIS OS (< 12.3) lacks the DCA framework — returns {} on 404.
    """
    out: Dict[str, Dict[str, Any]] = {}
    try:
        r = c.get(base + "/config/discover/apis")
        if r.status_code != 200:
            print(f"  [info] DCA discover unavailable (HTTP {r.status_code}) — legacy only", file=sys.stderr)
            return out
        apis = r.json()
        # Some firmwares wrap as {"apis": {...}}, others return the map directly.
        if "apis" in apis and isinstance(apis["apis"], dict):
            apis = apis["apis"]
        for api_id, versions in apis.items():
            if not isinstance(versions, dict):
                continue
            # Pick the highest major version entry for the flat record; keep all in detail.
            best = sorted(versions.keys())[-1]
            v = versions[best]
            out[api_id] = {
                "major": best,
                "version": v.get("version", ""),
                "state": v.get("state", ""),
                "rest_api": v.get("rest_api", ""),
                "openapi": v.get("rest_openapi", ""),
                "all_majors": sorted(versions.keys()),
            }
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] DCA discover failed: {e}", file=sys.stderr)
    return out


def build_snapshot(host: str, user: str, password: str) -> Dict[str, Any]:
    base, c = _client(host, user, password)
    with c:
        ident = get_identity(base, c)
        legacy = get_legacy_apis(base, c)
        dca = get_dca_apis(base, c)

    # Union of api ids from both sources.
    api_ids = sorted(set(legacy) | set(dca))
    flat: Dict[str, str] = {}
    detail: Dict[str, Dict[str, Any]] = {}
    for aid in api_ids:
        entry: Dict[str, Any] = {}
        if aid in legacy:
            entry["legacy"] = legacy[aid]
            flat[aid] = legacy[aid]["version"]  # back-compat: prefer legacy version string
        if aid in dca:
            entry["dca"] = {k: v for k, v in dca[aid].items() if v not in ("", None)}
            flat.setdefault(aid, dca[aid].get("version", ""))
        detail[aid] = entry

    return {
        "firmware": ident["firmware"],
        "discovered": _dt.date.today().isoformat(),
        "device_id": "",  # filled by caller if known
        "api_count": len(api_ids),
        "apis": flat,
        "apis_detail": detail,
        "_identity": ident,
    }


def write_snapshot(model: str, series_hint: Optional[str], snap: Dict[str, Any], dry_run: bool) -> Path:
    key = normalize_model(model)
    path = MODELS_DIR / f"{key}.yaml"
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    else:
        data = {"model": model, "series": series_hint, "snapshots": []}
    data.setdefault("model", model)
    if series_hint and not data.get("series"):
        data["series"] = series_hint
    snaps = data.setdefault("snapshots", [])

    ident = snap.pop("_identity", {})
    fw = snap["firmware"]
    # Idempotent: replace an existing snapshot for this firmware, else append.
    replaced = False
    for i, s in enumerate(snaps):
        if str(s.get("firmware")) == str(fw):
            snaps[i] = snap
            replaced = True
            break
    if not replaced:
        snaps.append(snap)
    snaps.sort(key=lambda s: str(s.get("firmware")))

    out = yaml.safe_dump(data, sort_keys=False, default_flow_style=False, width=100)
    if dry_run:
        print(f"\n--- DRY RUN: would write {path} ---")
        print(f"model={model} fw={fw} apis={snap['api_count']} (replaced={replaced})")
        # Show siren-and-light detail as a spot check if present.
        sl = snap["apis_detail"].get("siren-and-light")
        if sl:
            print("siren-and-light detail:", yaml.safe_dump(sl, default_flow_style=False).strip())
    else:
        path.write_text(out, encoding="utf-8")
        print(f"  wrote {path} (model={model}, fw={fw}, {snap['api_count']} APIs, replaced={replaced})")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="Refresh the Axis device API capability matrix from a live device.")
    ap.add_argument("--device-id", help="Resolve host+credentials from the ADMZ registry.")
    ap.add_argument("--host", help="Device host/IP (alternative to --device-id).")
    ap.add_argument("--user", help="Username (with --host).")
    ap.add_argument("--password", help="Password (with --host).")
    ap.add_argument("--series", help="Series hint for a new model file (e.g. c11).")
    ap.add_argument("--dry-run", action="store_true", help="Print the snapshot; do not write.")
    args = ap.parse_args()

    device_id = ""
    if args.device_id:
        from admz.factory import create_device_registry
        reg = create_device_registry()
        dev = reg.get_device_info(args.device_id)
        creds = reg.get_credentials(args.device_id)
        host = dev.get("host") or dev.get("ip_address")
        user, password = creds.get("username"), creds.get("password")
        device_id = args.device_id
        if not host:
            print("device has no host/ip", file=sys.stderr)
            return 2
    elif args.host and args.user is not None:
        host, user, password = args.host, args.user, args.password or ""
    else:
        ap.error("provide --device-id OR (--host --user [--password])")
        return 2

    print(f"Discovering APIs on {host} ...")
    snap = build_snapshot(host, user, password)
    snap["device_id"] = device_id
    ident = snap["_identity"]
    print(f"  {ident.get('product_full') or ident.get('model')}  fw={ident.get('firmware')}  "
          f"APIs: {snap['api_count']}")
    if not ident.get("model"):
        print("could not determine model from device", file=sys.stderr)
        return 2
    write_snapshot(ident["model"], args.series, snap, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
