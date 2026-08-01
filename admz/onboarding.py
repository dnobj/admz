"""Post-add credential onboarding — get a newly registered device to a
working credential without a password ever entering LLM context or a
caller's response.

Resolution order (first hit wins):

1. **Stored credentials verify** — the device already has a working
   ``default`` account: nothing to do.
2. **Factory-defaulted** (unauthenticated ``systemready`` says
   ``needsetup=yes``): provision the admin account from fleet settings
   (``default_username``/``default_password``, else a generated password)
   via :func:`admz.provisioning.provision_factory_default`.
3. **Fleet credential pair authenticates**: the device was set up elsewhere
   with the fleet-standard credentials — save them as the device's account,
   entirely server-side.
4. **Neither**: the caller must ask the operator — chat/MCP callers create a
   credential-capture session (the chat console renders it as an inline
   secure-form widget); the web form links to the capture page.

Every outcome dict carries ``status`` plus caller-safe metadata only —
NEVER a password. Shared by the MCP ``register_device``/``onboard_device``
tools and the REST device-create/onboard routes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from admz.fleet_settings import fleet_settings

logger = logging.getLogger(__name__)

# Kill switch for environments where the onboarding probes must not touch
# the network (the unit-test suite sets it; the probes would otherwise hit
# whatever LAN the test box sits on). Callers still get a well-formed
# credentials_needed outcome.
#
# The switch is declared as the ``test.no_onboarding_probes`` advanced
# capability (GH #132) and read through the registry, which is the only place
# ADMZ parses truthiness. The constant stays as documentation of the env var's
# name — it is what the registry declares and what tests/conftest.py sets.
_DISABLE_ENV = "ADMZ_DISABLE_ONBOARDING_PROBES"
_DISABLE_CAPABILITY = "test.no_onboarding_probes"

# Statuses (stable API for callers/tests):
ALREADY_CREDENTIALED = "already_credentialed"
PROVISIONED = "provisioned"
PROVISION_FAILED = "provision_failed"
FLEET_CREDENTIALS_SAVED = "fleet_credentials_saved"
CREDENTIALS_NEEDED = "credentials_needed"


async def onboard_device_credentials(
    *,
    device_id: str,
    registry: Any,
    catalog: Any,
    executors: Any,
    timeout_seconds: float = 10.0,
) -> Dict[str, Any]:
    """Resolve initial credentials for ``device_id``. Never raises for
    device-side problems; returns a ``status`` dict (see module docstring).
    Passwords are read from fleet settings / written to the registry only —
    they never appear in the returned dict."""
    from admz.fleet.health import (
        _confirm_credentials,
        _persist_probe_marker,
        _tcp_probe,
    )
    from admz.fleet.systemready import read_systemready
    from admz.provisioning import provision_factory_default, store_provisioned_creds

    # NOTE (GH #132): this used to be a bare ``if os.getenv(...)``, so ANY
    # non-empty value enabled the suppressor — ``=0`` meant "probes off". The
    # registry's shared parse accepts {1,true,yes,on} only, so ``=0`` now means
    # what it reads like. conftest.py sets "1", so the suite is unaffected.
    from admz import capabilities

    if capabilities.is_active(_DISABLE_CAPABILITY):
        return {"status": CREDENTIALS_NEEDED, "device_id": device_id,
                "reason": "onboarding probes disabled in this environment"}

    try:
        device_info = registry.get_device_info(device_id)
    except Exception as exc:  # noqa: BLE001 - unknown device
        return {"status": CREDENTIALS_NEEDED, "device_id": device_id,
                "reason": f"device lookup failed: {exc}"}

    executor = (executors or {}).get("vapix")
    if executor is None or catalog is None:
        return {"status": CREDENTIALS_NEEDED, "device_id": device_id,
                "reason": "vapix executor/catalog unavailable"}

    probe_info = {**device_info, "device_id": device_id}

    # Fast preflight: don't spend executor timeouts on a device that isn't
    # even accepting TCP (typo'd host, powered off, wrong subnet). Capture
    # remains available — storing credentials doesn't need the device up.
    host = device_info.get("host") or device_info.get("ip_address") or ""
    if host:
        up = await _tcp_probe(host, 80, 1.5)
        if up is None:
            up = await _tcp_probe(host, 443, 1.5)
        if up is None:
            return {"status": CREDENTIALS_NEEDED, "device_id": device_id,
                    "reason": f"device at {host} is not reachable"}

    # ---- 1. Stored credentials already work? -----------------------------
    stored: Optional[Dict[str, Any]] = None
    try:
        stored = registry.get_credentials(device_id)
    except Exception:  # noqa: BLE001 - no account yet
        stored = None
    if stored and stored.get("password"):
        ok, _facts, learned = await _confirm_credentials(
            catalog=catalog, executor=executor, device_info=probe_info,
            device_id=device_id, credentials=stored,
            timeout_seconds=timeout_seconds, strict=True,
        )
        if ok is True:
            if learned:
                _persist_probe_marker(registry, device_id, device_info, learned)
            return {"status": ALREADY_CREDENTIALED, "device_id": device_id}
        # Rejected or indeterminate: fall through — a stale stored password
        # is exactly what the fleet-pair try below may repair.

    # ---- 2. Factory-defaulted → provision from fleet settings ------------
    ready = await read_systemready(
        catalog, executor, probe_info,
        stored or {"username": "", "password": ""},
    )
    if ready and ready.get("needsetup"):
        host = device_info.get("host") or device_info.get("ip_address")
        result = await provision_factory_default(
            catalog, executors, registry,
            device_id=device_id, host=host,
        )
        if result.get("success"):
            return {
                "status": PROVISIONED, "device_id": device_id,
                "username": result.get("username"),
                "password_source": result.get("password_source"),
            }
        return {"status": PROVISION_FAILED, "device_id": device_id,
                "error": result.get("error")}

    # ---- 3. Fleet credential pair ----------------------------------------
    fleet_password = fleet_settings.get("default_password")
    if fleet_password:
        fleet_username = fleet_settings.get("default_username") or "root"
        # strict: only an authenticated 2xx proves the pair — saving on a
        # lenient "not rejected" once stored a bad password (P3408, 2026-07-02).
        # A 2xx from the corroborating param.cgi read counts (GH #149): strict
        # rejects *non-auth* answers as proof, and that is real proof.
        ok, facts, learned = await _confirm_credentials(
            catalog=catalog, executor=executor, device_info=probe_info,
            device_id=device_id,
            credentials={"username": fleet_username, "password": fleet_password},
            timeout_seconds=timeout_seconds, strict=True,
        )
        if ok is True:
            store_provisioned_creds(
                registry, device_id, fleet_username, fleet_password,
                purpose="Fleet default credentials verified at onboarding",
            )
            if learned:
                _persist_probe_marker(registry, device_id, device_info, learned)
            # Same opportunistic backfill as the health monitor: the verify
            # response is basicdeviceinfo, so lift model/serial/firmware. Empty
            # on the corroborated path (a param dump, not basicdeviceinfo's
            # shape) — the ``if facts`` / ``if v`` guards below mean that
            # never erases an already-stored model/serial.
            if facts:
                changed = {
                    k: v for k, v in facts.items()
                    if v and str(device_info.get(k) or "") != str(v)
                }
                if changed:
                    try:
                        registry.update_device_info(device_id, changed)
                    except Exception:  # noqa: BLE001 - best effort
                        pass
            return {"status": FLEET_CREDENTIALS_SAVED, "device_id": device_id,
                    "username": fleet_username}
        reason = ("fleet credentials rejected by the device"
                  if ok is False else
                  "device did not answer the credential check")
    else:
        reason = "no fleet default_password configured"

    return {"status": CREDENTIALS_NEEDED, "device_id": device_id, "reason": reason}
