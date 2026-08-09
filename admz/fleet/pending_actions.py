"""Back-compat shim over the unified task store (ADR-0037).

The detection-task half of ADMZ used to live here as the ``pending_device_actions``
table. It now lives in the unified ``tasks`` table (:mod:`admz.tasks.store`). This
module remains as a thin adapter so existing callers — the REST recovery routes
and the MCP recovery tools — keep working unchanged, reading/writing the unified
store and returning the old dict shape.

New code should use :mod:`admz.tasks` directly.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional

from admz.tasks.store import (
    DEFAULT_TTL_SECONDS,
    EVENT_NEEDS_SETUP,
    EVENT_ONLINE,
    Task,
    event_for_status,
    tasks_store,
)

# Old trigger names == the unified detection events.
TRIGGER_NEEDS_SETUP = EVENT_NEEDS_SETUP
TRIGGER_ONLINE = EVENT_ONLINE
VALID_TRIGGERS = {TRIGGER_NEEDS_SETUP, TRIGGER_ONLINE}

# Old name kept for back-compat.
trigger_for_status = event_for_status

__all__ = [
    "TRIGGER_NEEDS_SETUP", "TRIGGER_ONLINE", "VALID_TRIGGERS",
    "trigger_for_status", "DEFAULT_TTL_SECONDS", "pending_actions",
    "PendingActionStore", "register_pending_handler", "execute_pending_action",
]


def _task_to_legacy(t: Task) -> Dict[str, Any]:
    """Render a detection Task in the old ``pending_device_actions`` row shape."""
    return {
        "id": t.id,
        "device_id": t.device_id,
        "action": t.action,                 # {"action": type, **params}
        "trigger": t.event,
        "approved_by": t.approved_by,
        "description": t.description,
        "created_at": t.created_at,
        "expires_at": t.expires_at,
        "status": t.status,
        "last_error": t.last_error,
    }


class PendingActionStore:
    """Adapter exposing the old API on top of the unified :class:`TaskStore`."""

    def __init__(self, db_path=None, *, store=None):
        if store is not None:
            self._store = store
        elif db_path is not None:
            from admz.tasks.store import TaskStore
            self._store = TaskStore(str(db_path))
        else:
            self._store = tasks_store

    def create(
        self, *, device_id: str, action: Dict[str, Any], trigger: str,
        approved_by: str = "", description: str = "",
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
    ) -> str:
        action = action or {}
        action_type = action.get("action", "")
        params = {k: v for k, v in action.items() if k != "action"}
        return self._store.create_detection(
            device_id=device_id, event=trigger, action_type=action_type,
            action_params=params, approved_by=approved_by, description=description,
            ttl_seconds=ttl_seconds,
        )

    def list_active_for(self, device_id: str) -> List[Dict[str, Any]]:
        return [_task_to_legacy(t) for t in self._store.list_active_for(device_id)]

    def list_active(self) -> List[Dict[str, Any]]:
        return [_task_to_legacy(t) for t in self._store.list_active_detections()]

    def claim_for_trigger(self, device_id: str, trigger: str) -> List[Dict[str, Any]]:
        return [_task_to_legacy(t)
                for t in self._store.claim_for_event(device_id, trigger)]

    def mark(self, pid: str, status: str, error: str = "") -> None:
        self._store.mark(pid, status, error)

    def cancel(self, pid: str) -> bool:
        return self._store.cancel(pid)

    def expire_stale(self) -> int:
        return self._store.expire_stale()

    def get(self, pid: str) -> Optional[Dict[str, Any]]:
        t = self._store.get(pid)
        return _task_to_legacy(t) if t else None


# Module singleton (adapter over the shared unified store).
pending_actions = PendingActionStore()


# --- handler-registry back-compat ------------------------------------------
# The action handlers moved to admz.tasks.handlers. These wrappers keep the old
# (action_dict, device_id) handler signature working over the unified registry.
PendingHandler = Callable[[Dict[str, Any], str], Awaitable[None]]


def register_pending_handler(action_type: str, fn: PendingHandler) -> None:
    from admz.tasks.handlers import register_task_handler

    async def _adapter(task: Task, ctx) -> Dict[str, Any]:
        await fn(task.action, task.device_id)
        return {"success": True}

    register_task_handler(action_type)(_adapter)


async def execute_pending_action(action: Dict[str, Any], device_id: str) -> None:
    from admz.tasks.handlers import execute_task_action

    action = action or {}
    task = Task(
        id="",
        device_id=device_id,
        action_type=action.get("action", ""),
        action_params={k: v for k, v in action.items() if k != "action"},
    )
    await execute_task_action(task)
