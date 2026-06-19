"""Devices module (#1): Axis edge devices via VAPIX.

PR1-P1 introduces this module as the platform's first first-class module. In
this phase it declares only the **executor factory**, so ``build_components``
constructs the ``vapix`` executor through the module registry rather than a
hardcoded literal. The MCP tools, REST routers, nav section, and prompt section
are wired through this module in P2/P3; the device implementation code
physically moves into ``admz/modules/devices/`` in P4 (until then those
implementations live at their historical import paths and this module only
*constructs* the executor — no behavior change).
"""

from __future__ import annotations

import os
from typing import Dict

from admz.modules.contract import Module


def _executors() -> Dict[str, object]:
    """Build the VAPIX executor for the edge-device family.

    Reads ``ADMZ_VAPIX_RETRIES`` exactly as ``build_components`` historically
    did, so the constructed executor is byte-for-byte equivalent.
    """
    from admz.executor.vapix import VapixExecutor

    return {"vapix": VapixExecutor(retries=int(os.getenv("ADMZ_VAPIX_RETRIES", "1")))}


def _self_heals() -> bool:
    # VAPIX devices relearn scheme/auth on the wire (the executor self-heal +
    # the gate's _persist_learned_auth). Server targets (ACS Pro) do not.
    return True


def get_module() -> Module:
    return Module(
        id="devices",
        family="vapix",
        title="Devices",
        catalog_family="vapix",
        executors=_executors,
        self_heals=_self_heals,
    )
