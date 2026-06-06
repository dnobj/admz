"""
Diff a live device snapshot against the installed ``axis-api-atlas``.

Survey mode should only surface *new* information, judged against whatever atlas
the install already ships (``axis_api_atlas.default_data_path()``, or an
``ADMZ_CATALOG_PATH`` override). This keeps PRs to genuine deltas instead of
re-reporting devices the atlas already knows.

A :class:`SurveyDelta` answers: is this a new model? a new firmware for a known
model? which reported APIs have no catalog entry yet (the seed candidates)?
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml


def _normalize_model(model: str) -> str:
    m = model.strip()
    if m.upper().startswith("AXIS "):
        m = m[5:]
    return m.lower().replace(" ", "-")


@dataclass
class SurveyDelta:
    model: str
    firmware: str
    new_model: bool
    new_firmware: bool
    uncatalogued_apis: List[str] = field(default_factory=list)   # device api ids w/o catalog entry
    known_apis: List[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.new_model or self.new_firmware or self.uncatalogued_apis)

    def summary(self) -> str:
        bits = []
        if self.new_model:
            bits.append("NEW MODEL")
        if self.new_firmware:
            bits.append("new firmware")
        if self.uncatalogued_apis:
            bits.append(f"{len(self.uncatalogued_apis)} uncatalogued APIs")
        return f"{self.model} @ {self.firmware}: " + (", ".join(bits) or "nothing new")


class AtlasIndex:
    """A read-only view of the installed atlas data tree for diffing."""

    def __init__(self, data_path: Optional[str] = None):
        if data_path is None:
            data_path = os.getenv("ADMZ_CATALOG_PATH")
        if data_path is None:
            import axis_api_atlas
            data_path = axis_api_atlas.default_data_path()
        self.root = Path(data_path)
        self._models: Optional[Set[str]] = None
        self._fw_by_model: Optional[Dict[str, Set[str]]] = None
        self._api_dirs: Optional[Set[str]] = None
        self._id_map: Optional[Dict[str, str]] = None

    # --- known models + firmwares (from capability snapshots) ---
    def _load_models(self) -> None:
        models: Set[str] = set()
        fw: Dict[str, Set[str]] = {}
        cap_dir = self.root / "capabilities" / "models"
        if cap_dir.is_dir():
            for f in cap_dir.glob("*.yaml"):
                models.add(f.stem)
                try:
                    data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
                except Exception:  # noqa: BLE001
                    continue
                fws = {str(s.get("firmware")) for s in data.get("snapshots", [])
                       if isinstance(s, dict) and s.get("firmware")}
                fw[f.stem] = fws
        self._models = models
        self._fw_by_model = fw

    def known_models(self) -> Set[str]:
        if self._models is None:
            self._load_models()
        return self._models  # type: ignore[return-value]

    def firmwares_for(self, model: str) -> Set[str]:
        if self._fw_by_model is None:
            self._load_models()
        return self._fw_by_model.get(_normalize_model(model), set())  # type: ignore[union-attr]

    # --- catalogued API dirs (rest + cgi) + id map ---
    def _load_apis(self) -> None:
        dirs: Set[str] = set()
        for sub in ("rest", "cgi"):
            d = self.root / "vapix" / sub
            if d.is_dir():
                for child in d.iterdir():
                    if child.is_dir():
                        # cgi dirs keep a ".cgi" suffix; normalise both ways
                        dirs.add(child.name)
                        dirs.add(child.name.replace(".cgi", ""))
        id_map: Dict[str, str] = {}
        idmap_path = self.root / "capabilities" / "_api_id_map.yaml"
        if idmap_path.is_file():
            try:
                id_map = yaml.safe_load(idmap_path.read_text(encoding="utf-8")) or {}
            except Exception:  # noqa: BLE001
                id_map = {}
        self._api_dirs = dirs
        self._id_map = id_map

    def is_api_catalogued(self, device_api_id: str) -> bool:
        if self._api_dirs is None:
            self._load_apis()
        dirs = self._api_dirs  # type: ignore[assignment]
        idmap = self._id_map or {}
        dev2cat = {v: k for k, v in idmap.items()}
        candidates = {
            device_api_id,
            device_api_id.replace("-", ""),
            dev2cat.get(device_api_id, ""),
        }
        norm_dirs = {d.replace("-", "") for d in dirs}
        return any(c and (c in dirs or c.replace("-", "") in norm_dirs) for c in candidates)


def diff_snapshot(snapshot: Dict, *, model: str, index: AtlasIndex) -> SurveyDelta:
    """Compute what's new in ``snapshot`` for ``model`` vs the atlas index."""
    norm = _normalize_model(model)
    firmware = str(snapshot.get("firmware") or "")
    new_model = norm not in index.known_models()
    new_firmware = (not new_model) and firmware not in index.firmwares_for(model)

    uncat: List[str] = []
    known: List[str] = []
    for api_id in sorted(snapshot.get("apis", {})):
        if index.is_api_catalogued(api_id):
            known.append(api_id)
        else:
            uncat.append(api_id)

    return SurveyDelta(
        model=model, firmware=firmware,
        new_model=new_model, new_firmware=new_firmware,
        uncatalogued_apis=uncat, known_apis=known,
    )
