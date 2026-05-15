"""Tests for PlanEngine execution (create_plan is covered in test_catalog.py)."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

from admz.catalog.models import Operation
from admz.executor.base import BaseExecutor
from admz.executor.models import StepResult
from admz.plans.engine import PlanEngine
from admz.plans.models import FailurePolicy, PlanStatus


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeCatalog:
    """In-memory catalog for testing."""
    ops: Dict[str, Operation] = field(default_factory=dict)
    risks: Dict[str, str] = field(default_factory=dict)

    def get_operation(self, family: str, op_id: str) -> Optional[Operation]:
        return self.ops.get(op_id)

    def get_risk_level(self, family: str, op_id: str) -> str:
        return self.risks.get(op_id, "normal")


@dataclass
class FakeRegistry:
    devices: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    creds: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def device_exists(self, device_id: str) -> bool:
        return device_id in self.devices

    def get_device_info(self, device_id: str) -> Dict[str, Any]:
        return dict(self.devices[device_id])

    def get_credentials(self, device_id: str, account_id: str = "default", requester=None):
        return dict(self.creds.get(device_id, {"username": "x", "password": "y"}))


class RecordingExecutor(BaseExecutor):
    """Executor that records calls and returns scripted results."""

    def __init__(self):
        self.calls = []
        self.scripted_results: Dict[str, StepResult] = {}
        self.default_result_factory = lambda op, dev: StepResult(
            operation_id=op["id"],
            device_id=dev["device_id"],
            success=True,
            parsed_data="ok",
        )

    @property
    def family(self) -> str:
        return "vapix"

    async def execute(self, operation, device, credentials, params):
        self.calls.append({
            "operation_id": operation["id"],
            "device_id": device["device_id"],
            "params": dict(params),
        })
        scripted = self.scripted_results.get(operation["id"])
        if scripted:
            return scripted
        return self.default_result_factory(operation, device)


def make_op(op_id: str, cgi: str = "param.cgi", method: str = "GET") -> Operation:
    return Operation(
        id=op_id,
        cgi=cgi,
        method=method,
        risk_level="normal",
        request={"query": {"action": "list"}},
        response={"format": "text"},
        endpoint="/axis-cgi/param.cgi",
        generation="legacy-cgi",
        auth="digest",
    )


@pytest.fixture
def setup():
    catalog = FakeCatalog(
        ops={
            "param.cgi:list": make_op("param.cgi:list"),
            "param.cgi:update": make_op("param.cgi:update"),
        }
    )
    registry = FakeRegistry(
        devices={
            "cam-01": {"host": "192.168.1.10", "model": "AXIS P3245-V"},
            "cam-02": {"host": "192.168.1.11", "model": "AXIS P3245-V"},
            "cam-03": {"host": "192.168.1.12", "model": "AXIS P3245-V"},
        }
    )
    executor = RecordingExecutor()
    engine = PlanEngine(
        catalog=catalog,
        registry=registry,
        executors={"vapix": executor},
    )
    return engine, executor, catalog, registry


# ---------------------------------------------------------------------------
# Sequential execution
# ---------------------------------------------------------------------------


class TestSequentialExecution:

    @pytest.mark.asyncio
    async def test_single_step_success(self, setup):
        engine, executor, _, _ = setup
        plan = engine.create_plan(
            description="Test",
            steps=[{
                "operation_id": "param.cgi:list",
                "device_id": "cam-01",
                "params": {"group": "root"},
            }],
        )
        result = await engine.execute_plan(plan.plan_id)
        assert result.status == PlanStatus.COMPLETED
        assert len(executor.calls) == 1
        assert executor.calls[0]["device_id"] == "cam-01"

    @pytest.mark.asyncio
    async def test_multiple_steps_same_device_sequential(self, setup):
        engine, executor, _, _ = setup
        plan = engine.create_plan(
            description="Two steps",
            steps=[
                {"operation_id": "param.cgi:list", "device_id": "cam-01", "params": {}},
                {"operation_id": "param.cgi:update", "device_id": "cam-01", "params": {}},
            ],
        )
        result = await engine.execute_plan(plan.plan_id)
        assert result.status == PlanStatus.COMPLETED
        assert len(executor.calls) == 2
        # Same device → sequential, in order
        assert executor.calls[0]["operation_id"] == "param.cgi:list"
        assert executor.calls[1]["operation_id"] == "param.cgi:update"

    @pytest.mark.asyncio
    async def test_stop_on_failure(self, setup):
        engine, executor, _, _ = setup
        executor.scripted_results["param.cgi:list"] = StepResult(
            operation_id="param.cgi:list",
            device_id="cam-01",
            success=False,
            error="boom",
        )
        plan = engine.create_plan(
            description="Should stop",
            steps=[
                {"operation_id": "param.cgi:list", "device_id": "cam-01", "params": {}},
                {"operation_id": "param.cgi:update", "device_id": "cam-01", "params": {}},
            ],
            on_failure="stop",
        )
        result = await engine.execute_plan(plan.plan_id)
        assert result.status == PlanStatus.FAILED
        # Only the first call was made
        assert len(executor.calls) == 1

    @pytest.mark.asyncio
    async def test_continue_on_failure(self, setup):
        engine, executor, _, _ = setup
        executor.scripted_results["param.cgi:list"] = StepResult(
            operation_id="param.cgi:list",
            device_id="cam-01",
            success=False,
            error="boom",
        )
        plan = engine.create_plan(
            description="Should continue",
            steps=[
                {"operation_id": "param.cgi:list", "device_id": "cam-01", "params": {}},
                {"operation_id": "param.cgi:update", "device_id": "cam-01", "params": {}},
            ],
            on_failure="continue",
        )
        result = await engine.execute_plan(plan.plan_id)
        assert result.status == PlanStatus.FAILED  # one step failed
        assert len(executor.calls) == 2  # but second ran

    @pytest.mark.asyncio
    async def test_skip_dependents_when_dep_fails(self, setup):
        engine, executor, _, _ = setup
        executor.scripted_results["param.cgi:list"] = StepResult(
            operation_id="param.cgi:list",
            device_id="cam-01",
            success=False,
            error="boom",
        )
        plan = engine.create_plan(
            description="Skip dependents",
            steps=[
                {"operation_id": "param.cgi:list", "device_id": "cam-01", "params": {}},
                {"operation_id": "param.cgi:update", "device_id": "cam-01", "params": {}, "depends_on": [1]},
            ],
            on_failure="skip_dependents",
        )
        result = await engine.execute_plan(plan.plan_id)
        # Step 1 failed, step 2 should be skipped because it depends on 1
        assert len(executor.calls) == 1
        results_by_op = {r.operation_id: r for r in result.results}
        assert "param.cgi:update" in results_by_op
        assert results_by_op["param.cgi:update"].success is False
        assert "dependency" in results_by_op["param.cgi:update"].error.lower()


# ---------------------------------------------------------------------------
# Fleet parallel execution
# ---------------------------------------------------------------------------


class TestFleetParallel:

    @pytest.mark.asyncio
    async def test_multi_device_no_deps_runs_in_fleet_mode(self, setup):
        engine, executor, _, _ = setup
        plan = engine.create_plan(
            description="Fleet snapshot",
            steps=[
                {"operation_id": "param.cgi:list", "device_id": "cam-01", "params": {}},
                {"operation_id": "param.cgi:list", "device_id": "cam-02", "params": {}},
                {"operation_id": "param.cgi:list", "device_id": "cam-03", "params": {}},
            ],
        )
        result = await engine.execute_plan(plan.plan_id)
        assert result.status == PlanStatus.COMPLETED
        assert len(executor.calls) == 3
        device_ids = {c["device_id"] for c in executor.calls}
        assert device_ids == {"cam-01", "cam-02", "cam-03"}

    @pytest.mark.asyncio
    async def test_multi_device_with_deps_runs_sequential(self, setup):
        """If steps have inter-step deps, plan engine runs sequentially even
        if they target different devices."""
        engine, executor, _, _ = setup
        plan = engine.create_plan(
            description="Sequential by dependency",
            steps=[
                {"operation_id": "param.cgi:list", "device_id": "cam-01", "params": {}},
                {"operation_id": "param.cgi:list", "device_id": "cam-02", "params": {}, "depends_on": [1]},
            ],
        )
        result = await engine.execute_plan(plan.plan_id)
        assert result.status == PlanStatus.COMPLETED
        assert len(executor.calls) == 2
        # Order is sequential
        assert executor.calls[0]["device_id"] == "cam-01"
        assert executor.calls[1]["device_id"] == "cam-02"


# ---------------------------------------------------------------------------
# Plan lifecycle
# ---------------------------------------------------------------------------


class TestPlanLifecycle:

    @pytest.mark.asyncio
    async def test_execute_nonexistent_plan_raises(self, setup):
        engine, _, _, _ = setup
        with pytest.raises(ValueError):
            await engine.execute_plan("does-not-exist")

    def test_get_plan_status(self, setup):
        engine, _, _, _ = setup
        plan = engine.create_plan(
            description="Test",
            steps=[{"operation_id": "param.cgi:list", "device_id": "cam-01", "params": {}}],
        )
        status = engine.get_plan_status(plan.plan_id)
        assert status is not None
        assert status["plan_id"] == plan.plan_id

    def test_get_plan_status_missing(self, setup):
        engine, _, _, _ = setup
        assert engine.get_plan_status("nope") is None

    @pytest.mark.asyncio
    async def test_results_have_per_step_status(self, setup):
        engine, executor, _, _ = setup
        plan = engine.create_plan(
            description="Two devices",
            steps=[
                {"operation_id": "param.cgi:list", "device_id": "cam-01", "params": {}},
                {"operation_id": "param.cgi:list", "device_id": "cam-02", "params": {}},
            ],
        )
        result = await engine.execute_plan(plan.plan_id)
        assert len(result.results) == 2
        assert all(r.success for r in result.results)


# ---------------------------------------------------------------------------
# Rollback pre-read
# ---------------------------------------------------------------------------


class TestRollback:

    @pytest.mark.asyncio
    async def test_param_update_triggers_pre_read(self, setup):
        engine, executor, _, _ = setup
        plan = engine.create_plan(
            description="Update needs rollback",
            steps=[{
                "operation_id": "param.cgi:update",
                "device_id": "cam-01",
                "params": {"root.Image.I0.Resolution": "1920x1080"},
            }],
        )
        await engine.execute_plan(plan.plan_id)
        # Should see two calls: a pre-read (list) and the update
        op_ids = [c["operation_id"] for c in executor.calls]
        assert "param.cgi:list" in op_ids  # pre-read
        assert "param.cgi:update" in op_ids
