"""Tests for the product knowledge base: loader, resolver, and model normalization."""

import os
import pytest
import axis_api_atlas

from axis_api_atlas.knowledge.loader import KnowledgeLoader, normalize_model, derive_series
from axis_api_atlas.knowledge.resolver import KnowledgeResolver
from axis_api_atlas.knowledge.models import Hint, ProductKnowledge, KnowledgeResult

# Knowledge data now ships with the axis-api-atlas package (ADR-0029).
CATALOG_PATH = axis_api_atlas.default_data_path()


@pytest.fixture
def loader():
    return KnowledgeLoader(CATALOG_PATH)


@pytest.fixture
def resolver(loader):
    return KnowledgeResolver(loader)


# ------------------------------------------------------------------
# Model normalization
# ------------------------------------------------------------------


class TestNormalization:

    def test_normalize_model_basic(self):
        assert normalize_model("T8516") == "t8516"

    def test_normalize_model_spaces(self):
        assert normalize_model("  T8516  ") == "t8516"

    def test_normalize_model_strips_axis_prefix(self):
        assert normalize_model("AXIS T8516") == "t8516"

    def test_normalize_model_strips_axis_prefix_case(self):
        assert normalize_model("Axis P8815-2") == "p8815-2"

    def test_normalize_model_already_lower(self):
        assert normalize_model("c1710") == "c1710"

    def test_derive_series_t8516(self):
        assert derive_series("T8516") == "t85"

    def test_derive_series_p8815(self):
        assert derive_series("P8815-2") == "p88"

    def test_derive_series_c1710(self):
        assert derive_series("C1710") == "c17"

    def test_derive_series_i8016(self):
        assert derive_series("I8016-LVE") == "i80"

    def test_derive_series_axis_prefix(self):
        assert derive_series("AXIS T8516") == "t85"

    def test_derive_series_no_digits(self):
        assert derive_series("NoDigits") is None


# ------------------------------------------------------------------
# KnowledgeLoader tests
# ------------------------------------------------------------------


class TestKnowledgeLoader:

    def test_load_product(self, loader):
        pk = loader.load_product("T8516")
        assert pk is not None
        assert pk.level == "product"
        assert pk.identifier == "t8516"
        assert pk.series == "t85"
        assert pk.product_line == "network-switches"
        assert len(pk.hints) >= 2

    def test_load_product_hints_have_fields(self, loader):
        pk = loader.load_product("T8516")
        hint = pk.hints[0]
        assert hint.id == "t8516-no-vapix"
        assert hint.topic == "vapix-support"
        assert hint.summary != ""
        assert hint.text != ""
        assert len(hint.tags) > 0
        assert hint.source_level == "product"
        assert "products/t8516.yaml" in hint.source_file

    def test_load_product_c1710(self, loader):
        pk = loader.load_product("C1710")
        assert pk is not None
        assert pk.series == "c17"
        assert pk.product_line == "network-speakers"

    def test_load_product_missing(self, loader):
        pk = loader.load_product("NONEXISTENT-999")
        assert pk is None

    def test_load_series(self, loader):
        pk = loader.load_series("t85")
        assert pk is not None
        assert pk.level == "series"
        assert pk.product_line == "network-switches"
        assert len(pk.hints) >= 2

    def test_load_series_c17(self, loader):
        pk = loader.load_series("c17")
        assert pk is not None
        assert pk.product_line == "network-speakers"

    def test_load_series_missing(self, loader):
        pk = loader.load_series("zzz")
        assert pk is None

    def test_load_product_line(self, loader):
        pk = loader.load_product_line("network-switches")
        assert pk is not None
        assert pk.level == "product-line"
        assert len(pk.hints) >= 2

    def test_load_product_line_speakers(self, loader):
        pk = loader.load_product_line("network-speakers")
        assert pk is not None
        assert len(pk.hints) >= 2

    def test_load_product_line_missing(self, loader):
        pk = loader.load_product_line("nonexistent-line")
        assert pk is None

    def test_load_index(self, loader):
        index = loader.load_index("by-topic")
        assert "vapix-support" in index
        assert "poe-management" in index
        assert isinstance(index["vapix-support"], list)
        assert len(index["vapix-support"]) > 0

    def test_load_index_missing(self, loader):
        index = loader.load_index("nonexistent")
        assert index == {}

    def test_cache_works(self, loader):
        pk1 = loader.load_product("T8516")
        pk2 = loader.load_product("T8516")
        assert pk1 is pk2  # same object from cache

    def test_clear_cache(self, loader):
        loader.load_product("T8516")
        assert len(loader._knowledge_cache) > 0
        loader.clear_cache()
        assert len(loader._knowledge_cache) == 0
        assert len(loader._index_cache) == 0


# ------------------------------------------------------------------
# KnowledgeResolver tests
# ------------------------------------------------------------------


class TestKnowledgeResolver:

    def test_resolve_t8516_all_hints(self, resolver):
        """T8516 should load hints from product, series, and product-line."""
        result = resolver.resolve("t8516")
        assert result.model == "t8516"
        assert "product" in result.levels_loaded
        assert "series" in result.levels_loaded
        assert "product-line" in result.levels_loaded
        assert len(result.hints) > 0

    def test_resolve_t8516_deduplication(self, resolver):
        """Hint IDs should be unique after deduplication."""
        result = resolver.resolve("t8516")
        ids = [h.id for h in result.hints]
        assert len(ids) == len(set(ids))

    def test_resolve_t8516_product_wins(self, resolver):
        """Product-level hint should take precedence over series."""
        result = resolver.resolve("t8516")
        # t8516-no-vapix (product) should be present instead of t85-no-vapix (series)
        ids = [h.id for h in result.hints]
        assert "t8516-no-vapix" in ids

    def test_resolve_t8516_vapix_topic(self, resolver):
        """Filtering by vapix topic should return only VAPIX-related hints."""
        result = resolver.resolve("t8516", topic="vapix-support")
        assert len(result.hints) > 0
        for hint in result.hints:
            # All hints should be related to VAPIX/API
            assert (
                "vapix" in hint.topic.lower()
                or "api" in hint.tags
                or "vapix" in hint.summary.lower()
            )

    def test_resolve_t8516_poe_topic(self, resolver):
        """Filtering by poe topic should return only PoE-related hints."""
        result = resolver.resolve("t8516", topic="poe")
        assert len(result.hints) > 0
        for hint in result.hints:
            assert (
                "poe" in hint.topic.lower()
                or "poe" in hint.tags
                or "poe" in hint.summary.lower()
            )

    def test_resolve_c1710_all_hints(self, resolver):
        """C1710 should load from product, series, and product-line."""
        result = resolver.resolve("c1710")
        assert "product" in result.levels_loaded
        assert "series" in result.levels_loaded
        assert "product-line" in result.levels_loaded
        assert len(result.hints) > 0

    def test_resolve_with_device_info(self, resolver):
        """Should use model from device_info if available."""
        result = resolver.resolve(
            "my-switch",
            device_info={"model": "T8516", "host": "192.168.1.10"},
        )
        assert result.model == "T8516"
        assert "product" in result.levels_loaded

    def test_resolve_unknown_model_with_series_derivation(self, resolver):
        """Unknown product should fall back to series derivation."""
        # T8504 has no product file but should derive series t85
        result = resolver.resolve("t8504")
        assert "series" in result.levels_loaded
        assert "product-line" in result.levels_loaded

    def test_resolve_completely_unknown(self, resolver):
        """Completely unknown model should return empty with notes."""
        result = resolver.resolve("zzz-unknown")
        assert len(result.hints) == 0
        assert len(result.notes) > 0

    def test_resolve_topic_synonym_expansion(self, resolver):
        """Synonym 'api' should match vapix-support topic."""
        result = resolver.resolve("t8516", topic="api")
        assert len(result.hints) > 0
        topics = [h.topic for h in result.hints]
        assert "vapix-support" in topics

    def test_resolve_topic_no_match(self, resolver):
        """Filtering by nonexistent topic should return empty."""
        result = resolver.resolve("t8516", topic="xyzzy-nonsense-topic")
        assert len(result.hints) == 0
