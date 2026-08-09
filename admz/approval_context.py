"""Ambient "this work was already approved" marker (ADR-0059).

ADR-0059 moves the provisioning gate from the discovery entry points to
``onboarding.onboard_device_credentials``, the function that decides to
provision. That creates one problem the entry-point placement did not have:
**two callers reach that function having already been approved**, and must not
be asked again.

* ``operations.py::_action_register_discovered_device`` — the approval executor
  itself. Re-gating it would loop forever.
* ``demos/inference/collect.py`` — the deep survey, gated once at its route
  (#299). Re-gating would raise one widget *per device*, N times, inside an
  approval the operator has already given.

The rejected alternative was an ``approved_by=`` keyword threaded through every
caller. It fails closed — forget it and you gate something already approved,
which is annoying and safe — but it is the *"every caller must remember"*
shape, and a gate that some call sites forget is the exact failure ADR-0059
exists to end. A mechanism whose correctness depends on remembering is the
wrong instrument for a remembering bug.

So the marker is ambient, and the cost is stated plainly:

.. warning::

   **This fails OPEN.** A token that is set and never reset marks every later
   call on the same task approved — the gate silently stops existing, nothing
   raises, and nothing is logged. That is strictly worse than the rejected
   design's failure mode, and it is the price of not requiring callers to
   remember.

   Two structural rules keep it honest, both enforced by tests in
   ``tests/test_approval_context.py``:

   1. :func:`approved` resets in ``finally`` — so an exception cannot strand
      the token.
   2. ``_APPROVED.set()`` appears **nowhere** outside this module. A static
      test greps for it, because a leak on a path no test exercises is
      invisible to a dynamic one.

``ContextVar`` rather than a module global is load-bearing for the survey:
``asyncio.create_task`` copies the current context, so a background task
started inside an approval inherits it for the task's whole life, while
concurrent unrelated work does not see it. That is the correct semantics — the
operator approved *that survey*, including every device it provisions.

.. warning::

   **A detached task keeps the approval for its whole life, and the parent
   cannot revoke it.** ``create_task`` *copies* the value; resetting the token
   in the parent does not reach the child. So a task spawned inside an approval
   stays approved after ``execute_approved_session`` has returned or been
   cancelled.

   For the survey this is exactly what is wanted. It is a hazard for any
   *other* detached task an action executor might spawn, which would carry
   provisioning authority it was never meant to have. Two things bound it
   today: only the two provisioning actions establish the marker at all (see
   ``operations._PROVISIONING_APPROVAL_ACTIONS``), and consumers gate on
   :func:`is_approved_for` rather than "any approval". If a third action is
   ever added to that set, check what it spawns.

   Found in review of #361; recorded rather than designed away, because
   removing propagation would break the survey — the one caller that needs it.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional, Tuple

#: ``(action_id, confirm_token)`` or ``None``. Never ``set()`` outside
#: :func:`approved`.
_APPROVED: ContextVar[Optional[Tuple[str, Optional[str]]]] = ContextVar(
    "admz_approved_action", default=None
)


@contextmanager
def approved(action: str, token: Optional[str] = None) -> Iterator[None]:
    """Mark the enclosed work as already carrying the operator's approval.

    ``action`` is the approved action id; ``token`` is the confirm-session
    token, carried so a consumer can tell *which* approval covered a write and
    an audit row can say so.

    The ``try/finally`` is not defensive style; it is the thing that stops this
    from being a hole. See the module warning.
    """
    ctx_token = _APPROVED.set((action, token))
    try:
        yield
    finally:
        _APPROVED.reset(ctx_token)


def is_approved() -> bool:
    """True if the current context is inside *any* approved action.

    .. warning::

       **Do not gate on this.** Use :func:`is_approved_for` with the actions
       whose approval legitimately covers the write you are about to make.
       "Some approval is in scope" is not authority to do a different thing —
       ADR-0034's whole model is that an approval is for a *specific* action,
       and this predicate throws that away. It exists for audit and debugging.
    """
    return _APPROVED.get() is not None


def is_approved_for(*actions: str) -> bool:
    """True if the current context is inside an approval for one of ``actions``.

    This is the predicate a gate should use. It was added after review of the
    first draft (#361): the marker was established for **every** approved
    action, so approving an unrelated one — a task creation, a rule delete —
    would have been sufficient authority for provisioning had that executor
    ever reached the onboarding path. Approval for X is not approval for Y.
    """
    current = _APPROVED.get()
    return current is not None and current[0] in actions


def approved_action() -> Optional[str]:
    """The approved action id, or ``None`` — for audit rows, not for gating."""
    current = _APPROVED.get()
    return current[0] if current else None


def approved_token() -> Optional[str]:
    """The confirm token of the approval in scope, or ``None``.

    Identity, so a consumer can record *which* approval authorised a write —
    and so a future refinement can require the approval to be the one covering
    *this* device set. See the detached-task caveat in the module docstring.
    """
    current = _APPROVED.get()
    return current[1] if current else None


__all__ = [
    "approved",
    "is_approved",
    "is_approved_for",
    "approved_action",
    "approved_token",
]
