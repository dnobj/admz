"""Gated task writes (ADR-0034 applied to standing behavior).

Creating or modifying a task is a *persistent* change — it arms work that
runs later, unattended. Those writes now take the same out-of-context
approval widget as a reboot, with ONE exemption: an operator filling the
Tasks-page form in the console is already a deliberate human action, so
interactive web-session principals write directly (still audited).

This module is the single validation + write core shared by:

* the REST routes (direct path for interactive operators, gate for
  api-key/anonymous callers), and
* the ``create_task`` / ``update_task`` action executors that run when a
  confirm widget is approved (:mod:`admz.operations`).
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from admz.snapshot.scheduler import SnapshotSchedule, parse_interval
from admz.tasks.handlers import list_action_types
from admz.tasks.store import TRIGGER_DETECTION, TRIGGER_SCHEDULE, VALID_EVENTS


class TaskSpecError(ValueError):
    """A task spec that must be rejected (unknown action, bad interval, …)."""


def is_interactive(principal: Any) -> bool:
    """True for a human operator authenticated in the web console.

    Windows-local sessions (/login and SSO both mint ``source='windows'``
    principals) are the console; api-key, anonymous, and everything else
    takes the widget path.

    **This exemption belongs to the write gates only. Do not extend it to
    ADR-0034** (GH #275, which asked whether the difference was deliberate).

    There are two gates in this codebase and they answer different questions:

    * ``gate_task_write`` / ``gate_demo_write`` / ``gate_scan_write`` ask
      *"who authorized creating this automation?"*. A human doing it by hand at
      the console **is** the authorizer, so there is no absent person to
      approve on their behalf — hence this exemption.
    * ``operations.execute_gated_operation`` (ADR-0034) asks *"what will this
      operation do to the device?"*. Risk level → confirmation level, and a
      human clicking *reboot* should still confirm. That is the whole point of
      ``url_only`` / ``url_and_password``.

    So `catalog.py` and `acs_pro/routes.py` gating every caller is not an
    inconsistency with the routes above; it is a different mechanism. Note
    ``execute_gated_operation`` **takes no principal at all** — it cannot
    exempt anyone, by construction, which is the enforcement behind the
    invariant that capabilities may change *who may approve* but never remove
    a gate.
    """
    return getattr(principal, "source", "") == "windows"


# ---------------------------------------------------------------------------
# Validation (shared: fail fast at request time, re-checked at apply time)
# ---------------------------------------------------------------------------


def validate_create_spec(spec: Mapping[str, Any], registry: Any = None) -> None:
    """Raise :class:`TaskSpecError` when the spec can't become a task."""
    action_type = spec.get("action_type") or ""
    if action_type not in list_action_types():
        raise TaskSpecError(
            f"Unknown action_type {action_type!r}. "
            f"Registered: {list_action_types()}."
        )
    kind = spec.get("trigger_kind")
    if kind == TRIGGER_SCHEDULE:
        if not spec.get("interval"):
            raise TaskSpecError("schedule tasks need an 'interval'")
        try:
            parse_interval(str(spec["interval"]))
        except ValueError as e:
            raise TaskSpecError(str(e))
    elif kind == TRIGGER_DETECTION:
        if not spec.get("device_id"):
            raise TaskSpecError("detection tasks need a 'device_id'")
        if spec.get("event") not in VALID_EVENTS:
            raise TaskSpecError(f"event must be one of {sorted(VALID_EVENTS)}")
        if registry is not None and not registry.device_exists(spec["device_id"]):
            raise TaskSpecError(f"Device not found: {spec['device_id']}")
    else:
        raise TaskSpecError("trigger_kind must be 'schedule' or 'detection'")


# ---------------------------------------------------------------------------
# The one write path
# ---------------------------------------------------------------------------


def apply_create_task(
    spec: Mapping[str, Any], *, scheduler: Any, registry: Any, approved_by: str
) -> Dict[str, Any]:
    """Validate + write one task; returns the created task's dict."""
    validate_create_spec(spec, registry)

    if spec["trigger_kind"] == TRIGGER_SCHEDULE:
        schedule = SnapshotSchedule(
            id=spec.get("task_id") or _new_id(),
            description=spec.get("description") or "",
            interval_seconds=parse_interval(str(spec["interval"])),
            tag_filter=spec.get("tag_filter"),
            device_ids=spec.get("device_ids"),
            job_type=spec["action_type"],
            params=dict(spec.get("action_params") or {}),
        )
        scheduler.add_schedule(schedule)
        return scheduler.store.get(schedule.id).to_dict()

    tid = scheduler.store.create_detection(
        device_id=spec["device_id"],
        event=spec["event"],
        action_type=spec["action_type"],
        action_params=dict(spec.get("action_params") or {}),
        approved_by=approved_by,
        description=spec.get("description")
        or f"{spec['action_type']} {spec['device_id']} on {spec['event']}",
        task_id=spec.get("task_id"),
    )
    return scheduler.store.get(tid).to_dict()


def apply_update_task(
    task_id: str, fields: Mapping[str, Any], *, scheduler: Any
) -> Dict[str, Any]:
    """Validate + apply a schedule-task update; returns the updated dict."""
    task = scheduler.store.get(task_id)
    if task is None:
        raise TaskSpecError(f"Task not found: {task_id}")
    if task.trigger_kind != TRIGGER_SCHEDULE:
        raise TaskSpecError(
            "only schedule tasks are editable; cancel a detection task instead"
        )
    kwargs: Dict[str, Any] = {}
    if fields.get("interval") is not None:
        try:
            kwargs["interval_seconds"] = parse_interval(str(fields["interval"]))
        except ValueError as e:
            raise TaskSpecError(str(e))
    for key in ("enabled", "tag_filter", "description"):
        if fields.get(key) is not None:
            kwargs[key] = fields[key]
    if not kwargs:
        raise TaskSpecError("no editable fields provided")
    scheduler.update_schedule(task_id, **kwargs)
    return scheduler.store.get(task_id).to_dict()


# ---------------------------------------------------------------------------
# Widget path — reason text + session creation
# ---------------------------------------------------------------------------


def describe_create(spec: Mapping[str, Any]) -> str:
    """Plain-language card text for a create-task approval."""
    if spec.get("trigger_kind") == TRIGGER_SCHEDULE:
        if spec.get("tag_filter"):
            scope = f"devices tagged '{spec['tag_filter']}'"
        elif spec.get("device_ids"):
            scope = f"{len(spec['device_ids'])} selected device(s)"
        else:
            scope = "ALL devices"
        return (
            f"Create a RECURRING scheduled task: run '{spec.get('action_type')}' "
            f"every {spec.get('interval')} on {scope}. It will keep running "
            "unattended until removed."
        )
    return (
        f"Pre-authorize a one-shot '{spec.get('action_type')}' on device "
        f"{spec.get('device_id')} that fires automatically when it reports "
        f"'{spec.get('event')}'. Expires unused after 24h."
    )


def describe_update(task_id: str, fields: Mapping[str, Any]) -> str:
    changed = ", ".join(k for k, v in fields.items() if v is not None) or "fields"
    return f"Modify scheduled task '{task_id}' ({changed})."


def describe_delete(task: Any) -> str:
    label = getattr(task, "description", "") or getattr(task, "id", "task")
    return (
        f"Delete the scheduled task '{getattr(task, 'id', '?')}' ({label}). "
        "Whatever it was doing on its cadence stops permanently."
    )


def apply_delete_task(task_id: str, *, scheduler: Any) -> Dict[str, Any]:
    """Delete a schedule task (or cancel a still-pending detection)."""
    task = scheduler.store.get(task_id)
    if task is None:
        raise TaskSpecError(f"Task not found: {task_id}")
    if task.trigger_kind == TRIGGER_SCHEDULE:
        scheduler.remove_schedule(task_id)
        return {"deleted": task_id}
    if not scheduler.store.cancel(task_id):
        raise TaskSpecError("detection task is no longer pending")
    return {"cancelled": task_id}


def gate_task_write(
    action: str, target: str, payload: Mapping[str, Any], reason: str
) -> Dict[str, Any]:
    """Create the url_only action session and return the blocked envelope —
    identical shape to a gated VAPIX operation, so the chat approval card,
    the /confirm page, audit, and the console event notes all just work."""
    from admz import operations

    session = operations.create_action_session(
        action=action, device_id=target, payload=dict(payload), reason=reason,
    )
    env = operations.blocked_envelope(session, reason=reason)
    env["success"] = False
    return env


def _new_id() -> str:
    import uuid

    return uuid.uuid4().hex[:12]
