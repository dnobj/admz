"""Install the task-handler context at app startup (ADR-0037).

The ``reprovision`` action handler now lives in :mod:`admz.tasks.handlers`
(registered at import). This module just wires the live AppContext deps into the
unified task context so detection tasks fired by the health sweep can resolve the
registry / catalog / executors they need. (Was ``register_recovery_handlers``,
which closed those deps into a pending-action handler.)

SECURITY: detection tasks run only for actions the operator approved up front
(the queue route requires an authenticated principal), with no new gate at fire
time.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

ACTION_REPROVISION = "reprovision"


def register_recovery_handlers(ctx: Any) -> None:
    """Install the unified task context from the AppContext (idempotent). Name
    kept for back-compat with the app lifespan + tests."""
    from admz.tasks.handlers import TaskContext, set_task_context

    set_task_context(TaskContext(
        snapshot_engine=getattr(ctx, "snapshot_engine", None),
        drift_detector=getattr(ctx, "drift_detector", None),
        registry=getattr(ctx, "registry", None),
        catalog=getattr(ctx, "catalog", None),
        executors=getattr(ctx, "executors", None),
    ))
    logger.info("Task context installed (reprovision + scheduled handlers ready)")
