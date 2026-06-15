"""Applications facet — installed ACAP apps and their run-state.

Reads the VAPIX applications list (``applications-list.cgi:list``) through the
``extra_read_ops`` seam — NOT param.cgi. Each app's running state, version,
license, and signature are captured so drift flags:

  * an app **Stopped that should be Running** (or vice-versa) — Axis devices
    persist a respawn app's started/stopped state across reboot, so ``Status``
    is the effective "will it run on boot" signal (there is no separate
    auto-start toggle in VAPIX),
  * an app **installed / removed** (the app key appears / disappears),
  * a **version** change (upgrade / downgrade) or **license** change.

Read-only for restore: run-state IS revertable via ``applications-control.cgi``
(start/stop), but that's a service-affecting write deferred to a follow-up —
drift only observes it for now (same posture the action-rules facet started
with). App *settings* (``root.<App>.*`` params) are captured separately by the
param facets / catch-all.
"""

from typing import Any, Dict, List

from admz.snapshot.facets.base import (
    DeviceCriteria,
    FacetAdapter,
    ReadSpec,
    register_facet,
)


def _extract_apps(payload: Any) -> List[Dict[str, Any]]:
    """Pull the <application> entries out of the parsed list.cgi reply.

    XML→dict gives ``{"@result": "ok", "application": [ {...}, ... ]}`` — but a
    single installed app collapses ``application`` to one dict, and attributes
    arrive ``@Name``-prefixed. Defensive about both shapes (and a bare list)."""
    if isinstance(payload, list):
        return [a for a in payload if isinstance(a, dict)]
    if isinstance(payload, dict):
        apps = payload.get("application")
        if isinstance(apps, dict):
            return [apps]
        if isinstance(apps, list):
            return [a for a in apps if isinstance(a, dict)]
    return []


def _attr(app: Dict[str, Any], name: str) -> str:
    """Read an attribute whether the XML parser kept the ``@`` prefix or not."""
    val = app.get("@" + name, app.get(name, ""))
    return "" if val is None else str(val)


@register_facet
class ApplicationsFacet(FacetAdapter):
    NAME = "applications"

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def applies_to(self) -> List[DeviceCriteria]:
        # All VAPIX devices; on a product without ACAP the op just fails and
        # the engine yields an empty facet (graceful — no harm).
        return [DeviceCriteria(families=["vapix"])]

    @property
    def extra_read_ops(self) -> List[ReadSpec]:
        return [
            ReadSpec(
                operation_id="applications-list.cgi:list",
                result_key="applications",
            )
        ]

    @property
    def write_ops(self) -> List[str]:
        return []

    @property
    def restore_order(self) -> int:
        return 75

    def serialize(self, raw_responses: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for app in _extract_apps(raw_responses.get("applications")):
            name = _attr(app, "Name")
            if not name:
                continue
            result[name] = {
                "status": _attr(app, "Status"),
                "version": _attr(app, "Version"),
                "license": _attr(app, "License"),
                "signature": _attr(app, "SignatureStatus"),
            }
        return result

    def deserialize(self, yaml_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Read-only: starting/stopping an app is a control.cgi write, deferred.
        return []
