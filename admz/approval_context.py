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
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

#: The approved action id, or ``None``. Never ``set()`` outside :func:`approved`.
_APPROVED: ContextVar[Optional[str]] = ContextVar("admz_approved_action", default=None)


@contextmanager
def approved(action: str) -> Iterator[None]:
    """Mark the enclosed work as already carrying the operator's approval.

    ``action`` is the approved action id (e.g. ``register_discovered_device``).
    It is recorded so :func:`approved_action` can name it in an audit row —
    "provisioned under approval X" is a more useful trail than "provisioned".

    The ``try/finally`` is not defensive style; it is the thing that stops this
    from being a hole. See the module warning.
    """
    token = _APPROVED.set(action)
    try:
        yield
    finally:
        _APPROVED.reset(token)


def is_approved() -> bool:
    """True if the current context is running inside an approved action."""
    return _APPROVED.get() is not None


def approved_action() -> Optional[str]:
    """The approved action id, or ``None`` — for audit rows, not for gating.

    Gate on :func:`is_approved`. This exists so an approved provisioning can
    record *which* approval covered it.
    """
    return _APPROVED.get()


__all__ = ["approved", "is_approved", "approved_action"]
