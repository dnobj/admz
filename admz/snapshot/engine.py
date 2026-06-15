import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from axis_api_atlas.catalog.loader import CatalogLoader
from admz.device_registry import DeviceRegistry
from admz.executor.base import BaseExecutor
from admz.snapshot.facets import get_facets_for_device
from admz.snapshot.facets.base import FacetAdapter
from admz.snapshot.git_repo import GitRepo
from admz.snapshot.models import (
    DeviceSnapshot,
    FacetResult,
    SnapshotStatus,
)

logger = logging.getLogger(__name__)


# Maximum number of devices snapshotted concurrently.
# Default 50 is a balanced value for typical Experience Center fleets
# (~6-50 devices) and small enterprise installs (~100-500); higher
# values may exhaust file descriptors or device-side connection limits
# at scale (~1000+ devices over httpx-pooled connections). Override
# with ADMZ_SNAPSHOT_FLEET_CONCURRENCY for unusual deployments.
_DEFAULT_FLEET_CONCURRENCY = 50


def _resolve_fleet_concurrency() -> int:
    """Read ADMZ_SNAPSHOT_FLEET_CONCURRENCY env var.

    Values must parse as a positive integer; anything else falls back
    to the default with a warning so misconfigurations are visible.
    """
    raw = os.getenv("ADMZ_SNAPSHOT_FLEET_CONCURRENCY", "")
    if not raw:
        return _DEFAULT_FLEET_CONCURRENCY
    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "ADMZ_SNAPSHOT_FLEET_CONCURRENCY=%r is not an integer — "
            "falling back to %d",
            raw, _DEFAULT_FLEET_CONCURRENCY,
        )
        return _DEFAULT_FLEET_CONCURRENCY
    if value < 1:
        logger.warning(
            "ADMZ_SNAPSHOT_FLEET_CONCURRENCY=%d is not positive — "
            "falling back to %d",
            value, _DEFAULT_FLEET_CONCURRENCY,
        )
        return _DEFAULT_FLEET_CONCURRENCY
    return value

VOLATILE_PREFIXES = [
    "root.Properties.System.Soc.",
    "root.Properties.Firmware.",
]

SENSITIVE_PREFIXES = [
    "root.HTTPS.PrivateKey",
    "root.Network.Wireless.WPA.",
    "root.RemoteService.",
]

# param.cgi masks password-class values as "******", but some secret params
# come back in PLAINTEXT — SNMP community strings (V1WriteCommunity, …), WPA /
# 802.1x pre-shared keys, passphrases. Comprehensive capture (the catch-all
# facet) would otherwise commit these credentials to the git config repo,
# violating "credentials never committed". Dropped by substring, in addition
# to the shared redaction key matcher (password/secret/token/apikey/key/pat).
_SECRET_PARAM_SUBSTRINGS = (
    "community",
    "passphrase",
    "psk",
    "presharedkey",
    "wpapsk",
    "privatekey",
    "pwd",
)


def _is_volatile(key: str) -> bool:
    return any(key.startswith(p) for p in VOLATILE_PREFIXES)


def _is_sensitive(key: str) -> bool:
    if any(key.startswith(p) for p in SENSITIVE_PREFIXES):
        return True
    from admz import redact
    if redact.is_sensitive_key(key):
        return True
    k = key.lower()
    return any(s in k for s in _SECRET_PARAM_SUBSTRINGS)


def _is_ignored(key: str, patterns) -> bool:
    """Operator-configured ignore list (admz.snapshot.ignore). ``patterns`` is
    precomputed once per dump so this is a cheap per-key check, not a DB hit."""
    from admz.snapshot.ignore import is_ignored
    return is_ignored(key, patterns)


def _parse_param_dump(text: str) -> Dict[str, str]:
    from admz.snapshot.ignore import get_ignore_patterns
    ignore = get_ignore_patterns()  # read once for the whole dump
    params = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            key = key.strip()
            if (
                not _is_volatile(key)
                and not _is_sensitive(key)
                and not _is_ignored(key, ignore)
            ):
                params[key] = value.strip()
    return params


class SnapshotEngine:

    def __init__(
        self,
        catalog: CatalogLoader,
        registry: DeviceRegistry,
        executors: Dict[str, BaseExecutor],
        git_repo: GitRepo,
        fleet_concurrency: Optional[int] = None,
    ):
        self.catalog = catalog
        self.registry = registry
        self.executors = executors
        self.git = git_repo
        self.fleet_concurrency = (
            fleet_concurrency
            if fleet_concurrency is not None
            else _resolve_fleet_concurrency()
        )

    async def snapshot_device(
        self,
        device_id: str,
        message: Optional[str] = None,
        family: str = "vapix",
    ) -> DeviceSnapshot:
        device_info = self.registry.get_device_info(device_id)
        device_info["device_id"] = device_id
        snapshot = DeviceSnapshot(device_id=device_id, device_info=device_info)

        facets = get_facets_for_device(device_info)
        if not facets:
            snapshot.status = SnapshotStatus.COMPLETED
            return snapshot

        raw_params = await self._read_all_params(device_id, device_info, family)

        extra_results = await self._read_extra_ops(
            device_id, device_info, facets, family
        )

        for facet in facets:
            result = self._run_facet(facet, raw_params, extra_results)
            snapshot.facets.append(result)

        self._write_files(device_id, device_info, snapshot)

        sha = self.git.commit_snapshot(device_id, message=message)
        snapshot.git_sha = sha

        # An explicit snapshot blesses the current config as the baseline.
        # Pin to the committed sha, or HEAD when nothing changed (the device
        # is already at its baseline). Only when we actually captured config.
        if snapshot.succeeded_facets:
            self._set_baseline_pointers(device_id, sha or self.git.head_sha())

        if snapshot.failed_facets and snapshot.succeeded_facets:
            snapshot.status = SnapshotStatus.PARTIAL
        elif snapshot.failed_facets:
            snapshot.status = SnapshotStatus.FAILED
        else:
            snapshot.status = SnapshotStatus.COMPLETED

        return snapshot

    async def snapshot_fleet(
        self,
        device_ids: Optional[List[str]] = None,
        tag_filter: Optional[str] = None,
        message: Optional[str] = None,
        family: str = "vapix",
    ) -> List[DeviceSnapshot]:
        if device_ids is None:
            all_devices = self.registry.list_devices()
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

        # Phase 3D: bound the fan-out. At N devices, unbounded asyncio
        # gather opens N concurrent httpx connection pools and N file
        # descriptors — fine at fleet sizes <100, problematic at 1000+
        # where we'd exhaust the OS limits. Semaphore caps in-flight
        # work to self.fleet_concurrency.
        semaphore = asyncio.Semaphore(self.fleet_concurrency)

        async def _bounded(device_id: str) -> DeviceSnapshot:
            async with semaphore:
                return await self._snapshot_device_no_commit(device_id, family)

        tasks = [_bounded(did) for did in device_ids]
        snapshots = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        committed_ids = []
        for i, snap in enumerate(snapshots):
            if isinstance(snap, Exception):
                results.append(
                    DeviceSnapshot(
                        device_id=device_ids[i],
                        device_info={},
                        status=SnapshotStatus.FAILED,
                        facets=[
                            FacetResult(
                                name="__fleet__",
                                success=False,
                                error=str(snap),
                            )
                        ],
                    )
                )
            else:
                results.append(snap)
                if snap.succeeded_facets:
                    committed_ids.append(snap.device_id)

        if committed_ids:
            sha = self.git.commit_fleet_snapshot(committed_ids, message=message)
            baseline = sha or self.git.head_sha()
            for snap in results:
                if snap.device_id in committed_ids:
                    snap.git_sha = sha
                    self._set_baseline_pointers(snap.device_id, baseline)

        return results

    def _set_baseline_pointers(self, device_id: str, sha: Optional[str]) -> None:
        """Bless ``sha`` as the device's baseline + latest observation.

        Called after an explicit snapshot ("this state is good now"). The
        write is best-effort: a backend without config-pointer support (the
        stubbed Vault backend, per the H-4 deferral) degrades to a no-op
        rather than failing the snapshot.
        """
        if not sha:
            return
        try:
            self.registry.set_config_pointers(
                device_id,
                baseline_sha=sha,
                latest_observed_sha=sha,
                last_observed_at=time.time(),
            )
        except NotImplementedError:
            pass
        except Exception:  # pragma: no cover — must not break the snapshot
            logger.warning(
                "could not set baseline pointer for %s", device_id, exc_info=True
            )

    async def _snapshot_device_no_commit(
        self, device_id: str, family: str
    ) -> DeviceSnapshot:
        device_info = self.registry.get_device_info(device_id)
        device_info["device_id"] = device_id
        snapshot = DeviceSnapshot(device_id=device_id, device_info=device_info)

        facets = get_facets_for_device(device_info)
        if not facets:
            snapshot.status = SnapshotStatus.COMPLETED
            return snapshot

        raw_params = await self._read_all_params(device_id, device_info, family)
        extra_results = await self._read_extra_ops(
            device_id, device_info, facets, family
        )

        for facet in facets:
            result = self._run_facet(facet, raw_params, extra_results)
            snapshot.facets.append(result)

        self._write_files(device_id, device_info, snapshot)

        if snapshot.failed_facets and snapshot.succeeded_facets:
            snapshot.status = SnapshotStatus.PARTIAL
        elif snapshot.failed_facets:
            snapshot.status = SnapshotStatus.FAILED
        else:
            snapshot.status = SnapshotStatus.COMPLETED

        return snapshot

    async def _read_all_params(
        self, device_id: str, device_info: Dict, family: str
    ) -> Dict[str, str]:
        operation = self.catalog.get_operation(family, "param.cgi:list")
        if not operation:
            return {}

        executor = self.executors.get(family)
        if not executor:
            return {}

        credentials = self.registry.get_credentials(device_id)
        op_dict = operation.to_executor_dict()
        result = await executor.execute(
            op_dict, device_info, credentials, {"group": "root"}
        )

        if not result.success:
            logger.warning(
                "Failed to read params for %s: %s", device_id, result.error
            )
            return {}

        if isinstance(result.parsed_data, dict):
            raw_text = result.parsed_data.get("raw", "")
            if raw_text:
                return _parse_param_dump(raw_text)
            from admz.snapshot.ignore import get_ignore_patterns
            ignore = get_ignore_patterns()
            return {
                k: v
                for k, v in result.parsed_data.items()
                if not _is_volatile(k)
                and not _is_sensitive(k)
                and not _is_ignored(k, ignore)
            }

        if isinstance(result.parsed_data, str):
            return _parse_param_dump(result.parsed_data)

        return {}

    async def _read_extra_ops(
        self,
        device_id: str,
        device_info: Dict,
        facets: List[FacetAdapter],
        family: str,
    ) -> Dict[str, Any]:
        seen = set()
        specs = []
        for facet in facets:
            for spec in facet.extra_read_ops:
                ck = spec.cache_key()
                if ck not in seen:
                    seen.add(ck)
                    specs.append(spec)

        if not specs:
            return {}

        credentials = self.registry.get_credentials(device_id)
        executor = self.executors.get(family)
        if not executor:
            return {}

        results = {}
        for spec in specs:
            operation = self.catalog.get_operation(family, spec.operation_id)
            if not operation:
                continue
            op_dict = operation.to_executor_dict()
            result = await executor.execute(
                op_dict, device_info, credentials, spec.params
            )
            key = spec.result_key or spec.operation_id
            if result.success:
                results[key] = result.parsed_data

        return results

    def _run_facet(
        self,
        facet: FacetAdapter,
        raw_params: Dict[str, str],
        extra_results: Dict[str, Any],
    ) -> FacetResult:
        try:
            raw_responses = {"params": raw_params}
            raw_responses.update(extra_results)

            normalized = facet.serialize(raw_responses)
            if not normalized:
                return FacetResult(name=facet.name, success=True, normalized={})

            relevant_raw = {}
            for key, value in raw_params.items():
                if any(key.startswith(p) for p in facet.param_prefixes):
                    relevant_raw[key] = value

            return FacetResult(
                name=facet.name,
                success=True,
                normalized=normalized,
                raw=relevant_raw if relevant_raw else None,
            )
        except Exception as e:
            logger.exception("Facet %s failed for snapshot", facet.name)
            return FacetResult(name=facet.name, success=False, error=str(e))

    # Keys never written to fleet/<id>/device.yaml. Secrets (ADR-0014) plus
    # registry-managed bookkeeping: the config pointers are DB state ABOUT
    # the git repo — writing them into the repo would make every audit
    # change device.yaml (last_observed_at advances), defeating
    # commit-on-change and creating a commit per audit.
    _DEVICE_YAML_EXCLUDE = (
        "password", "secret", "token", "credentials",
        "baseline_sha", "latest_observed_sha", "last_observed_at",
        "created_at",
    )

    def _write_files(
        self,
        device_id: str,
        device_info: Dict,
        snapshot: DeviceSnapshot,
    ):
        safe_info = {
            k: v
            for k, v in device_info.items()
            if k not in self._DEVICE_YAML_EXCLUDE
        }
        self.git.write_device_yaml(device_id, safe_info)

        for facet_result in snapshot.succeeded_facets:
            if facet_result.normalized:
                self.git.write_facet(
                    device_id,
                    facet_result.name,
                    facet_result.normalized,
                    raw=facet_result.raw,
                )

