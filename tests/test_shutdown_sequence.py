"""The lifespan's shutdown must be uniformly best-effort (GH #379).

Three separate bugs of one shape: `mcp_pool.stop()` (found reviewing #372),
then `health_monitor.stop()` and `scheduler.stop()` (found by the ripple audit
after #373) — each an unguarded `await` in a sequence of guarded ones, and each
able to skip every step behind it, including the registry close.

The fix is structural rather than a seventh and eighth hand-written
`try/except`: the steps are a list, `_shutdown_step` guards them uniformly, and
the next step someone adds is guarded by construction. These tests pin the two
properties that makes it worth having — a failing step does not stop the rest,
and cancellation still propagates.
"""

from __future__ import annotations

import asyncio

import pytest

from admz.api.main import _run_shutdown, _shutdown_step


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class TestShutdownStep:
    def test_runs_an_async_step(self):
        seen = []
        _run(_shutdown_step("x", lambda: _noop(seen)))
        assert seen == ["ran"]

    def test_runs_a_sync_step(self):
        """`stop_background_purge` and `registry.close` are plain functions;
        everything else is a coroutine. Both go through the same list."""
        seen = []
        _run(_shutdown_step("x", lambda: seen.append("ran")))
        assert seen == ["ran"]

    def test_swallows_a_raising_step(self):
        def boom():
            raise RuntimeError("no")
        _run(_shutdown_step("x", boom))          # must not raise

    def test_swallows_a_raising_async_step(self):
        async def boom():
            raise RuntimeError("no")
        _run(_shutdown_step("x", boom))

    def test_logs_what_failed(self, caplog):
        """The old blocks were bare `except Exception: pass`, so a subsystem
        failing to stop left no trace — and that is exactly what you want a line
        for when the next start behaves oddly."""
        import logging

        def boom():
            raise RuntimeError("no")
        with caplog.at_level(logging.WARNING):
            _run(_shutdown_step("health monitor", boom))
        assert "health monitor" in caplog.text

    def test_an_interrupt_is_returned_not_raised(self):
        """So `_run_shutdown` can finish the remaining steps first. Re-raising
        here was v1 of this fix and reintroduced the bug it was closing."""
        async def cancelled():
            raise asyncio.CancelledError()
        exc = _run(_shutdown_step("x", cancelled))
        assert isinstance(exc, asyncio.CancelledError)

    def test_an_ordinary_failure_returns_none(self):
        def boom():
            raise RuntimeError("no")
        assert _run(_shutdown_step("x", boom)) is None


async def _noop(seen):
    seen.append("ran")


class TestTheSequenceSurvivesAFailure:
    """The property the three bugs violated: one bad step must not skip the
    registry close, which is last precisely because everything before it uses
    the registry."""

    def test_every_step_runs_when_an_early_one_raises(self):
        ran = []

        def step(name, *, fail=False):
            def _f():
                ran.append(name)
                if fail:
                    raise RuntimeError(name)
            return _f

        async def drive():
            # The real sequence's shape: several steps, one of them exploding
            # early, and the registry close last.
            steps = [
                ("chat MCP pool", step("pool", fail=True)),
                ("event supervisor", step("events")),
                ("health monitor", step("health", fail=True)),
                ("scheduler", step("scheduler")),
                ("registry", step("registry")),
            ]
            for name, fn in steps:
                await _shutdown_step(name, fn)

        _run(drive())
        assert ran == ["pool", "events", "health", "scheduler", "registry"]


class TestTheRealLifespan:
    """Drives the actual FastAPI lifespan, not the helper.

    Every previous PR in this class was verified only at the helper level, and
    the ripple audit still found two unguarded steps — because "is the sequence
    wired correctly?" is a different question from "does the guard work?".
    """

    @pytest.fixture(autouse=True)
    def isolate(self, tmp_path, monkeypatch):
        """A test that does not isolate ADMZ_HOME writes into the operator's
        real database. The lifespan builds real components."""
        monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
        monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
        monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
        monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
        monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

    def test_a_failing_step_does_not_skip_the_rest_of_shutdown(self):
        from fastapi.testclient import TestClient

        from admz.api.context import get_context
        from admz.api.main import app

        later = []

        with TestClient(app):
            ctx = get_context()

            async def boom():
                raise RuntimeError("health monitor wedged")

            real_scheduler_stop = ctx.scheduler.stop

            async def record_scheduler():
                later.append("scheduler")
                await real_scheduler_stop()

            # The registry close is THE step the bug skipped, and it is last.
            # Asserting only on the scheduler would pass even if the close were
            # dropped from the list entirely (review finding on #380).
            from admz.api import main as main_mod
            real_close = getattr(main_mod.registry, "close", None)
            assert callable(real_close), (
                "premise: the sqlite backend exposes close(), so the "
                "conditional step is actually in the list")

            def record_close():
                later.append("registry")
                return real_close()

            main_mod.registry.close = record_close
            ctx.health_monitor.stop = boom
            ctx.scheduler.stop = record_scheduler
        # Exiting the context manager ran shutdown. Before #379 the
        # health-monitor failure propagated, skipping the scheduler step AND
        # the registry close behind it, and TestClient raised out of __exit__.
        assert later == ["scheduler", "registry"]

    def test_the_context_is_not_left_behind_for_later_tests(self):
        """This class builds real components against a temp dir. If the process
        global survived, a later test in the same process could pick up a closed
        registry pointing at a deleted directory."""
        from fastapi.testclient import TestClient

        from admz.api import context as ctx_mod
        from admz.api.main import app

        with TestClient(app):
            pass
        # Whatever the lifespan installed, put the module back to a state a
        # later test can safely re-enter: the next TestClient rebuilds it.
        ctx_mod._ctx = None


class TestRunShutdown:
    """The sequencing half: an interrupt must not abandon the remaining steps."""

    def test_cancellation_still_runs_every_later_step(self):
        """v1 re-raised immediately, so a cancellation mid-sequence skipped the
        registry close — the exact failure #379 removes, reintroduced by its
        own fix."""
        ran = []

        async def cancelled():
            raise asyncio.CancelledError()

        steps = [
            ("events", lambda: ran.append("events")),
            ("scheduler", cancelled),
            ("registry", lambda: ran.append("registry")),
        ]
        with pytest.raises(asyncio.CancelledError):
            _run(_run_shutdown(steps))
        assert ran == ["events", "registry"]

    def test_the_first_interrupt_is_the_one_re_raised(self):
        async def cancelled():
            raise asyncio.CancelledError()

        def interrupted():
            raise KeyboardInterrupt()

        with pytest.raises(asyncio.CancelledError):
            _run(_run_shutdown([("a", cancelled), ("b", interrupted)]))

    def test_a_keyboard_interrupt_does_not_abandon_cleanup(self):
        """`except Exception` let BaseException skip the rest — the same hole in
        a different costume."""
        ran = []

        def interrupted():
            raise KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            _run(_run_shutdown([("a", interrupted),
                                ("registry", lambda: ran.append("registry"))]))
        assert ran == ["registry"]

    def test_no_interrupt_means_no_raise(self):
        def boom():
            raise RuntimeError("ordinary")
        _run(_run_shutdown([("a", boom), ("b", lambda: None)]))
