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
        # Read-only: never blind-restore uncategorized params.
        return []
