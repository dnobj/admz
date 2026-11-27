"""
ADMZ (Axis Device Manager) - Backend-agnostic credential management for Axis devices.
"""

from admz.device_registry import DeviceRegistry
from admz.factory import create_device_registry
from admz.exceptions import (
    ADMZError,
    DeviceNotFoundError,
    AccountNotFoundError,
    PermissionDeniedError,
    AuthenticationError,
    ConfigurationError,
    BackendError,
)

#: The release the source is working towards (ADR-0075 §2). Several builds may
#: carry it; one of them is promoted, and this then moves on to the next number.
#: The build that is actually running is `admz.build_info.build_id()`.
__version__ = "2.1.0"

__all__ = [
    "DeviceRegistry",
    "create_device_registry",
    "ADMZError",
    "DeviceNotFoundError",
    "AccountNotFoundError",
    "PermissionDeniedError",
    "AuthenticationError",
    "ConfigurationError",
    "BackendError",
    "discovery",
]
