"""Event schedules via the ``event-schedules`` config-rest API (v2beta).

Schedules (the "Weekends"/"Office Hours" iCal windows action rules reference)
live only behind ``/config/rest/event-schedules/v2beta`` — no param.cgi
presence. Serialized as a dict keyed by the stable schedule ``id`` (the
ActionRules list-reshape pattern), so drift shows per-schedule changes.

Revert = make live match baseline, per schedule:
  * changed live            -> updateSchedule with the baseline fields
  * deleted live            -> createSchedule from the baseline entry
  * ADDED live (no baseline)-> deleteSchedule — that *is* revert; the plan
    step says so explicitly and the whole plan is widget-gated (ADR-0034).

Live shape (Q3538, AXIS OS 12): list of {id, name, schedule, scheduleType}.
Config-rest write bodies are {"data": <entity>}.
"""

from typing import Any, Dict, List

from admz.snapshot.facets.base import (
    DeviceCriteria,
    FacetAdapter,
    ReadSpec,
    register_facet,
)

_FIELDS = ("name", "schedule", "scheduleType")


def _schedules(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, list):
        return [s for s in raw if isinstance(s, dict)]
    if isinstance(raw, dict):  # tolerate {"data": [...]} / {"schedules": [...]}
        for key in ("data", "schedules"):
            inner = raw.get(key)
            if isinstance(inner, list):
                return [s for s in inner if isinstance(s, dict)]
    return []


@register_facet
class EventSchedulesFacet(FacetAdapter):
    NAME = "event_schedules"

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def applies_to(self) -> List[DeviceCriteria]:
        # Beta config-rest API — AXIS OS 12+ (same gate as action_rules).
        return [DeviceCriteria(families=["vapix"], min_firmware="12")]

    @property
    def extra_read_ops(self) -> List[ReadSpec]:
        return [ReadSpec(
            operation_id="event-schedules:listSchedules",
            result_key="event_schedules",
        )]

    @property
    def write_ops(self) -> List[str]:
        return [
            "event-schedules:createSchedule",
            "event-schedules:updateSchedule",
            "event-schedules:deleteSchedule",
        ]

    @property
    def restore_order(self) -> int:
        return 65  # before action_rules (70), which may reference schedules

    def serialize(self, raw_responses: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for i, sched in enumerate(_schedules(raw_responses.get("event_schedules"))):
            sid = str(sched.get("id") or i)
            out[sid] = {k: sched[k] for k in _FIELDS if k in sched}
        return out

    def op_revertable(self, path: str) -> bool:
        return True  # every schedule field reverts via update/create/delete

    @staticmethod
    def _sid_of(path: str) -> str:
        # Schedule ids CONTAIN dots ("com.axis.schedules.weekends"), so the id
        # can't be split off the flattened path naively — strip the known
        # trailing field name instead.
        for f in _FIELDS:
            suffix = "." + f
            if path.endswith(suffix):
                return path[: -len(suffix)]
        return path

    def build_revert_ops(self, drifted, baseline_doc):
        # Group the drifted flattened paths ("<id>.<field>", or "<id>" when a
        # whole entry appeared/vanished) by schedule id, then decide per id.
        by_id: Dict[str, List[tuple]] = {}
        for path, expected, actual in drifted:
            sid = self._sid_of(path)
            by_id.setdefault(sid, []).append((path, expected, actual))

        steps: List[Dict[str, Any]] = []
        for sid in sorted(by_id):
            baseline_entry = baseline_doc.get(sid)
            if baseline_entry is None:
                # Not in baseline -> the schedule was ADDED live: delete it.
                steps.append({
                    "operation_id": "event-schedules:deleteSchedule",
                    "params": {"id1": sid},
                    "description": f"Delete live-added schedule '{sid}' (not in baseline)",
                })
                continue
            data = {"id": sid, **{k: v for k, v in baseline_entry.items()
                                  if k in _FIELDS}}
            deleted_live = all(str(a) == "<missing>" for _, _, a in by_id[sid])
            if deleted_live:
                steps.append({
                    "operation_id": "event-schedules:createSchedule",
                    "params": {"data": data},
                    "description": f"Re-create schedule '{sid}' from baseline",
                })
            else:
                steps.append({
                    "operation_id": "event-schedules:updateSchedule",
                    "params": {"id1": sid, "data": data},
                    "description": f"Restore baseline schedule '{sid}'",
                })
        return steps or None

    def deserialize(self, yaml_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Full restore-from-commit: idempotent updates for every baseline
        # schedule (extras added live are NOT deleted here — same additive
        # posture as full param restore; accept absorbs them).
        calls: List[Dict[str, Any]] = []
        for sid, entry in sorted((yaml_doc or {}).items()):
            if not isinstance(entry, dict):
                continue
            data = {"id": sid, **{k: v for k, v in entry.items() if k in _FIELDS}}
            calls.append({
                "operation_id": "event-schedules:updateSchedule",
                "params": {"id1": sid, "data": data},
            })
        return calls
