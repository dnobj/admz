"""SIP configuration via the VAPIX Call service API (``/vapix/call``,
apiDiscovery id ``sip``) — speakers, intercoms, door stations.

SIP has NO param.cgi presence (only ``Properties.API.SIP.*`` capability
flags), so this facet is the only way ADMZ tracks it. Reads
``sip:getSIPConfiguration`` (the global SIP config object) and
``sip:getSIPAccounts`` (account list).

Secrets rule (must-keep): ``GetSIPAccounts`` returns each account's SIP
``Password`` in PLAINTEXT, and ``extra_read_ops`` data does not pass the
engine's param-level secret filter — serialization censors secret keys
recursively before anything reaches YAML/git.

Revert: the ``SIPConfiguration`` object reverts whole-object via
``sip:setSIPConfiguration`` (no secrets in it). Accounts are TRACKED but not
auto-reverted (a credential-bearing collection — writing a baseline account
without its censored password could break registration; same posture as the
MQTT subscription list).

Live shapes captured 2026-06-22 on a C1710 (API version 2.2); devices without
the API (cameras) fail the read gracefully and serialize empty.
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
    if isinstance(obj, dict):
        return {k: _censor(v) for k, v in obj.items() if not is_sensitive_key(k)}
    if isinstance(obj, list):
        return [_censor(v) for v in obj]
    return obj


def _stabilize(d: Dict[str, Any]) -> Dict[str, Any]:
    """Lists → sorted JSON strings so flatten() stays deterministic."""
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, list):
            out[k] = json.dumps(v, sort_keys=True, separators=(",", ":"))
        else:
            out[k] = v
    return out


@register_facet
class SipFacet(FacetAdapter):
    NAME = "sip"

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def applies_to(self) -> List[DeviceCriteria]:
        # Capability (Properties.API.SIP) isn't expressible in DeviceCriteria;
        # non-SIP devices 404 the read and serialize empty (graceful).
        return [DeviceCriteria(families=["vapix"])]

    @property
    def extra_read_ops(self) -> List[ReadSpec]:
        return [
            ReadSpec(operation_id="sip:getSIPConfiguration", result_key="sip_config"),
            ReadSpec(operation_id="sip:getSIPAccounts", result_key="sip_accounts"),
        ]

    @property
    def write_ops(self) -> List[str]:
        return ["sip:setSIPConfiguration"]

    @property
    def restore_order(self) -> int:
        return 55

    def serialize(self, raw_responses: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        cfg = raw_responses.get("sip_config")
        if isinstance(cfg, dict):
            conf = cfg.get("SIPConfiguration")
            if isinstance(conf, dict):
                out["config"] = _stabilize(_censor(conf))
        accts = raw_responses.get("sip_accounts")
        if isinstance(accts, dict):
            entries = accts.get("SIPAccount")
            if isinstance(entries, list):
                acc_out: Dict[str, Any] = {}
                for i, a in enumerate(entries):
                    if not isinstance(a, dict):
                        continue
                    aid = str(a.get("Id") or i)
                    acc_out[aid] = _stabilize(_censor(a))
                out["accounts"] = acc_out
        return out

    def _config_params(self, baseline_doc: Dict[str, Any]):
        conf = (baseline_doc or {}).get("config")
        if not isinstance(conf, dict):
            return None
        data = {}
        for k, v in conf.items():
            if isinstance(v, str) and v.startswith(("[", "{")):
                try:
                    data[k] = json.loads(v)
                    continue
                except (ValueError, TypeError):
                    pass
            data[k] = v
        return {"SIPConfiguration": data}

    def op_revertable(self, path: str) -> bool:
        return path.startswith("config.") or path == "config"

    def build_revert_ops(self, drifted, baseline_doc):
        params = self._config_params(baseline_doc)
        if params is None:
            return None
        fields = ", ".join(sorted(p for p, *_ in drifted)) or "config"
        return [{
            "operation_id": "sip:setSIPConfiguration",
            "params": params,
            "description": f"Restore baseline SIP configuration ({fields})",
        }]

    def deserialize(self, yaml_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        params = self._config_params(yaml_doc or {})
        if params is None:
            return []
        return [{
            "operation_id": "sip:setSIPConfiguration",
            "params": params,
        }]
