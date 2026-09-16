"""How a notice is shown to a reader — the REST list and the chat tool.

The row itself holds identifiers and counts only. A reader also wants to know
which device it is, so the view adds the device's model, nickname and host
from the registry: device-written text, sanitized here, and shown only where
it is treated as data (the strip renders it as text; the prompt fences it).
"""

from __future__ import annotations

from typing import Any, Dict

from admz.notices.producers import SOURCE_LABELS
from admz.notices.store import Notice


def device_view(registry: Any, device_id: str) -> Dict[str, str]:
    """The device's model, nickname and host, sanitized; ``{}`` when unknown."""
    from admz.validators import sanitize_display_text

    if not device_id or registry is None:
        return {}
    try:
        info = registry.get_device_info(device_id) or {}
    except Exception:  # noqa: BLE001 — a removed device keeps its notice
        return {}
    return {
        "model": sanitize_display_text(info.get("model")),
        "nickname": sanitize_display_text(info.get("nickname")),
        "host": sanitize_display_text(info.get("host"), max_length=253),
    }


def notice_view(notice: Notice, registry: Any = None) -> Dict[str, Any]:
    view = notice.to_dict()
    view["device"] = device_view(registry, notice.device_id)
    view["source_label"] = SOURCE_LABELS.get(notice.source, notice.source)
    return view
