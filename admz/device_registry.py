"""
Abstract interface for device credential registries.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

from admz.exceptions import BackendError


def canonical_mac(value: Optional[str]) -> str:
    """Normalize a MAC address to a comparable canonical form.

    Strips separators (``:``, ``-``, ``.``, spaces) and uppercases, so that
    ``"AC:CC:8E:E6:E7:EE"`` and the colon-stripped device-id form
    ``"ACCC8EE6E7EE"`` compare equal. Returns ``""`` for falsy input.
    """
    if not value:
        return ""
    out = str(value).upper()
    for sep in (":", "-", ".", " "):
        out = out.replace(sep, "")
    return out


class DeviceRegistry(ABC):
    """
    Abstract base class for device credential registries.

    Provides a unified interface for managing device credentials and metadata
    across different storage backends (Vault, AWS Secrets Manager, etc.).

    Supports multi-account management where each device can have multiple
    accounts (service accounts, admin accounts, etc.) with different purposes.
    """

    @abstractmethod
    def get_credentials(
        self,
        device_id: str,
        account_id: str = "default",
        requester: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get credentials for a specific device account.

        Args:
            device_id: Unique device identifier (e.g., 'front-door')
            account_id: Account identifier (e.g., 'aoa-agent', 'admin').
                       Defaults to 'default'.
            requester: Optional identifier of who/what is requesting access
                      (e.g., 'john@company.com', 'aoa-agent-service').
                      Used for access control and audit logging.

        Returns:
            Dictionary with credential fields:
                - username: Authentication username
                - password: Authentication password
                - host: Device IP or hostname
                - account_type: Type of account (service, admin, etc.)
                - permissions: List of permissions
                - purpose: Description of account purpose
                Plus any additional account-specific metadata

        Raises:
            DeviceNotFoundError: Device not found in registry
            AccountNotFoundError: Account not found for device
            PermissionDeniedError: Access denied based on access control rules
            BackendError: Backend storage system error
        """
        pass

    @abstractmethod
    def get_device_info(self, device_id: str) -> Dict[str, Any]:
        """
        Get device information and metadata for a device.

        Returns non-sensitive device information (no credentials).

        Args:
            device_id: Unique device identifier

        Returns:
            Dictionary with device information:
                - host: Device IP or hostname
                - nickname: Human-readable device nickname (optional)
                - ip_address: IP address
                - serial_number: Device serial number
                - mac_address: MAC address
                - firmware_version: Firmware version
                - model: Device model
                - warranty_expiration: Warranty expiration date
                - location: Physical location
                - tags: List of tags
                - network: Network configuration (vlan, subnet)
                Plus any additional device-specific metadata

        Raises:
            DeviceNotFoundError: Device not found in registry
            BackendError: Backend storage system error
        """
        pass

    @abstractmethod
    def get_device_by_nickname(self, nickname: str) -> Optional[Dict[str, Any]]:
        """
        Get device information by nickname.

        Args:
            nickname: Human-readable device nickname

        Returns:
            Device information dictionary, or None if not found
        """
        pass

    @abstractmethod
    def list_devices(self) -> List[Dict[str, Any]]:
        """
        List all devices in the registry.

        Returns device information for all devices (no credentials).

        Returns:
            List of device dictionaries with device information.
            Each dictionary contains the same fields as get_device_info().

        Raises:
            BackendError: Backend storage system error
        """
        pass

    @abstractmethod
    def list_accounts(self, device_id: str) -> List[Dict[str, str]]:
        """
        List all accounts for a device.

        Returns account metadata (no passwords).

        Args:
            device_id: Unique device identifier

        Returns:
            List of account dictionaries with fields:
                - account_id: Account identifier
                - username: Account username (no password!)
                - account_type: Type of account (service, admin, etc.)
                - purpose: Description of account purpose
                - permissions: List of permissions

        Raises:
            DeviceNotFoundError: Device not found in registry
            BackendError: Backend storage system error
        """
        pass

    @abstractmethod
    def device_exists(self, device_id: str) -> bool:
        """
        Check if a device exists in the registry.

        Args:
            device_id: Unique device identifier

        Returns:
            True if device exists, False otherwise

        Raises:
            BackendError: Backend storage system error
        """
        pass

    @abstractmethod
    def account_exists(self, device_id: str, account_id: str) -> bool:
        """
        Check if an account exists for a device.

        Args:
            device_id: Unique device identifier
            account_id: Account identifier

        Returns:
            True if account exists, False otherwise

        Raises:
            DeviceNotFoundError: Device not found in registry
            BackendError: Backend storage system error
        """
        pass

    # Future methods for credential lifecycle management
    # These are optional and may not be implemented by all backends

    def add_device(
        self,
        device_id: str,
        device_info: Dict[str, Any],
        accounts: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        """
        Add a new device to the registry.

        Optional method - not all backends may support this.

        Args:
            device_id: Unique device identifier
            device_info: Device information dictionary
            accounts: Optional dictionary of account_id -> account_data

        Raises:
            NotImplementedError: If backend doesn't support this operation
            BackendError: Backend storage system error
        """
        raise NotImplementedError("This registry does not support adding devices")

    def _assert_no_mac_collision(
        self, device_id: str, device_info: Dict[str, Any]
    ) -> None:
        """Refuse to register a second row for the same physical device.

        The registry is keyed by ``device_id``; the MAC lives inside the
        device info. Without this guard, adding a device under a non-MAC
        ``device_id`` (e.g. a model name like ``"P8815-2"``) for a device
        already registered under its MAC silently creates a duplicate row that
        points at the same physical box. Concrete backends call this from
        ``add_device`` after the duplicate-``device_id`` check.

        No-op when the new device carries no MAC (nothing to collide on).
        Raises :class:`~admz.exceptions.BackendError` on collision.
        """
        new_mac = canonical_mac(device_info.get("mac_address"))
        if not new_mac:
            return
        for existing in self.list_devices():
            if existing.get("device_id") == device_id:
                continue
            if canonical_mac(existing.get("mac_address")) == new_mac:
                raise BackendError(
                    f"A device with MAC {device_info.get('mac_address')} is "
                    f"already registered as "
                    f"'{existing.get('device_id')}'. Refusing to add a second "
                    f"entry '{device_id}' for the same physical device — use the "
                    f"existing device_id, or remove/update the existing entry."
                )

    def update_device(
        self,
        device_id: str,
        updates: Dict[str, Any],
    ) -> None:
        """
        Merge updates into an existing device's information.

        Args:
            device_id: Device to update
            updates: Fields to merge into device info

        Raises:
            DeviceNotFoundError: Device does not exist
            BackendError: Backend storage system error
        """
        raise NotImplementedError("This registry does not support updating devices")

    def remove_device(self, device_id: str) -> None:
        """
        Remove a device from the registry.

        Optional method - not all backends may support this.

        Args:
            device_id: Unique device identifier

        Raises:
            NotImplementedError: If backend doesn't support this operation
            DeviceNotFoundError: Device not found in registry
            BackendError: Backend storage system error
        """
        raise NotImplementedError("This registry does not support removing devices")

    def add_account(
        self, device_id: str, account_id: str, account_data: Dict[str, Any]
    ) -> None:
        """
        Add an account to a device.

        Optional method - not all backends may support this.

        Args:
            device_id: Unique device identifier
            account_id: Account identifier
            account_data: Account data including username, password, etc.

        Raises:
            NotImplementedError: If backend doesn't support this operation
            DeviceNotFoundError: Device not found in registry
            BackendError: Backend storage system error
        """
        raise NotImplementedError("This registry does not support adding accounts")

    def update_device_info(
        self,
        device_id: str,
        updates: Dict[str, Any],
    ) -> None:
        """
        Partially update device information (merge *updates* into existing info).

        Args:
            device_id: Unique device identifier
            updates: Dictionary of fields to merge into the device info.

        Raises:
            NotImplementedError: If backend doesn't support this operation
            DeviceNotFoundError: Device not found in registry
            BackendError: Backend storage system error
        """
        raise NotImplementedError("This registry does not support updating device info")

    def set_config_pointers(
        self,
        device_id: str,
        *,
        baseline_sha: Optional[str] = None,
        latest_observed_sha: Optional[str] = None,
        last_observed_at: Optional[float] = None,
    ) -> None:
        """Update the git config-baseline pointers for a device.

        These track the device's relationship to the git config repo (the
        source of truth for config bytes — see ADR-0014/0031):

            baseline_sha        — the commit the operator has blessed as the
                                  intended baseline (drift is measured vs this).
            latest_observed_sha — the most recent commit an audit/snapshot
                                  recorded for the device.
            last_observed_at    — Unix epoch of that last observation.

        Only non-None arguments are written, so a caller can advance the
        observed pointer without disturbing the baseline (and vice versa).

        Optional method — backends that don't track config (e.g. the stubbed
        Vault backend) raise NotImplementedError; callers treat it best-effort.

        Raises:
            NotImplementedError: If the backend doesn't support this operation.
            DeviceNotFoundError: Device not found in registry.
            BackendError: Backend storage system error.
        """
        raise NotImplementedError(
            "This registry does not support config-baseline pointers"
        )

    def save_named_baseline(
        self,
        device_id: str,
        name: str,
        commit_sha: str,
        *,
        note: str = "",
        created_by: str = "",
    ) -> None:
        """Save (or overwrite) a named full-config baseline (an "alternate
        configuration") for a device — a name pointing at a git commit that
        holds a saved config. The ACTIVE baseline is whichever name's
        ``commit_sha`` equals the device's ``baseline_sha`` (no separate flag).

        Optional method — backends that don't track config (e.g. the stubbed
        Vault backend) raise NotImplementedError; callers treat it best-effort.
        """
        raise NotImplementedError(
            "This registry does not support named config baselines"
        )

    def list_named_baselines(self, device_id: str) -> List[Dict[str, Any]]:
        """All named baselines (alternate configs) for a device, newest first.
        Optional — see :meth:`save_named_baseline`. An empty list is a valid
        'none saved'; NotImplementedError means the backend is unsupported."""
        raise NotImplementedError(
            "This registry does not support named config baselines"
        )

    def delete_named_baseline(self, device_id: str, name: str) -> bool:
        """Remove a named baseline (the underlying git commit stays in
        history). Returns True if a row was removed. Optional — see
        :meth:`save_named_baseline`."""
        raise NotImplementedError(
            "This registry does not support named config baselines"
        )

    def set_active_scenario(
        self, device_id: str, scenario_name: Optional[str] = None
    ) -> None:
        """Mark which named alternate config ("scenario") is currently pushed to
        the device, or ``None`` to clear it (back on baseline). Does NOT move
        ``baseline_sha`` — a scenario is a temporary push (ADR-0044). Surfaced
        in device_info as ``active_scenario``. Optional — see
        :meth:`save_named_baseline`."""
        raise NotImplementedError(
            "This registry does not support scenario markers"
        )

    def update_account(
        self,
        device_id: str,
        account_id: str,
        updates: Dict[str, Any],
    ) -> None:
        """
        Partially update an account (merge *updates* into existing data).

        Atomic — the account is never observably absent during the
        update, unlike ``remove_account`` + ``add_account``.

        Args:
            device_id: Unique device identifier.
            account_id: Account identifier.
            updates: Fields to merge into the existing account_data
                     (typically ``{"password": "<new>"}`` for rotation).
                     Keys not present in ``updates`` are preserved.

        Raises:
            NotImplementedError: If backend doesn't support this operation.
            DeviceNotFoundError: Device not found in registry.
            AccountNotFoundError: Account not found for the device.
            BackendError: Backend storage system error.
        """
        raise NotImplementedError(
            "This registry does not support updating accounts"
        )

    def remove_account(self, device_id: str, account_id: str) -> None:
        """
        Remove an account from a device.

        Optional method - not all backends may support this.

        Args:
            device_id: Unique device identifier
            account_id: Account identifier

        Raises:
            NotImplementedError: If backend doesn't support this operation
            DeviceNotFoundError: Device not found in registry
            AccountNotFoundError: Account not found for device
            BackendError: Backend storage system error
        """
        raise NotImplementedError("This registry does not support removing accounts")

    # ------------------------------------------------------------------
    # Organization → Site hierarchy (ADR-0032)
    # ------------------------------------------------------------------
    #
    # Org = who owns the cameras (and owns the git config repo:
    # repo_path / repo_remote_url). Site = which site/LAN the cameras
    # are installed on. There is deliberately NO Group level —
    # operational grouping is done with device TAGS (free-form, many
    # per device), which already drive scheduling, drift/snapshot
    # scoping, and search.
    #
    # Optional — backends that don't carry the hierarchy raise
    # NotImplementedError. The SQLite backend implements all of them;
    # the Vault backend stubs them out for now (a follow-up PR will
    # land a Vault implementation once the SQLite shape proves out).

    def add_organization(
        self,
        org_id: str,
        name: str,
        repo_path: str,
        repo_remote_url: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Insert a new Organization. ``repo_path`` is the absolute
        filesystem location of this Org's git config repo; the caller
        is responsible for git-init'ing it before inserting."""
        raise NotImplementedError(
            "This registry does not support organizations"
        )

    def get_organization(self, org_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError(
            "This registry does not support organizations"
        )

    def list_organizations(self) -> List[Dict[str, Any]]:
        raise NotImplementedError(
            "This registry does not support organizations"
        )

    def update_organization(
        self, org_id: str, updates: Dict[str, Any],
    ) -> None:
        raise NotImplementedError(
            "This registry does not support organizations"
        )

    def remove_organization(self, org_id: str) -> None:
        raise NotImplementedError(
            "This registry does not support organizations"
        )

    def add_site(
        self,
        site_id: str,
        org_id: str,
        name: str,
        location: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        raise NotImplementedError("This registry does not support sites")

    def get_site(self, site_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError("This registry does not support sites")

    def list_sites(
        self, org_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError("This registry does not support sites")

    def update_site(self, site_id: str, updates: Dict[str, Any]) -> None:
        raise NotImplementedError("This registry does not support sites")

    def remove_site(self, site_id: str) -> None:
        raise NotImplementedError("This registry does not support sites")

    def set_device_org_site(
        self, device_id: str, org_id: str, site_id: str,
    ) -> None:
        """Assign a device to an Org + Site. Both must exist and the
        Site must belong to the named Org."""
        raise NotImplementedError(
            "This registry does not support per-device org/site assignment"
        )

    def get_device_org_site(
        self, device_id: str,
    ) -> Optional[Dict[str, str]]:
        """Return ``{"org_id": ..., "site_id": ...}`` or None if the
        device hasn't been migrated (legacy pre-Slice-1 row)."""
        raise NotImplementedError(
            "This registry does not support per-device org/site assignment"
        )
