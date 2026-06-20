"""A transparent registry proxy that resolves the synthetic ACS server target.

ACS Pro is a *server*, not a device with a registry row. To route ACS actions
through the same confirmation gate as device ops (which fetch the target from
the registry via ``device_exists`` / ``get_device_info`` / ``get_credentials``),
we wrap the real registry: lookups for the reserved id ``acs-server`` resolve to
the configured ACS connection (host + verify_tls, no credentials — Negotiate),
and **every other call delegates unchanged** to the wrapped registry. So no
synthetic device row pollutes ``list_devices`` / the roster / health / snapshot —
the ACS target only exists at the gate's execution tail.
"""

from __future__ import annotations

from typing import Any, Dict

ACS_DEVICE_ID = "acs-server"


class AcsRegistryView:
    """Wrap a DeviceRegistry so ``acs-server`` resolves to the ACS connection."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def device_exists(self, device_id: str) -> bool:
        if device_id == ACS_DEVICE_ID:
            from admz.modules.acs_pro.config import acs_enabled

            return acs_enabled()
        return self._inner.device_exists(device_id)

    def get_device_info(self, device_id: str) -> Dict[str, Any]:
        if device_id == ACS_DEVICE_ID:
            from admz.modules.acs_pro.config import acs_config, base_url

            cfg = acs_config()
            return {
                "device_id": ACS_DEVICE_ID,
                "host": base_url(),
                "verify_tls": cfg["verify_tls"],
                "kind": "acs_server",
            }
        return self._inner.get_device_info(device_id)

    def get_credentials(self, device_id: str) -> Dict[str, str]:
        if device_id == ACS_DEVICE_ID:
            # Negotiate — no stored credential; the execution tail falls back to
            # empty creds on AccountNotFoundError, exactly as for a device with
            # no stored account.
            from admz.exceptions import AccountNotFoundError

            raise AccountNotFoundError("ACS Pro uses Negotiate (no stored credentials)")
        return self._inner.get_credentials(device_id)

    def __getattr__(self, name: str) -> Any:
        # Everything else (update_device_info, list_devices, …) delegates.
        return getattr(self._inner, name)
