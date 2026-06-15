"""Catch-all facet: captures every param.cgi key not owned by another facet.

ADMZ already reads the whole ``param.cgi?action=list&group=root`` tree on every
snapshot/drift, but only params under a *claimed* prefix are kept — so config a
named facet doesn't cover (audio gain, PTZ, recording, syslog, SIP, …) was
fetched and silently dropped, and drift never noticed changes to it.

This facet keeps the complement: every param NOT under any other facet's
prefix, stored under its full ``root.*`` key so the bucket is self-describing.
It's the **discovery surface** — read what lands here on a real device and
promote prefixes into named category facets (audio, ptz, …) over time, which
shrinks this bucket. It is **read-only** for restore: uncategorized params are
never blind-written back (no curated RESTORE_EXCLUDE yet), but drift on them is
fully observed.
"""

from typing import Any, Dict, List

from admz.snapshot.facets.base import (
    DeviceCriteria,
    FacetAdapter,
    claimed_prefixes,
    is_restorable,
    register_facet,
)


@register_facet
class CatchAllParamsFacet(FacetAdapter):
    NAME = "other"

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def applies_to(self) -> List[DeviceCriteria]:
        return [DeviceCriteria(families=["vapix"])]

    @property
    def write_ops(self) -> List[str]:
        return []

    @property
    def restore_order(self) -> int:
        # Late, though it's read-only anyway.
        return 95

    # No param_prefixes — it owns the *complement*, computed at serialize time
    # from every other facet's prefixes.

    def serialize(self, raw_responses: Dict[str, Any]) -> Dict[str, Any]:
        params = raw_responses.get("params", {})
        owned = claimed_prefixes(exclude=self.NAME)
        result: Dict[str, str] = {}
        for key, value in sorted(params.items()):
            if not any(key.startswith(p) for p in owned):
                # Full root.* key — the bucket is self-describing for triage.
                result[key] = value
        return result

    def deserialize(self, yaml_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Read-only for FULL-facet restore: never blind-restore the whole
        # uncategorized bucket (hundreds of unknown keys, some structural).
        # Single-field TARGETED revert is a different, much narrower risk and
        # IS allowed — see revert_param.
        return []

    def revert_param(self, path: str, baseline_value: Any):
        # The catch-all stores params under their FULL ``root.*`` key, so
        # ``path`` is already the param.cgi key (no PREFIX to re-add).
        #
        # Full-facet restore stays disabled (deserialize -> []), but a
        # *targeted* revert of one drifted field is safe to allow here: we
        # write a single, known prior value for a key that demonstrably
        # drifted from a blessed baseline — not a blind bulk re-push. A key
        # that can't actually take the write (read-only/structural) fails
        # loudly at plan execution (on_failure=stop), never silently.
        if not is_restorable(path, baseline_value):
            return None
        # Defense in depth: the engine already drops secret params at capture
        # (so the baseline shouldn't carry them), but never write a value back
        # for a secret-class key even if a legacy baseline holds one. Reuse the
        # engine's authoritative predicate (SENSITIVE_PREFIXES + redaction key
        # matcher + SNMP/WPA/PSK substrings); lazy import avoids the
        # facets<->engine import cycle.
        from admz.snapshot.engine import _is_sensitive
        if _is_sensitive(path):
            return None
        return (path, str(baseline_value))
