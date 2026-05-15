from typing import Any, Dict, List

from admz.snapshot.facets.base import (
    DeviceCriteria,
    FacetAdapter,
    register_facet,
)


@register_facet
class ImageFacet(FacetAdapter):

    @property
    def name(self) -> str:
        return "image"

    @property
    def applies_to(self) -> List[DeviceCriteria]:
        return [DeviceCriteria(families=["vapix"])]

    @property
    def param_prefixes(self) -> List[str]:
        return ["root.Image."]

    @property
    def write_ops(self) -> List[str]:
        return ["param.cgi:update"]

    @property
    def restore_order(self) -> int:
        return 30

    def serialize(self, raw_responses: Dict[str, Any]) -> Dict[str, Any]:
        params = raw_responses.get("params", {})
        result = {}
        for key, value in sorted(params.items()):
            if key.startswith("root.Image."):
                short_key = key[len("root.Image."):]
                result[short_key] = value
        return result

    def deserialize(self, yaml_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        params = {}
        for key, value in yaml_doc.items():
            params[f"root.Image.{key}"] = str(value)
        return [{"operation_id": "param.cgi:update", "params": params}]
