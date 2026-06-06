"""
Survey collector -- per-device, read-only API discovery.

Wraps the atlas refresh tool (``build_snapshot``) plus an OpenAPI-spec fetch,
diffs against the installed atlas, and redacts. The result feeds
:mod:`admz.survey.bundle`.

The collector is **read-only**: it issues GET / DCA / OpenAPI reads only. It is
also dependency-injected (``snapshot_fn`` / ``spec_fetcher``) so the orchestration
and diff/redact path are unit-testable without a live device; production wiring
uses the real atlas tool + an httpx client.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from admz.ssl_config import verify_ssl_default
from admz.survey import secrets
from admz.survey.bundle import DeviceSurvey
from admz.survey.diff import AtlasIndex, diff_snapshot
from admz.survey.redact import is_safe_openapi, redact_snapshot

logger = logging.getLogger(__name__)

# build_snapshot(host, user, password, verify=, auth=) -> snapshot dict
SnapshotFn = Callable[..., Dict]
# spec_fetcher(host, user, password, verify, openapi_path) -> spec dict | None
SpecFetcher = Callable[..., Optional[Dict]]


@dataclass
class CollectResult:
    surveys: List[DeviceSurvey] = field(default_factory=list)
    skipped: Dict[str, str] = field(default_factory=dict)   # device_id -> reason
    errors: Dict[str, str] = field(default_factory=dict)    # device_id -> error


def _default_snapshot_fn() -> SnapshotFn:
    from axis_api_atlas.tools.refresh_capabilities import build_snapshot
    return build_snapshot


def _default_spec_fetcher() -> SpecFetcher:
    import httpx

    def fetch(host: str, user: str, password: str, verify: bool, path: str) -> Optional[Dict]:
        # host already includes scheme; auth: try basic (Axis over HTTPS), then digest
        for auth in (httpx.BasicAuth(user, password), httpx.DigestAuth(user, password)):
            try:
                with httpx.Client(verify=verify, timeout=30, auth=auth) as c:
                    r = c.get(f"{host}{path}")
                    if r.status_code == 200:
                        return r.json()
            except Exception:  # noqa: BLE001
                continue
        return None

    return fetch


class SurveyCollector:
    def __init__(
        self,
        registry,
        *,
        index: Optional[AtlasIndex] = None,
        snapshot_fn: Optional[SnapshotFn] = None,
        spec_fetcher: Optional[SpecFetcher] = None,
        profile: Optional[str] = None,
        validate: bool = False,
        validation_tier: int = 0,
        validation_pace: float = 0.25,
        write_back_ops: Optional[List[str]] = None,
    ):
        self.registry = registry
        self.index = index or AtlasIndex()
        self.snapshot_fn = snapshot_fn or _default_snapshot_fn()
        self.spec_fetcher = spec_fetcher or _default_spec_fetcher()
        self.profile = profile or secrets.get_redaction_profile()
        self.validate = validate
        self.validation_tier = validation_tier
        self.validation_pace = validation_pace
        self.write_back_ops = list(write_back_ops or ())
        self._key = secrets.hmac_key()

    # -- single device -------------------------------------------------------
    def survey_device(self, device_id: str) -> Optional[DeviceSurvey]:
        creds = self.registry.get_credentials(device_id, requester="survey-mode")
        host = creds.get("host") or ""
        user = creds.get("username") or ""
        password = creds.get("password") or ""
        if not host.startswith("http"):
            host = f"https://{host}"
        verify = verify_ssl_default()

        snapshot = self.snapshot_fn(host, user, password, verify=verify, auth="auto")
        model = snapshot.get("model") or self._model_from_registry(device_id)
        if not model:
            raise ValueError("could not determine model")

        delta = diff_snapshot(snapshot, model=model, index=self.index)

        # validation (read-only Tier 0; Tier 1 only on lab-tagged devices) over the
        # device's *cataloged* APIs -- evidence for cataloged-but-untested ops.
        validation = self._validate(device_id, host, user, password, verify, snapshot)

        if delta.is_empty and not validation:
            return None  # nothing new and no validation evidence -> no contribution

        # fetch OpenAPI specs for uncatalogued REST APIs only (schema docs, never model.json)
        specs: Dict[str, Dict] = {}
        detail = snapshot.get("apis_detail", {})
        for api_id in delta.uncatalogued_apis:
            d = detail.get(api_id, {})
            dca = d.get("dca") if isinstance(d, dict) else None
            if not dca:
                continue  # legacy CGI; needs the validation/probe path, not OpenAPI
            spec_path = dca.get("openapi")
            if not spec_path or not is_safe_openapi(api_id, spec_path):
                continue
            spec = self.spec_fetcher(host, user, password, verify, spec_path)
            if spec:
                specs[api_id] = {
                    "spec": spec,
                    "base_path": dca.get("rest_api", f"/config/rest/{api_id}"),
                    "version": dca.get("major", "v1"),
                    "state": dca.get("state", "beta"),
                }

        return DeviceSurvey(
            model=model,
            redacted_snapshot=redact_snapshot(snapshot, profile=self.profile, key=self._key),
            new_model=delta.new_model,
            new_firmware=delta.new_firmware,
            uncatalogued_apis=delta.uncatalogued_apis,
            openapi_specs=specs,
            validation=validation,
        )

    def _validate(self, device_id, host, user, password, verify, snapshot) -> list:
        if not self.validate:
            return []
        from admz.survey.redact import redact_validation_result
        from admz.survey.validate import (
            ValidationRunner,
            is_lab_device,
            load_ops_for_apis,
            run_validation,
        )

        api_ids = list(snapshot.get("apis", {}))
        ops = load_ops_for_apis(api_ids)
        if not ops:
            return []
        lab = False
        if self.validation_tier >= 1:
            try:
                lab = is_lab_device(self.registry.get_device_info(device_id))
            except Exception:  # noqa: BLE001
                lab = False
        runner = ValidationRunner(host, user, password, verify=verify)
        raw = run_validation(runner, ops, tier=self.validation_tier, lab=lab,
                             write_back_ops=self.write_back_ops,
                             pace_seconds=self.validation_pace)
        return [redact_validation_result(r) for r in raw]

    def _model_from_registry(self, device_id: str) -> str:
        try:
            return self.registry.get_device_info(device_id).get("model") or ""
        except Exception:  # noqa: BLE001
            return ""

    # -- fleet ---------------------------------------------------------------
    def survey_fleet(self, device_ids: Optional[List[str]] = None) -> CollectResult:
        result = CollectResult()
        if device_ids is None:
            device_ids = [d.get("device_id") for d in self.registry.list_devices()]
        for did in device_ids:
            if not did:
                continue
            try:
                survey = self.survey_device(did)
                if survey is None:
                    result.skipped[did] = "nothing new vs installed atlas"
                else:
                    result.surveys.append(survey)
            except Exception as exc:  # noqa: BLE001 - one device shouldn't sink the run
                logger.warning("survey failed for %s: %s", did, exc)
                result.errors[did] = str(exc)
        return result
