"""
Plan engine — validates, executes, and manages execution plans.
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from axis_api_atlas.catalog.loader import CatalogLoader
from admz.executor.base import BaseExecutor
from admz.executor.models import StepResult
from admz.device_registry import DeviceRegistry
from admz.plans.models import (
    ExecutionPlan,
    FailurePolicy,
    PlanStatus,
    PlanStep,
)

logger = logging.getLogger(__name__)

# Severity order for risk levels — used to honor a step dict's declared
# risk_level as a floor over the catalog's (raise-only).
_RISK_ORDER = {
    "read-only": 0,
    "normal": 1,
    "service-affecting": 2,
    "dangerous": 3,
}


class PlanEngine:
    """
    Validates and executes multi-step plans.

    Handles dependency tracking, failure policies, pre-read for
    rollback, and parallel fleet execution.
    """

    def __init__(
        self,
        catalog: CatalogLoader,
        registry: DeviceRegistry,
        executors: Dict[str, BaseExecutor],
    ):
        self.catalog = catalog
        self.registry = registry
        self.executors = executors
        self._plans: Dict[str, ExecutionPlan] = {}

    def create_plan(
        self,
        description: str,
        steps: List[Dict[str, Any]],
        on_failure: str = "stop",
        created_by: str = "",
    ) -> ExecutionPlan:
        """
        Validate and store an execution plan.

        Does NOT execute — returns the plan for user review.

        Args:
            description: Human-readable plan description.
            steps: List of step dicts, each with:
                - operation_id: str
                - device_id: str
                - params: dict
                - description: str (optional)
                - depends_on: list of step numbers (optional)
                - family: str (default "vapix")
                - risk_level: str (optional) — a floor over the catalog's
                  risk for this operation. It can only RAISE the risk
                  (ADR-0034: restore plans mark every step
                  service-affecting so the plan always gates at the
                  approval widget); a declared level below the catalog's
                  is ignored.
            on_failure: "stop" | "skip_dependents" | "continue"
            created_by: Who created the plan.

        Returns:
            ExecutionPlan with status=pending_approval.

        Raises:
            ValueError: If validation fails.
        """
        plan_steps = []
        risk_counts: Dict[str, int] = {}
        validation_errors = []

        for i, step_data in enumerate(steps):
            step_num = i + 1
            op_id = step_data.get("operation_id", "")
            device_id = step_data.get("device_id", "")
            family = step_data.get("family", "vapix")
            params = step_data.get("params", {})

            # Validate operation exists in catalog
            operation = self.catalog.get_operation(family, op_id)
            if not operation:
                validation_errors.append(
                    f"Step {step_num}: operation '{op_id}' not found in "
                    f"{family} catalog"
                )
                risk_level = "normal"
            else:
                risk_level = operation.risk_level

            # Raise-only risk floor (ADR-0034): a declared per-step
            # risk_level can escalate the catalog risk so the plan-level
            # confirmation gate engages, but can never soften it. Unknown
            # strings rank -1 and are ignored.
            declared = str(step_data.get("risk_level", "") or "")
            if _RISK_ORDER.get(declared, -1) > _RISK_ORDER.get(risk_level, 0):
                risk_level = declared

            # Validate device exists in registry
            if not self.registry.device_exists(device_id):
                validation_errors.append(
                    f"Step {step_num}: device '{device_id}' not found in registry"
                )

            # Validate executor exists for this family
            if family not in self.executors:
                validation_errors.append(
                    f"Step {step_num}: no executor for family '{family}'"
                )

            # Validate dependencies reference valid step numbers
            depends = step_data.get("depends_on", [])
            for dep in depends:
                if dep < 1 or dep >= step_num:
                    validation_errors.append(
                        f"Step {step_num}: invalid dependency on step {dep}"
                    )

            risk_counts[risk_level] = risk_counts.get(risk_level, 0) + 1

            plan_steps.append(PlanStep(
                step_number=step_num,
                operation_id=op_id,
                device_id=device_id,
                params=params,
                description=step_data.get("description", ""),
                risk_level=risk_level,
                family=family,
                depends_on=depends,
            ))

        if validation_errors:
            raise ValueError(
                "Plan validation failed:\n" + "\n".join(validation_errors)
            )

        try:
            failure_policy = FailurePolicy(on_failure)
        except ValueError:
            failure_policy = FailurePolicy.STOP

        plan = ExecutionPlan(
            description=description,
            steps=plan_steps,
            on_failure=failure_policy,
            risk_summary=risk_counts,
            created_by=created_by,
        )

        self._plans[plan.plan_id] = plan
        return plan

    async def run_plan(self, plan_id: str) -> ExecutionPlan:
        """Execute an approved plan's steps — **un-gated**.

        The confirmation gate now lives in
        :func:`admz.operations.execute_gated_plan`, which computes the plan's
        required confirmation level (the strictest level across its steps,
        per the configurable per-risk policy) and either calls this to run the
        plan or returns a blocked envelope for web/widget approval. This method
        just runs the steps; callers that haven't been gated MUST go through
        ``execute_gated_plan`` first.

        Runs all steps respecting dependencies and failure policy; groups steps
        by device for parallel execution when possible.

        Raises:
            ValueError: if the plan id is unknown or the plan is not in an
                executable state.
        """
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")

        if plan.status not in (PlanStatus.PENDING_APPROVAL, PlanStatus.APPROVED):
            raise ValueError(
                f"Plan {plan_id} is in state {plan.status.value}, "
                "cannot execute"
            )

        plan.status = PlanStatus.EXECUTING
        plan.results = []
        rollback_data: Dict[int, Dict[str, str]] = {}

        # Check if all steps target different devices (fleet mode)
        devices_in_plan = set(s.device_id for s in plan.steps)
        has_dependencies = any(s.depends_on for s in plan.steps)

        if len(devices_in_plan) > 1 and not has_dependencies:
            # Fleet mode: run devices in parallel
            await self._execute_fleet_parallel(plan, rollback_data)
        else:
            # Sequential mode
            await self._execute_sequential(plan, rollback_data)

        # Build rollback steps from captured data
        plan.rollback_steps = self._build_rollback_steps(plan, rollback_data)

        if all(r.success for r in plan.results):
            plan.status = PlanStatus.COMPLETED
        else:
            plan.status = PlanStatus.FAILED

        return plan

    async def _execute_sequential(
        self,
        plan: ExecutionPlan,
        rollback_data: Dict[int, Dict[str, str]],
    ) -> None:
        """Execute steps sequentially, honoring failure policy.

        Three failure policies (Phase 3C fix):

        STOP — break on first failure. Dependents never run, but that's
          implicit because the loop terminates.

        SKIP_DEPENDENTS — continue to subsequent steps, but skip any
          step whose dependency tree contains a failure. Useful for
          large plans where you want all the independent work done
          even if one branch fails.

        CONTINUE — run every step regardless. Dependent steps may
          fail for the same reason their parent failed, but the
          attempt is made. Useful for "best-effort" cleanup plans.
        """
        failed_steps: set = set()

        for step in plan.steps:
            # Phase 3C: only enforce the dep-met check under STOP /
            # SKIP_DEPENDENTS. Under CONTINUE we run every step.
            if plan.on_failure != FailurePolicy.CONTINUE:
                if not self._dependencies_met(step, failed_steps, plan):
                    plan.results.append(StepResult(
                        operation_id=step.operation_id,
                        device_id=step.device_id,
                        success=False,
                        error="Skipped: dependency failed",
                    ))
                    failed_steps.add(step.step_number)
                    continue

            # Pre-read for rollback if this is a write operation
            pre_read = await self._pre_read_for_rollback(step)
            if pre_read:
                rollback_data[step.step_number] = pre_read

            # Execute the step
            result = await self._execute_step(step)
            plan.results.append(result)

            if not result.success:
                failed_steps.add(step.step_number)
                if plan.on_failure == FailurePolicy.STOP:
                    logger.warning(
                        "Plan %s: stopping at step %d due to failure",
                        plan.plan_id, step.step_number,
                    )
                    break

    async def _execute_fleet_parallel(
        self,
        plan: ExecutionPlan,
        rollback_data: Dict[int, Dict[str, str]],
    ) -> None:
        """Execute steps grouped by device, devices in parallel."""
        # Group steps by device
        by_device: Dict[str, List[PlanStep]] = defaultdict(list)
        for step in plan.steps:
            by_device[step.device_id].append(step)

        # Create a task for each device's steps
        async def run_device_steps(
            device_id: str, steps: List[PlanStep]
        ) -> List[StepResult]:
            results = []
            for step in steps:
                pre_read = await self._pre_read_for_rollback(step)
                if pre_read:
                    rollback_data[step.step_number] = pre_read

                result = await self._execute_step(step)
                results.append(result)

                if not result.success and plan.on_failure == FailurePolicy.STOP:
                    break
            return results

        # Run all devices in parallel
        device_tasks = [
            run_device_steps(device_id, steps)
            for device_id, steps in by_device.items()
        ]
        all_results = await asyncio.gather(*device_tasks, return_exceptions=True)

        # Flatten results, maintaining step order
        result_map: Dict[str, List[StepResult]] = {}
        for (device_id, _), results in zip(by_device.items(), all_results):
            if isinstance(results, Exception):
                logger.exception(
                    "Fleet execution failed for device %s", device_id
                )
                result_map[device_id] = []
            else:
                result_map[device_id] = results

        # Flatten in original step order
        for step in plan.steps:
            device_results = result_map.get(step.device_id, [])
            if device_results:
                plan.results.append(device_results.pop(0))
            else:
                plan.results.append(StepResult(
                    operation_id=step.operation_id,
                    device_id=step.device_id,
                    success=False,
                    error="Device execution failed",
                ))

    async def _execute_step(self, step: PlanStep) -> StepResult:
        """Execute a single plan step via the shared execution tail.

        The tail (load op → pick executor → fetch device+creds → execute) is
        the same code single-op execution uses; failures are mapped back to a
        ``StepResult`` so the plan's failure-policy logic is unchanged.
        """
        from admz import operations

        try:
            result = await operations.run_execution_tail(
                device_id=step.device_id,
                operation_id=step.operation_id,
                family=step.family,
                params=step.params,
                catalog=self.catalog,
                registry=self.registry,
                executors=self.executors,
            )
        except operations.NoExecutorError:
            return StepResult(
                operation_id=step.operation_id,
                device_id=step.device_id,
                success=False,
                error=f"No executor for family '{step.family}'",
            )
        except operations.OperationNotFoundError:
            return StepResult(
                operation_id=step.operation_id,
                device_id=step.device_id,
                success=False,
                error=f"Operation '{step.operation_id}' not found in catalog",
            )
        except Exception as e:  # device lookup / unexpected
            return StepResult(
                operation_id=step.operation_id,
                device_id=step.device_id,
                success=False,
                error=f"Failed to execute step: {e}",
            )

        logger.info(
            "Step %d (%s on %s): %s [%.0fms]",
            step.step_number,
            step.operation_id,
            step.device_id,
            "OK" if result.success else f"FAIL: {result.error}",
            result.duration_ms or 0,
        )

        return result

    async def _pre_read_for_rollback(
        self, step: PlanStep
    ) -> Optional[Dict[str, str]]:
        """
        Read current values before a write, for rollback purposes.

        Only applies to param.cgi:update operations.
        """
        if step.operation_id != "param.cgi:update":
            return None

        # Figure out which parameter groups to read
        groups_to_read = set()
        for key in step.params:
            # Extract the group from param keys like "root.Image.I0.Resolution"
            parts = key.split(".")
            if len(parts) >= 2 and parts[0] == "root":
                groups_to_read.add(parts[1])

        if not groups_to_read:
            return None

        # Read current values
        current_values: Dict[str, str] = {}
        for group in groups_to_read:
            read_step = PlanStep(
                step_number=0,
                operation_id="param.cgi:list",
                device_id=step.device_id,
                params={"action": "list", "group": group},
                family=step.family,
            )
            result = await self._execute_step(read_step)
            if result.success and result.parsed_data:
                # Parse "key=value" lines
                for line in str(result.parsed_data).split("\n"):
                    line = line.strip()
                    if "=" in line and line.startswith("root."):
                        k, v = line.split("=", 1)
                        # Only save values for keys we're about to change
                        if k in step.params:
                            current_values[k] = v

        return current_values if current_values else None

    def _dependencies_met(
        self, step: PlanStep, failed_steps: set, plan: ExecutionPlan
    ) -> bool:
        """Check if all dependencies of a step have succeeded."""
        if not step.depends_on:
            return True

        for dep_num in step.depends_on:
            if dep_num in failed_steps:
                return False

        return True

    def _build_rollback_steps(
        self,
        plan: ExecutionPlan,
        rollback_data: Dict[int, Dict[str, str]],
    ) -> List[PlanStep]:
        """Build rollback steps from pre-read data (in reverse order)."""
        rollback_steps = []
        step_num = 1

        # Iterate completed steps in reverse
        for i in range(len(plan.results) - 1, -1, -1):
            result = plan.results[i]
            if not result.success:
                continue

            original_step = plan.steps[i]
            pre_read = rollback_data.get(original_step.step_number)
            if not pre_read:
                continue

            rollback_steps.append(PlanStep(
                step_number=step_num,
                operation_id=original_step.operation_id,
                device_id=original_step.device_id,
                params=pre_read,
                description=f"Revert step {original_step.step_number}: "
                            f"{original_step.description}",
                risk_level="normal",
                family=original_step.family,
            ))
            step_num += 1

        return rollback_steps

    # ------------------------------------------------------------------
    # Plan management
    # ------------------------------------------------------------------

    def register_plan(self, plan: ExecutionPlan) -> None:
        """Register an externally-constructed plan so run_plan can find it.

        Used by ``admz.operations`` to install a plan reconstructed from a
        confirm session's serialized steps when the approving process is not
        the one that created the plan (C-1 cross-process approval).
        """
        self._plans[plan.plan_id] = plan

    def get_plan(self, plan_id: str) -> Optional[ExecutionPlan]:
        """Get a plan by ID."""
        return self._plans.get(plan_id)

    def get_plan_status(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get plan status summary."""
        plan = self._plans.get(plan_id)
        if not plan:
            return None

        completed = len(plan.results)
        total = len(plan.steps)

        return {
            "plan_id": plan_id,
            "status": plan.status.value,
            "progress": f"{completed}/{total}",
            "results_so_far": [
                {
                    "step": i + 1,
                    "operation_id": r.operation_id,
                    "device_id": r.device_id,
                    "success": r.success,
                    "error": r.error,
                }
                for i, r in enumerate(plan.results)
            ],
            "errors": [
                {"step": i + 1, "error": r.error}
                for i, r in enumerate(plan.results)
                if not r.success
            ],
        }

    def list_plans(self) -> List[Dict[str, Any]]:
        """List all plans with summary info."""
        return [
            {
                "plan_id": p.plan_id,
                "description": p.description,
                "status": p.status.value,
                "step_count": len(p.steps),
                "created_at": p.created_at.isoformat(),
            }
            for p in self._plans.values()
        ]
