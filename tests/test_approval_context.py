"""The approved-context marker, and the fail-open hazard it carries (ADR-0059).

This module exists because ADR-0059 moves the provisioning gate to a chokepoint
that already-approved callers pass through, so they need a way to say "the
operator said yes to this" without every caller remembering to.

**The marker fails open.** A token set and never reset marks every later call on
the task approved: the gate stops existing, nothing raises, nothing is logged.
That is the one property the rejected `approved_by=` design did not have, and it
is why these tests are not optional garnish — they are the mechanism's safety.

Pinned here:
  - the token unwinds on the normal path, on the exception path, and on nesting
  - it does not leak across concurrent tasks, and DOES cross `create_task`
    (the survey depends on the second one)
  - `execute_approved_session` both establishes and unwinds it, including when
    the action executor raises
  - `_APPROVED.set()` appears nowhere outside the module — a STATIC check,
    because a leak on a path no test takes is invisible to a dynamic one
"""

from __future__ import annotations

import asyncio

import pytest

from admz.approval_context import approved, approved_action, is_approved


# ---------------------------------------------------------------------------
# The context manager itself
# ---------------------------------------------------------------------------


class TestApprovedContext:
    def test_false_by_default(self):
        assert is_approved() is False
        assert approved_action() is None

    def test_true_inside_and_false_after(self):
        with approved("register_discovered_device"):
            assert is_approved() is True
            assert approved_action() == "register_discovered_device"
        assert is_approved() is False
        assert approved_action() is None

    def test_resets_on_the_exception_path(self):
        """The `finally` is the whole safety property. Without it, one raising
        approved action leaves every later call on this task approved."""
        with pytest.raises(RuntimeError):
            with approved("boom"):
                raise RuntimeError("executor blew up")
        assert is_approved() is False, "token stranded by an exception"

    def test_nesting_unwinds_to_the_outer_value(self):
        with approved("outer"):
            with approved("inner"):
                assert approved_action() == "inner"
            # `reset(token)` restores the previous value rather than clearing.
            assert approved_action() == "outer"
        assert is_approved() is False

    @pytest.mark.asyncio
    async def test_does_not_leak_into_a_concurrent_outsider_task(self):
        """A ContextVar, not a module global: unrelated work running
        *concurrently with* an approval must not be approved by it.

        The outsider is created BEFORE the `with`, so its copied context
        predates the token, and it observes from inside the window when the
        approval is active in the parent.
        """
        seen = {}

        async def outsider():
            await asyncio.sleep(0)          # resume while the approval is live
            seen["outsider"] = is_approved()

        task = asyncio.create_task(outsider())
        with approved("register_discovered_device"):
            await asyncio.sleep(0)          # let the outsider run right here
            seen["inside"] = is_approved()
        await task

        assert seen["inside"] is True
        assert seen["outsider"] is False

    @pytest.mark.asyncio
    async def test_a_task_created_inside_the_approval_inherits_it(self):
        """`create_task` copies the context — the property the deep survey
        depends on. The operator approved that survey, including every device
        it provisions in the background."""
        result = {}

        async def background():
            await asyncio.sleep(0)
            result["approved"] = is_approved()

        with approved("run_survey"):
            task = asyncio.create_task(background())
        # Deliberately awaited AFTER the context exits: the task captured the
        # context at creation, so it stays approved even though the `with`
        # block has closed. That is the intended semantics, not a leak — the
        # copy belongs to that task and dies with it.
        await task

        assert result["approved"] is True
        assert is_approved() is False


# ---------------------------------------------------------------------------
# The one place that sets it
# ---------------------------------------------------------------------------


class TestExecuteApprovedSessionEstablishesContext:
    """`execute_approved_session` is the sole producer of the marker."""

    def _session(self, action_name="register_discovered_device"):
        from types import SimpleNamespace
        return SimpleNamespace(
            is_action=True, is_plan=False,
            action={"action": action_name, "device_id": "cam-1"},
            confirmed_by="AXIS\\alice", token="tok-1",
        )

    @pytest.mark.asyncio
    async def test_the_action_executor_runs_approved(self, monkeypatch):
        from admz import operations

        seen = {}

        def _spy(action, registry, git_repo=None):
            seen["approved"] = is_approved()
            seen["action"] = approved_action()
            return {"success": True}

        monkeypatch.setitem(
            operations._ACTION_EXECUTORS, "register_discovered_device", _spy)

        out = await operations.execute_approved_session(
            self._session(), catalog=None, registry=None, executors={})

        assert out == {"success": True}
        assert seen["approved"] is True
        assert seen["action"] == "register_discovered_device"

    @pytest.mark.asyncio
    async def test_context_is_gone_after_it_returns(self, monkeypatch):
        from admz import operations

        monkeypatch.setitem(
            operations._ACTION_EXECUTORS, "register_discovered_device",
            lambda action, registry, git_repo=None: {"success": True})

        await operations.execute_approved_session(
            self._session(), catalog=None, registry=None, executors={})

        assert is_approved() is False

    @pytest.mark.asyncio
    async def test_context_is_gone_after_the_executor_raises(self, monkeypatch):
        """The route swallows the exception into an error dict — so nothing
        downstream would notice a stranded token. This is the case that turns
        the marker into a silent hole if the `with` is placed wrongly."""
        from admz import operations

        def _boom(action, registry, git_repo=None):
            raise RuntimeError("device unreachable")

        monkeypatch.setitem(
            operations._ACTION_EXECUTORS, "register_discovered_device", _boom)

        out = await operations.execute_approved_session(
            self._session(), catalog=None, registry=None, executors={})

        assert out["success"] is False
        assert "RuntimeError" in out["error"]
        assert is_approved() is False, "token stranded by a raising executor"

    @pytest.mark.asyncio
    async def test_an_unknown_action_does_not_establish_context(self, monkeypatch):
        from admz import operations

        out = await operations.execute_approved_session(
            self._session("no_such_action"), catalog=None, registry=None,
            executors={})

        assert out["success"] is False
        assert is_approved() is False


# ---------------------------------------------------------------------------
# The static rule
# ---------------------------------------------------------------------------


def test_approved_is_never_set_outside_its_module():
    """`_APPROVED.set()` anywhere else is a hole with no dynamic symptom.

    A caller that sets the token directly has no `finally`, so it strands the
    marker for the rest of the task — and because the gate then just... passes,
    there is no failure for a test to catch. This is the same reasoning as the
    setting-policy and mock-faithfulness lints: a static check for the mistake
    whose runtime signature is silence.
    """
    import pathlib
    import re

    root = pathlib.Path("admz")
    offenders = []
    for path in sorted(root.rglob("*.py")):
        if path.name == "approval_context.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"_APPROVED\s*\.\s*set\s*\(", text):
            offenders.append(str(path))

    assert not offenders, (
        "_APPROVED.set() outside admz/approval_context.py — use the "
        f"`approved()` context manager, which resets in finally: {offenders}"
    )


def test_the_scanner_is_not_vacuous():
    """The lint above passes trivially if the tree is unreadable or the pattern
    never matches anything. Prove it fires on the real thing."""
    import re
    import pathlib

    src = pathlib.Path("admz/approval_context.py").read_text(encoding="utf-8")
    assert re.search(r"_APPROVED\s*\.\s*set\s*\(", src), (
        "the pattern no longer matches the one legitimate call site — the "
        "lint is now checking for nothing"
    )
