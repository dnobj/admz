"""
Factory for creating device registry instances.
"""

import os
from typing import Optional

from admz.device_registry import DeviceRegistry
from admz.backends.vault_backend import VaultDeviceRegistry
from admz.exceptions import ConfigurationError


def create_device_registry(
    backend: Optional[str] = None, **kwargs
) -> DeviceRegistry:
    """
    Create a device registry instance based on configuration.

    Auto-detects backend from environment or uses explicit backend parameter.

    Args:
        backend: Backend type ('vault'). If None, reads from
                DEVICE_REGISTRY_BACKEND environment variable.
                Defaults to 'vault' if not specified.
        **kwargs: Additional parameters to pass to the backend constructor

    Returns:
        DeviceRegistry instance

    Raises:
        ConfigurationError: If backend configuration is invalid
        AuthenticationError: If authentication fails

    Environment Variables:
        DEVICE_REGISTRY_BACKEND: Backend type ('vault')
        VAULT_ADDR: Vault server URL
        VAULT_TOKEN: Vault authentication token
        VAULT_ROLE_ID: AppRole role ID
        VAULT_SECRET_ID: AppRole secret ID
        VAULT_MOUNT_POINT: KV mount point (default: 'secret')
        VAULT_PATH_PREFIX: Path prefix for devices (default: 'devices')

    Examples:
        # Auto-detect backend from environment
        >>> registry = create_device_registry()

        # Explicit Vault backend
        >>> registry = create_device_registry('vault')

        # With custom parameters
        >>> registry = create_device_registry(
        ...     'vault',
        ...     vault_addr='https://vault.company.com',
        ...     mount_point='devices-kv'
        ... )
    """
    # Determine backend
    backend = backend or os.getenv("DEVICE_REGISTRY_BACKEND", "vault")
    backend = backend.lower()

    if backend == "vault":
        return VaultDeviceRegistry(**kwargs)
    else:
        raise ConfigurationError(
            f"Unknown backend: '{backend}'. Supported backends: vault"
        )
