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
    registry: Any, device_id: str, username: str, password: str
) -> None:
    """Store the provisioned admin credential as the device's ``default``
    account (replacing any existing one)."""
    account_data = {
        "username": username,
        "password": password,
        "account_type": "admin",
        "purpose": "Provisioned by provision_device",
    }
    if registry.account_exists(device_id, "default"):
        registry.remove_account(device_id, "default")
    registry.add_account(device_id, "default", account_data)


async def provision_factory_default(
    catalog: Any,
    executors: Any,
    registry: Any,
    *,
    device_id: str,
    host: str,
    username: str = "root",
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """Provision a FACTORY-DEFAULT device: create the admin user (no auth
    needed), store the credential, mark the device digest-authed. The password
    comes from ``password`` > fleet ``default_password`` > a generated one (the
    value is never returned). Returns a result dict.

    Used by the MCP tool's factory-default path and the deferred ``reprovision``
    recovery handler — the device must actually be factory-default (needsetup)."""
    if password:
        new_password, source = password, "provided"
    else:
        fleet_default = fleet_settings.get("default_password")
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
