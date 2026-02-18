"""
Data models for the product knowledge base.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Hint:
    """A single knowledge hint about a product, series, or product line."""

    id: str
    topic: str
    summary: str
    text: str
    tags: List[str] = field(default_factory=list)
    source_level: str = ""  # "product" | "series" | "product-line"
    source_file: str = ""


@dataclass
class ProductKnowledge:
    """Parsed YAML knowledge file."""

    level: str  # "product" | "series" | "product-line"
    identifier: str  # model, series name, or product-line name
    series: Optional[str] = None
    product_line: Optional[str] = None
    display_name: str = ""
    hints: List[Hint] = field(default_factory=list)


@dataclass
class KnowledgeResult:
    """Result of a knowledge query."""

    device_id: str
    model: Optional[str] = None
    hints: List[Hint] = field(default_factory=list)
    levels_loaded: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
