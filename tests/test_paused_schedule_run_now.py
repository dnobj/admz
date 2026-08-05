"""GH #156: a paused schedule must not be fired by a caller who did not ask to.

`FR-SCH-008` was marked ✅ — *"`enabled=False` skips a schedule without deleting
it"* — while only the scheduler's own loop honoured it. `run_now` checked
`task is None or task.trigger_kind != TRIGGER_SCHEDULE` and nothing else, so all
three on-demand paths fired a paused schedule: the ▶ button the UI renders on a
row labelled "Paused", the REST route behind it, and an ungated MCP tool.

**The semantics chosen, because a uniform check would be wrong.** `enabled`
means "do not run *automatically*", not "do not run at all" — `update_schedule`
cancels and restarts the *timer* and nothing else, and a maintenance window
exists to stop unattended work. So a pause does not revoke an operator's
ability to run the thing deliberately; it revokes everyone *else's*, because
only the operator can express "I know it is paused".

That is `allow_paused`, defaulting to **False**, with the two REST routes
passing `is_interactive(principal)` — the same predicate `tasks/gated.py`
already uses to let a console operator write directly. The MCP tool passes
nothing and gets the default.

**The vacuity shape.** "a paused schedule does not run" is trivially green if
*nothing* runs — a broken scheduler, a missing task, a handler that never
fires all produce `success: False`. So every refusal test is paired with an
identical fixture that is *enabled* and asserts the job actually executed, and
the assertions are on the **handler's call count**, not only the return value.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from admz.snapshot.scheduler import SnapshotSchedule, SnapshotScheduler


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """ADR-0037: schedules live in the SQLite tasks store. Per-test DB, and
    ADMZ_HOME redirected so nothing can reach a real database."""
    import admz.tasks.store as _sm
    from admz.tasks.store import TaskStore

    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setattr(_sm, "tasks_store", TaskStore(str(tmp_path / "tasks.db")))
    yield


class _Engine:
    """Records every snapshot the scheduler asks for."""

    def __init__(self):
        self.calls = []

    async def snapshot_fleet(self, **kw):
        self.calls.append(kw)
        # An empty list, matching tests/test_scheduler.py's MockSnapshotEngine.
        # The handler iterates these looking for `succeeded_facets`, so a dict
        # envelope here fails inside the handler — which is how the *positive*
        # pairs caught this and the refusal tests could not have.
        return []


def _scheduler(tmp_path, *, enabled=True):
    engine = _Engine()
    sched = SnapshotScheduler(engine, str(tmp_path / "schedules.json"))
    sched.add_schedule(SnapshotSchedule(
        id="nightly", description="Nightly snapshot", interval_seconds=86400,
    ))
    if not enabled:
        sched.update_schedule("nightly", enabled=False)
    return sched, engine


# --- the defect ------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_paused_schedule_is_refused_by_default(tmp_path):
    """THE #156 defect. `run_now` fired this regardless of `enabled`."""
    sched, engine = _scheduler(tmp_path, enabled=False)

    result = await sched.run_now("nightly")

    assert result["success"] is False
    assert result.get("paused") is True
    assert engine.calls == [], "the paused schedule executed anyway"


@pytest.mark.asyncio
async def test_an_enabled_schedule_still_runs(tmp_path):
    """The anti-vacuity pair, on the same fixture. Without it, the test above
    passes for a scheduler that can no longer run anything at all."""
    sched, engine = _scheduler(tmp_path, enabled=True)

    result = await sched.run_now("nightly")

    assert result["success"] is True
    assert len(engine.calls) == 1, "the enabled schedule did not execute"


@pytest.mark.asyncio
async def test_an_explicit_override_runs_a_paused_schedule(tmp_path):
    """The console operator's deliberate override — the whole reason this is
    `allow_paused` rather than a blanket `and task.enabled`."""
    sched, engine = _scheduler(tmp_path, enabled=False)

    result = await sched.run_now("nightly", allow_paused=True)

    assert result["success"] is True
    assert len(engine.calls) == 1, "the override did not actually run it"


@pytest.mark.asyncio
async def test_the_refusal_says_it_is_paused_and_how_to_proceed(tmp_path):
    """An operator told only "failed" concludes the feature is broken and
    un-pauses the schedule — the outcome the refusal exists to avoid."""
    sched, _ = _scheduler(tmp_path, enabled=False)

    err = (await sched.run_now("nightly"))["error"].lower()

    assert "paused" in err
    assert "console" in err or "enable" in err


@pytest.mark.asyncio
async def test_a_missing_schedule_is_still_not_found_not_paused(tmp_path):
    """The two refusals must stay distinguishable: a caller that cannot tell
    "deleted" from "paused" will go looking for the wrong thing."""
    sched, _ = _scheduler(tmp_path)

    result = await sched.run_now("no-such-schedule")

    assert result["success"] is False
    assert not result.get("paused")
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_override_does_not_resurrect_a_missing_schedule(tmp_path):
    """`allow_paused` overrides the pause, not existence."""
    sched, engine = _scheduler(tmp_path)

    result = await sched.run_now("no-such-schedule", allow_paused=True)

    assert result["success"] is False
    assert engine.calls == []


@pytest.mark.asyncio
async def test_allow_paused_defaults_to_refusing(tmp_path):
    """Deny by default, so a caller added later is refused until it opts in —
    the failure direction ADR-0053 argues for, and the one #156 got backwards.
    """
    import inspect

    sig = inspect.signature(SnapshotScheduler.run_now)
    assert sig.parameters["allow_paused"].default is False
    assert sig.parameters["allow_paused"].kind is inspect.Parameter.KEYWORD_ONLY


# --- the loop is unchanged -------------------------------------------------


@pytest.mark.asyncio
async def test_the_loop_still_refuses_a_paused_schedule(tmp_path):
    """The one path that already worked must keep working — this change is
    about the other three."""
    sched, engine = _scheduler(tmp_path, enabled=False)

    task = sched.store.get("nightly")
    assert task is not None and task.enabled is False

    # _schedule_loop returns immediately on a disabled task rather than sleeping.
    await sched._schedule_loop("nightly")
    assert engine.calls == []


# --- per-caller: who may override ------------------------------------------


def _principal(source):
    return MagicMock(source=source)


@pytest.mark.parametrize("source,may_override", [
    ("windows", True),      # console operator — /login and SSO both mint this
    ("api-key", False),
    ("none", False),
    ("", False),
])
def test_only_the_console_operator_may_override(source, may_override):
    """The per-caller decision, asserted through the shared predicate rather
    than a copy of it — `tasks/gated.py::is_interactive` already draws this
    line for task writes, and a second implementation is the #255 drift."""
    from admz.tasks.gated import is_interactive

    assert is_interactive(_principal(source)) is may_override


@pytest.mark.asyncio
async def test_the_mcp_tool_passes_no_override(tmp_path):
    """The model cannot mean "I know it is paused" — nobody expressed that.

    Asserted against the real handler, so it fails if someone later threads an
    override through the MCP path.
    """
    from admz.mcp.server import ADMZMCPServer

    sched, engine = _scheduler(tmp_path, enabled=False)
    srv = object.__new__(ADMZMCPServer)
    srv.scheduler = sched

    result = await srv._run_snapshot_schedule("nightly")

    assert result["success"] is False
    assert result.get("paused") is True
    assert engine.calls == [], "the model fired a paused schedule"


@pytest.mark.asyncio
async def test_the_mcp_tool_still_runs_an_enabled_schedule(tmp_path):
    """Pair for the above — otherwise it is green for a tool that never works."""
    from admz.mcp.server import ADMZMCPServer

    sched, engine = _scheduler(tmp_path, enabled=True)
    srv = object.__new__(ADMZMCPServer)
    srv.scheduler = sched

    result = await srv._run_snapshot_schedule("nightly")

    assert result["success"] is True
    assert len(engine.calls) == 1


# --- the REST routes pass the predicate ------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("route_mod,fn_name,arg", [
    ("admz.api.routes.tasks", "run_task_now", "task_id"),
    ("admz.api.routes.schedules", "run_schedule_now", "schedule_id"),
])
async def test_rest_routes_forward_the_interactive_verdict(
    tmp_path, monkeypatch, route_mod, fn_name, arg,
):
    """Both routes must hand `run_now` the principal's verdict.

    Asserted on the call, because a route that computed `is_interactive` and
    then forgot to pass it would still look right on inspection.
    """
    import importlib

    mod = importlib.import_module(route_mod)
    sched, _ = _scheduler(tmp_path, enabled=False)
    seen = {}

    async def _spy(sid, *, allow_paused=False):
        seen["allow_paused"] = allow_paused
        return {"success": True}

    sched.run_now = _spy
    ctx = MagicMock(scheduler=sched)
    ctx.scheduler.store = sched.store

    monkeypatch.setattr(
        "admz.auth.get_current_principal", AsyncMock(return_value=_principal("windows")))
    monkeypatch.setattr("admz.audit.record_event", MagicMock())

    fn = getattr(mod, fn_name)
    await fn(**{"request": MagicMock(), arg: "nightly", "ctx": ctx})

    assert seen.get("allow_paused") is True, (
        "the route did not forward the console operator's override")

    # ...and the inverse, so it is not simply hardcoded True.
    seen.clear()
    monkeypatch.setattr(
        "admz.auth.get_current_principal", AsyncMock(return_value=_principal("api-key")))
    await fn(**{"request": MagicMock(), arg: "nightly", "ctx": ctx})
    assert seen.get("allow_paused") is False, (
        "an api-key caller was granted the console override")
