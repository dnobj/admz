"""Device provisioning primitives — shared between the MCP ``provision_device``
tool and the deferred ``reprovision`` recovery handler (factory-defaulted →
re-provision when it comes back).

Extracted from the MCP server so the API-process health loop can run the same
credential-creation logic the MCP tool uses (the MCP server runs as a separate
subprocess).

SECURITY: this creates an admin account on a device and stores the password in
the registry. The password is NEVER returned, logged, or exposed; ADMZ uses it
only to reach the device. The caller is responsible for authorization (the MCP
tool gates; the recovery handler runs only pre-approved deferred actions).
"""

from __future__ import annotations

import secrets
from typing import Any, Dict, Optional, Tuple

from admz.fleet_settings import fleet_settings


def generate_device_password(length: int = 24) -> str:
    """A strong random password with upper/lower/digit guaranteed."""
    while True:
        pw = secrets.token_urlsafe(length)[:length]
        if (any(c.isupper() for c in pw)
                and any(c.islower() for c in pw)
                and any(c.isdigit() for c in pw)):
            return pw


def serial_to_mac(serial: str) -> str:
    s = serial.upper().replace(":", "").replace("-", "")
    if len(s) != 12:
        return serial
    return ":".join(s[i:i + 2] for i in range(0, 12, 2))


async def execute_on_host(
    catalog: Any,
    executors: Any,
    host: str,
    operation_id: str,
    params: Dict[str, str],
    *,
    credentials: Optional[Dict[str, str]] = None,
    auth_method: str = "digest",
    auth: Optional[Dict[str, str]] = None,
    family: str = "vapix",
) -> Tuple[bool, Optional[str]]:
    """Run a VAPIX op against a bare host (no registered device). Returns
    ``(ok, error)``."""
    operation = catalog.get_operation(family, operation_id)
    if not operation:
        return False, f"Operation '{operation_id}' not found in {family} catalog"

    executor = executors.get(family)
    if not executor:
        return False, f"No executor for family '{family}'"

    device: Dict[str, Any] = {
        "host": host,
        "device_id": f"_host_{host}",
        "auth_method": auth_method,
        "port": 80,
    }
    if auth:
        device["auth"] = auth
    else:
        device["auth"] = {"http": auth_method, "https": auth_method, "scheme": "http"}

    creds = credentials or {"username": "", "password": ""}
    op_dict = {
        "id": operation.id,
        "cgi": operation.cgi,
        "method": operation.method,
        "risk_level": operation.risk_level,
        "request": operation.request,
        "response": operation.response,
        "requires": operation.requires,
        "_endpoint": operation.endpoint,
        "_generation": operation.generation,
        "_auth": operation.auth,
        "service_impact": operation.service_impact,
        "base_path": operation.base_path,
        "path": operation.path,
    }
    result = await executor.execute(op_dict, device, creds, params)
    if result.success:
        return True, None
    return False, result.error or f"HTTP {result.status_code}"


def store_provisioned_creds(
    registry: Any, device_id: str, username: str, password: str,
    purpose: str = "Provisioned by provision_device",
) -> None:
    """Store the provisioned admin credential as the device's ``default``
    account (replacing any existing one)."""
    account_data = {
        "username": username,
        "password": password,
        "account_type": "admin",
        "purpose": purpose,
    }
    if registry.account_exists(device_id, "default"):
        registry.remove_account(device_id, "default")
    registry.add_account(device_id, "default", account_data)


#: The account ADMZ creates for its own ongoing use (ADR-0061, FR-CRED-011).
OWN_ACCOUNT_USERNAME = "admz"


async def adopt_with_admz_account(
    catalog: Any,
    executors: Any,
    registry: Any,
    *,
    device_id: str,
    host: str,
    entry: Dict[str, str],
    device_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Use a working entry credential to create ADMZ's own account.

    ADR-0061: fleet credentials get ADMZ **in**; the per-device ``admz`` account
    keeps it in. This is the second half — the caller has already proved
    ``entry`` authenticates, and this converts that one-time access into a
    credential nothing else holds.

    Differs from :func:`provision_factory_default` in the one way that matters:
    that function writes to a device with **no** account and therefore uses
    ``auth_method="none"``. This one authenticates *as* the entry credential,
    because the device is already set up.

    **The entry credential is never removed or rotated.** If ADMZ's database is
    lost, every generated password goes with it and the entry credential is the
    only way back in. That is a rule, not a preference — see ADR-0061.

    Returns a result dict; the generated password is never in it.
    """
    new_password = generate_device_password()
    ok, error = await execute_on_host(
        catalog, executors, host, "pwdgrp.cgi:add-user",
        params={
            "username": OWN_ACCOUNT_USERNAME,
            "password": new_password,
            "group": "root",
            "secondary_groups": "admin:operator:viewer:ptz",
        },
        credentials=entry,
        auth_method=(device_info or {}).get("auth_method") or "digest",
        auth=(device_info or {}).get("auth"),
    )
    if not ok:
        # The entry credential still works even though this did not, so the
        # caller can fall back to storing it rather than losing the device.
        return {"success": False, "status": "admz_account_failed",
                "device_id": device_id, "error": error}

    store_provisioned_creds(
        registry, device_id, OWN_ACCOUNT_USERNAME, new_password,
        purpose="ADMZ's own account, created at adoption (ADR-0061)",
    )
    return {"success": True, "status": "admz_account_created",
            "device_id": device_id, "username": OWN_ACCOUNT_USERNAME}


async def provision_factory_default(
    catalog: Any,
    executors: Any,
    registry: Any,
    *,
    device_id: str,
    host: str,
    username: str = "root",
    password: Optional[str] = None,
    allow_fleet_default: bool = False,
) -> Dict[str, Any]:
    """Provision a FACTORY-DEFAULT device: create the admin user (no auth
    needed), store the credential, mark the device digest-authed. The password
    is ``password`` if given, else a generated one (the value is never
    returned). Returns a result dict.

    Used by onboarding's factory-default step and the deferred ``reprovision``
    recovery handler — the device must actually be factory-default (needsetup).
    (The MCP ``provision_device`` tool carries its own copy of this write and
    follows the same rule.)

    **The generated password wins** — FR-CRED-007, ADR-0064 slice E. Until
    2026-09-06 the fleet ``default_password`` was preferred over a generated
    one whenever a caller did not opt out. ADR-0061 split the fleet
    credential's two jobs: it is an *entry* credential — an input for
    authentication on a device set up elsewhere — never a value written to a
    device. Writing it onto a brand-new account was the least appropriate
    place to prefer it:

    - ``needsetup=yes`` — the only signal this call exists to respond to — is
      read from an unauthenticated device response, and the deferred
      ``reprovision`` task can fire up to 24h after an operator approved it,
      unattended, against whatever host answers at the device's registered
      address at that later moment. ADMZ cannot authenticate a peer that (by
      definition of ``needsetup=yes``) has no account yet, and no other
      identity check exists on this path (GH #185). Sending the *shared
      fleet-wide* password there means a spoofed peer — a reassigned DHCP
      lease, ARP spoofing, the port a decommissioned camera vacated — walks
      away with a credential valid on every other device ADMZ manages. A
      freshly generated one does not verify the peer either (nothing here
      does), but it makes who the peer turns out to be matter much less: the
      disclosed value is reused nowhere else, and is not even valid against
      the real device at this ``device_id``, which was never contacted. The
      disclosure itself, and the registry then believing it holds a working
      credential for hardware it never touched, are #185's residual gap.
    - A leak from one device stops at that device (#296's own reasoning).

    ``allow_fleet_default=True`` is the explicit opt-in a caller must ask for
    by name to have the fleet ``default_password`` written; no caller in the
    tree does, and #296 part 2 (shared versus per-device as a first-class
    setting) is where a deliberate shared mode would live. The trade ADR-0061
    accepted, stated plainly: a device provisioned here holds only its
    generated password, so if ADMZ's database is lost the entry credentials do
    not get back in — the device is factory-reset and provisioned again. The
    username stays ``root`` until a measurement says an Axis unit accepts a
    non-``root`` first account (ADR-0064 decision 9).
    """
    if password:
        new_password, source = password, "provided"
    else:
        fleet_default = (
            fleet_settings.get("default_password") if allow_fleet_default else None
        )
        if fleet_default:
            new_password, source = fleet_default, "fleet_default"
        else:
            new_password, source = generate_device_password(), "generated"

    ok, error = await execute_on_host(
        catalog, executors, host, "pwdgrp.cgi:add-user",
        params={
            "username": username,
            "password": new_password,
            "group": "root",
            "secondary_groups": "admin:operator:viewer:ptz",
        },
        auth_method="none",
    )
    if not ok:
        return {"success": False, "status": "vapix_error",
                "device_id": device_id, "error": error}

    store_provisioned_creds(registry, device_id, username, new_password)
    try:
        registry.update_device_info(device_id, {"auth_method": "digest"})
    except Exception:  # noqa: BLE001 - best effort
        pass
    return {"success": True, "status": "provisioned", "device_id": device_id,
            "username": username, "password_source": source}
