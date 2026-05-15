from typing import Any, Dict, List

from admz.snapshot.facets.base import (
    DeviceCriteria,
    FacetAdapter,
    ReadSpec,
    register_facet,
)


@register_facet
class UsersFacet(FacetAdapter):
    """Captures user accounts (usernames and roles, never passwords)."""

    @property
    def name(self) -> str:
        return "users"

    @property
    def applies_to(self) -> List[DeviceCriteria]:
        return [DeviceCriteria(families=["vapix"])]

    @property
    def param_prefixes(self) -> List[str]:
        return ["root.Properties.API.HTTP.AdminAccess"]

    @property
    def write_ops(self) -> List[str]:
        return ["pwdgrp.cgi:add-user"]

    @property
    def restore_order(self) -> int:
        return 80  # near-last — don't lock yourself out

    def serialize(self, raw_responses: Dict[str, Any]) -> Dict[str, Any]:
        params = raw_responses.get("params", {})
        users = {}
        for key, value in sorted(params.items()):
            if key.startswith("root.Properties.API.HTTP.AdminAccess"):
                short_key = key.split(".")[-1]
                users[short_key] = value
        return {"admin_access": users} if users else {}

    def deserialize(self, yaml_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []
