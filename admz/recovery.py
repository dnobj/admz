"""Synchronous reboot-recovery poller (GitHub issue #49, v1).

Reboot-class operations return an immediate "command accepted" response,
then the device goes offline for ~30-90s and recovers on its own. This
module polls the device's ``systemready.cgi:systemReady`` API (response
fields: ``systemready``, ``needsetup``, ``uptime``, ``bootid``) until the
device demonstrably completed a reboot, or the timeout elapses.

Like ``admz/operations.py`` this is a **leaf**: it receives ``catalog`` /
``registry`` as parameters and never imports the MCP server or any route
module, so the v2 REST surface can reuse it without an import cycle.

Designed for REPEATED calls from the chatbot: the chat SSE stream aborts a
turn after ~120s without an event and no events flow while an MCP tool
runs, so a single call defaults to a 90s budget and a not-yet-recovered
result comes back as ``status="still_waiting"`` carrying the observed
``baseline_bootid`` — pass that to the next call and detection continues
seamlessly across calls.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, Optional

from admz.exceptions import (
    AccountNotFoundError,
    DeviceNotFoundError,
    OperationNotFoundError,
)

SYSTEMREADY_OP = "systemready.cgi:systemReady"

DEFAULT_TIMEOUT_S = 90.0
MIN_TIMEOUT_S, MAX_TIMEOUT_S = 5.0, 600.0
DEFAULT_POLL_INTERVAL_S = 3.0
MIN_POLL_INTERVAL_S, MAX_POLL_INTERVAL_S = 1.0, 30.0
# Each probe uses its own short-timeout executor: the shared one defaults to
# 15s + retries, which would make every offline probe block ~30s and wreck
# the poll cadence.
PROBE_TIMEOUT_S = 5.0
# A healthy response with uptime below this means the device booted recently
# — treat as recovered even when we never saw it go down (called late).
FRESH_BOOT_UPTIME_S = 180
# A 401/403 means the device is UP but the stored credentials don't work —
# give up fast instead of polling out the whole budget. Two consecutive,
# because a single 401 can be transient while the web server comes up
# mid-boot before the auth subsystem.
AUTH_FAILFAST_CONSECUTIVE = 2


def _clamp(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, out))


def _to_int_or_none(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def await_device_recovery(
    *,
    device_id: str,
    timeout_s: Any = DEFAULT_TIMEOUT_S,
    poll_interval_s: Any = DEFAULT_POLL_INTERVAL_S,
    baseline_bootid: str = "",
    catalog: Any,
    registry: Any,
    probe_executor: Any = None,
    sleep: Optional[Callable[[float], Awaitable[Any]]] = None,
    monotonic: Optional[Callable[[], float]] = None,
) -> Dict[str, Any]:
    """Poll ``systemready`` until ``device_id`` completed a reboot.

    Recovery requires a healthy ``systemready=yes`` response PLUS evidence
    of an actual boot cycle: an observed offline period, an observed
    ``systemready=no``, a bootid change vs the baseline, an uptime decrease
    between probes, or a fresh uptime (< ``FRESH_BOOT_UPTIME_S``). A first
    healthy response on the pre-reboot boot (old bootid, high uptime) is
    NOT recovery — the device just hasn't gone down yet.

    Returns an envelope with ``status`` one of ``recovered`` /
    ``still_waiting`` / ``auth_failed``. ``probe_executor`` / ``sleep`` /
    ``monotonic`` are test seams.
    """
    timeout = _clamp(timeout_s, DEFAULT_TIMEOUT_S, MIN_TIMEOUT_S, MAX_TIMEOUT_S)
    interval = _clamp(
        poll_interval_s, DEFAULT_POLL_INTERVAL_S,
        MIN_POLL_INTERVAL_S, MAX_POLL_INTERVAL_S,
    )

    if not registry.device_exists(device_id):
        raise DeviceNotFoundError(f"Device not found: {device_id}")

    operation = catalog.get_operation("vapix", SYSTEMREADY_OP)
    if not operation:
        raise OperationNotFoundError(
            f"Operation '{SYSTEMREADY_OP}' not found in the vapix catalog — "
            "update axis-api-atlas"
        )
    op_dict = operation.to_executor_dict()

    device = registry.get_device_info(device_id)
    device["device_id"] = device_id
    try:
        credentials = registry.get_credentials(device_id)
    except AccountNotFoundError:
        credentials = {"username": "", "password": ""}

    if probe_executor is None:
        from admz.executor.vapix import VapixExecutor

        probe_executor = VapixExecutor(timeout=PROBE_TIMEOUT_S, retries=0)
    sleep = sleep or asyncio.sleep
    monotonic = monotonic or time.monotonic

    start = monotonic()
    baseline: Optional[str] = baseline_bootid or None
    prev_uptime: Optional[int] = None
    offline_observed = False
    not_ready_observed = False
    consecutive_auth = 0
    polls = 0
    last: Dict[str, Any] = {}
    last_error = ""

    def _envelope(status: str, *, recovered: bool, success: bool,
                  message: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "success": success,
            "recovered": recovered,
            "status": status,
            "device_id": device_id,
            "waited_s": round(monotonic() - start, 1),
            "polls": polls,
            "offline_observed": offline_observed,
            "not_ready_observed": not_ready_observed,
            "bootid": last.get("bootid", ""),
            "uptime_s": last.get("uptime_s"),
            "needsetup": last.get("needsetup", False),
            "baseline_bootid": baseline or "",
            "timeout_s": timeout,
            "poll_interval_s": interval,
            "message": message,
        }
        if status == "auth_failed":
            out["error"] = last_error
        return out

    while True:
        polls += 1
        # The systemready op's {timeout:int} long-poll param is deliberately
        # omitted (params={}) — the device answers immediately with current
        # state and the loop owns the wait.
        result = await probe_executor.execute(op_dict, device, credentials, {})

        if result.success:
            consecutive_auth = 0
            data = result.parsed_data if isinstance(result.parsed_data, dict) else {}
            ready = str(data.get("systemready", "")).lower() == "yes"
            bootid = str(data.get("bootid", "") or "")
            needsetup = str(data.get("needsetup", "")).lower() == "yes"
            uptime = _to_int_or_none(data.get("uptime"))
            last = {"bootid": bootid, "uptime_s": uptime, "needsetup": needsetup}

            if baseline is None and bootid:
                baseline = bootid

            uptime_decreased = (
                prev_uptime is not None
                and uptime is not None
                and uptime < prev_uptime
            )
            if uptime is not None:
                prev_uptime = uptime

            if not ready:
                not_ready_observed = True
            else:
                recovered = (
                    offline_observed
                    or not_ready_observed
                    or bool(bootid and baseline and bootid != baseline)
                    or uptime_decreased
                    or (uptime is not None and uptime < FRESH_BOOT_UPTIME_S)
                )
                if recovered:
                    waited = round(monotonic() - start, 1)
                    msg = (
                        f"Device {device_id} recovered after {waited}s "
                        f"(uptime {uptime}s, boot id {bootid or 'n/a'}"
                    )
                    if baseline and bootid and bootid != baseline:
                        msg += f", changed from {baseline}"
                    msg += ")."
                    if needsetup:
                        msg += (
                            " NOTE: needsetup=yes — the device came back in "
                            "factory-default state and needs provisioning."
                        )
                    return _envelope(
                        "recovered", recovered=True, success=True, message=msg
                    )
        else:
            if result.status_code in (401, 403):
                consecutive_auth += 1
                last_error = result.error or f"HTTP {result.status_code}"
                if consecutive_auth >= AUTH_FAILFAST_CONSECUTIVE:
                    return _envelope(
                        "auth_failed", recovered=False, success=False,
                        message=(
                            f"Device {device_id} is responding but rejected "
                            f"credentials (HTTP {result.status_code}) on "
                            f"{consecutive_auth} consecutive probes — it is "
                            "up, but the stored credentials don't work. "
                            "Stopping; verify credentials (e.g. "
                            "test_device_credentials) instead of waiting."
                        ),
                    )
            else:
                # Connection refused / timed out / 5xx — device is (still) down.
                offline_observed = True
                consecutive_auth = 0

        elapsed = monotonic() - start
        if elapsed + interval > timeout:
            waited = round(elapsed, 1)
            if offline_observed or not_ready_observed:
                seen = "device went offline during the window but has not come back"
            elif baseline:
                seen = (
                    "device is up but still reporting its pre-reboot state "
                    f"(boot id {baseline})"
                )
            else:
                seen = "device did not respond to any probe"
            return _envelope(
                "still_waiting", recovered=False, success=True,
                message=(
                    f"Device {device_id} not confirmed recovered after "
                    f"{waited}s ({polls} probes; {seen}). Call "
                    f"await_device_recovery again with "
                    f"baseline_bootid='{baseline or ''}' to continue waiting."
                ),
            )
        await sleep(interval)
