"""ADR-0073 / #375 — the MCP server is a tool server, not a runtime.

No MCP process, pool or standalone, starts the scheduler or any other
background owner; the web service is the only runtime. A standalone
``python -m admz mcp`` used to start a scheduler and nothing it depends on,
and the scheduler has no cross-process claim, so beside the web service every
schedule fired twice.

``run()`` is driven for real, with only the stdio transport and the protocol
loop stubbed, so what it starts and what it installs are observed rather than
read off the source.
"""

import ast
import asyncio
import contextlib
import logging
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import admz

#: What the web service's lifespan starts (``admz/api/main.py``), as
#: ``ctx.<owner>.start()``. None of them belongs in an MCP process.
BACKGROUND_OWNERS = {"scheduler", "health_monitor", "event_supervisor",
                     "acs_event_poller", "acs_firebird_poller"}


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    from admz.mcp.server import ADMZMCPServer

    return ADMZMCPServer()


@pytest.fixture(params=["standalone", "pool-subprocess"])
def role(request, monkeypatch):
    """Both roles an MCP process runs in. The pool marker is what
    chatbot/mcp_pool.py sets; standalone is its absence."""
    if request.param == "pool-subprocess":
        monkeypatch.setenv("ADMZ_MCP_NO_SCHEDULER", "1")
    else:
        monkeypatch.delenv("ADMZ_MCP_NO_SCHEDULER", raising=False)
    return request.param


def _run(server, monkeypatch):
    """Run ``server.run()`` to completion as if a client connected and left.

    Returns the spy standing in for the scheduler's ``start``."""
    import admz.mcp.server as srv

    @contextlib.asynccontextmanager
    async def _no_client():
        yield (object(), object())

    monkeypatch.setattr(srv, "stdio_server", _no_client)
    monkeypatch.setattr(server.server, "run", AsyncMock(return_value=None))
    start = AsyncMock()
    monkeypatch.setattr(server.scheduler, "start", start)
    asyncio.run(server.run())
    return start


def test_no_mcp_process_starts_the_scheduler(server, monkeypatch, role):
    start = _run(server, monkeypatch)
    start.assert_not_awaited()
    assert server.scheduler._running is False
    assert server.scheduler._tasks == {}, "no schedule loop runs in this process"


def test_a_schedule_created_through_a_tool_is_stored_not_run_here(server, monkeypatch, role):
    """The web service's scheduler adopts it across processes (its reconcile
    loop); this process only writes it."""
    from admz.snapshot.scheduler import SnapshotSchedule

    _run(server, monkeypatch)
    server.scheduler.add_schedule(SnapshotSchedule(
        id="tool-made-375", description="made by a tool", interval_seconds=3600))
    assert server.scheduler.store.get("tool-made-375") is not None
    assert server.scheduler._tasks == {}


def test_every_mcp_process_installs_the_module_task_handlers(server, monkeypatch, role):
    """``run_snapshot_schedule`` runs a task inline, so its handler must be
    registered in THIS process. A chat pool subprocess used to skip this and
    fail a module action with "no handler registered" (GH #172)."""
    installed = []
    monkeypatch.setattr("admz.tasks.handlers.install_module_task_handlers",
                        lambda registry: installed.append(registry) or 0)
    _run(server, monkeypatch)
    assert installed == [server.module_registry]


def test_it_says_where_scheduled_work_runs(server, monkeypatch, role, caplog):
    caplog.set_level(logging.INFO, logger="admz.mcp.server")
    _run(server, monkeypatch)
    assert "tool server" in caplog.text and "ADR-0073" in caplog.text


def test_the_schedule_tool_says_who_runs_the_job():
    from admz.mcp.tools.schedules import TOOLS

    tool = next(t for t in TOOLS if t.name == "create_snapshot_schedule")
    assert "The ADMZ web service runs the job" in tool.description
    assert "ADR-0073" in tool.description


def test_nothing_in_the_mcp_package_starts_a_background_owner():
    """Static, so it covers paths no test drives: no ``<x>.<owner>.start()``
    for any owner the web service starts, and no rule-secret purge sweep."""
    root = Path(admz.__file__).parent / "mcp"
    offenders, seen_files = [], 0
    for path in sorted(root.rglob("*.py")):
        seen_files += 1
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (isinstance(func, ast.Attribute) and func.attr == "start"
                    and isinstance(func.value, ast.Attribute)
                    and func.value.attr in BACKGROUND_OWNERS):
                offenders.append(f"{path.name}:{node.lineno} {func.value.attr}.start()")
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name == "start_background_purge":
                offenders.append(f"{path.name}:{node.lineno} start_background_purge()")
    assert seen_files > 5, "the scan found the package"
    assert offenders == []


def test_the_guard_would_see_a_scheduler_start():
    """The control for the guard above: the shape it looks for is the shape
    the web service uses, so a regression would not slip past on syntax."""
    main = (Path(admz.__file__).parent / "api" / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(main)
    found = {node.func.value.attr for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == "start" and isinstance(node.func.value, ast.Attribute)
             and node.func.value.attr in BACKGROUND_OWNERS}
    assert found == BACKGROUND_OWNERS
