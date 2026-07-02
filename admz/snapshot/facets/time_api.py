"""Timezone configuration via the ``time`` config-rest API (v2).

The IANA timezone ("America/Chicago") only exists behind this API — the param
tree carries just the derived POSIX string (``root.Time.POSIXTimeZone``, which
the existing param-backed TimeFacet already tracks AND can param-revert). To
avoid double-reporting, this facet serializes ONLY what params can't express:
the IANA zone + the DHCP-timezone switch.

NOTE ``time:getTime`` is the live CLOCK (changes every second) — never
serialized. The config surface is ``getTimezone``/``setTimezone``.

Live getTimezone shape (Q3538, AXIS OS 12): {activeTimeZone, dhcp: {enabled,
timeZone}, iana: {timeZone, posixTimeZone}, posix: {dstEnabled, timeZone}}.
setTimezone = PATCH /timeZone/iana/timeZone with body {"data": "<zone>"}
(the leaf setter — parent entities 405 "Set operation is not defined").
"""

from typing import Any, Dict, List

from admz.snapshot.facets.base import (
    DeviceCriteria,
    FacetAdapter,
    ReadSpec,
    register_facet,
)


@register_facet
class TimeApiFacet(FacetAdapter):
    NAME = "time_api"

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def applies_to(self) -> List[DeviceCriteria]:
        # time v2 config-rest API — atlas _api.yaml says fw >= 11.8.
        return [DeviceCriteria(families=["vapix"], min_firmware="11.8")]

    @property
    def extra_read_ops(self) -> List[ReadSpec]:
        return [ReadSpec(operation_id="time:getTimezone", result_key="timezone")]

    @property
    def write_ops(self) -> List[str]:
        return ["time:setTimezone"]

    @property
    def restore_order(self) -> int:
        return 21  # with time (20) / ntp (22)

    def serialize(self, raw_responses: Dict[str, Any]) -> Dict[str, Any]:
        raw = raw_responses.get("timezone")
        if not isinstance(raw, dict):
            return {}
        out: Dict[str, Any] = {}
        iana = raw.get("iana")
        if isinstance(iana, dict) and iana.get("timeZone") is not None:
            out["iana_timezone"] = iana.get("timeZone")
        dhcp = raw.get("dhcp")
        if isinstance(dhcp, dict) and dhcp.get("enabled") is not None:
            out["dhcp_enabled"] = dhcp.get("enabled")
        return out

    def op_revertable(self, path: str) -> bool:
        # setTimezone writes the IANA zone; the dhcp switch has no dedicated
        # setter in the catalog yet — tracked only.
        return path == "iana_timezone"

    def build_revert_ops(self, drifted, baseline_doc):
        tz = (baseline_doc or {}).get("iana_timezone")
        if not tz:
            return None
        return [{
            "operation_id": "time:setTimezone",
            "params": {"data": str(tz)},
            "description": f"Restore baseline IANA timezone '{tz}'",
        }]

    def deserialize(self, yaml_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        tz = (yaml_doc or {}).get("iana_timezone")
        if not tz:
            return []
        return [{
            "operation_id": "time:setTimezone",
            "params": {"data": str(tz)},
        }]
