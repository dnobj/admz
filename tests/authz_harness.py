"""Install an authenticated principal for tests that exercise gated writes.

Several suites POST to handlers that write protected fleet settings. Those
handlers refuse an anonymous principal (#351 and, before it, CR-3 on
``/confirm-settings``), which is correct behaviour and which the default
``ADMZ_AUTH_BACKEND=none`` test posture does not satisfy.

Before this existed the pattern was copy-pasted per file — ``_with_admin`` in
``test_credential_gate_split.py`` and a local ``StubBackend`` in two others —
which is how three suites ended up with three slightly different synthetic
principals. Use :func:`as_authenticated` instead of writing a fourth.
"""

from __future__ import annotations

from contextlib import contextmanager

from admz.auth import (
    AuthBackend,
    Principal,
    get_active_backend,
    set_active_backend,
)


class _StubBackend(AuthBackend):
    def __init__(self, principal: Principal):
        self._principal = principal

    async def authenticate(self, request):
        return self._principal


@contextmanager
def as_authenticated(name: str = "admin", groups=("Administrators",)):
    """Run the block with a real (non-anonymous) Windows-shaped principal.

    Restores **whatever backend was active on entry**, not a hardcoded
    :class:`NoAuth`. The active backend is process-wide, so restoring a
    constant would silently destroy an outer fixture's specialised backend and
    change how later requests authenticate — a nesting bug that only shows up
    in whichever test happens to run next.

    ``groups`` defaults to ``Administrators`` so the principal also satisfies
    the reveal/approver gates; pass ``groups=()`` to test the authenticated-
    but-unprivileged case, which is the shape CLAUDE.md documents as supported
    and the one most likely to be under-tested.
    """
    principal = Principal(
        name=f"AXIS\\{name}",
        display_name=name,
        domain="AXIS",
        groups=list(groups),
        source="windows",
        is_anonymous=False,
    )
    previous = get_active_backend()
    set_active_backend(_StubBackend(principal))
    try:
        yield principal
    finally:
        set_active_backend(previous)
