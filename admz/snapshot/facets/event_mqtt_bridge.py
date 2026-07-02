"""MQTT event-bridge configuration via ``event-mqtt-bridge`` (config-rest,
v2beta) — what the device publishes/subscribes on the MQTT event bridge.

Live shape (Q3538): ``{deviceTopicPrefix, publication: {appendEventTopic,
customTopicPrefix, eventFilter[], includeSerialNumberInPayload,
includeTopicNamespaces, topicPrefix}, subscription: [...]}``.

Serialization notes:
  * ``deviceTopicPrefix`` is DERIVED (carries the serial) — dropped.
  * **Secrets rule (must-keep):** subscription/broker entries can carry
    credentials, and ``extra_read_ops`` data does NOT pass the engine's
    param-level secret filter — so this facet censors sensitive keys itself
    (``admz.redact.is_sensitive_key``) before anything reaches YAML/git.
  * ``publication.eventFilter`` (a list of filter dicts) is serialized as a
    stable JSON string — flatten() stringifies lists non-deterministically
    otherwise.

Revert v1: the ``publication`` object reverts via ``updatePublication``
(whole-object write from baseline). ``subscription`` entries are TRACKED but
not auto-reverted (a collection with per-entry credentials — deferred).
"""

import json
from typing import Any, Dict, List

from admz.redact import is_sensitive_key
from admz.snapshot.facets.base import (
    DeviceCriteria,
    FacetAdapter,
    ReadSpec,
    register_facet,
)


def _censor(obj: Any) -> Any:
    """Recursively drop secret-class keys (never committed to git)."""
    if isinstance(obj, dict):
        return {k: _censor(v) for k, v in obj.items() if not is_sensitive_key(k)}
    if isinstance(obj, list):
        return [_censor(v) for v in obj]
    return obj


@register_facet
class MqttBridgeFacet(FacetAdapter):
    NAME = "event_mqtt_bridge"

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def applies_to(self) -> List[DeviceCriteria]:
        return [DeviceCriteria(families=["vapix"], min_firmware="12")]

    @property
    def extra_read_ops(self) -> List[ReadSpec]:
        return [ReadSpec(
            operation_id="event-mqtt-bridge:getConfig",
            result_key="event_mqtt_bridge",
        )]

    @property
    def write_ops(self) -> List[str]:
        return ["event-mqtt-bridge:updatePublication"]

    @property
    def restore_order(self) -> int:
        return 68

    def serialize(self, raw_responses: Dict[str, Any]) -> Dict[str, Any]:
        raw = raw_responses.get("event_mqtt_bridge")
        if not isinstance(raw, dict):
            return {}
        out: Dict[str, Any] = {}
        pub = raw.get("publication")
        if isinstance(pub, dict):
            pub = _censor(pub)
            # Stable scalar form for the filter list (order-preserving JSON).
            if isinstance(pub.get("eventFilter"), list):
                pub["eventFilter"] = json.dumps(
                    pub["eventFilter"], sort_keys=True, separators=(",", ":"))
            out["publication"] = pub
        subs = raw.get("subscription")
        if isinstance(subs, list):
            # Tracked (secrets censored), keyed by index-stable JSON string.
            out["subscription"] = json.dumps(
                _censor(subs), sort_keys=True, separators=(",", ":"))
        return out

    def _publication_params(self, baseline_doc: Dict[str, Any]):
        pub = baseline_doc.get("publication")
        if not isinstance(pub, dict):
            return None
        data = dict(pub)
        ef = data.get("eventFilter")
        if isinstance(ef, str):
            try:
                data["eventFilter"] = json.loads(ef)
            except (ValueError, TypeError):
                data.pop("eventFilter", None)
        return {"data": data}

    def op_revertable(self, path: str) -> bool:
        return path.startswith("publication.") or path == "publication"

    def build_revert_ops(self, drifted, baseline_doc):
        params = self._publication_params(baseline_doc)
        if params is None:
            return None
        fields = ", ".join(sorted(p for p, *_ in drifted)) or "publication"
        return [{
            "operation_id": "event-mqtt-bridge:updatePublication",
            "params": params,
            "description": f"Restore baseline MQTT publication config ({fields})",
        }]

    def deserialize(self, yaml_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        params = self._publication_params(yaml_doc or {})
        if params is None:
            return []
        return [{
            "operation_id": "event-mqtt-bridge:updatePublication",
            "params": params,
        }]
