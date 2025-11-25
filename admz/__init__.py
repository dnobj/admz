"""
ADMZ (Axis Device Manager) - Backend-agnostic credential management for Axis devices.
"""

from admz.device_registry import DeviceRegistry
from admz.factory import create_device_registry
from admz.exceptions import (
    AxisSecretsError,
    DeviceNotFoundError,
    AccountNotFoundError,
    PermissionDeniedError,
    AuthenticationError,
    ConfigurationError,
    BackendError,
)

__version__ = "2.0.0"

__all__ = [
    "DeviceRegistry",
    "create_device_registry",
    "AxisSecretsError",
    "DeviceNotFoundError",
    "AccountNotFoundError",
    "PermissionDeniedError",
    "AuthenticationError",
    "ConfigurationError",
    "BackendError",
]
