"""
HashiCorp Vault backend for device credential storage.
"""

import os
from typing import Dict, List, Optional, Any
import hvac
from hvac.exceptions import InvalidPath, Forbidden, VaultError

from admz.device_registry import DeviceRegistry
from admz.exceptions import (
    DeviceNotFoundError,
    AccountNotFoundError,
    PermissionDeniedError,
    AuthenticationError,
    ConfigurationError,
    BackendError,
)


class VaultDeviceRegistry(DeviceRegistry):
    """
    HashiCorp Vault backend for device credential management.

    Stores device information and account credentials in Vault's KV v2 secrets engine.

    Vault Path Structure:
        {mount_point}/data/{path_prefix}/{device_id}/device_info
        {mount_point}/data/{path_prefix}/{device_id}/accounts/{account_id}

    Example:
        secret/data/devices/front-door/device_info
        secret/data/devices/front-door/accounts/aoa-agent
        secret/data/devices/front-door/accounts/admin

    Environment Variables:
        VAULT_ADDR: Vault server URL (required)
        VAULT_TOKEN: Vault authentication token (optional, for token auth)
        VAULT_ROLE_ID: AppRole role ID (optional, for AppRole auth)
        VAULT_SECRET_ID: AppRole secret ID (optional, for AppRole auth)
        VAULT_MOUNT_POINT: KV secrets engine mount point (default: 'secret')
        VAULT_PATH_PREFIX: Path prefix for devices (default: 'devices')
    """

    def __init__(
        self,
        vault_addr: Optional[str] = None,
        vault_token: Optional[str] = None,
        vault_role_id: Optional[str] = None,
        vault_secret_id: Optional[str] = None,
        mount_point: str = "secret",
        path_prefix: str = "devices",
        verify: bool = True,
    ):
        """
        Initialize Vault device registry.

        Args:
            vault_addr: Vault server URL (falls back to VAULT_ADDR env var)
            vault_token: Vault token (falls back to VAULT_TOKEN env var)
            vault_role_id: AppRole role ID (falls back to VAULT_ROLE_ID env var)
            vault_secret_id: AppRole secret ID (falls back to VAULT_SECRET_ID env var)
            mount_point: KV secrets engine mount point (default: 'secret')
            path_prefix: Path prefix for devices (default: 'devices')
            verify: Verify TLS certificates (default: True)

        Raises:
            ConfigurationError: If Vault configuration is invalid
            AuthenticationError: If authentication to Vault fails
        """
        self.vault_addr = vault_addr or os.getenv("VAULT_ADDR")
        self.mount_point = mount_point
        self.path_prefix = path_prefix

        if not self.vault_addr:
            raise ConfigurationError(
                "Vault address not configured. "
                "Set VAULT_ADDR environment variable or pass vault_addr parameter."
            )

        # Initialize Vault client
        try:
            self.client = hvac.Client(url=self.vault_addr, verify=verify)
        except Exception as e:
            raise ConfigurationError(f"Failed to initialize Vault client: {e}")

        # Authenticate to Vault
        self._authenticate(vault_token, vault_role_id, vault_secret_id)

    def _authenticate(
        self,
        vault_token: Optional[str],
        vault_role_id: Optional[str],
        vault_secret_id: Optional[str],
    ) -> None:
        """
        Authenticate to Vault using token or AppRole.

        Tries token authentication first, then AppRole.

        Args:
            vault_token: Vault token
            vault_role_id: AppRole role ID
            vault_secret_id: AppRole secret ID

        Raises:
            AuthenticationError: If all authentication methods fail
        """
        # Try token authentication
        token = vault_token or os.getenv("VAULT_TOKEN")
        if token:
            self.client.token = token
            if self._verify_authentication():
                return

        # Try AppRole authentication
        role_id = vault_role_id or os.getenv("VAULT_ROLE_ID")
        secret_id = vault_secret_id or os.getenv("VAULT_SECRET_ID")

        if role_id and secret_id:
            try:
                response = self.client.auth.approle.login(
                    role_id=role_id, secret_id=secret_id
                )
                self.client.token = response["auth"]["client_token"]
                if self._verify_authentication():
                    return
            except Exception as e:
                raise AuthenticationError(f"AppRole authentication failed: {e}")

        raise AuthenticationError(
            "No valid authentication method found. "
            "Provide either VAULT_TOKEN or VAULT_ROLE_ID + VAULT_SECRET_ID."
        )

    def _verify_authentication(self) -> bool:
        """
        Verify that the current authentication is valid.

        Returns:
            True if authenticated, False otherwise
        """
        try:
            return self.client.is_authenticated()
        except Exception:
            return False

    def _build_path(self, device_id: str, *parts: str) -> str:
        """
        Build a Vault path for a device resource.

        Args:
            device_id: Device identifier
            *parts: Additional path components

        Returns:
            Full Vault path (without mount_point prefix for hvac)
        """
        path_parts = [self.path_prefix, device_id] + list(parts)
        return "/".join(path_parts)

    def get_credentials(
        self,
        device_id: str,
        account_id: str = "default",
        requester: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get credentials for a device account from Vault."""
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")

        if not self.account_exists(device_id, account_id):
            raise AccountNotFoundError(
                f"Account '{account_id}' not found for device '{device_id}'"
            )

        path = self._build_path(device_id, "accounts", account_id)

        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path, mount_point=self.mount_point
            )
            credentials = response["data"]["data"]

            # Include host from device_info for convenience
            device_info = self.get_device_info(device_id)
            credentials["host"] = device_info.get("host")

            return credentials

        except Forbidden as e:
            raise PermissionDeniedError(
                f"Access denied to {device_id}/{account_id}. "
                f"Check Vault token permissions. Error: {e}"
            )
        except InvalidPath:
            raise AccountNotFoundError(
                f"Account '{account_id}' not found for device '{device_id}'"
            )
        except VaultError as e:
            raise BackendError(f"Vault error reading credentials: {e}")

    def get_device_info(self, device_id: str) -> Dict[str, Any]:
        """Get device information for a device from Vault."""
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")

        path = self._build_path(device_id, "device_info")

        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path, mount_point=self.mount_point
            )
            device_info = response["data"]["data"]

            # Add device_id to the response
            device_info["device_id"] = device_id

            return device_info

        except Forbidden as e:
            raise PermissionDeniedError(
                f"Access denied to device info for {device_id}. "
                f"Check Vault token permissions. Error: {e}"
            )
        except InvalidPath:
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        except VaultError as e:
            raise BackendError(f"Vault error reading device info: {e}")

    def list_devices(self) -> List[Dict[str, Any]]:
        """List all devices from Vault."""
        try:
            # List all device directories under the path prefix
            response = self.client.secrets.kv.v2.list_secrets(
                path=self.path_prefix, mount_point=self.mount_point
            )

            device_ids = response["data"]["keys"]

            # Get device info for each device
            devices = []
            for device_id in device_ids:
                # Remove trailing slash if present
                device_id = device_id.rstrip("/")
                try:
                    device_info = self.get_device_info(device_id)
                    devices.append(device_info)
                except (DeviceNotFoundError, PermissionDeniedError):
                    # Skip devices we can't access
                    continue

            return devices

        except InvalidPath:
            # No devices exist yet
            return []
        except Forbidden as e:
            raise PermissionDeniedError(
                f"Access denied to list devices. "
                f"Check Vault token permissions. Error: {e}"
            )
        except VaultError as e:
            raise BackendError(f"Vault error listing devices: {e}")

    def list_accounts(self, device_id: str) -> List[Dict[str, str]]:
        """List all accounts for a device from Vault."""
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")

        accounts_path = self._build_path(device_id, "accounts")

        try:
            response = self.client.secrets.kv.v2.list_secrets(
                path=accounts_path, mount_point=self.mount_point
            )

            account_ids = response["data"]["keys"]

            # Get account metadata (without passwords)
            accounts = []
            for account_id in account_ids:
                account_id = account_id.rstrip("/")
                try:
                    account_path = self._build_path(device_id, "accounts", account_id)
                    response = self.client.secrets.kv.v2.read_secret_version(
                        path=account_path, mount_point=self.mount_point
                    )
                    account_data = response["data"]["data"].copy()

                    # Remove password from the listing
                    account_data.pop("password", None)
                    account_data["account_id"] = account_id

                    accounts.append(account_data)
                except (InvalidPath, PermissionDeniedError):
                    # Skip accounts we can't access
                    continue

            return accounts

        except InvalidPath:
            # No accounts exist for this device
            return []
        except Forbidden as e:
            raise PermissionDeniedError(
                f"Access denied to list accounts for {device_id}. "
                f"Check Vault token permissions. Error: {e}"
            )
        except VaultError as e:
            raise BackendError(f"Vault error listing accounts: {e}")

    def device_exists(self, device_id: str) -> bool:
        """Check if a device exists in Vault."""
        path = self._build_path(device_id, "device_info")

        try:
            self.client.secrets.kv.v2.read_secret_version(
                path=path, mount_point=self.mount_point
            )
            return True
        except InvalidPath:
            return False
        except Forbidden:
            # If we can't read it due to permissions, we can't say if it exists
            return False
        except VaultError:
            return False

    def account_exists(self, device_id: str, account_id: str) -> bool:
        """Check if an account exists for a device in Vault."""
        if not self.device_exists(device_id):
            return False

        path = self._build_path(device_id, "accounts", account_id)

        try:
            self.client.secrets.kv.v2.read_secret_version(
                path=path, mount_point=self.mount_point
            )
            return True
        except InvalidPath:
            return False
        except Forbidden:
            return False
        except VaultError:
            return False

    def get_device_by_nickname(self, nickname: str) -> Optional[Dict[str, Any]]:
        """Get device by nickname."""
        devices = self.list_devices()
        for device in devices:
            if device.get("nickname", "").lower() == nickname.lower():
                return device
        return None

    # Write operations (optional - for credential management)

    def add_device(
        self,
        device_id: str,
        device_info: Dict[str, Any],
        accounts: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        """Add a new device to Vault."""
        if self.device_exists(device_id):
            raise BackendError(f"Device '{device_id}' already exists")

        # Write device info
        path = self._build_path(device_id, "device_info")
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path, secret=device_info, mount_point=self.mount_point
            )
        except Forbidden as e:
            raise PermissionDeniedError(
                f"Access denied to create device {device_id}. "
                f"Check Vault token permissions. Error: {e}"
            )
        except VaultError as e:
            raise BackendError(f"Vault error creating device: {e}")

        # Write accounts if provided
        if accounts:
            for account_id, account_data in accounts.items():
                self.add_account(device_id, account_id, account_data)

    def add_account(
        self, device_id: str, account_id: str, account_data: Dict[str, Any]
    ) -> None:
        """Add an account to a device in Vault."""
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")

        if self.account_exists(device_id, account_id):
            raise BackendError(
                f"Account '{account_id}' already exists for device '{device_id}'"
            )

        path = self._build_path(device_id, "accounts", account_id)

        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path, secret=account_data, mount_point=self.mount_point
            )
        except Forbidden as e:
            raise PermissionDeniedError(
                f"Access denied to create account {device_id}/{account_id}. "
                f"Check Vault token permissions. Error: {e}"
            )
        except VaultError as e:
            raise BackendError(f"Vault error creating account: {e}")

    def remove_device(self, device_id: str) -> None:
        """Remove a device and all its accounts from Vault."""
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")

        # Remove all accounts first
        try:
            accounts = self.list_accounts(device_id)
            for account in accounts:
                self.remove_account(device_id, account["account_id"])
        except Exception:
            # Continue even if account removal fails
            pass

        # Remove device info
        path = self._build_path(device_id, "device_info")
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path, mount_point=self.mount_point
            )
        except Forbidden as e:
            raise PermissionDeniedError(
                f"Access denied to delete device {device_id}. "
                f"Check Vault token permissions. Error: {e}"
            )
        except VaultError as e:
            raise BackendError(f"Vault error deleting device: {e}")

    def update_account(
        self,
        device_id: str,
        account_id: str,
        updates: Dict[str, Any],
    ) -> None:
        """Partially update an account in Vault (read-modify-write).

        Vault's KV-v2 supports an atomic ``patch_secret`` for partial
        updates, but that requires the ``patch`` ACL capability which
        operators may not have configured. The read-modify-write
        approach uses only ``read`` + ``create_or_update_secret``,
        which every read/write-capable token already has. Trade-off
        is a tiny race window if two updates land at the same instant
        — last-write-wins, which is acceptable for credential
        rotation (humans don't race themselves).
        """
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")
        if not self.account_exists(device_id, account_id):
            raise AccountNotFoundError(
                f"Account '{account_id}' not found for device '{device_id}'"
            )

        path = self._build_path(device_id, "accounts", account_id)
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path, mount_point=self.mount_point
            )
            current = dict(response["data"]["data"])
            current.update(updates)
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path, secret=current, mount_point=self.mount_point
            )
        except Forbidden as e:
            raise PermissionDeniedError(
                f"Access denied to update account {device_id}/{account_id}. "
                f"Check Vault token permissions. Error: {e}"
            )
        except VaultError as e:
            raise BackendError(f"Vault error updating account: {e}")

    def remove_account(self, device_id: str, account_id: str) -> None:
        """Remove an account from a device in Vault."""
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(f"Device '{device_id}' not found")

        if not self.account_exists(device_id, account_id):
            raise AccountNotFoundError(
                f"Account '{account_id}' not found for device '{device_id}'"
            )

        path = self._build_path(device_id, "accounts", account_id)

        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path, mount_point=self.mount_point
            )
        except Forbidden as e:
            raise PermissionDeniedError(
                f"Access denied to delete account {device_id}/{account_id}. "
                f"Check Vault token permissions. Error: {e}"
            )
        except VaultError as e:
            raise BackendError(f"Vault error deleting account: {e}")
