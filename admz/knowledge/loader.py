"""
Knowledge loader — reads product knowledge YAML files from the catalog directory.

Parallel to CatalogLoader: handles YAML I/O and caching for the
product knowledge base (products, series, product-lines, index files).
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from admz.knowledge.models import Hint, ProductKnowledge

logger = logging.getLogger(__name__)


def normalize_model(model: str) -> str:
    """Normalize a model string for file lookup.

    Strips "AXIS " prefix (devices report "AXIS T8516" not "T8516"),
    lowercases, strips whitespace, replaces spaces with hyphens.
    """
    s = model.strip()
    # Strip common manufacturer prefix
    if s.upper().startswith("AXIS "):
        s = s[5:]
    return s.lower().replace(" ", "-")


def derive_series(model: str) -> Optional[str]:
    """Derive a series prefix from a model string.

    Examples:
        T8516 → t85
        AXIS T8516 → t85
        P8815-2 → p88
        C1710 → c17
        I8016-LVE → i80

    Pattern: strip "AXIS " prefix, then first letter(s) + first 2 digits.
    """
    s = model.strip()
    if s.upper().startswith("AXIS "):
        s = s[5:]
    m = re.match(r"([a-zA-Z]+)(\d{2})", s)
    if m:
        return (m.group(1) + m.group(2)).lower()
    return None


class KnowledgeLoader:
    """
    Reads product knowledge YAML files from the catalog directory.

    Expects files under catalog_path/knowledge/:
        products/{model}.yaml
        series/{series}.yaml
        product-lines/{product-line}.yaml
        index/{index-name}.yaml
    """

    def __init__(self, catalog_path: str):
        self.catalog_path = Path(catalog_path)
        self._knowledge_cache: Dict[str, ProductKnowledge] = {}
        self._index_cache: Dict[str, Dict[str, List[str]]] = {}

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load and parse a YAML file."""
        with open(path) as f:
            return yaml.safe_load(f) or {}

    # ------------------------------------------------------------------
    # Knowledge files
    # ------------------------------------------------------------------

    def load_product(self, model: str) -> Optional[ProductKnowledge]:
        """Load a product-level knowledge file."""
        key = normalize_model(model)
        return self._load_knowledge_file("products", key, "product")

    def load_series(self, series: str) -> Optional[ProductKnowledge]:
        """Load a series-level knowledge file."""
        key = series.strip().lower()
        return self._load_knowledge_file("series", key, "series")

    def load_product_line(self, product_line: str) -> Optional[ProductKnowledge]:
        """Load a product-line-level knowledge file."""
        key = product_line.strip().lower()
        return self._load_knowledge_file("product-lines", key, "product-line")

    def _load_knowledge_file(
        self, subdir: str, key: str, level: str
    ) -> Optional[ProductKnowledge]:
        """Load and cache a knowledge YAML file."""
        cache_key = f"{subdir}/{key}"
        if cache_key in self._knowledge_cache:
            return self._knowledge_cache[cache_key]

        path = self.catalog_path / "knowledge" / subdir / f"{key}.yaml"
        if not path.exists():
            return None

        data = self._load_yaml(path)
        rel_path = f"knowledge/{subdir}/{key}.yaml"

        hints = []
        for h in data.get("hints", []):
            hints.append(
                Hint(
                    id=h["id"],
                    topic=h.get("topic", ""),
                    summary=h.get("summary", ""),
                    text=h.get("text", ""),
                    tags=h.get("tags", []),
                    source_level=level,
                    source_file=rel_path,
                )
            )

        pk = ProductKnowledge(
            level=level,
            identifier=key,
            series=data.get("series"),
            product_line=data.get("product_line"),
            display_name=data.get("display_name", ""),
            hints=hints,
        )
        self._knowledge_cache[cache_key] = pk
        return pk

    # ------------------------------------------------------------------
    # Index files
    # ------------------------------------------------------------------

    def load_index(self, index_name: str) -> Dict[str, List[str]]:
        """Load a knowledge index file (e.g., by-topic).

        Returns a dict mapping keys to lists of file paths.
        """
        if index_name in self._index_cache:
            return self._index_cache[index_name]

        path = self.catalog_path / "knowledge" / "index" / f"{index_name}.yaml"
        if not path.exists():
            return {}

        data = self._load_yaml(path)
        index = {k: v for k, v in data.items() if isinstance(v, list)}
        self._index_cache[index_name] = index
        return index

    def clear_cache(self):
        """Clear all caches."""
        self._knowledge_cache.clear()
        self._index_cache.clear()
