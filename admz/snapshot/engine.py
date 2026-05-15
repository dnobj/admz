import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from admz.snapshot.facets import get_facets_for_device
from admz.snapshot.facets.base import FacetAdapter
from admz.snapshot.git_repo import GitRepo
from admz.snapshot.models import (
    DeviceSnapshot,
    FacetResult,
    SnapshotStatus,
)

logger = logging.getLogger(__name__)

VOLATILE_PREFIXES = [
    "root.Properties.System.Soc.",
    "root.Properties.Firmware.",
]

SENSITIVE_PREFIXES = [
    "root.HTTPS.PrivateKey",
    "root.Network.Wireless.WPA.",
    "root.RemoteService.",
]


def _is_volatile(key: str) -> bool:
    return any(key.startswith(p) for p in VOLATILE_PREFIXES)


def _is_sensitive(key: str) -> bool:
    return any(key.startswith(p) for p in SENSITIVE_PREFIXES)


def _parse_param_dump(text: str) -> Dict[str, str]:
    params = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            key = key.strip()
            if not _is_volatile(key) and not _is_sensitive(key):
                params[key] = value.strip()
    return params


class SnapshotEngine:

    def __init__(
        self,
        catalog,
        registry,
        executors: Dict[str, Any],
        git_repo: GitRepo,
    ):
        self.catalog = catalog
        self.registry = registry
        self.executors = executors
        self.git = git_repo

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

        tasks = [
            self._snapshot_device_no_commit(did, family) for did in device_ids
        ]
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
            for snap in results:
                if snap.device_id in committed_ids:
                    snap.git_sha = sha

        return results

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
        op_dict = self._op_to_dict(operation)
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
            return {
                k: v
                for k, v in result.parsed_data.items()
                if not _is_volatile(k) and not _is_sensitive(k)
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
            op_dict = self._op_to_dict(operation)
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

    def _write_files(
        self,
        device_id: str,
        device_info: Dict,
        snapshot: DeviceSnapshot,
    ):
        safe_info = {
            k: v
            for k, v in device_info.items()
            if k not in ("password", "secret", "token", "credentials")
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

    def _op_to_dict(self, operation) -> Dict[str, Any]:
        return {
            "id": operation.id,
            "cgi": operation.cgi,
            "method": operation.method,
            "risk_level": operation.risk_level,
            "request": operation.request,
            "response": operation.response,
            "requires": getattr(operation, "requires", None),
            "_endpoint": operation.endpoint,
            "_generation": operation.generation,
            "_auth": getattr(operation, "auth", None),
            "service_impact": getattr(operation, "service_impact", None),
        }
