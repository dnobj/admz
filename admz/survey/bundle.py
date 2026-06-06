"""
Assemble a contribution bundle from survey results.

Takes the *redacted* per-device survey output and writes a bundle directory in
the format ``axis_api_atlas.contrib`` expects, then validates it locally with the
same gate CI will run. Nothing here talks to a device or the network.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from axis_api_atlas.contrib.schema import (
    BUNDLE_SCHEMA_VERSION,
    BundleManifest,
    write_manifest,
)
from axis_api_atlas.contrib.validate import validate_bundle
from axis_api_atlas.tools.seed_from_openapi import seed_rest_api

from admz.survey import COLLECTOR_VERSION


def _normalize_model(model: str) -> str:
    m = model.strip()
    if m.upper().startswith("AXIS "):
        m = m[5:]
    return m.lower().replace(" ", "-")


def derive_series(model: str) -> str:
    norm = _normalize_model(model)
    m = re.match(r"([a-z]+)(\d{2})", norm)
    return (m.group(1) + m.group(2)) if m else ""


@dataclass
class DeviceSurvey:
    """One device's redacted survey output (input to the bundler)."""

    model: str
    redacted_snapshot: Dict          # firmware/discovered/device_id/api_count/apis/apis_detail
    new_model: bool = False
    new_firmware: bool = False
    uncatalogued_apis: List[str] = field(default_factory=list)
    openapi_specs: Dict[str, Dict] = field(default_factory=dict)   # api_id -> {base_path, version, state, spec}
    validation: List[Dict] = field(default_factory=list)


def assemble_bundle(
    out_dir: Path,
    surveys: List[DeviceSurvey],
    *,
    profile: str,
    contributor: str,
    admz_version: str,
    bundle_id: str,
    created_utc: str,
    kinds: Optional[List[str]] = None,
) -> Path:
    """Write a bundle dir and return its root. Raises if local validation fails."""
    root = Path(out_dir) / bundle_id
    files: List[str] = []

    def _write(rel: str, text: str) -> None:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        files.append(rel)

    models: List[str] = []
    firmwares: Dict[str, str] = {}
    has_validation = False

    for s in surveys:
        norm = _normalize_model(s.model)
        models.append(s.model)
        fw = str(s.redacted_snapshot.get("firmware") or "")
        firmwares[s.model] = fw

        # capability snapshot
        snap_doc = {
            "model": s.model,
            "series": derive_series(s.model),
            "snapshots": [s.redacted_snapshot],
        }
        _write(f"capabilities/{norm}.yaml",
               yaml.safe_dump(snap_doc, sort_keys=False, allow_unicode=True))

        # raw OpenAPI specs (schema-only, already filtered by redaction) + seeded ops
        for api_id, meta in sorted(s.openapi_specs.items()):
            spec = meta.get("spec") or {}
            ver = meta.get("version", "v1")
            _write(f"openapi/{api_id}-{ver}.json",
                   json.dumps(spec, indent=2, sort_keys=True))
            seeded = seed_rest_api(
                api_id,
                meta.get("base_path", f"/config/rest/{api_id}/{ver}"),
                spec.get("paths", {}),
                state=meta.get("state", "beta"),
                min_firmware=fw or "12.0",
            )
            _write(f"seeded/{seeded.api_rel_path}", seeded.api_yaml_text)
            for op in seeded.ops:
                _write(f"seeded/{op.rel_path}", op.yaml_text)

        # validation results
        if s.validation:
            has_validation = True
            _write(f"validation/{norm}-{fw}.json",
                   json.dumps(s.validation, indent=2, sort_keys=True))

    if kinds is None:
        kinds = ["discovery"] + (["validation"] if has_validation else [])

    manifest = BundleManifest(
        schema_version=BUNDLE_SCHEMA_VERSION,
        bundle_id=bundle_id,
        kinds=kinds,
        contributor=contributor,
        admz_version=admz_version,
        collector_version=COLLECTOR_VERSION,
        redaction_profile=profile,
        created_utc=created_utc,
        models=models,
        firmwares=firmwares,
        files=sorted(files),
    )
    write_manifest(root, manifest)

    report = validate_bundle(root)
    if not report.ok:
        raise ValueError("assembled bundle failed local validation:\n" + report.summary())
    return root
