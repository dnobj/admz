"""A module's ``self_heals()`` must agree with its executor's (#374).

``self_heals`` decides whether ADMZ persists auth it relearned on the wire.
Edge devices (VAPIX) relearn and the gate writes the correction back; server
targets (ACS Pro) authenticate per connection and must **not** have their
stored auth rewritten (ADR-0039).

It is declared **twice**, and only one declaration is consulted:

===============================================  ==============  ============
declaration                                      consulted?      default
===============================================  ==============  ============
module contract ``self_heals()``                 **no**          ``False``
executor ``self_heals()``                        yes, via        ``True``
                                                 ``operations``
===============================================  ==============  ============

``admz/operations.py`` asks the *executor*. ``ModuleRegistry.self_heals()``
invokes the *contract* and has no production caller, which is what #374 is
about. Note the defaults point in opposite directions, so "nobody said" does
not resolve to the same answer on the two sides either.

WHAT THIS TEST DELIBERATELY DOES NOT DO
---------------------------------------
It does not pick a source of truth. #374 offers three options — make the
registry authoritative, delete the contract factory, or keep both and detect
disagreement — and the first two are design calls that belong to the owner.
This is the third, and it is the only one that **forecloses nothing**: whichever
way that decision goes, the two declarations agreeing is a precondition rather
than an obstacle.

The invariant is not invented here either. ``admz/executor/base.py``'s own
docstring already states it — *"a module's ``self_heals()`` must agree with its
executor's"* — with nothing enforcing it. A rule asserted in prose and checked
nowhere is how the two declarations were free to drift in the first place.

It passes today, so adopting it costs nothing; it earns its place the first
time someone adds a module and sets one of the two values.
"""

from __future__ import annotations

import pytest

from admz.modules.registry import ModuleRegistry


@pytest.fixture(scope="module")
def modules():
    return ModuleRegistry().discover().get_modules()


def test_discovery_found_the_modules(modules):
    """Vacuity guard: an empty registry satisfies every assertion below.

    Discovery is import-driven, so a module that fails to import disappears
    from this list rather than failing loudly — and would take its own
    agreement check with it.
    """
    ids = sorted(m.id for m in modules)
    assert len(ids) >= 2, f"expected at least devices + acs_pro, discovered {ids}"
    assert "devices" in ids, f"the devices module did not discover: {ids}"


def test_every_module_supplies_an_executor_for_its_own_family(modules):
    """Also a vacuity guard: no executor, nothing to compare, silent pass."""
    for m in modules:
        assert m.family in m.executors(), (
            f"module {m.id!r} declares family {m.family!r} but supplies no "
            f"executor for it ({sorted(m.executors())}), so its self_heals() "
            f"declaration is unenforceable"
        )


def test_contract_and_executor_agree_on_self_heals(modules):
    disagreements = []
    for m in modules:
        contract = m.self_heals()
        for family, executor in m.executors().items():
            if executor.self_heals() != contract:
                disagreements.append(
                    f"{m.id}: contract says {contract!r} for family {m.family!r}, "
                    f"but its {type(executor).__name__} for {family!r} says "
                    f"{executor.self_heals()!r}"
                )
    assert not disagreements, (
        "module and executor disagree about self_heals; the EXECUTOR is what "
        "admz/operations.py actually consults, so the contract's value is the "
        "one silently ignored (#374):\n  " + "\n  ".join(disagreements)
    )


def test_the_two_declarations_default_in_opposite_directions():
    """Pin the asymmetry, because it is surprising and easy to 'tidy' wrongly.

    An unknown family is ``False`` through the registry and ``True`` through
    the executor path. Neither is reachable in a way that matters today — the
    registry helper has no production caller, and an executor being run always
    exists — but anyone unifying the two declarations has to choose which
    default survives, and should choose it deliberately rather than discover it.
    """
    from admz.executor.base import BaseExecutor
    from admz.modules.contract import _self_heals_default

    assert _self_heals_default() is False
    assert BaseExecutor.self_heals(object()) is True  # type: ignore[arg-type]
    assert ModuleRegistry().discover().self_heals("no-such-family") is False
