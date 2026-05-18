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

import os
from dataclasses import dataclass
from typing import Dict, Optional

from admz.catalog.loader import CatalogLoader
from admz.catalog.resolver import CatalogResolver
from admz.device_registry import DeviceRegistry
from admz.executor.base import BaseExecutor
from admz.executor.vapix import VapixExecutor
from admz.plans.engine import PlanEngine
from admz.snapshot.drift import DriftDetector
from admz.snapshot.engine import SnapshotEngine
from admz.snapshot.git_repo import GitRepo
from admz.snapshot.restore import RestoreBuilder
from admz.snapshot.scheduler import SnapshotScheduler


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


def _default_catalog_path() -> str:
    return os.getenv(
        "ADMZ_CATALOG_PATH",
        os.path.join(
            os.path.dirname(__file__), "..", "catalog"
        ),
    )


def _default_config_repo_path() -> str:
    return os.getenv(
        "ADMZ_CONFIG_REPO_PATH",
        os.path.join(os.path.expanduser("~"), ".admz", "config-repo"),
    )


def _default_schedule_path() -> str:
    return os.path.join(
        os.path.expanduser("~"), ".admz", "schedules.json"
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

    catalog = CatalogLoader(catalog_path)
    resolver = CatalogResolver(catalog)

    vapix_executor = VapixExecutor(
        retries=int(os.getenv("ADMZ_VAPIX_RETRIES", "1"))
    )
    executors: Dict[str, BaseExecutor] = {"vapix": vapix_executor}

    plan_engine = PlanEngine(
        catalog=catalog,
        registry=registry,
        executors=executors,
    )

    git_repo = GitRepo(config_repo_path, remote_url=config_repo_remote)

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

    scheduler = SnapshotScheduler(
        snapshot_engine=snapshot_engine,
        schedule_path=schedule_path,
    )

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
    )
