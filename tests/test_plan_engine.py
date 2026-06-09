"""Tests for PlanEngine execution (create_plan is covered in test_catalog.py)."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

from axis_api_atlas.catalog.models import Operation
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
        result = await engine.run_plan(plan.plan_id)
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
        result = await engine.run_plan(plan.plan_id)
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
        result = await engine.run_plan(plan.plan_id)
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
        result = await engine.run_plan(plan.plan_id)
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
        result = await engine.run_plan(plan.plan_id)
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
        result = await engine.run_plan(plan.plan_id)
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
        result = await engine.run_plan(plan.plan_id)
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
            await engine.run_plan("does-not-exist")

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
        result = await engine.run_plan(plan.plan_id)
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
        await engine.run_plan(plan.plan_id)
        # Should see two calls: a pre-read (list) and the update
        op_ids = [c["operation_id"] for c in executor.calls]
        assert "param.cgi:list" in op_ids  # pre-read
        assert "param.cgi:update" in op_ids


# ---------------------------------------------------------------------------
# Phase 2D: dangerous-step plan-level gate
# ---------------------------------------------------------------------------


def make_dangerous_op(op_id: str) -> Operation:
    return Operation(
        id=op_id,
        cgi="factorydefault.cgi",
        method="GET",
        risk_level="dangerous",
        request={"query": {}},
        response={"format": "text"},
        endpoint="/axis-cgi/factorydefault.cgi",
        generation="legacy-cgi",
        auth="digest",
    )


# --- plan-gate test scaffolding (decoupled from the DB) -------------------

def _default_levels(risk):
    """The shipped default risk→level mapping, as a pure function."""
    return {
        "read-only": "none",
        "normal": "none",
        "service-affecting": "llm_confirm",
        "dangerous": "url_and_password",
    }.get(risk, "none")


class _FakeSession:
    def __init__(self, token, risk_level="", confirmation_level=""):
        self.token = token
        self.risk_level = risk_level
        self.confirmation_level = confirmation_level


class _FakeStore:
    """In-memory stand-in for ConfirmStore so plan-gate tests touch no DB."""

    def __init__(self):
        self.created = []
        self._by_plan = {}

    def create_session(self, **kw):
        session = _FakeSession(
            "plantoken1234567890123456789012",
            risk_level=kw.get("risk_level", ""),
            confirmation_level=kw.get("confirmation_level", ""),
        )
        self.created.append(kw)
        self._by_plan[kw.get("plan_id", "")] = session
        return session

    def get_session_by_plan(self, plan_id):
        return self._by_plan.get(plan_id)


class TestPlanGate:
    """Plans go through the SAME configurable per-risk confirmation gate as
    single ops (admz.operations.execute_gated_plan). The strictest step level
    decides: 'none' runs; 'llm_confirm' needs confirm_dangerous=True; 'url_*'
    needs deterministic web/widget approval (a blocked envelope, never run by
    a boolean)."""

    def _setup_with_dangerous_op(self):
        catalog = FakeCatalog(
            ops={
                "param.cgi:list": make_op("param.cgi:list"),
                "factorydefault.cgi:reset": make_dangerous_op(
                    "factorydefault.cgi:reset"
                ),
            },
            risks={
                "param.cgi:list": "read-only",
                "factorydefault.cgi:reset": "dangerous",
            },
        )
        registry = FakeRegistry(
            devices={"cam-01": {"host": "192.168.1.10", "model": "AXIS P3245-V"}}
        )
        executor = RecordingExecutor()
        engine = PlanEngine(
            catalog=catalog,
            registry=registry,
            executors={"vapix": executor},
        )
        return engine, executor

    def test_resolve_plan_confirmation_takes_max(self, monkeypatch):
        from types import SimpleNamespace

        from admz import operations
        monkeypatch.setattr(operations, "resolve_confirmation", _default_levels)
        step = lambda risk: SimpleNamespace(risk_level=risk)

        assert operations.resolve_plan_confirmation([]) == "none"
        assert operations.resolve_plan_confirmation([step("read-only")]) == "none"
        assert operations.resolve_plan_confirmation(
            [step("read-only"), step("service-affecting")]
        ) == "llm_confirm"
        assert operations.resolve_plan_confirmation(
            [step("service-affecting"), step("dangerous")]
        ) == "url_and_password"

    @pytest.mark.asyncio
    async def test_dangerous_plan_blocks_for_web_approval(self, monkeypatch):
        """Default config: dangerous → url_and_password. A boolean is NOT
        enough — even confirm_dangerous=True returns a blocked envelope that
        must be approved at the confirm_url. (Option A: same gate as single
        ops; closes the route-through-a-plan-for-a-weaker-gate hole.)"""
        from admz import operations
        monkeypatch.setattr(operations, "resolve_confirmation", _default_levels)
        engine, executor = self._setup_with_dangerous_op()
        plan = engine.create_plan(
            description="Factory reset",
            steps=[{
                "operation_id": "factorydefault.cgi:reset",
                "device_id": "cam-01",
                "params": {},
            }],
        )
        store = _FakeStore()
        result = await operations.execute_gated_plan(
            engine, plan.plan_id, store=store, confirm_dangerous=True
        )
        assert result["blocked"] is True
        assert result["confirmation_level"] == "url_and_password"
        assert "/confirm/" in result["confirm_url"]
        assert executor.calls == []          # never ran
        assert store.created                  # a plan confirm session was made

    @pytest.mark.asyncio
    async def test_dangerous_plan_runs_when_configured_llm_confirm(self, monkeypatch):
        """If the operator lowers dangerous → llm_confirm, confirm_dangerous=True
        runs it (the back-compat tier); without it, blocked with retry_with."""
        from admz import operations
        monkeypatch.setattr(
            operations, "resolve_confirmation",
            lambda r: "llm_confirm" if r == "dangerous" else "none",
        )
        engine, executor = self._setup_with_dangerous_op()
        plan = engine.create_plan(
            description="Factory reset",
            steps=[{
                "operation_id": "factorydefault.cgi:reset",
                "device_id": "cam-01",
                "params": {},
            }],
        )
        blocked = await operations.execute_gated_plan(
            engine, plan.plan_id, store=_FakeStore()
        )
        assert blocked["blocked"] is True
        assert blocked["retry_with"] == {"confirm_dangerous": True}
        assert executor.calls == []

        result = await operations.execute_gated_plan(
            engine, plan.plan_id, store=_FakeStore(), confirm_dangerous=True
        )
        assert result["success"] is True
        assert len(executor.calls) == 1

    @pytest.mark.asyncio
    async def test_non_dangerous_plan_runs_without_confirm(self, monkeypatch):
        from admz import operations
        monkeypatch.setattr(operations, "resolve_confirmation", _default_levels)
        engine, executor = self._setup_with_dangerous_op()
        plan = engine.create_plan(
            description="Read only",
            steps=[{
                "operation_id": "param.cgi:list",
                "device_id": "cam-01",
                "params": {},
            }],
        )
        result = await operations.execute_gated_plan(
            engine, plan.plan_id, store=_FakeStore()
        )
        assert result["success"] is True
        assert len(executor.calls) == 1

    @pytest.mark.asyncio
    async def test_mixed_plan_gated_by_dangerous_step(self, monkeypatch):
        from admz import operations
        monkeypatch.setattr(operations, "resolve_confirmation", _default_levels)
        engine, executor = self._setup_with_dangerous_op()
        plan = engine.create_plan(
            description="Read then reset",
            steps=[
                {
                    "operation_id": "param.cgi:list",
                    "device_id": "cam-01",
                    "params": {},
                },
                {
                    "operation_id": "factorydefault.cgi:reset",
                    "device_id": "cam-01",
                    "params": {},
                },
            ],
        )
        # The read-only step doesn't lower the bar — the dangerous step gates
        # the whole plan to url_and_password.
        result = await operations.execute_gated_plan(
            engine, plan.plan_id, store=_FakeStore()
        )
        assert result["blocked"] is True
        assert result["confirmation_level"] == "url_and_password"
        assert executor.calls == []


# ---------------------------------------------------------------------------
# Phase 3C: FailurePolicy.CONTINUE actually runs dependents
# ---------------------------------------------------------------------------


class TestContinuePolicyRunsDependents:
    """Regression: before Phase 3C, FailurePolicy.CONTINUE silently
    behaved like SKIP_DEPENDENTS — when a step failed, downstream
    dependents were skipped instead of attempted. The catalog
    contract says CONTINUE means "run everything"; this test verifies
    we now honor that."""

    @pytest.mark.asyncio
    async def test_continue_attempts_dependent_after_failure(self, setup):
        engine, executor, _, _ = setup
        # Step 1 fails
        executor.scripted_results["param.cgi:list"] = StepResult(
            operation_id="param.cgi:list",
            device_id="cam-01",
            success=False,
            error="boom",
        )
        # Step 2 will succeed (scripted_results miss → default factory)
        plan = engine.create_plan(
            description="Continue past dep failure",
            steps=[
                {"operation_id": "param.cgi:list", "device_id": "cam-01", "params": {}},
                {
                    "operation_id": "param.cgi:update",
                    "device_id": "cam-01",
                    "params": {},
                    "depends_on": [1],
                },
            ],
            on_failure="continue",
        )
        result = await engine.run_plan(plan.plan_id)

        # The dependent step MUST have been attempted (not skipped)
        assert len(executor.calls) == 2, (
            "step 2 should have been attempted under CONTINUE; was it "
            "silently skipped by the old dependency check?"
        )
        results_by_op = {r.operation_id: r for r in result.results}
        # Step 1: failed (scripted)
        assert results_by_op["param.cgi:list"].success is False
        # Step 2: succeeded (no error from the default factory)
        assert results_by_op["param.cgi:update"].success is True
        # Importantly: step 2's error must NOT mention "dependency"
        # (i.e. it wasn't skipped — it actually ran)
        if results_by_op["param.cgi:update"].error:
            assert "dependency" not in results_by_op["param.cgi:update"].error.lower()

    @pytest.mark.asyncio
    async def test_skip_dependents_still_skips_dependent_on_failure(self, setup):
        """Companion test: under SKIP_DEPENDENTS, the dependent must
        still be skipped (we didn't break that behavior in fixing CONTINUE)."""
        engine, executor, _, _ = setup
        executor.scripted_results["param.cgi:list"] = StepResult(
            operation_id="param.cgi:list",
            device_id="cam-01",
            success=False,
            error="boom",
        )
        plan = engine.create_plan(
            description="Skip on dep failure",
            steps=[
                {"operation_id": "param.cgi:list", "device_id": "cam-01", "params": {}},
                {
                    "operation_id": "param.cgi:update",
                    "device_id": "cam-01",
                    "params": {},
                    "depends_on": [1],
                },
            ],
            on_failure="skip_dependents",
        )
        result = await engine.run_plan(plan.plan_id)
        # Step 2 should NOT have been called
        assert len(executor.calls) == 1
        results_by_op = {r.operation_id: r for r in result.results}
        assert "dependency" in results_by_op["param.cgi:update"].error.lower()
