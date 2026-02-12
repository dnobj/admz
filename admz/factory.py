"""
Factory for creating device registry instances.
"""

import os
from typing import Optional

from admz.device_registry import DeviceRegistry
from admz.exceptions import ConfigurationError


def create_device_registry(
    backend: Optional[str] = None, **kwargs
) -> DeviceRegistry:
    """
    Create a device registry instance based on configuration.

    Auto-detects backend from environment or uses explicit backend parameter.

    Args:
        backend: Backend type ('sqlite' or 'vault'). If None, reads from
                DEVICE_REGISTRY_BACKEND environment variable.
                Defaults to 'sqlite' if not specified (zero-config local storage).
        **kwargs: Additional parameters to pass to the backend constructor

    Returns:
        DeviceRegistry instance

    Raises:
        ConfigurationError: If backend configuration is invalid
        AuthenticationError: If authentication fails (Vault only)

    Environment Variables:
        DEVICE_REGISTRY_BACKEND: Backend type ('sqlite' or 'vault')

        SQLite backend:
            ADMZ_DB_PATH: Database file path (default: ~/.admz/admz.db)
            ADMZ_KEY_PATH: Encryption key file path (default: ~/.admz/admz.key)

        Vault backend:
            VAULT_ADDR: Vault server URL
            VAULT_TOKEN: Vault authentication token
            VAULT_ROLE_ID: AppRole role ID
            VAULT_SECRET_ID: AppRole secret ID
            VAULT_MOUNT_POINT: KV mount point (default: 'secret')
            VAULT_PATH_PREFIX: Path prefix for devices (default: 'devices')

    Examples:
        # Local SQLite backend (default — zero config)
        >>> registry = create_device_registry()

        # Explicit SQLite with custom path
        >>> registry = create_device_registry('sqlite', db_path='/data/admz.db')

        # Vault backend for enterprise deployments
        >>> registry = create_device_registry('vault')

        # Vault with custom parameters
        >>> registry = create_device_registry(
        ...     'vault',
        ...     vault_addr='https://vault.company.com',
        ...     mount_point='devices-kv'
        ... )
    """
    # Determine backend
    backend = backend or os.getenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    backend = backend.lower()

    if backend == "sqlite":
        from admz.backends.sqlite_backend import SQLiteDeviceRegistry
        return SQLiteDeviceRegistry(**kwargs)
    elif backend == "vault":
        from admz.backends.vault_backend import VaultDeviceRegistry
        return VaultDeviceRegistry(**kwargs)
    else:
        raise ConfigurationError(
            f"Unknown backend: '{backend}'. Supported backends: sqlite, vault"
        )
