"""
Capabilities loader -- reads per-model capability YAML files and the API ID mapping.

Parallel to KnowledgeLoader: handles YAML I/O and caching for the
device API capabilities registry.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from admz.capabilities.models import FirmwareSnapshot, ModelCapabilities
from admz.knowledge.loader import normalize_model, derive_series

logger = logging.getLogger(__name__)


class CapabilitiesLoader:
    """
    Reads per-model capability YAML files from the catalog directory.

    Expects files under catalog_path/capabilities/:
        models/{model}.yaml
        _api_id_map.yaml
    """

    def __init__(self, catalog_path: str):
        self.catalog_path = Path(catalog_path)
        self._model_cache: Dict[str, ModelCapabilities] = {}
        self._api_id_map: Optional[Dict[str, str]] = None
        self._reverse_map: Optional[Dict[str, str]] = None

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load and parse a YAML file."""
        with open(path) as f:
            return yaml.safe_load(f) or {}

    # ------------------------------------------------------------------
    # Model capabilities
    # ------------------------------------------------------------------

    def load_model(self, model: str) -> Optional[ModelCapabilities]:
        """Load a model's capability file."""
        key = normalize_model(model)
        if key in self._model_cache:
            return self._model_cache[key]

        path = self.catalog_path / "capabilities" / "models" / f"{key}.yaml"
        if not path.exists():
            return None

        data = self._load_yaml(path)
        snapshots = []
        for s in data.get("snapshots", []):
            snapshots.append(
                FirmwareSnapshot(
                    firmware=str(s["firmware"]),
                    discovered=s.get("discovered", ""),
                    device_id=s.get("device_id", ""),
                    api_count=s.get("api_count", 0),
                    apis=s.get("apis", {}),
                )
            )

        mc = ModelCapabilities(
            model=data.get("model", model),
            series=data.get("series") or derive_series(model),
            snapshots=snapshots,
        )
        self._model_cache[key] = mc
        return mc

    def list_models(self) -> List[str]:
        """List all model names that have capability files."""
        models_dir = self.catalog_path / "capabilities" / "models"
        if not models_dir.exists():
            return []
        return [
            p.stem for p in sorted(models_dir.glob("*.yaml"))
        ]

    # ------------------------------------------------------------------
    # API ID mapping
    # ------------------------------------------------------------------

    def get_api_id_map(self) -> Dict[str, str]:
        """Load the catalog api_id -> device-reported id mapping.

        Only contains entries where they differ.
        """
        if self._api_id_map is not None:
            return self._api_id_map

        path = self.catalog_path / "capabilities" / "_api_id_map.yaml"
        if not path.exists():
            self._api_id_map = {}
            return self._api_id_map

        self._api_id_map = self._load_yaml(path)
        return self._api_id_map

    def catalog_api_id_to_device_id(self, catalog_api_id: str) -> str:
        """Translate a catalog api_id to the device-reported id.

        If no mapping exists, returns the input unchanged (they match).
        """
        mapping = self.get_api_id_map()
        return mapping.get(catalog_api_id, catalog_api_id)

    def device_id_to_catalog_api_id(self, device_reported_id: str) -> str:
        """Translate a device-reported API id to the catalog api_id.

        If no mapping exists, returns the input unchanged (they match).
        """
        if self._reverse_map is None:
            mapping = self.get_api_id_map()
            self._reverse_map = {v: k for k, v in mapping.items()}
        return self._reverse_map.get(device_reported_id, device_reported_id)

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def clear_cache(self):
        """Clear all caches."""
        self._model_cache.clear()
        self._api_id_map = None
        self._reverse_map = None
