import logging
import time
from typing import Any, Dict, List, Optional

from admz.snapshot.facets import get_facets_for_device
from admz.snapshot.flatten import flatten as _flatten
from admz.snapshot.git_repo import GitRepo
from admz.snapshot.models import (
    FACET_FAILED,
    FACET_OK,
    FACET_SKIPPED,
    DriftField,
    DriftReport,
    FacetResult,
)

logger = logging.getLogger(__name__)


class DriftDetector:
    """Compares live device state against the device's blessed baseline.

    Every check also records what it *observed* into the git config repo
    (ADR-0031 slice 2): the live config is captured once, written to the
    working tree, and committed with an ``Audit:`` message — commit-on-change,
    so an unchanged device records nothing new. The observation advances the
    device's ``latest_observed_sha`` pointer but NEVER its ``baseline_sha``;
    only an explicit snapshot or accept/promote moves the baseline.
    """

    def __init__(self, snapshot_engine, git_repo: GitRepo, demo_store=None):
        self.engine = snapshot_engine
        self.git = git_repo
        # ADR-0047: source of active demos for fragment attribution. Optional
        # so direct constructions (tests, tools) skip attribution entirely.
        self.demo_store = demo_store

    async def check_drift(
        self,
        device_id: str,
        baseline_sha: Optional[str] = None,
        family: str = "vapix",
    ) -> DriftReport:
        device_info = self.engine.registry.get_device_info(device_id)
        device_info["device_id"] = device_id

        # Drift is measured against the device's blessed baseline commit, not
        # whatever happens to be at git HEAD (ADR-0031). An explicit
        # baseline_sha overrides; otherwise use the device's stored pointer.
        if baseline_sha is None:
            baseline_sha = device_info.get("baseline_sha")

        # Readability gate: if the live device can't be read (auth failure /
        # unreachable), a field-by-field compare would mark EVERY baselined
        # field as "removed" (false drift) and record an empty audit. Report
        # 'couldn't read' instead — before probing or recording anything.
        try:
            ok, reason = await self.engine.probe_readable(
                device_id, device_info, family
            )
        except Exception:  # noqa: BLE001 - engine without a usable probe -> don't block
            ok, reason = True, ""
        if not ok:
            return DriftReport(
                device_id=device_id, has_drift=False,
                unreadable=True, unreadable_reason=reason,
            )

        # Probe the device ONCE and record the observation. Best-effort: if
        # capture/commit fails (e.g. an engine without a git repo), drift
        # detection still proceeds via a direct probe below.
        snapshot = None
        observed_sha: Optional[str] = None
        try:
            snapshot = await self.engine._snapshot_device_no_commit(
                device_id, family
            )
            sha = self.engine.git.commit_snapshot(
                device_id, message=f"Audit: {device_id}", auto_push=False
            )
            head = sha or self.engine.git.head_sha()
            if isinstance(head, str) and head:
                observed_sha = head
                self._record_observation_pointers(device_id, observed_sha)
        except Exception as exc:
            logger.warning(
                "audit observation not recorded for %s: %s", device_id, exc
            )

        if not baseline_sha:
            # Nothing blessed to compare against — say so explicitly rather
            # than silently reporting "no drift" (which would imply in-sync).
            # The observation above was still recorded, so this state is
            # promotable to a baseline later. The facet statuses ride along
            # (ADR-0063): "skipped as unsupported" is knowledge about the
            # device whether or not a baseline exists yet.
            return DriftReport(
                device_id=device_id,
                has_drift=False,
                no_baseline=True,
                observed_sha=observed_sha,
                facet_status=(
                    {f.name: f.status for f in snapshot.facets}
                    if snapshot is not None else {}
                ),
            )

        # The live state per facet: from the captured observation when we
        # have one (no second probe), else a direct read. Only a facet whose
        # every read succeeded (``status == ok``) takes part in the compare —
        # a ``failed`` facet's live state is unknown, not empty, and a
        # ``skipped`` one the device is known to lack (ADR-0063).
        if snapshot is not None:
            facet_results = snapshot.facets
            # The engine's copy of device_info carries the firmware it just
            # lifted from the dump; select facets against that.
            device_info = snapshot.device_info or device_info
        else:
            facet_results = await self._probe_facets(
                device_id, device_info, family
            )
        live_by_facet = {
            f.name: (f.normalized or {})
            for f in facet_results
            if f.status == FACET_OK
        }
        facet_status = {f.name: f.status for f in facet_results}

        report = DriftReport(
            device_id=device_id, has_drift=False, observed_sha=observed_sha,
            baseline_sha=baseline_sha, facet_status=facet_status,
        )

        # Operator ignore list, scoped to this device. Applied to BOTH sides of
        # the compare so an excluded field vanishes from drift immediately, even
        # if an older baseline still holds it (no forced re-baseline).
        from admz.snapshot.ignore import applicable_rules, is_ignored
        ignore_rules = applicable_rules(device_id, device_info.get("tags"))
        facets_by_name = {
            f.name: f for f in get_facets_for_device(device_info)
        }

        # ADR-0047: demo-fragment attribution. Keys an ACTIVE demo owns are
        # part of this device's *expected* state; keys matching an INACTIVE
        # demo's fragment get a "looks like demo Y" annotation. Devices held
        # by a legacy scenario keep ADR-0044 semantics untouched (partition
        # rule — the in_scenario supersede already covers them).
        owned: Dict[Any, Any] = {}
        candidates_map: Dict[Any, Any] = {}
        if self.demo_store is not None and not device_info.get("active_scenario"):
            try:
                from admz.demos.fragments import attribution_maps
                owned, candidates_map = attribution_maps(
                    self.git, self.demo_store.list(), device_id, device_info)
            except Exception:  # noqa: BLE001 — attribution must never break drift
                logger.warning(
                    "demo attribution unavailable for %s", device_id,
                    exc_info=True)

        for facet_name in sorted(live_by_facet):
            stored = self.git.read_facet(device_id, facet_name, baseline_sha)
            if stored is None:
                continue

            report.facets_checked += 1

            facet = facets_by_name.get(facet_name)

            # Order-only canonicalisation (#228), applied to BOTH sides for the
            # same reason the ignore list is: a baseline captured before the
            # normalisation shipped must clear on the next computation, with no
            # forced re-baseline. Best-effort — a facet's normaliser must never
            # be able to break drift detection.
            stored_doc = stored
            live_doc = live_by_facet[facet_name]
            if facet is not None:
                try:
                    stored_doc = facet.normalize_doc(stored_doc)
                    live_doc = facet.normalize_doc(live_doc)
                except Exception:  # noqa: BLE001
                    logger.warning(
                        "normalize_doc failed for facet %s on %s; comparing raw",
                        facet_name, device_id, exc_info=True)
                    stored_doc, live_doc = stored, live_by_facet[facet_name]

            stored_flat = _flatten(stored_doc)
            live_flat = _flatten(live_doc)

            if ignore_rules and facet is not None:
                stored_flat = {
                    k: v for k, v in stored_flat.items()
                    if not is_ignored(facet.canonical_key(k), rules=ignore_rules)
                }
                live_flat = {
                    k: v for k, v in live_flat.items()
                    if not is_ignored(facet.canonical_key(k), rules=ignore_rules)
                }

            all_keys = set(stored_flat.keys()) | set(live_flat.keys())
            # Keys an active demo owns take part in expected state even when
            # base and live agree elsewhere (a not-yet-loaded fragment key
            # must surface as drift AGAINST the demo).
            all_keys |= {k[1] for k in owned if k[0] == facet_name}
            facet_drifted = False

            for key in sorted(all_keys):
                base_val = stored_flat.get(key, "<missing>")
                actual = live_flat.get(key, "<missing>")
                own = owned.get((facet_name, key))
                canonical = facet.canonical_key(key) if facet else None

                if own is not None:
                    # An ignore rule added AFTER capture strips the key from
                    # both sides above — attributing the resulting "<missing>"
                    # would false-flag the demo as broken. Ignored = invisible,
                    # for demos too.
                    if (ignore_rules and canonical
                            and is_ignored(canonical, rules=ignore_rules)):
                        continue
                    want, demo_id, demo_name = own
                    if actual == want:
                        if base_val != actual:
                            # Deliberate: the active demo set this. Recorded
                            # for display, NOT counted as drift.
                            report.fields.append(DriftField(
                                facet=facet_name, path=key,
                                expected=base_val, actual=actual,
                                canonical_key=canonical,
                                bucket="demo_set",
                                owner=demo_id, owner_name=demo_name,
                                base_value=base_val,
                            ))
                        continue  # matches base AND demo → nothing at all
                    # Owned but wrong: the DEMO is broken. expected = the
                    # demo's value, so a targeted revert repairs the demo.
                    report.fields.append(DriftField(
                        facet=facet_name, path=key,
                        expected=want, actual=actual,
                        canonical_key=canonical,
                        bucket="demo_broken",
                        owner=demo_id, owner_name=demo_name,
                        base_value=base_val,
                    ))
                    facet_drifted = True
                    continue

                if base_val != actual:
                    cands = [
                        {"id": c["id"], "name": c["name"]}
                        for c in candidates_map.get((facet_name, key), [])
                        if c.get("value") == actual
                    ]
                    report.fields.append(DriftField(
                        facet=facet_name, path=key,
                        expected=base_val, actual=actual,
                        canonical_key=canonical,
                        bucket="candidate" if cands else "unclaimed",
                        candidates=cands,
                    ))
                    facet_drifted = True

            if facet_drifted:
                report.facets_drifted += 1
                report.has_drift = True

        # ADR-0063 (FR-DRF-013): visit the BASELINE's facets too. A facet
        # the live read did not produce used to vanish from the compare; it
        # is one of two very different things:
        #   skipped  — the device is known to lack the API. That IS drift: a
        #              baselined facet the device no longer answers for. It is
        #              reported honestly and counted — but carries no
        #              DriftField, because the revert builder must never write
        #              to an API the device does not have.
        #   failed   — the read was attempted and did not succeed. The live
        #              state is UNKNOWN, which is not drift. (Before this, a
        #              transient API failure read every stored key as
        #              "<missing>" and reported the whole facet drifted.)
        # A baseline facet that simply no longer applies to the device (not
        # in the live read at all) stays as it was: not visited.
        try:
            baseline_facets = self.git.list_facets_at(device_id, baseline_sha)
        except Exception:  # noqa: BLE001 — a stub repo without the method
            baseline_facets = []
        for facet_name in baseline_facets:
            if facet_name in live_by_facet:
                continue
            status = facet_status.get(facet_name)
            if status == FACET_SKIPPED:
                report.facets_absent.append(facet_name)
                report.facets_checked += 1
                report.facets_drifted += 1
                report.has_drift = True
            elif status == FACET_FAILED:
                report.facets_unverified.append(facet_name)

        # Phase 8: hand the report to the alert store so transitions
        # (sync→drifted, drift-set-changed, drifted→sync) get
        # recorded for ``list_drift_alerts``. Best-effort — a store
        # failure must never mask the report from the caller. The
        # transition (if any) rides on the report so callers (e.g. the
        # drift_audit scheduler job) can count alerts without
        # re-processing — a second process_report sees "no change".
        try:
            import admz.snapshot.drift_alerts as _alerts_module
            alert = _alerts_module.drift_alerts.process_report(report)
            if alert is not None:
                report.alert_transition = alert.transition
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning(
                "DriftDetector: alert store failed for %s: %s",
                device_id,
                exc,
            )

        return report

    async def _probe_facets(
        self, device_id: str, device_info: Dict[str, Any], family: str
    ) -> List[FacetResult]:
        """Direct live read — the fallback when the observation capture itself
        raised (a git write failure; a stubbed test engine). Composed from the
        two read primitives every stub provides, so a mocked engine keeps
        working; a facet whose serialization fails reports ``failed`` (its
        live state is unknown) instead of silently vanishing from the compare.
        """
        facets = get_facets_for_device(device_info)
        raw_params = await self.engine._read_all_params(
            device_id, device_info, family
        )
        extra_results = await self.engine._read_extra_ops(
            device_id, device_info, facets, family
        )
        raw_responses = {"params": raw_params}
        raw_responses.update(extra_results)

        results: List[FacetResult] = []
        for facet in facets:
            try:
                results.append(FacetResult(
                    name=facet.name, success=True,
                    normalized=facet.serialize(raw_responses),
                ))
            except Exception as e:
                logger.warning(
                    "Failed to serialize facet %s for drift check: %s",
                    facet.name,
                    e,
                )
                results.append(FacetResult(
                    name=facet.name, success=False, error=str(e),
                ))
        return results

    def _record_observation_pointers(self, device_id: str, sha: str) -> None:
        """Advance the observed pointer — NEVER the baseline. Best-effort:
        a backend without pointer support (the stubbed Vault, H-4) is a
        no-op rather than a failed audit."""
        try:
            self.engine.registry.set_config_pointers(
                device_id,
                latest_observed_sha=sha,
                last_observed_at=time.time(),
            )
        except NotImplementedError:
            pass
        except Exception:  # pragma: no cover — best effort
            logger.debug(
                "could not record observation pointer for %s",
                device_id,
                exc_info=True,
            )

    async def check_fleet_drift(
        self,
        device_ids: Optional[List[str]] = None,
        tag_filter: Optional[str] = None,
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
                report = await self.check_drift(did, family=family)
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
