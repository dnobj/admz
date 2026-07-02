"""NTP client configuration via the dedicated ``ntp.cgi`` JSON API.

On modern AXIS OS the ``root.Time.NTP.*`` param tree is a READ-ONLY mirror —
``param.cgi:update`` rejects writes even of an unchanged value (verified live,
see TimeFacet.RESTORE_EXCLUDE). The real config lives behind
``ntp.cgi:getNTPInfo`` / ``setNTPClientConfiguration``, so this facet tracks it
there AND makes it genuinely revertable: it's the first facet using the
op-level revert seam (``build_revert_ops``) — reverting any drifted NTP field
writes the whole baseline client config back through the setter, which also
removes live-added servers (something the param.cgi path can never do).

Live response shape (P3748-PLVE, AXIS OS 12): ``{"client": {enabled,
NTSEnabled, serversSource, staticServers[], staticNTSKEServers[], minpoll,
maxpoll, ...}}`` plus volatile sync state (synced, timeOffset, timeToNextSync,
advertisedServers — the DHCP-provided list — and the capability constant
maxSupportedStaticServers), which is dropped so it never flaps as drift.
"""

from typing import Any, Dict, List, Optional

from admz.snapshot.facets.base import (
    DeviceCriteria,
    FacetAdapter,
    ReadSpec,
    register_facet,
)

#: Stable, operator-set client config — what we serialize (and diff).
_CONFIG_FIELDS = ("enabled", "serversSource", "NTSEnabled", "minpoll", "maxpoll")
#: Server lists are joined to one space-separated string for a stable flatten.
_LIST_FIELDS = ("staticServers", "staticNTSKEServers")
#: The subset the ``setNTPClientConfiguration`` catalog op can write back.
_REVERTABLE = {"enabled", "serversSource", "staticServers"}


def _client(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        client = raw.get("client")
        if isinstance(client, dict):
            return client
    return {}


@register_facet
class NtpFacet(FacetAdapter):
    NAME = "ntp"

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def applies_to(self) -> List[DeviceCriteria]:
        # ntp.cgi is a plain JSON API present well before AXIS OS 12; devices
        # without it simply return nothing and the facet serializes empty.
        return [DeviceCriteria(families=["vapix"])]

    @property
    def extra_read_ops(self) -> List[ReadSpec]:
        return [ReadSpec(operation_id="ntp.cgi:getNTPInfo", result_key="ntp")]

    @property
    def write_ops(self) -> List[str]:
        return ["ntp.cgi:setNTPClientConfiguration"]

    @property
    def restore_order(self) -> int:
        return 22  # alongside time (20), before image/network

    def serialize(self, raw_responses: Dict[str, Any]) -> Dict[str, Any]:
        client = _client(raw_responses.get("ntp"))
        out: Dict[str, Any] = {}
        for key in _CONFIG_FIELDS:
            if key in client:
                out[key] = client[key]
        for key in _LIST_FIELDS:
            if key in client:
                vals = client[key]
                if isinstance(vals, list):
                    out[key] = " ".join(str(v) for v in vals)
                else:
                    out[key] = str(vals)
        return out

    def _setter_params(self, doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Map a serialized facet doc → setNTPClientConfiguration params."""
        if not doc:
            return None
        params: Dict[str, Any] = {
            "enabled": bool(str(doc.get("enabled", "")).lower() in ("true", "1", "yes")),
            "serversSource": str(doc.get("serversSource", "static")),
        }
        servers = str(doc.get("staticServers", "")).split()
        # The catalog's param_rules require staticServers when static — send
        # the (possibly empty) list explicitly so the intent is unambiguous.
        params["staticServers"] = servers
        return params

    def op_revertable(self, path: str) -> bool:
        return path in _REVERTABLE

    def build_revert_ops(self, drifted, baseline_doc):
        params = self._setter_params(baseline_doc)
        if params is None:
            return None
        fields = ", ".join(sorted(p for p, *_ in drifted)) or "config"
        return [{
            "operation_id": "ntp.cgi:setNTPClientConfiguration",
            "params": params,
            "description": f"Restore baseline NTP client config ({fields})",
        }]

    def deserialize(self, yaml_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Full restore-from-commit: same whole-object write as targeted revert.
        params = self._setter_params(yaml_doc)
        if params is None:
            return []
        return [{
            "operation_id": "ntp.cgi:setNTPClientConfiguration",
            "params": params,
        }]
