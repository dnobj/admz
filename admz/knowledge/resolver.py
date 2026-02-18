"""
Knowledge resolver — maps (device, topic) to relevant product hints.

Given a device and optional topic, loads hints from the product hierarchy
(product → series → product-line), deduplicates, and optionally filters
by topic.
"""

import logging
from typing import Any, Dict, List, Optional

from admz.knowledge.loader import KnowledgeLoader, derive_series, normalize_model
from admz.knowledge.models import Hint, KnowledgeResult

logger = logging.getLogger(__name__)

# Synonyms for topic matching. Maps common words/phrases to canonical
# topic keys used in knowledge YAML files.
_TOPIC_SYNONYMS: Dict[str, List[str]] = {
    "vapix": ["vapix-support"],
    "api": ["vapix-support"],
    "api support": ["vapix-support"],
    "poe": ["poe-management"],
    "power over ethernet": ["poe-management"],
    "port power": ["poe-management"],
    "audio": ["audio-playback", "audio-config"],
    "speaker": ["audio-playback", "audio-config"],
    "sound": ["audio-playback"],
    "playback": ["audio-playback"],
    "sip": ["sip-config"],
    "intercom": ["sip-config"],
    "analytics": ["analytics-config"],
    "people counter": ["analytics-config"],
}


class KnowledgeResolver:
    """Maps (device, topic) to relevant product knowledge hints."""

    def __init__(self, loader: KnowledgeLoader):
        self.loader = loader

    def resolve(
        self,
        device_id: str,
        topic: str = "",
        device_info: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeResult:
        """
        Resolve knowledge hints for a device, optionally filtered by topic.

        Loads hints from the product hierarchy:
        1. Product file (most specific, from model)
        2. Series file (from product file or derived from model)
        3. Product-line file (from product/series file)

        Deduplicates by hint ID; product-level wins over series, series
        wins over product-line.

        Args:
            device_id: Device identifier.
            topic: Optional topic to filter by (natural language or key).
            device_info: Device metadata from registry.

        Returns:
            KnowledgeResult with merged, deduplicated hints.
        """
        model = self._extract_model(device_id, device_info)
        if not model:
            return KnowledgeResult(
                device_id=device_id,
                notes=["No model information available for knowledge lookup."],
            )

        normalized = normalize_model(model)
        all_hints: List[Hint] = []
        levels_loaded: List[str] = []

        # Track series/product_line from the hierarchy
        series_key: Optional[str] = None
        product_line_key: Optional[str] = None

        # 1. Load product file
        product = self.loader.load_product(normalized)
        if product:
            all_hints.extend(product.hints)
            levels_loaded.append("product")
            series_key = product.series
            product_line_key = product.product_line

        # 2. Determine series (from product file or derived)
        if not series_key:
            series_key = derive_series(model)

        if series_key:
            series = self.loader.load_series(series_key)
            if series:
                all_hints.extend(series.hints)
                levels_loaded.append("series")
                if not product_line_key:
                    product_line_key = series.product_line

        # 3. Load product-line file
        if product_line_key:
            product_line = self.loader.load_product_line(product_line_key)
            if product_line:
                all_hints.extend(product_line.hints)
                levels_loaded.append("product-line")

        # 4. Deduplicate: product > series > product-line
        hints = self._deduplicate(all_hints)

        # 5. Filter by topic if provided
        if topic:
            hints = [h for h in hints if self._match_topic(topic, h)]

        notes = []
        if not levels_loaded:
            notes.append(f"No knowledge files found for model '{model}'.")

        return KnowledgeResult(
            device_id=device_id,
            model=model,
            hints=hints,
            levels_loaded=levels_loaded,
            notes=notes,
        )

    def _extract_model(
        self,
        device_id: str,
        device_info: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        """Get model string from device_info or fall back to device_id."""
        if device_info:
            model = device_info.get("model")
            if model:
                return model
        # Fall back: use device_id as model guess
        return device_id

    def _deduplicate(self, hints: List[Hint]) -> List[Hint]:
        """Deduplicate hints by ID. First occurrence wins (product > series > line)."""
        seen: Dict[str, Hint] = {}
        for hint in hints:
            if hint.id not in seen:
                seen[hint.id] = hint
        return list(seen.values())

    def _match_topic(self, topic: str, hint: Hint) -> bool:
        """Check if a hint matches a topic query.

        Matches against (in order):
        1. hint.topic against canonical topic keys (exact or substring)
        2. hint.topic against raw topic (substring)
        3. hint.tags against raw topic words (exact word match)
        4. hint.summary against raw topic words (word intersection)
        """
        topic_lower = topic.lower().strip()

        # Expand synonyms to canonical topic keys
        canonical_topics = self._expand_topic(topic_lower)

        # 1. Check hint.topic against canonical keys
        hint_topic = hint.topic.lower()
        for ct in canonical_topics:
            if ct == hint_topic or ct in hint_topic or hint_topic in ct:
                return True

        # 2. Check raw topic against hint.topic
        if topic_lower in hint_topic or hint_topic in topic_lower:
            return True

        # 3. Check tags against raw topic words (exact word match only)
        topic_words = set(topic_lower.replace("-", " ").split())
        tags_lower = {t.lower() for t in hint.tags}
        if topic_words & tags_lower:
            return True

        # 4. Check summary word intersection with raw topic words
        summary_words = set(hint.summary.lower().replace("-", " ").split())
        if topic_words & summary_words:
            return True

        return False

    def _expand_topic(self, topic: str) -> List[str]:
        """Expand a topic query into canonical topic keys using synonyms."""
        # Exact synonym match
        if topic in _TOPIC_SYNONYMS:
            return _TOPIC_SYNONYMS[topic]

        # Partial match
        expanded = []
        for synonym, keys in _TOPIC_SYNONYMS.items():
            if synonym in topic or topic in synonym:
                for k in keys:
                    if k not in expanded:
                        expanded.append(k)
        if expanded:
            return expanded

        # Return as-is (will match directly against hint fields)
        return [topic]
