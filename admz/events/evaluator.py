"""Event-pattern detection evaluator (ADR-0041 layer 3).

Wired as the ingest supervisor's ``on_event`` callback: for every live event it
checks the enabled :class:`EventDetection` rules and, on a match past the rule's
cooldown, fires the rule's action **asynchronously** (so a slow action never
stalls the event stream) — reusing the task action-handlers + the autonomous
fire-and-audit pattern from the health sweep. Service-affecting actions only fire
for a rule whose ``pre_authorized`` flag is set.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List

from admz.events.detections import (
    DetectionStore, EventDetection, SERVICE_AFFECTING_ACTIONS, detection_store,
)

logger = logging.getLogger(__name__)


class DetectionEvaluator:
    def __init__(self, *, registry: Any, store: DetectionStore = None):
        self.registry = registry
        self.store = store or detection_store
        self._rules: List[EventDetection] = []
        self._rules_version = -1
        self._last_fired: Dict[str, int] = {}   # rule id → epoch ms (in-process cooldown)
        self._tags_cache: Dict[str, list] = {}

    # ----- rule cache -----
    def _refresh(self) -> None:
        if self.store.version != self._rules_version:
            self._rules = self.store.list(enabled_only=True)
            self._rules_version = self.store.version
            self._tags_cache.clear()

    def _device_tags(self, device_id: str) -> list:
        if device_id in self._tags_cache:
            return self._tags_cache[device_id]
        tags: list = []
        try:
            info = self.registry.get_device_info(device_id) or {}
            tags = info.get("tags") or []
        except Exception:  # noqa: BLE001
            tags = []
        self._tags_cache[device_id] = tags
        return tags

    # ----- matching -----
    def _matches(self, rule: EventDetection, rec: Dict[str, Any]) -> bool:
        if rec.get("source") != rule.source:
            return False
        did = rec.get("device_id")
        if rule.device_id:
            if did != rule.device_id:
                return False
        elif rule.tag:
            if rule.tag not in self._device_tags(did):
                return False
        m = rule.match or {}
        data = rec.get("data") or {}
        if m.get("category") and data.get("category") != m["category"]:
            return False
        if m.get("topic") and str(m["topic"]).lower() not in (rec.get("type") or "").lower():
            return False
        cond = m.get("condition") or {}
        key = cond.get("key")
        if key:
            inner = data.get("data") or {}
            op = (cond.get("op") or "eq").lower()
            if op == "exists":
                if key not in inner:
                    return False
            else:
                val, target = inner.get(key), cond.get("value")
                if op == "ne":
                    if str(val) == str(target):
                        return False
                elif str(val) != str(target):  # eq (default)
                    return False
        return True

    # ----- evaluate (on_event hook) -----
    async def evaluate(self, rec: Dict[str, Any]) -> None:
        self._refresh()
        if not self._rules:
            return
        now_ms = int(time.time() * 1000)
        for rule in self._rules:
            try:
                if not self._matches(rule, rec):
                    continue
                cd = rule.cooldown_seconds or 0
                if cd and (now_ms - self._last_fired.get(rule.id, 0)) < cd * 1000:
                    continue
                if rule.action_type in SERVICE_AFFECTING_ACTIONS and not rule.pre_authorized:
                    continue  # autonomous service-affecting action needs explicit pre-auth
                self._last_fired[rule.id] = now_ms  # optimistic — debounce rapid repeats
                asyncio.create_task(self._fire(rule, rec, now_ms))
            except Exception:  # noqa: BLE001 — one bad rule must not break the stream
                logger.debug("detection match error for rule %s", rule.id, exc_info=True)

    async def _fire(self, rule: EventDetection, rec: Dict[str, Any], now_ms: int) -> None:
        from types import SimpleNamespace

        from admz.audit import record_event
        from admz.tasks.handlers import execute_task_action
        from admz.tasks.store import Task

        did = rec.get("device_id") or ""
        principal = SimpleNamespace(name=f"detection:{rule.name or rule.id}", source="event-trigger")
        task = Task(
            id=f"det-{rule.id}",
            description=rule.name or "detection",
            action_type=rule.action_type,
            action_params=dict(rule.action_params or {}),
            device_id=did,
            device_ids=[did] if did else None,
            tag_filter=rule.tag,
        )
        try:
            result = await execute_task_action(task)
            ok = bool(result.get("success", True))
            err = "" if ok else str(result.get("error") or result.get("summary") or "")[:200]
            self.store.record_fire(rule.id, now_ms, err)
            record_event(
                principal, "detection.fired" if ok else "detection.failed",
                resource=f"device:{did}", success=ok, error_message=err,
                details={"rule": rule.id, "name": rule.name, "action": rule.action_type,
                         "topic": rec.get("type"), "event_id": rec.get("id"),
                         "summary": result.get("summary")},
            )
        except Exception as exc:  # noqa: BLE001
            self.store.record_fire(rule.id, now_ms, str(exc)[:200])
            try:
                record_event(principal, "detection.failed", resource=f"device:{did}",
                             success=False, error_message=str(exc)[:200],
                             details={"rule": rule.id, "action": rule.action_type})
            except Exception:  # noqa: BLE001
                pass
            logger.warning("detection %s fire failed: %s", rule.id, exc)
