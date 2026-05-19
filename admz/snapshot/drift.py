import logging
from typing import Any, Dict, List, Optional

from admz.snapshot.facets import get_facets_for_device
from admz.snapshot.git_repo import GitRepo
from admz.snapshot.models import DriftField, DriftReport

logger = logging.getLogger(__name__)


def _flatten(d: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
    items = {}
    for k, v in d.items():
        full_key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            items.update(_flatten(v, full_key))
        else:
            items[full_key] = str(v)
    return items


class DriftDetector:
    """Compares live device state against what's stored in git."""

    def __init__(self, snapshot_engine, git_repo: GitRepo):
        self.engine = snapshot_engine
        self.git = git_repo

    async def check_drift(
        self,
        device_id: str,
        ref: str = "HEAD",
        family: str = "vapix",
    ) -> DriftReport:
        device_info = self.engine.registry.get_device_info(device_id)
        device_info["device_id"] = device_id

        facets = get_facets_for_device(device_info)

        raw_params = await self.engine._read_all_params(
            device_id, device_info, family
        )
        extra_results = await self.engine._read_extra_ops(
            device_id, device_info, facets, family
        )

        report = DriftReport(device_id=device_id, has_drift=False)

        for facet in facets:
            stored = self.git.read_facet(device_id, facet.name, ref)
            if stored is None:
                continue

            report.facets_checked += 1

            raw_responses = {"params": raw_params}
            raw_responses.update(extra_results)
            try:
                live = facet.serialize(raw_responses)
            except Exception as e:
                logger.warning(
                    "Failed to serialize facet %s for drift check: %s",
                    facet.name,
                    e,
                )
                continue

            stored_flat = _flatten(stored)
            live_flat = _flatten(live)

            all_keys = set(stored_flat.keys()) | set(live_flat.keys())
            facet_drifted = False

            for key in sorted(all_keys):
                expected = stored_flat.get(key, "<missing>")
                actual = live_flat.get(key, "<missing>")
                if expected != actual:
                    report.fields.append(
                        DriftField(
                            facet=facet.name,
                            path=key,
                            expected=expected,
                            actual=actual,
                        )
                    )
                    facet_drifted = True

            if facet_drifted:
                report.facets_drifted += 1
                report.has_drift = True

        # Phase 8: hand the report to the alert store so transitions
        # (sync→drifted, drift-set-changed, drifted→sync) get
        # recorded for ``list_drift_alerts``. Best-effort — a store
        # failure must never mask the report from the caller.
        try:
            import admz.snapshot.drift_alerts as _alerts_module
            _alerts_module.drift_alerts.process_report(report)
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "DriftDetector: alert store failed for %s: %s",
                device_id,
                exc,
            )

        return report

    async def check_fleet_drift(
        self,
        device_ids: Optional[List[str]] = None,
        tag_filter: Optional[str] = None,
        ref: str = "HEAD",
        family: str = "vapix",
    ) -> List[DriftReport]:
        if device_ids is None:
            all_devices = self.engine.registry.list_devices()
            if tag_filter:
                device_ids = [
                    d.get("device_id", d.get("id", ""))
                    for d in all_devices
                    if tag_filter in d.get("tags", [])
                ]
            else:
                device_ids = [
                    d.get("device_id", d.get("id", ""))
                    for d in all_devices
                ]

        reports = []
        for did in device_ids:
            try:
                report = await self.check_drift(did, ref, family)
                reports.append(report)
            except Exception as e:
                logger.exception("Drift check failed for %s", did)
                report = DriftReport(device_id=did, has_drift=False)
                report.fields.append(
                    DriftField(
                        facet="__error__",
                        path="",
                        expected="",
                        actual=str(e),
                    )
                )
                reports.append(report)

        return reports
