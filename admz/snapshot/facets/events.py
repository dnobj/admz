from typing import Any, Dict, List

from admz.snapshot.facets.base import (
    DeviceCriteria,
    FacetAdapter,
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
        for key, value in yaml_doc.get("event", {}).items():
            params[f"root.Event.{key}"] = str(value)
        for key, value in yaml_doc.get("ioport", {}).items():
            params[f"root.IOPort.{key}"] = str(value)
        if not params:
            return []
        return [{"operation_id": "param.cgi:update", "params": params}]
