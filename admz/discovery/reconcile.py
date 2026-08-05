"""MAC-based IP reconciliation.

Devices move IP when DHCP leases change. ADMZ keys a device by its MAC
(the ``device_id`` is the normalized MAC), so when a device's MAC turns up at
a new IP during discovery, its registered ``host`` can be corrected
automatically — following the MAC, not the stale IP. This prevents the
"looks online but ADMZ says unreachable" class of failures where the address
moved out from under the registry.

**The MAC is an unauthenticated claim, so it is not sufficient on its own**
(#193). It arrives in an mDNS TXT record (`mdns_discovery.py:359`) parsed from
a raw multicast UDP packet — nothing signs it — and ADMZ's ``device_id`` *is*
the normalized MAC, so an attacker on the segment needs only to assert a MAC
that is already registered. The old ``by_mac.setdefault(mac, ip)`` comment said
it plainly: *first responder for a MAC wins*, which is a race anyone adjacent
can enter.

Repointing a **credentialed** device is the harmful case: every later
operation — a health probe, a snapshot, an operator action — then authenticates
to whoever holds the new address.

So a rewrite now requires the new address to **prove** it is the device, by
authenticating with the device's own stored credentials
(``fleet.health._confirm_credentials`` in ``strict=True`` mode, where only a
genuine authenticated 2xx counts). That turns *"whoever answers first"* into
*"whoever can prove they are the device"*.

Why not a serial match: ``serial_number`` on a discovered device comes from the
**same forgeable sources** as the MAC — the mDNS TXT record
(`mdns_discovery.py:381`), SSDP (`ssdp_discovery.py:199`) and an
unauthenticated HTTP probe (`http_probe.py:223`). An attacker who forges one
forges the other in the same packet, so matching it proves nothing.

Verification and audit live **here**, not at the calling surface. Today the only
production caller is the MCP tool, but this module's own contract (below) says
"the MCP/REST/CLI surfaces run discovery and call in here" — a check at one
entry point is a check the next surface does not inherit, which is the shape
#299/#313 kept re-learning.

Leaf module: takes ``registry`` + the discovered devices as parameters; the
MCP/REST/CLI surfaces run discovery and call in here.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def normalize_mac(mac: Any) -> str:
    """Strip separators and upper-case a MAC so it matches a ``device_id``.

    ``"B8:A4:4F:0C:5B:32"`` and ``"b8-a4-4f-0c-5b-32"`` both → ``"B8A44F0C5B32"``.
    """
    if not mac:
        return ""
    return "".join(c for c in str(mac) if c.isalnum()).upper()


def _discovered_mac(d: Any) -> str:
    raw = d.get("mac_address") if isinstance(d, dict) else getattr(d, "mac_address", None)
    return normalize_mac(raw)


def _discovered_ip(d: Any) -> str:
    ip = d.get("ip_address") if isinstance(d, dict) else getattr(d, "ip_address", None)
    return str(ip) if ip else ""


async def _identity_proven(
    *, registry: Any, catalog: Any, executor: Any, device_id: str,
    device_info: Dict[str, Any], new_ip: str, timeout_seconds: float,
) -> "tuple[bool, str]":
    """Can the host at ``new_ip`` prove it is ``device_id``? ``(ok, reason)``.

    The proof is an authenticated request with the device's **own stored
    credentials**, in ``strict=True`` mode — only a genuine authenticated 2xx
    counts, so a device that merely *answers* proves nothing
    (``fleet/health.py``).

    **Fails closed.** Anything other than a definite yes refuses the rewrite:
    no credentials, no executor, an explicit rejection, or an indeterminate
    answer. A stale registry entry is a nuisance; a credentialed device
    pointed at an attacker is a credential disclosure.
    """
    if catalog is None or executor is None:
        return False, "no catalog/executor available to verify identity"
    try:
        creds = registry.get_credentials(device_id)
    except Exception:  # noqa: BLE001 — no account is a legitimate state
        creds = None
    if not creds or not creds.get("password"):
        # Nothing to prove with. Refusing is still right: an uncredentialed
        # device repointed at an attacker becomes the target of the NEXT
        # onboarding, which sends the fleet default password (#185).
        return False, "device has no stored credentials, so identity cannot be proven"

    # ── DEPENDS ON GH #171 / PR #292 ────────────────────────────────────────
    # This probe DELIBERATELY sends the device's credentials to an address we
    # have not yet verified — that is the whole mechanism. It is safe only
    # because HTTP Digest never puts the password on the wire, and because
    # `executor/vapix.py` REFUSES to relearn Basic over a plaintext channel
    # (the `offered == "basic" and _is_plaintext_channel(scheme)` branch).
    #
    # If that refusal is ever relaxed, this line silently becomes a PLAINTEXT
    # CREDENTIAL DISCLOSURE to an attacker-chosen host: the claimant answers
    # `401 WWW-Authenticate: Basic`, the executor retries with `httpx.BasicAuth`
    # — which sends `Authorization: Basic base64(user:pass)` preemptively — and
    # the password crosses in the clear to whoever won the mDNS race.
    #
    # The coupling is pinned by
    # `tests/test_reconcile_requires_proof.py::TestThisDependsOnTheBasicDowngradeRefusal`,
    # which fails here rather than in the executor's own tests, so anyone
    # relaxing that branch is told which caller they just broke.
    from admz.fleet.health import _confirm_credentials

    probe_info = {**device_info, "host": new_ip, "ip_address": new_ip,
                  "device_id": device_id}
    try:
        ok, _facts, _learned = await _confirm_credentials(
            catalog=catalog, executor=executor, device_info=probe_info,
            device_id=device_id, credentials=creds,
            timeout_seconds=timeout_seconds, strict=True,
        )
    except Exception as exc:  # noqa: BLE001 — a failed probe is not a proof
        return False, f"identity probe failed: {exc}"
    if ok is True:
        return True, ""
    if ok is False:
        return False, "the host at the new address rejected this device's credentials"
    return False, "identity could not be confirmed (indeterminate probe)"


async def reconcile_device_ips(
    registry: Any,
    discovered: Any,
    *,
    catalog: Any = None,
    executors: Any = None,
    principal: Any = None,
    timeout_seconds: float = 5.0,
) -> List[Dict[str, Any]]:
    """Update registered devices whose MAC now answers at a different IP.

    ``discovered`` is an iterable of DiscoveredDevice objects (or dicts) with
    ``mac_address`` + ``ip_address``. A device is matched by its stored
    ``mac_address`` if present, else by its ``device_id`` (the MAC).

    **Every rewrite is verified and audited** (#193). A candidate address must
    prove it is the device (see :func:`_identity_proven`) before the registry
    is touched, and both the applied change and the refusal are recorded with
    ``record_event`` — before this there were zero audit rows on an address
    change, so a credentialed device could move silently.

    Returns one entry per candidate: ``{device_id, old_host, new_ip}`` plus
    ``applied: bool`` and, when refused, ``reason``.
    """
    from admz.audit import record_event

    executor = (executors or {}).get("vapix") if executors else None

    by_mac: Dict[str, str] = {}
    for d in discovered or []:
        mac, ip = _discovered_mac(d), _discovered_ip(d)
        if mac and ip:
            # Still first-responder, but winning the race no longer wins the
            # rewrite — the winner must then authenticate as the device.
            by_mac.setdefault(mac, ip)

    changes: List[Dict[str, Any]] = []
    try:
        devices = registry.list_devices()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("reconcile: list_devices failed: %s", exc)
        return changes

    for dev in devices:
        device_id = dev.get("device_id")
        if not device_id:
            continue
        mac = normalize_mac(dev.get("mac_address") or device_id)
        new_ip = by_mac.get(mac)
        cur_host = dev.get("host")
        if not new_ip or new_ip == cur_host:
            continue

        proven, why = await _identity_proven(
            registry=registry, catalog=catalog, executor=executor,
            device_id=device_id, device_info=dev, new_ip=new_ip,
            timeout_seconds=timeout_seconds,
        )
        if not proven:
            logger.warning(
                "reconcile: REFUSED %s host %s -> %s (MAC %s): %s",
                device_id, cur_host, new_ip, mac, why,
            )
            record_event(
                principal, "device.address_reconcile_refused",
                resource=f"device:{device_id}", success=False,
                error_message=why,
                details={"old_host": cur_host, "claimed_ip": new_ip, "mac": mac},
            )
            changes.append({
                "device_id": device_id, "old_host": cur_host, "new_ip": new_ip,
                "applied": False, "reason": why,
            })
            continue

        try:
            registry.update_device_info(device_id, {"host": new_ip})
            logger.info(
                "reconcile: %s host %s -> %s (MAC %s, identity verified)",
                device_id, cur_host, new_ip, mac,
            )
            record_event(
                principal, "device.address_reconciled",
                resource=f"device:{device_id}",
                details={"old_host": cur_host, "new_host": new_ip, "mac": mac,
                         "verified": "stored-credential authentication"},
            )
            changes.append({"device_id": device_id, "old_host": cur_host,
                            "new_ip": new_ip, "applied": True})
        except Exception as exc:
            logger.warning("reconcile: could not update %s: %s", device_id, exc)
            record_event(
                principal, "device.address_reconciled",
                resource=f"device:{device_id}", success=False,
                error_message=str(exc),
                details={"old_host": cur_host, "new_host": new_ip, "mac": mac},
            )
            changes.append({
                "device_id": device_id, "old_host": cur_host,
                "new_ip": new_ip, "applied": False, "error": str(exc),
            })
    return changes
