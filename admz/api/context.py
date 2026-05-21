"""
Shared dependencies and singletons for the FastAPI application.

``AppContext`` wraps a :class:`~admz.components.Components` bundle. The
MCP server uses the same builder, so running both surfaces in one
process now shares state — including a single ``SnapshotScheduler``
instance (no more racing schedule files).
"""

from typing import Optional

from fastapi import HTTPException

from admz.components import Components, build_components
from admz.device_registry import DeviceRegistry


class AppContext:
    """Holds the long-lived ADMZ orchestration objects."""

    def __init__(self, registry: DeviceRegistry):
        self._components: Components = build_components(registry)

    # Convenience attribute forwarding so existing route code that does
    # ``ctx.registry``, ``ctx.catalog``, etc. continues to work without
    # any changes.
    @property
    def registry(self) -> DeviceRegistry:
        return self._components.registry

    @property
    def catalog(self):
        return self._components.catalog

    @property
    def resolver(self):
        return self._components.resolver

    @property
    def executors(self):
        return self._components.executors

    @property
    def plan_engine(self):
        return self._components.plan_engine

    @property
    def git_repo(self):
        return self._components.git_repo

    @property
    def snapshot_engine(self):
        return self._components.snapshot_engine

    @property
    def restore_builder(self):
        return self._components.restore_builder

    @property
    def drift_detector(self):
        return self._components.drift_detector

    @property
    def scheduler(self):
        return self._components.scheduler

    @property
    def health_monitor(self):
        return self._components.health_monitor


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
