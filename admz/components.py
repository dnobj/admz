"""Shared component-builder for the FastAPI ``AppContext`` and the MCP server.

Both surfaces need to construct the same set of orchestration objects:
catalog, executors, plan engine, snapshot/restore/drift, and the scheduler.
Before this module existed, ``AppContext.__init__`` and
``ADMZMCPServer.__init__`` each rebuilt the entire stack independently —
which meant running MCP and the FastAPI app in the same process resulted
in **two SnapshotScheduler instances** racing over
``~/.admz/schedules.json``.

``build_components(registry)`` returns a single ``Components`` bundle that
both surfaces consume. The MCP server adds knowledge / capabilities /
temp-credentials on top — those are MCP-specific concerns that aren't
currently exposed via the REST API.
"""

import logging
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, Optional


logger = logging.getLogger(__name__)

import axis_api_atlas
from axis_api_atlas.catalog.loader import CatalogLoader
from axis_api_atlas.catalog.resolver import CatalogResolver
from admz.device_registry import DeviceRegistry
from admz.executor.base import BaseExecutor
from admz.modules.registry import ModuleRegistry
from admz.plans.engine import PlanEngine
from admz.snapshot.drift import DriftDetector
from admz.snapshot.engine import SnapshotEngine
from admz.snapshot.git_repo import GitRepo
from admz.snapshot.restore import RestoreBuilder
from admz.snapshot.scheduler import SnapshotScheduler
from admz.fleet.health import HealthMonitor
from admz.events.store import EventStore
from admz.events.ingest import EventIngestSupervisor
from admz.events.acs_ingest import AcsActionRulePoller
from admz.events.acs_firebird_ingest import AcsFirebirdPoller
from admz.events.detections import DetectionStore
from admz.events.evaluator import DetectionEvaluator
from admz.events.watched import WatchedEventStore
from admz.demos.store import DemoStore


@dataclass
class Components:
    """Bundle of orchestration objects shared between the MCP and REST surfaces."""

    registry: DeviceRegistry
    catalog: CatalogLoader
    resolver: CatalogResolver
    executors: Dict[str, BaseExecutor]
    plan_engine: PlanEngine
    git_repo: GitRepo
    snapshot_engine: SnapshotEngine
    restore_builder: RestoreBuilder
    drift_detector: DriftDetector
    scheduler: SnapshotScheduler
    health_monitor: HealthMonitor
    # ADR-0039: the discovered module set. MCP (tools), the web layer (nav),
    # and the chatbot host (prompt sections) all read this rather than a global.
    module_registry: ModuleRegistry
    # ADR-0041: the live device-event store + the per-device WS ingest supervisor
    # (off by default; gated on the event_ingest_enabled fleet flag).
    event_store: EventStore
    event_supervisor: EventIngestSupervisor
    acs_event_poller: AcsActionRulePoller
    acs_firebird_poller: AcsFirebirdPoller
    watched_event_store: WatchedEventStore
    # ADR-0041 layer 3: event-pattern detection rules + the evaluator that fires
    # them (the supervisor's on_event callback).
    detection_store: DetectionStore
    detection_evaluator: DetectionEvaluator
    # ADR-0046: demos — the experience-center unit of work. A pure store; its
    # readiness is computed on read from the drift/health caches.
    demo_store: DemoStore


def _default_catalog_path() -> str:
    # The catalog/knowledge/capabilities data now ships with the
    # axis-api-atlas package (single source of truth — see ADR-0029).
    # ADMZ no longer carries an in-tree copy. Still overridable via
    # ADMZ_CATALOG_PATH for a local/forked atlas data dir.
    return os.getenv("ADMZ_CATALOG_PATH", axis_api_atlas.default_data_path())


def _default_config_repo_path() -> str:
    from admz.paths import config_repo_dir
    return str(config_repo_dir())


def _default_schedule_path() -> str:
    from admz.paths import schedules_path
    return str(schedules_path())


def _default_repo_path_root() -> str:
    """Parent dir under which new Org repos auto-create.

    Each Org's actual repo lives at ``{root}/{org_id}/``. Operators
    override via ``ADMZ_REPO_PATH_ROOT``; the default keeps everything
    under the ADMZ_HOME family (ADR-0042).
    """
    from admz.paths import repos_root
    return str(repos_root())


def _detect_existing_origin(repo_path: str) -> str:
    """If ``repo_path`` is a git repo with an ``origin`` remote
    configured, return the URL. Otherwise return empty string.

    Used by the default-Org bootstrap to adopt any remote the
    operator manually set on the legacy ~/.admz/config-repo/ before
    Slice 1 landed (e.g. the homelab user pointing the legacy repo
    at github.com/.../admz-config-homelab.git).
    """
    if not os.path.isdir(os.path.join(repo_path, ".git")):
        return ""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_path, capture_output=True, text=True, check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except OSError:
        pass
    return ""


def _bootstrap_default_hierarchy(
    registry,
    legacy_config_repo_path: str,
) -> None:
    """Idempotently create the default Org/Site rows on first run.

    (ADR-0032: there is no Group level — devices are organized by Org →
    Site, with free-form tags for operational grouping.)

    Behavior:
      * Default Org's ``repo_path`` adopts the legacy ~/.admz/config-repo/
        when it exists on disk (so existing installs keep using their
        same git tree). Otherwise points at ``$ADMZ_REPO_PATH_ROOT/default/``.
      * Default Org's ``repo_remote_url`` is seeded from the legacy
        repo's ``origin`` remote (if any) so any prior ``git remote add``
        the operator did manually is preserved.
      * Re-running this function is a no-op when the rows already exist
        (catches BackendError on duplicate-PK INSERTs and proceeds).

    Skips silently if the registry doesn't support organizations
    (e.g. Vault backend) — the hierarchy is a SQLite-only concept
    in v1.
    """
    # Probe support — if the backend doesn't implement add_organization,
    # bail without raising. Operators on Vault keep the flat model.
    try:
        existing_orgs = registry.list_organizations()
    except NotImplementedError:
        return

    if any(o["org_id"] == "default" for o in existing_orgs):
        return  # Already bootstrapped

    # Pick the default Org's repo path: adopt the legacy location if
    # it exists, else use the new ADMZ_REPO_PATH_ROOT default.
    if os.path.isdir(legacy_config_repo_path):
        default_repo_path = legacy_config_repo_path
    else:
        default_repo_path = os.path.join(
            _default_repo_path_root(), "default"
        )

    default_remote = _detect_existing_origin(default_repo_path)

    try:
        registry.add_organization(
            org_id="default",
            name="Default Organization",
            repo_path=default_repo_path,
            repo_remote_url=default_remote,
        )
        registry.add_site(
            site_id="default",
            org_id="default",
            name="Default Site",
        )
        logger.info(
            "Bootstrapped default Org/Site: repo_path=%s remote=%r",
            default_repo_path,
            default_remote or "(none)",
        )
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(
            "Default-hierarchy bootstrap raised %s — proceeding (rows may "
            "have been partially created): %s",
            type(exc).__name__, exc,
        )


def _backfill_mac_addresses(registry: DeviceRegistry) -> None:
    """One-time migration for the slot/unit identity model (ADR-0036).

    `device_id` is the stable ADMZ *slot*; the currently-installed *unit*'s
    MAC lives in the `mac_address` field. For legacy rows whose `device_id`
    is a MAC (the historical auto-registration default) but whose
    `mac_address` is empty, copy the MAC across so discovery IP-reconcile
    and the collision check key on the authoritative `mac_address` (and so a
    later hardware swap, which changes `mac_address`, doesn't desync them).
    Idempotent; best-effort.
    """
    from admz.device_registry import canonical_mac
    try:
        devices = registry.list_devices()
    except Exception:  # pragma: no cover — defensive
        return
    for d in devices:
        did = d.get("device_id")
        if not did or d.get("mac_address"):
            continue
        # Only when the device_id itself is a 12-hex MAC.
        if len(canonical_mac(did)) != 12:
            continue
        try:
            registry.update_device_info(did, {"mac_address": did})
            logger.info("Backfilled mac_address for slot %s", did)
        except NotImplementedError:
            return  # backend can't update info (stubbed Vault)
        except Exception:  # pragma: no cover — best effort
            logger.debug("mac_address backfill skipped for %s", did, exc_info=True)


def _backfill_baselines(registry: DeviceRegistry, git_repo) -> None:
    """One-time migration: pin a baseline for devices that have committed
    config but no ``baseline_sha`` yet (snapshotted before the pointer landed).

    Sets baseline_sha + latest_observed_sha to the current HEAD — HEAD holds
    each device's current config, so it's the correct baseline. Idempotent:
    devices that already have a pointer are skipped before any git work, so
    this is a cheap no-op on every subsequent start. Best-effort: a backend
    without pointer support (the stubbed Vault) bails out quietly.
    """
    head = git_repo.head_sha()
    if not head:
        return
    try:
        devices = registry.list_devices()
    except Exception:  # pragma: no cover — defensive
        return
    now = time.time()
    for d in devices:
        did = d.get("device_id")
        if not did or d.get("baseline_sha"):
            continue
        try:
            if not git_repo.device_snapshot_status(did).get("has_baseline"):
                continue
            registry.set_config_pointers(
                did,
                baseline_sha=head,
                latest_observed_sha=head,
                last_observed_at=now,
            )
            logger.info("Backfilled baseline for %s -> %s", did, head[:10])
        except NotImplementedError:
            return  # backend can't store pointers (Vault) — nothing to do
        except Exception:  # pragma: no cover — best effort
            logger.debug(
                "baseline backfill skipped for %s", did, exc_info=True
            )


def build_components(
    registry: DeviceRegistry,
    *,
    catalog_path: Optional[str] = None,
    config_repo_path: Optional[str] = None,
    config_repo_remote: Optional[str] = None,
    schedule_path: Optional[str] = None,
) -> Components:
    """Build the shared component stack on top of a ``registry``.

    All paths default to the same environment-variable-driven locations
    that the MCP server and FastAPI app have always used. Callers can
    override any path for testing or unusual deployment topologies.
    """
    catalog_path = catalog_path or _default_catalog_path()
    config_repo_path = config_repo_path or _default_config_repo_path()
    if config_repo_remote is None:
        config_repo_remote = os.getenv("ADMZ_CONFIG_REPO_REMOTE")
    schedule_path = schedule_path or _default_schedule_path()

    # Slice 1: ensure the default Org/Site/Group rows exist. Idempotent
    # — re-runs are no-ops. Skipped for backends that don't support
    # organizations (e.g. Vault). Done BEFORE constructing GitRepo so
    # the legacy config-repo's existing origin remote can be detected
    # and adopted as the default Org's repo_remote_url.
    _bootstrap_default_hierarchy(registry, config_repo_path)

    catalog = CatalogLoader(catalog_path)
    resolver = CatalogResolver(catalog)

    # ADR-0039: build executors through the module registry. Discovery is an
    # explicit, ordered import of each module's get_module(); the devices
    # module contributes {"vapix": VapixExecutor(...)} exactly as the old
    # hardcoded literal did. The registry is stored on Components so the MCP,
    # web, and chatbot surfaces share the same module set.
    module_registry = ModuleRegistry()
    module_registry.discover()
    executors: Dict[str, BaseExecutor] = module_registry.executors_for_all()

    plan_engine = PlanEngine(
        catalog=catalog,
        registry=registry,
        executors=executors,
    )

    git_repo = GitRepo(config_repo_path, remote_url=config_repo_remote)

    # One-time backfill: devices snapshotted before the baseline-pointer
    # migration have committed config but a NULL baseline_sha. Pin them so
    # drift/restore have a baseline. Idempotent no-op once every config-bearing
    # device has a pointer.
    _backfill_baselines(registry, git_repo)
    # ADR-0036: ensure each slot's installed-unit MAC is in `mac_address`.
    _backfill_mac_addresses(registry)

    snapshot_engine = SnapshotEngine(
        catalog=catalog,
        registry=registry,
        executors=executors,
        git_repo=git_repo,
    )
    restore_builder = RestoreBuilder(
        catalog=catalog,
        registry=registry,
        git_repo=git_repo,
    )
    drift_detector = DriftDetector(
        snapshot_engine=snapshot_engine,
        git_repo=git_repo,
    )

    # ADR-0037: schedule tasks live in the unified SQLite tasks store. Bind it
    # to the resolved DB path at app-build time (not the import-time singleton)
    # so each app — including isolated tests — uses the right database.
    from admz.tasks.store import TaskStore, _default_db_path
    task_store = TaskStore(str(_default_db_path()))

    scheduler = SnapshotScheduler(
        snapshot_engine=snapshot_engine,
        schedule_path=schedule_path,
        # ADR-0026: pass the drift detector so the unified scheduler's
        # drift_audit handler can call check_fleet_drift without
        # reaching for a global.
        drift_detector=drift_detector,
        store=task_store,
    )

    # Health monitor: background poller that maintains the
    # device_health table. Opt-in via the health_monitor_enabled
    # fleet setting; .start() is a no-op when disabled.
    health_monitor = HealthMonitor(
        registry=registry,
        catalog=catalog,
        executors=executors,
    )

    # ADR-0041: live device-event subsystem. The store is bound to the resolved
    # DB path; the supervisor maintains one WS stream per device but only when
    # the event_ingest_enabled fleet flag is on (.start() is a no-op otherwise).
    from admz.events.store import _default_db_path as _events_db_path
    event_store = EventStore(str(_events_db_path()))
    # ADR-0041 layer 3: event-pattern detections. The evaluator is the
    # supervisor's on_event callback, so it's built first.
    detection_store = DetectionStore(str(_events_db_path()))
    detection_evaluator = DetectionEvaluator(registry=registry, store=detection_store)
    event_supervisor = EventIngestSupervisor(
        registry=registry, store=event_store, on_event=detection_evaluator.evaluate,
    )
    # ACS Pro has no push API, so action-rule firings are POLLED into the same
    # store + evaluator as device events (source="acs"). Off until both the ACS
    # module and acs_event_ingest_enabled are on.
    acs_event_poller = AcsActionRulePoller(
        catalog=catalog, executors=executors, store=event_store,
        on_event=detection_evaluator.evaluate,
    )
    # Reads ACS's embedded Firebird LOG (copy → read) for NAMED rule firings — no
    # rule edit needed. Off unless acs_firebird_enabled + ACS connected + driver present.
    acs_firebird_poller = AcsFirebirdPoller(
        store=event_store, on_event=detection_evaluator.evaluate,
    )
    # Watched events: a passive library of bookmarked event patterns (no worker,
    # no evaluator, no ingest dependency — it just feeds the detection builder).
    watched_event_store = WatchedEventStore(str(_events_db_path()))
    # Demos live in the control-plane DB (like tasks) — they reference devices
    # and scenarios, not the event log.
    demo_store = DemoStore()

    return Components(
        registry=registry,
        catalog=catalog,
        resolver=resolver,
        executors=executors,
        plan_engine=plan_engine,
        git_repo=git_repo,
        snapshot_engine=snapshot_engine,
        restore_builder=restore_builder,
        drift_detector=drift_detector,
        scheduler=scheduler,
        health_monitor=health_monitor,
        module_registry=module_registry,
        event_store=event_store,
        event_supervisor=event_supervisor,
        acs_event_poller=acs_event_poller,
        acs_firebird_poller=acs_firebird_poller,
        watched_event_store=watched_event_store,
        detection_store=detection_store,
        detection_evaluator=detection_evaluator,
        demo_store=demo_store,
    )
