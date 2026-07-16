"""Demo readiness — "the green light" (ADR-0046).

Pure rollup over caches ADMZ already keeps: the device's last-known drift status
(:func:`admz.snapshot.drift_status.drift_status_for`) and its last-known health.
Never a live probe — mirrors the contract of ``drift_status.py``, so the Demos
page and the Devices page can never disagree about a device.

The model turns on one idea: **the baseline IS the demo config** for everyday
demos. A device's normal state already supports the demos it takes part in, so
those demos need no scenario at all and "Prepare" is a *check*, not a push. A
scenario is the exception — a *sidelined* demo you load when needed and snap back
from (ADR-0044). Hence:

* Baseline demos on the same device **coexist** — all ready at once, no conflict.
* Only a sidelined demo takes **exclusive** control (``active_scenario`` is
  one-per-device). Ending it hands the device back, so ``in_scenario: <other>``
  is exactly the **"on loan"** signal.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from admz.snapshot import drift_status as ds

# --- config_source vocabulary -------------------------------------------------
BASELINE = "baseline"
SCENARIO_PREFIX = "scenario:"

# --- per-device config verdicts ----------------------------------------------
READY = "ready"              # config is what the demo needs
NOT_LOADED = "not_loaded"    # sidelined demo, device still on baseline → Prepare
DRIFTED = "drifted"          # baseline demo, device drifted off baseline
ON_LOAN = "on_loan"          # baseline demo, device held by someone's scenario
CONFLICT = "conflict"        # sidelined demo, a DIFFERENT scenario is loaded
NO_BASELINE = "no_baseline"  # nothing blessed to compare against
UNCHECKED = "unchecked"      # baseline set, no drift check has run yet

# Worst-wins ranking for rolling per-device verdicts up to the demo.
_SEVERITY = {
    READY: 0, NOT_LOADED: 1, UNCHECKED: 2, NO_BASELINE: 3,
    DRIFTED: 4, ON_LOAN: 5, CONFLICT: 6,
}

# --- demo-level states --------------------------------------------------------
DEMO_READY = "ready"
DEMO_NOT_LOADED = "not_loaded"  # actionable: hit Prepare
DEMO_BLOCKED = "blocked"        # another demo holds a device
DEMO_NOT_READY = "not_ready"    # drifted / offline / unknown
DEMO_EMPTY = "empty"            # no devices resolved

_HEALTHY = "online"


def scenario_of(config_source: Optional[str]) -> Optional[str]:
    """The scenario name a demo needs, or None when it rides the baseline."""
    if config_source and config_source.startswith(SCENARIO_PREFIX):
        return config_source[len(SCENARIO_PREFIX):].strip() or None
    return None


def config_verdict_for(
    config_source: Optional[str],
    drift: Dict[str, Any],
) -> Dict[str, Any]:
    """Map (what the demo needs) × (what the device is) → a config verdict.

    Args:
        config_source: ``"baseline"`` (default) or ``"scenario:<name>"``.
        drift: a :func:`drift_status_for` result.

    Returns ``{"state", ...}`` — one of the per-device verdict constants, plus
    ``count`` when drifted or ``scenario_name`` when on loan / conflicting.
    """
    state = (drift or {}).get("state")
    want = scenario_of(config_source)

    if want is None:  # ---- baseline demo: the normal config IS the demo config
        if state == ds.IN_SYNC:
            return {"state": READY}
        if state == ds.DRIFTED:
            return {"state": DRIFTED, "count": (drift or {}).get("count", 0)}
        if state == ds.IN_SCENARIO:
            # Someone's sidelined demo has taken the device out of baseline.
            return {"state": ON_LOAN,
                    "scenario_name": (drift or {}).get("scenario_name")}
        if state == ds.NONE:
            return {"state": NO_BASELINE}
        return {"state": UNCHECKED}

    # ---- sidelined demo: it needs its own scenario loaded
    if state == ds.IN_SCENARIO:
        got = (drift or {}).get("scenario_name")
        if got == want:
            return {"state": READY, "scenario_name": got}
        return {"state": CONFLICT, "scenario_name": got}
    if state in (ds.IN_SYNC, ds.DRIFTED):
        return {"state": NOT_LOADED}   # on baseline → Prepare will load it
    if state == ds.NONE:
        return {"state": NO_BASELINE}
    return {"state": UNCHECKED}


def device_readiness(
    config_source: Optional[str],
    device_id: str,
    role: str,
    drift: Dict[str, Any],
    health_status: Optional[str],
) -> Dict[str, Any]:
    """One row of the checklist: this device's config verdict + health."""
    config = config_verdict_for(config_source, drift)
    return {
        "device_id": device_id,
        "role": role or "",
        "config": config,
        "health": health_status or "unknown",
        "online": (health_status or "") == _HEALTHY,
    }


def demo_readiness(
    config_source: Optional[str],
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Roll per-device rows up to the demo's one-glance verdict (worst wins).

    Returns ``{"state", "devices", "blockers", "offline"}`` where ``blockers`` is
    the human-readable reasons the demo isn't ready.
    """
    if not rows:
        return {"state": DEMO_EMPTY, "devices": [], "blockers": ["no devices"],
                "offline": 0}

    worst = max(rows, key=lambda r: _SEVERITY.get(r["config"]["state"], 0))
    worst_state = worst["config"]["state"]
    offline = [r for r in rows if not r["online"]]

    blockers: List[str] = []
    for r in rows:
        st = r["config"]["state"]
        if st == ON_LOAN:
            blockers.append(
                f"{r['device_id']} is on loan to scenario "
                f"'{r['config'].get('scenario_name')}'")
        elif st == CONFLICT:
            blockers.append(
                f"{r['device_id']} has scenario "
                f"'{r['config'].get('scenario_name')}' loaded instead")
        elif st == DRIFTED:
            blockers.append(
                f"{r['device_id']} drifted ({r['config'].get('count', 0)} field(s))")
        elif st == NO_BASELINE:
            blockers.append(f"{r['device_id']} has no baseline")
        elif st == UNCHECKED:
            blockers.append(f"{r['device_id']} config not checked yet")
    for r in offline:
        blockers.append(f"{r['device_id']} is {r['health']}")

    if worst_state in (ON_LOAN, CONFLICT):
        state = DEMO_BLOCKED
    elif worst_state == READY:
        state = DEMO_READY if not offline else DEMO_NOT_READY
    elif worst_state == NOT_LOADED:
        # Expected resting state of a sidelined demo — actionable, not broken.
        state = DEMO_NOT_LOADED if not offline else DEMO_NOT_READY
    else:
        state = DEMO_NOT_READY

    return {"state": state, "devices": rows, "blockers": blockers,
            "offline": len(offline)}
