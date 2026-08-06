"""A run that is cancelled, or interrupted by a process death, must not stay
``running`` forever (GH #192).

Two mechanisms, tested separately because they cover different failures:

* ``run_fast``'s ``except asyncio.CancelledError`` handles a *graceful*
  cancellation — the task is cancelled while the process lives on. It records
  the state and **re-raises**, because swallowing ``CancelledError`` breaks
  cooperative cancellation.
* ``reconcile_interrupted_runs`` is the backstop for the case where nothing got
  a chance to run at all — a hard kill, an OOM. Every row still ``running`` at
  startup is stale by construction, because a ``fast`` run completes inside one
  request and a ``survey`` task does not survive a restart.

Both directions are pinned in each case. "A cancelled run does not stay
running" is trivially green for a store that marks everything failed, so each
class also asserts the ordinary path still reaches its own terminal state.

Store tests take an explicit ``db_path``: singletons bind their path at import,
so a test that does not isolate can reach a real database.
"""

from __future__ import annotations

import asyncio

import pytest

from admz.demos.inference.collect import reconcile_interrupted_runs, run_fast
from admz.demos.inference.runs import (MODE_FAST, MODE_SURVEY, STATUS_COMPLETE,
                                       STATUS_FAILED, STATUS_RUNNING,
                                       InferenceRunStore)


@pytest.fixture
def store(tmp_path):
    return InferenceRunStore(db_path=str(tmp_path / "admz.db"))


class _Ctx:
    """The only thing run_fast needs from ctx is whatever collect_graph reads;
    the graph call itself is monkeypatched in these tests."""


class TestCancelledFastRunIsRecordedAndReRaised:
    @pytest.mark.asyncio
    async def test_a_cancelled_run_does_not_stay_running(self, store, monkeypatch):
        async def _cancel(*_a, **_k):
            raise asyncio.CancelledError()

        monkeypatch.setattr("admz.demos.inference.collect.collect_graph", _cancel)

        with pytest.raises(asyncio.CancelledError):
            await run_fast(_Ctx(), store)

        rows = store.list(limit=5)
        assert len(rows) == 1
        assert rows[0].status == STATUS_FAILED, (
            "a cancelled fast run must land in a terminal state; leaving it "
            "running is #192 — the row is then permanent and is reported as "
            "in-flight")
        assert rows[0].status != STATUS_RUNNING

    @pytest.mark.asyncio
    async def test_the_cancellation_still_propagates(self, store, monkeypatch):
        """Recording the state must not swallow the cancellation — catching
        CancelledError without re-raising breaks cooperative cancellation, so
        an awaiting caller would never learn the task was cancelled."""
        async def _cancel(*_a, **_k):
            raise asyncio.CancelledError()

        monkeypatch.setattr("admz.demos.inference.collect.collect_graph", _cancel)

        # pytest.raises is the assertion: if run_fast returned normally, the
        # handler swallowed it and this fails.
        with pytest.raises(asyncio.CancelledError):
            await run_fast(_Ctx(), store)

    @pytest.mark.asyncio
    async def test_an_ordinary_run_still_completes(self, store, monkeypatch):
        """The vacuity guard: 'a run does not stay running' is trivially true
        for an implementation that fails everything."""
        async def _ok(*_a, **_k):
            return {"nodes": [], "edges": [], "acs": {"available": False}}

        monkeypatch.setattr("admz.demos.inference.collect.collect_graph", _ok)

        run = await run_fast(_Ctx(), store)
        assert run.status == STATUS_COMPLETE, (
            "the ordinary path must still reach complete — otherwise the "
            "cancellation tests above pass for the wrong reason")


class TestStartupReconciliation:
    def test_a_row_left_running_is_reconciled(self, store):
        run = store.start(mode=MODE_FAST, created_by="t")
        assert store.get(run.id).status == STATUS_RUNNING

        fixed = reconcile_interrupted_runs(store)

        assert run.id in fixed
        assert store.get(run.id).status == STATUS_FAILED
        assert store.running() == [], (
            "nothing may remain running after reconciliation — at startup a "
            "running row is stale by construction")

    def test_a_survey_row_is_reconciled_too(self, store):
        """A survey's background task does not survive a restart either, so it
        is stale by the same argument — no age threshold applies at boot."""
        run = store.start(mode=MODE_SURVEY, created_by="t")
        reconcile_interrupted_runs(store)
        assert store.get(run.id).status == STATUS_FAILED

    def test_a_terminal_row_is_left_alone(self, store):
        """Both directions: reconciliation must not rewrite history. A store
        that failed every row would pass the tests above."""
        done = store.start(mode=MODE_FAST, created_by="t")
        store.finish(done.id, {"nodes": [], "edges": []}, message="ok")
        assert store.get(done.id).status == STATUS_COMPLETE

        reconcile_interrupted_runs(store)

        assert store.get(done.id).status == STATUS_COMPLETE, (
            "a completed run must survive reconciliation unchanged")

    def test_it_is_a_noop_with_nothing_to_fix(self, store):
        assert reconcile_interrupted_runs(store) == []

    def test_a_broken_store_does_not_raise(self, store, monkeypatch):
        """Best-effort, like every other startup sweep: a locked or unreadable
        database must not stop the server booting."""
        def _boom(*_a, **_k):
            raise RuntimeError("database is locked")

        monkeypatch.setattr(store, "running", _boom)
        assert reconcile_interrupted_runs(store) == []
