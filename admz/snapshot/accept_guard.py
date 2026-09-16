"""The ADR-0047 accept-baseline guard, for every path (ADR-0070 §4).

An observation commit holds the device's LIVE state, which includes every
value an active demo set. Blessing it would silently bake the demo's config
into the base — after which deactivating the demo pushes nothing and the demo
config survives forever, labelled "baseline". So an accept is refused while an
active demo owns config on the device.

The guard used to live in the REST route alone, so an accept driven from the
chat — the MCP handler and the approved-action executor — never ran it. It now
has three callers: the REST wrapper, the MCP handler **before a card is
minted**, and the executor **before the pointer moves**, so a demo activated
between minting and approval still cannot be baked in.
"""

from __future__ import annotations

import logging
import sqlite3
import subprocess
from typing import Any, Mapping

logger = logging.getLogger(__name__)

#: A genuine active demo owns keys on the device.
ACTIVE_DEMO = 409
#: The guard itself could not be evaluated.
GUARD_UNAVAILABLE = 503


class AcceptRefused(Exception):
    """Accepting now could bake demo config into the baseline.

    ``status`` is :data:`ACTIVE_DEMO` (409) or :data:`GUARD_UNAVAILABLE` (503);
    ``detail`` is the operator-facing sentence.
    """

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail

    @property
    def reason(self) -> str:
        """A stable tag for an outcome or audit row."""
        return "active_demo" if self.status == ACTIVE_DEMO else "guard_unavailable"


def check_accept_allowed(
    *, git_repo: Any, demo_store: Any, device_id: str,
    device_info: Mapping[str, Any],
) -> None:
    """Raise :class:`AcceptRefused` unless accepting ``device_id`` is safe.

    #174: this guard must fail CLOSED, not open. It used to swallow every
    exception and return as if no demo owned anything — on an irreversible,
    silent write, indistinguishable from "verified clean". The asymmetry that
    settles it: a transient sqlite lock or git timeout blocking a legitimate
    accept costs one retry; the same failure permitting the accept costs a
    permanent, undetected corruption of the baseline (the demo's config,
    labelled "baseline" forever, discoverable only by hand-diffing config
    afterwards). Over-refusing is recoverable; under-refusing is not.

    Narrowed to the realistic infrastructure failures — a `DemoStore.list()`
    lock/corruption (`sqlite3.Error`) or a `git show` hang
    (`subprocess.SubprocessError` — `owning_demos` -> `_set_map_for` ->
    `load_fragment` -> `GitRepo.get_file` -> `_run_git`, which re-raises
    `TimeoutExpired` by design — see its own docstring) or git itself being
    unreachable (`OSError`, e.g. the binary missing) — rather than bare
    `Exception`, so a genuine bug inside `owning_demos` still surfaces as a
    bug, not as "guard unavailable".

    ``owning_demos`` is imported at call time on purpose: tests replace it on
    the module to simulate a lock, and a module-level import would not see it.
    """
    try:
        from admz.demos.fragments import owning_demos

        owners = owning_demos(
            git_repo, demo_store.list(), device_id, dict(device_info))
    except (sqlite3.Error, subprocess.SubprocessError, OSError) as exc:
        logger.warning("accept-baseline demo guard unavailable for %s",
                       device_id, exc_info=True)
        raise AcceptRefused(
            GUARD_UNAVAILABLE,
            f"Cannot verify whether an active demo owns config on "
            f"{device_id} right now, and accepting without that check "
            "could permanently bake demo config into the baseline "
            "(ADR-0047 H1). Retry in a moment — this is a transient "
            "check failure, not a refusal.",
        ) from exc
    if owners:
        names = ", ".join(
            f"'{d.name}' ({n} key{'s' if n != 1 else ''})" for d, n in owners)
        raise AcceptRefused(
            ACTIVE_DEMO,
            f"{device_id} has active demo config loaded — accepting now "
            f"would bake it into the baseline. Deactivate {names} first, "
            "or revert their keys.",
        )
