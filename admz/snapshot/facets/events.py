from typing import Any, Dict, List

from admz.snapshot.facets.base import (
    DeviceCriteria,
    FacetAdapter,
    is_restorable,
    register_facet,
)


@register_facet
class EventsFacet(FacetAdapter):
    """Captures event rules and I/O port configuration.

    Two parameter trees are merged into one facet because events and
    I/O ports are conceptually linked (rules often trigger on I/O).
    Both trees are kept side-by-side in the serialized output.
    """

    PREFIXES = ["root.Event.", "root.IOPort."]

    # Per-group restore excludes: I/O port Configurable is a hardware
    # capability flag — 401 on write (verified live, AXIS OS 12).
    RESTORE_EXCLUDE = {
        "event": (),
        "ioport": ("I*.Configurable",),
    }

    @property
    def name(self) -> str:
        return "events"

    @property
    def applies_to(self) -> List[DeviceCriteria]:
        return [DeviceCriteria(families=["vapix"])]

    @property
    def param_prefixes(self) -> List[str]:
        return list(self.PREFIXES)

    @property
    def write_ops(self) -> List[str]:
        return ["param.cgi:update"]

    @property
    def restore_order(self) -> int:
        return 60

    def serialize(self, raw_responses: Dict[str, Any]) -> Dict[str, Any]:
        params = raw_responses.get("params", {})
        groups: Dict[str, Dict[str, str]] = {"event": {}, "ioport": {}}
        for key, value in sorted(params.items()):
            if key.startswith("root.Event."):
                groups["event"][key[len("root.Event."):]] = value
            elif key.startswith("root.IOPort."):
                groups["ioport"][key[len("root.IOPort."):]] = value
        return {k: v for k, v in groups.items() if v}

    def deserialize(self, yaml_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        params: Dict[str, str] = {}
        skipped = []
        for group, prefix in (("event", "root.Event."), ("ioport", "root.IOPort.")):
            exclude = self.RESTORE_EXCLUDE.get(group, ())
            for key, value in yaml_doc.get(group, {}).items():
                if not is_restorable(key, value, exclude):
                    skipped.append(f"{group}.{key}")
                    continue
                params[f"{prefix}{key}"] = str(value)
        if not params:
            return []
        call: Dict[str, Any] = {
            "operation_id": "param.cgi:update",
            "params": params,
        }
        if skipped:
            call["skipped"] = sorted(skipped)
        return [call]
