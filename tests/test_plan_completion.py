"""Plan-completion hook (ADR-0048 wizard foundation).

The declarative ``on_complete`` payload dispatched at the tail of run_plan:
covers direct dispatch (COMPLETED + FAILED), the never-raises contract (unknown
handler / bad module / handler exception → note), the summary/results
serialization, the cross-process round-trip via ``_register_plan_from_session``,
and end-to-end dispatch through a real ``PlanEngine.run_plan``.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from admz.plans.models import ExecutionPlan, PlanStatus, PlanStep


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture
def completion():
    """The completion module with its registry restored after each test."""
    from admz.plans import completion as mod
    saved = dict(mod._REGISTRY)
    try:
        yield mod
    finally:
        mod._REGISTRY.clear()
        mod._REGISTRY.update(saved)


def _plan(on_complete=None, status=PlanStatus.COMPLETED, steps=None):
    p = ExecutionPlan(description="d", steps=steps or [], on_complete=on_complete)
    p.status = status
    return p


# ---------------------------------------------------------------------------
# run_completion — dispatch + never-raises
# ---------------------------------------------------------------------------


class TestRunCompletion:
    def test_dispatch_passes_plan_args_registry(self, completion):
        seen = {}

        def handler(plan, args, registry=None):
            seen["plan"] = plan
            seen["args"] = args
            seen["registry"] = registry

        completion.register_callable("t", handler)
        reg = object()
        p = _plan(on_complete={"handler": "t", "demo_id": "d1", "demo_name": "Lobby"})
        completion.run_completion(p, registry=reg)
        assert seen["plan"] is p
        assert seen["args"] == {"demo_id": "d1", "demo_name": "Lobby"}  # handler key stripped
        assert seen["registry"] is reg

    def test_runs_on_failed_too(self, completion):
        calls = []
        completion.register_callable("t", lambda plan, args, registry=None: calls.append(plan.status))
        completion.run_completion(_plan(on_complete={"handler": "t"}, status=PlanStatus.FAILED))
        assert calls == [PlanStatus.FAILED]  # handlers decide their own failure semantics

    def test_no_on_complete_is_noop(self, completion):
        p = _plan(on_complete=None)
        completion.run_completion(p)
        assert p.completion_note == ""

    def test_unknown_handler_notes_no_raise(self, completion):
        p = _plan(on_complete={"handler": "does-not-exist"})
        completion.run_completion(p)  # must not raise
        assert "not registered" in p.completion_note

    def test_handler_exception_noted_no_raise(self, completion):
        def boom(plan, args, registry=None):
            raise RuntimeError("kaboom")

        completion.register_callable("t", boom)
        p = _plan(on_complete={"handler": "t"})
        completion.run_completion(p)  # must not raise
        assert "failed" in p.completion_note and "kaboom" in p.completion_note

    def test_bad_module_path_noted_no_raise(self, completion):
        completion.register_handler("t", "admz.plans.completion", "no_such_fn")
        p = _plan(on_complete={"handler": "t"})
        completion.run_completion(p)  # AttributeError caught
        assert "failed" in p.completion_note


# ---------------------------------------------------------------------------
# Serialization: summary omits when unset, results carries the note
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_summary_omits_on_complete_when_none(self):
        assert "on_complete" not in _plan(on_complete=None).to_summary()

    def test_summary_includes_on_complete_when_set(self):
        oc = {"handler": "demo_activation", "demo_id": "d1"}
        assert _plan(on_complete=oc).to_summary()["on_complete"] == oc

    def test_results_includes_completion_note_when_set(self):
        p = _plan()
        p.completion_note = "demo stays inactive — device X failed"
        assert p.to_results()["completion_note"] == "demo stays inactive — device X failed"

    def test_results_omits_note_when_empty(self):
        assert "completion_note" not in _plan().to_results()


# ---------------------------------------------------------------------------
# Cross-process round-trip: on_complete survives _register_plan_from_session
# ---------------------------------------------------------------------------


class TestCrossProcessRoundTrip:
    def test_on_complete_survives_register_from_session(self):
        from admz.operations import _register_plan_from_session

        oc = {"handler": "demo_activation", "demo_id": "d1", "demo_name": "Lobby"}
        original = ExecutionPlan(
            description="push demo",
            steps=[PlanStep(step_number=1, operation_id="param.cgi:update",
                            device_id="cam-a", params={"k": "v"}, risk_level="service-affecting")],
            on_complete=oc,
        )

        class _Session:
            plan_id = original.plan_id
            plan_steps_json = json.dumps([s.to_dict() for s in original.steps])
            plan_summary = original.to_summary()

        class _Engine:
            def __init__(self):
                self.registered = None
            def register_plan(self, plan):
                self.registered = plan

        eng = _Engine()
        _register_plan_from_session(eng, _Session())
        assert eng.registered is not None
        assert eng.registered.on_complete == oc  # rode across the boundary


# ---------------------------------------------------------------------------
# End-to-end: run_plan dispatches the hook (0-step plan reaches COMPLETED)
# ---------------------------------------------------------------------------


class TestEngineDispatch:
    def test_run_plan_dispatches_completion(self, completion):
        from admz.plans.engine import PlanEngine

        seen = {}
        completion.register_callable(
            "t", lambda plan, args, registry=None: seen.update(status=plan.status, registry=registry))

        sentinel = object()
        engine = PlanEngine(catalog=None, registry=sentinel, executors={})
        plan = engine.create_plan("empty", steps=[], on_complete={"handler": "t"})
        done = _run(engine.run_plan(plan.plan_id))
        assert done.status == PlanStatus.COMPLETED
        assert seen["status"] == PlanStatus.COMPLETED
        assert seen["registry"] is sentinel  # engine passes its registry to handlers
