"""
Abstract interface for device credential registries.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


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
    # Slice 1: Organization → Site → Group hierarchy
    # ------------------------------------------------------------------
    #
    # Optional — backends that don't carry the hierarchy raise
    # NotImplementedError. The SQLite backend implements all of them;
    # the Vault backend stubs them out for now (a follow-up PR will
    # land a Vault implementation once the SQLite shape proves out).
    #
    # See plans/majestic-munching-marble.md for the design.

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

    def add_device_group(
        self,
        group_id: str,
        site_id: str,
        name: str,
        purpose: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        raise NotImplementedError(
            "This registry does not support device groups"
        )

    def get_device_group(
        self, group_id: str,
    ) -> Optional[Dict[str, Any]]:
        raise NotImplementedError(
            "This registry does not support device groups"
        )

    def list_device_groups(
        self, site_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError(
            "This registry does not support device groups"
        )

    def update_device_group(
        self, group_id: str, updates: Dict[str, Any],
    ) -> None:
        raise NotImplementedError(
            "This registry does not support device groups"
        )

    def remove_device_group(self, group_id: str) -> None:
        raise NotImplementedError(
            "This registry does not support device groups"
        )

    def add_device_to_group(
        self,
        device_id: str,
        group_id: str,
        is_primary: bool = False,
    ) -> None:
        raise NotImplementedError(
            "This registry does not support device group memberships"
        )

    def remove_device_from_group(
        self, device_id: str, group_id: str,
    ) -> None:
        raise NotImplementedError(
            "This registry does not support device group memberships"
        )

    def list_groups_for_device(
        self, device_id: str,
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError(
            "This registry does not support device group memberships"
        )

    def set_device_primary_group(
        self, device_id: str, group_id: str,
    ) -> None:
        raise NotImplementedError(
            "This registry does not support device group memberships"
        )

    def get_device_primary_group(
        self, device_id: str,
    ) -> Optional[Dict[str, Any]]:
        raise NotImplementedError(
            "This registry does not support device group memberships"
        )

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
