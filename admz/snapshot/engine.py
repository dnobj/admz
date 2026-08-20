import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from axis_api_atlas.catalog.loader import CatalogLoader
from admz.device_capabilities import (
    DeviceCapabilityStore,
    capability_store as _default_capability_store,
    device_firmware,
    learn as _learn_capabilities,
    probe_key_for,
)
from admz.device_registry import DeviceRegistry
from admz.executor.base import BaseExecutor
from admz.snapshot.facets import get_facets_for_device
from admz.snapshot.facets.base import FacetAdapter, ReadSpec
from admz.snapshot.git_repo import GitRepo
from admz.snapshot.models import (
    FACET_FAILED,
    FACET_OK,
    FACET_SKIPPED,
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

# The firmware line of a param.cgi dump. VOLATILE — dropped by the parser
# below, which is why the engine lifts it from the raw text *first*
# (ADR-0063): the audit's own dump is the freshest firmware fact ADMZ has,
# and it reaches devices the health monitor cannot authenticate to.
_FIRMWARE_LINE = re.compile(
    r"^root\.Properties\.Firmware\.Version=(.+?)\s*$", re.MULTILINE
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


def _prune_nested(d: Dict[str, Any], drop: set, prefix: str = "") -> Dict[str, Any]:
    """Rebuild a (possibly one-level-nested) facet dict, dropping leaves whose
    flattened key is in ``drop`` and discarding any group left empty."""
    out: Dict[str, Any] = {}
    for k, v in d.items():
        fk = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            sub = _prune_nested(v, drop, fk)
            if sub:
                out[k] = sub
        elif fk not in drop:
            out[k] = v
    return out


def _filter_ignored(facet, normalized: Dict[str, Any], rules) -> Dict[str, Any]:
    """Drop operator-excluded fields from a facet's serialized output before it
    enters the snapshot/git. Matches each field's canonical key (so it covers
    param + non-param facets uniformly) against ``rules`` — the ignore rules
    already filtered to this device's scope."""
    if not rules:
        return normalized
    from admz.snapshot.flatten import flatten
    from admz.snapshot.ignore import is_ignored
    flat = flatten(normalized)
    drop = {
        fk for fk in flat
        if is_ignored(facet.canonical_key(fk), rules=rules)
    }
    if not drop:
        return normalized
    return _prune_nested(normalized, drop)


def _parse_param_dump(text: str) -> Dict[str, str]:
    # NOTE: only volatile/secret params are dropped here (param-level, always).
    # The operator IGNORE list is applied later, per-facet and device-aware, in
    # _run_facet via _filter_ignored — it needs device/tag scope + canonical
    # keys, which aren't available at this raw-param stage.
    params = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            key = key.strip()
            if not _is_volatile(key) and not _is_sensitive(key):
                params[key] = value.strip()
    return params


def firmware_from_dump(text: str) -> str:
    """``root.Properties.Firmware.Version`` from a raw param.cgi dump, or ``""``."""
    m = _FIRMWARE_LINE.search(text or "")
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------
# Read outcomes — what the engine learns from, and what facet status is
# derived from (ADR-0063)
# ---------------------------------------------------------------------------


@dataclass
class ProbeOutcome:
    """One extra read the engine asked for: did it succeed, and the executor's
    ``StepResult`` when one was obtained (``None`` when the read never left
    ADMZ — no executor, operation not in the catalog)."""
    spec: ReadSpec
    ok: bool
    result: Optional[Any] = None
    error: str = ""


class ExtraReadResults(dict):
    """``{result_key: parsed_data}`` for the extra reads that succeeded — the
    contract every caller, and every test override of ``_read_extra_ops``,
    has always had — plus ``outcomes``: ``{spec.cache_key(): ProbeOutcome}``
    for EVERY spec the real engine asked for, succeeded or not.

    A plain ``dict`` (a test stub's return) carries no outcomes, and the
    engine then treats those reads exactly as it always did: nothing learned,
    nothing marked failed. The honesty and the learning ride on the real
    engine's return value only.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes: Dict[tuple, ProbeOutcome] = {}


@dataclass
class _Capture:
    """One device's live reads for one cycle, with the bookkeeping facet
    status and the learner need."""
    facets: List[FacetAdapter]
    raw_params: Dict[str, str]
    dump_ok: bool
    extra_results: Dict[str, Any]
    # spec.cache_key() -> FACET_OK | FACET_FAILED | FACET_SKIPPED. A spec with
    # no entry was read by a stub that reports nothing: legacy, treated as ok.
    op_status: Dict[tuple, str] = field(default_factory=dict)
    op_error: Dict[tuple, str] = field(default_factory=dict)
    skipped_reason: Dict[tuple, str] = field(default_factory=dict)


class SnapshotEngine:

    def __init__(
        self,
        catalog: CatalogLoader,
        registry: DeviceRegistry,
        executors: Dict[str, BaseExecutor],
        git_repo: GitRepo,
        fleet_concurrency: Optional[int] = None,
        capability_store: Optional[DeviceCapabilityStore] = None,
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
        # ADR-0063: the local record of what each device's APIs answered.
        # Injected by tests; the module singleton otherwise.
        self.capability_store = (
            capability_store if capability_store is not None
            else _default_capability_store
        )
        self._probe_keys: Dict[Tuple[str, str], str] = {}

    async def snapshot_device(
        self,
        device_id: str,
        message: Optional[str] = None,
        family: str = "vapix",
        bless: bool = True,
        force_probe: bool = False,
    ) -> DeviceSnapshot:
        """Capture the device's live config into a git commit.

        By default the new commit is blessed as the device's baseline. Pass
        ``bless=False`` to capture the commit WITHOUT moving ``baseline_sha`` —
        used to save an alternate config ("scenario") from the current live
        state while leaving the blessed baseline untouched (ADR-0044).

        ``force_probe=True`` ignores the local capability record and reads
        every facet (ADR-0063) — an explicit operator capture may want to
        re-ask an API the audit has recorded absent, without waiting for the
        record to expire. The audit never does this."""
        snapshot = await self._read_device(device_id, family, force_probe=force_probe)
        if not snapshot.facets:
            return snapshot

        self._write_files(device_id, snapshot.device_info, snapshot)

        sha = self.git.commit_snapshot(device_id, message=message)
        snapshot.git_sha = sha

        # An explicit snapshot blesses the current config as the baseline.
        # Pin to the committed sha, or HEAD when nothing changed (the device
        # is already at its baseline). Only when we actually captured config —
        # and only when the caller wants it blessed (scenario saves pass
        # bless=False to keep the baseline pointer where it is).
        if bless and snapshot.succeeded_facets:
            self._set_baseline_pointers(device_id, sha or self.git.head_sha())

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
        """Read the device and write its facets to the config repo's working
        tree — no commit (the caller commits: the audit, or the fleet
        snapshot as one commit for many devices)."""
        snapshot = await self._read_device(device_id, family)
        if snapshot.facets and self.git is not None:
            self._write_files(device_id, snapshot.device_info, snapshot)
        return snapshot

    async def _read_device(
        self, device_id: str, family: str, *, force_probe: bool = False
    ) -> DeviceSnapshot:
        """Read the device's live config into a ``DeviceSnapshot`` — every
        facet run, every status set, the rollup done — WITHOUT writing files
        or committing. The one capture path (ADR-0063): the explicit
        snapshot, the fleet snapshot and the drift audit all come through
        here, so the capability record is consulted and taught in one place.
        """
        device_info = self.registry.get_device_info(device_id)
        device_info["device_id"] = device_id
        snapshot = DeviceSnapshot(device_id=device_id, device_info=device_info)

        capture = await self._capture(
            device_id, device_info, family, force_probe=force_probe
        )
        if not capture.facets:
            snapshot.status = SnapshotStatus.COMPLETED
            return snapshot

        from admz.snapshot.ignore import applicable_rules
        ignore_rules = applicable_rules(device_id, device_info.get("tags"))
        for facet in capture.facets:
            snapshot.facets.append(self._run_facet(
                facet, capture.raw_params, capture.extra_results, ignore_rules,
                read=capture,
            ))

        # ``skipped`` is settled — it never makes a snapshot PARTIAL, for the
        # same reason ``reachable_no_api`` does not count as a failure.
        if snapshot.failed_facets and snapshot.succeeded_facets:
            snapshot.status = SnapshotStatus.PARTIAL
        elif snapshot.failed_facets:
            snapshot.status = SnapshotStatus.FAILED
        else:
            snapshot.status = SnapshotStatus.COMPLETED
        return snapshot

    # ------------------------------------------------------------------
    # Capture: the reads, the selection, the learning
    # ------------------------------------------------------------------

    async def _capture(
        self,
        device_id: str,
        device_info: Dict,
        family: str,
        *,
        force_probe: bool = False,
    ) -> _Capture:
        """Issue this cycle's reads. The shared ``param.cgi`` dump first — it
        lifts the firmware, and its success is the readability control the
        learner needs — then the API-backed facets, minus those whose API the
        local record says (non-stale, ``supported=0``) the device lacks.
        Everything else probes: present, unknown, stale, expired. Every
        outcome the real executor produced is then taught to the record.
        """
        raw_params = await self._read_all_params(device_id, device_info, family)
        dump_ok = bool(raw_params)
        # Facets are selected AFTER the dump so ``min_firmware`` criteria see
        # the firmware just lifted from it, not only what the registry knew.
        facets = get_facets_for_device(device_info)
        capture = _Capture(
            facets=facets, raw_params=raw_params, dump_ok=dump_ok,
            extra_results={},
        )
        if not facets:
            return capture

        firmware = device_firmware(device_info)
        view = {} if force_probe else self._capability_view(device_id, firmware)

        to_probe: List[FacetAdapter] = []
        for facet in facets:
            specs = facet.extra_read_ops
            if not specs:
                continue
            absent_rows = []
            for spec in specs:
                row = view.get(self._probe_key(family, spec.operation_id))
                if row is not None and not row.supported:
                    absent_rows.append((spec, row))
            # Skip a facet's reads only when EVERY API it reads is recorded
            # absent. A facet that reads one API the device lacks and one it
            # has is probed whole — unknown means probe, and no facet today
            # spans two APIs anyway.
            if absent_rows and len(absent_rows) == len(specs):
                for spec, row in absent_rows:
                    when = datetime.fromtimestamp(
                        row.observed_at, tz=timezone.utc
                    ).strftime("%Y-%m-%d %H:%MZ")
                    capture.op_status[spec.cache_key()] = FACET_SKIPPED
                    capture.skipped_reason[spec.cache_key()] = (
                        f"{row.probe_key} recorded {row.classification} "
                        f"({row.source}, {when}; {row.reason or 'no detail'})"
                    )
            else:
                to_probe.append(facet)

        extra = await self._read_extra_ops(device_id, device_info, to_probe, family)
        capture.extra_results = extra
        outcomes = getattr(extra, "outcomes", None)
        if outcomes:
            for ck, outcome in outcomes.items():
                capture.op_status[ck] = FACET_OK if outcome.ok else FACET_FAILED
                if not outcome.ok:
                    capture.op_error[ck] = outcome.error
            self._learn(
                device_id, firmware, family, outcomes, device_readable=dump_ok
            )
        return capture

    def _probe_key(self, family: str, operation_id: str) -> str:
        key = (family, operation_id)
        if key not in self._probe_keys:
            self._probe_keys[key] = probe_key_for(self.catalog, family, operation_id)
        return self._probe_keys[key]

    def _capability_view(self, device_id: str, firmware: str) -> Dict[str, Any]:
        """The non-stale rows for this device at this firmware; ``{}`` when
        the store is unavailable (a store failure must not fail a read — it
        just means nothing is skipped)."""
        try:
            return self.capability_store.view(device_id, firmware)
        except Exception:  # noqa: BLE001
            logger.warning(
                "capability record unavailable for %s; probing everything",
                device_id, exc_info=True,
            )
            return {}

    def _learn(
        self,
        device_id: str,
        firmware: str,
        family: str,
        outcomes: Dict[tuple, ProbeOutcome],
        *,
        device_readable: bool,
    ) -> None:
        """Teach the capability record what this cycle's reads showed. Only
        outcomes that carry an executor result are device evidence; a read
        that never left ADMZ (no executor, op not in catalog) teaches
        nothing."""
        pairs = [
            (self._probe_key(family, o.spec.operation_id), o.result)
            for o in outcomes.values()
            if o.result is not None
        ]
        if not pairs:
            return
        try:
            _learn_capabilities(
                self.capability_store,
                device_id=device_id, firmware=firmware, outcomes=pairs,
                device_readable=device_readable,
            )
        except Exception:  # noqa: BLE001 — the learner must never fail a read
            logger.warning(
                "capability learning failed for %s", device_id, exc_info=True
            )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

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
                self._note_firmware(device_id, device_info, firmware_from_dump(raw_text))
                return _parse_param_dump(raw_text)
            self._note_firmware(
                device_id, device_info,
                str(result.parsed_data.get("root.Properties.Firmware.Version") or ""),
            )
            return {
                k: v
                for k, v in result.parsed_data.items()
                if not _is_volatile(k) and not _is_sensitive(k)
            }

        if isinstance(result.parsed_data, str):
            self._note_firmware(
                device_id, device_info, firmware_from_dump(result.parsed_data)
            )
            return _parse_param_dump(result.parsed_data)

        return {}

    def _note_firmware(self, device_id: str, device_info: Dict, firmware: str) -> None:
        """The dump's firmware is the freshest firmware fact ADMZ has. Put it
        on this cycle's ``device_info`` (facet selection and the capability
        key both read it) and persist the delta, best-effort, so the registry
        catches up even for devices the health monitor cannot authenticate
        to. Only written on an actual change — no churn."""
        firmware = (firmware or "").strip()
        if not firmware or firmware == str(device_info.get("firmware_version") or ""):
            return
        device_info["firmware_version"] = firmware
        update = getattr(self.registry, "update_device_info", None)
        if update is None:
            return
        try:
            update(device_id, {"firmware_version": firmware})
        except NotImplementedError:
            pass
        except Exception:  # noqa: BLE001 — bookkeeping must not fail a read
            logger.debug(
                "firmware not persisted for %s", device_id, exc_info=True
            )

    async def probe_readable(
        self, device_id: str, device_info: Dict, family: str = "vapix"
    ):
        """Lightweight authenticated read to tell whether the live device is
        actually readable. Returns ``(ok, reason)`` — ``ok=False`` with reason
        ``"auth_failed"`` (HTTP 401) or ``"unreachable"``.

        Drift uses this so an unreadable device isn't mistaken for one whose
        every baselined field was removed. Fail-OPEN: when we can't even
        attempt the probe (no executor/catalog/op — e.g. a stubbed test
        engine), return ``(True, "")`` so drift proceeds as before."""
        executor = self.executors.get(family) if self.executors else None
        catalog = getattr(self, "catalog", None)
        if executor is None or catalog is None:
            return True, ""
        operation = catalog.get_operation(family, "param.cgi:list")
        if not operation:
            return True, ""
        try:
            credentials = self.registry.get_credentials(device_id)
            result = await executor.execute(
                operation.to_executor_dict(), device_info, credentials,
                {"group": "root.Brand"},  # tiny authenticated read
            )
        except Exception:  # noqa: BLE001 - connection error etc.
            return False, "unreachable"
        if getattr(result, "success", False):
            return True, ""
        if getattr(result, "status_code", None) == 401:
            # A factory-defaulted device 401s on every authed read but reports
            # needsetup via systemready (no auth) — tell the two apart.
            try:
                from admz.fleet.systemready import read_systemready
                sr = await read_systemready(
                    catalog, executor, device_info, credentials, family
                )
                if sr and sr.get("needsetup"):
                    return False, "needs_setup"
            except Exception:  # noqa: BLE001
                pass
            return False, "auth_failed"
        return False, "unreachable"

    async def _read_extra_ops(
        self,
        device_id: str,
        device_info: Dict,
        facets: List[FacetAdapter],
        family: str,
    ) -> Dict[str, Any]:
        """Issue the facets' extra reads. Returns ``{result_key: parsed_data}``
        for the reads that succeeded; the real engine's return value also
        carries ``.outcomes`` for every read asked (see
        :class:`ExtraReadResults`). A failed read is an outcome, not a
        silence — that silence was the defect ADR-0063 closes."""
        seen = set()
        specs = []
        for facet in facets:
            for spec in facet.extra_read_ops:
                ck = spec.cache_key()
                if ck not in seen:
                    seen.add(ck)
                    specs.append(spec)

        results = ExtraReadResults()
        if not specs:
            return results

        credentials = self.registry.get_credentials(device_id)
        executor = self.executors.get(family)
        if not executor:
            for spec in specs:
                results.outcomes[spec.cache_key()] = ProbeOutcome(
                    spec, ok=False, error=f"no executor for family {family!r}"
                )
            return results

        for spec in specs:
            ck = spec.cache_key()
            operation = self.catalog.get_operation(family, spec.operation_id)
            if not operation:
                results.outcomes[ck] = ProbeOutcome(
                    spec, ok=False,
                    error=f"{spec.operation_id} is not in the catalog",
                )
                continue
            op_dict = operation.to_executor_dict()
            result = await executor.execute(
                op_dict, device_info, credentials, spec.params
            )
            key = spec.result_key or spec.operation_id
            if result.success:
                results[key] = result.parsed_data
                results.outcomes[ck] = ProbeOutcome(spec, ok=True, result=result)
            else:
                results.outcomes[ck] = ProbeOutcome(
                    spec, ok=False, result=result,
                    error=str(result.error or f"{spec.operation_id} failed"),
                )

        return results

    # ------------------------------------------------------------------
    # Facets
    # ------------------------------------------------------------------

    def _facet_read_status(
        self, facet: FacetAdapter, read: _Capture
    ) -> Tuple[str, Optional[str]]:
        """``(status, detail)`` for a facet given this cycle's reads.

        ``skipped`` when every API it reads is recorded absent; ``failed``
        when any read it depends on — an extra op that was attempted, or the
        shared dump for a facet that reads params — did not succeed; ``ok``
        otherwise. A spec with no recorded outcome (a stub that reports
        nothing) counts as ok: legacy behaviour, by design.
        """
        specs = facet.extra_read_ops
        if specs:
            statuses = [read.op_status.get(s.cache_key()) for s in specs]
            if all(s == FACET_SKIPPED for s in statuses):
                return FACET_SKIPPED, read.skipped_reason.get(specs[0].cache_key())
            if any(s == FACET_FAILED for s in statuses):
                errors = [
                    read.op_error.get(s.cache_key()) or s.operation_id
                    for s in specs
                    if read.op_status.get(s.cache_key()) == FACET_FAILED
                ]
                return FACET_FAILED, "; ".join(errors)
        reads_dump = (not specs) or bool(facet.param_prefixes)
        if reads_dump and not read.dump_ok:
            return FACET_FAILED, "param.cgi dump unavailable"
        return FACET_OK, None

    def _run_facet(
        self,
        facet: FacetAdapter,
        raw_params: Dict[str, str],
        extra_results: Dict[str, Any],
        ignore_rules=None,
        *,
        read: Optional[_Capture] = None,
    ) -> FacetResult:
        if read is not None:
            status, detail = self._facet_read_status(facet, read)
            if status == FACET_SKIPPED:
                return FacetResult(
                    name=facet.name, success=False, status=FACET_SKIPPED,
                    skipped_reason=detail,
                )
            if status == FACET_FAILED:
                # The live state is UNKNOWN — not empty. Serialising what we
                # have would record ``{}`` as success, which is the defect.
                return FacetResult(
                    name=facet.name, success=False, status=FACET_FAILED,
                    error=detail,
                )
        try:
            raw_responses = {"params": raw_params}
            raw_responses.update(extra_results)

            normalized = facet.serialize(raw_responses)
            # Apply the operator ignore list (device-scoped) before commit.
            normalized = _filter_ignored(facet, normalized, ignore_rules)
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
