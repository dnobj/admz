"""Shared flattening of a facet's nested config dict into dotted keys.

Used on BOTH sides of drift comparison AND the snapshot-capture ignore filter,
so canonical keys line up (e.g. the nested ``applications`` facet flattens
``{"vmd": {"status": "Stopped"}}`` to ``vmd.status`` everywhere).
"""

from typing import Any, Dict


def flatten(d: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
    items: Dict[str, str] = {}
    for k, v in d.items():
        full_key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            items.update(flatten(v, full_key))
        else:
            items[full_key] = str(v)
    return items
