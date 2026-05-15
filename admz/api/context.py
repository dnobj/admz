"""
Shared dependencies and singletons for the FastAPI application.

The web app uses the same orchestration objects as the MCP server
(catalog, executors, plan engine, snapshot engine, scheduler) so the
two surfaces stay consistent.
"""

import os
from typing import Dict, Optional

from fastapi import HTTPException

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


class AppContext:
    """Holds the long-lived ADMZ orchestration objects."""

    def __init__(self, registry: DeviceRegistry):
        self.registry = registry

        catalog_path = os.getenv(
            "ADMZ_CATALOG_PATH",
            os.path.join(
                os.path.dirname(__file__), "..", "..", "catalog"
            ),
        )
        self.catalog = CatalogLoader(catalog_path)
        self.resolver = CatalogResolver(self.catalog)

        self.executors: Dict[str, BaseExecutor] = {"vapix": VapixExecutor()}

        self.plan_engine = PlanEngine(
            catalog=self.catalog,
            registry=self.registry,
            executors=self.executors,
        )

        config_repo_path = os.getenv(
            "ADMZ_CONFIG_REPO_PATH",
            os.path.join(os.path.expanduser("~"), ".admz", "config-repo"),
        )
        config_repo_remote = os.getenv("ADMZ_CONFIG_REPO_REMOTE")
        self.git_repo = GitRepo(config_repo_path, remote_url=config_repo_remote)

        self.snapshot_engine = SnapshotEngine(
            catalog=self.catalog,
            registry=self.registry,
            executors=self.executors,
            git_repo=self.git_repo,
        )
        self.restore_builder = RestoreBuilder(
            catalog=self.catalog,
            registry=self.registry,
            git_repo=self.git_repo,
        )
        self.drift_detector = DriftDetector(
            snapshot_engine=self.snapshot_engine,
            git_repo=self.git_repo,
        )

        schedule_path = os.path.join(
            os.path.expanduser("~"), ".admz", "schedules.json"
        )
        self.scheduler = SnapshotScheduler(
            snapshot_engine=self.snapshot_engine,
            schedule_path=schedule_path,
        )


_ctx: Optional[AppContext] = None


def init_context(registry: DeviceRegistry) -> AppContext:
    """Initialize the global context. Called once at startup."""
    global _ctx
    _ctx = AppContext(registry)
    return _ctx


def get_context() -> AppContext:
    """FastAPI dependency: return the global context."""
    if _ctx is None:
        raise HTTPException(
            status_code=503, detail="Application context not initialized"
        )
    return _ctx
