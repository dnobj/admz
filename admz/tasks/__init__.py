"""Unified Tasks subsystem (ADR-0037).

A *task* is one unit of deferred/automated work with a **trigger** that is either
a **schedule** (time-based, recurring — e.g. "snapshot every 6h") or a
**detection** (event-based, one-shot — e.g. "re-provision when it returns
factory-defaulted"), plus an **action** and a **target**.

This supersedes the two parallel subsystems it grew out of:
  - the time-based ``SnapshotScheduler`` (``schedules.json``), and
  - the trigger-based pending-action store (``pending_device_actions``).

Both are now backed by the single SQLite ``tasks`` table (:mod:`admz.tasks.store`)
and dispatch through one handler registry (:mod:`admz.tasks.handlers`). The two
*evaluators* stay separate by necessity — the scheduler interval loop fires
schedule tasks, the health-monitor sweep fires detection tasks — but they read
one store.
"""

from admz.tasks.store import (
    Task,
    TaskStore,
    tasks_store,
    TRIGGER_SCHEDULE,
    TRIGGER_DETECTION,
    EVENT_NEEDS_SETUP,
    EVENT_ONLINE,
    VALID_EVENTS,
    event_for_status,
    DEFAULT_TTL_SECONDS,
)

__all__ = [
    "Task",
    "TaskStore",
    "tasks_store",
    "TRIGGER_SCHEDULE",
    "TRIGGER_DETECTION",
    "EVENT_NEEDS_SETUP",
    "EVENT_ONLINE",
    "VALID_EVENTS",
    "event_for_status",
    "DEFAULT_TTL_SECONDS",
]
