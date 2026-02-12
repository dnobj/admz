"""
Data models for execution plans.
"""

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from admz.executor.models import StepResult


class PlanStatus(enum.Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FailurePolicy(enum.Enum):
    STOP = "stop"
    SKIP_DEPENDENTS = "skip_dependents"
    CONTINUE = "continue"


@dataclass
class PlanStep:
    """One operation in an execution plan."""

    step_number: int
    operation_id: str
    device_id: str
    params: Dict[str, str]
    description: str = ""
    risk_level: str = "normal"
    family: str = "vapix"
    depends_on: List[int] = field(default_factory=list)
    condition: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "operation_id": self.operation_id,
            "device_id": self.device_id,
            "params": self.params,
            "description": self.description,
            "risk_level": self.risk_level,
            "family": self.family,
            "depends_on": self.depends_on,
        }


@dataclass
class ExecutionPlan:
    """A batch of operations approved for autonomous execution."""

    plan_id: str = field(default_factory=lambda: f"plan-{uuid.uuid4().hex[:12]}")
    description: str = ""
    steps: List[PlanStep] = field(default_factory=list)
    on_failure: FailurePolicy = FailurePolicy.STOP
    status: PlanStatus = PlanStatus.PENDING_APPROVAL
    risk_summary: Dict[str, int] = field(default_factory=dict)
    results: List[StepResult] = field(default_factory=list)
    rollback_steps: List[PlanStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    created_by: str = ""

    def to_summary(self) -> Dict[str, Any]:
        """Generate a summary dict suitable for LLM presentation."""
        step_summaries = []
        for step in self.steps:
            summary = {
                "step": step.step_number,
                "operation": step.operation_id,
                "device": step.device_id,
                "risk": step.risk_level,
                "description": step.description,
            }
            if step.depends_on:
                summary["depends_on"] = step.depends_on
            step_summaries.append(summary)

        return {
            "plan_id": self.plan_id,
            "description": self.description,
            "status": self.status.value,
            "step_count": len(self.steps),
            "risk_summary": self.risk_summary,
            "on_failure": self.on_failure.value,
            "steps": step_summaries,
            "dangerous_steps": [
                s.to_dict() for s in self.steps if s.risk_level == "dangerous"
            ],
        }

    def to_results(self) -> Dict[str, Any]:
        """Generate a results dict after execution."""
        succeeded = sum(1 for r in self.results if r.success)
        failed = sum(1 for r in self.results if not r.success and r.error)
        skipped = len(self.steps) - len(self.results)

        result_summaries = []
        for r in self.results:
            result_summaries.append({
                "operation_id": r.operation_id,
                "device_id": r.device_id,
                "success": r.success,
                "error": r.error,
                "duration_ms": r.duration_ms,
                "warnings": r.warnings,
            })

        return {
            "plan_id": self.plan_id,
            "status": self.status.value,
            "steps_total": len(self.steps),
            "steps_succeeded": succeeded,
            "steps_failed": failed,
            "steps_skipped": skipped,
            "results": result_summaries,
            "rollback_available": len(self.rollback_steps) > 0,
        }
