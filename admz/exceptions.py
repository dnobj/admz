"""
Exceptions for the ADMZ (Axis Device Manager) library.
"""


class ADMZError(Exception):
    """Base exception for all ADMZ errors."""
    pass


# Backward-compatible alias for the legacy name
AxisSecretsError = ADMZError


class DeviceNotFoundError(ADMZError):
    """Raised when a device ID is not found in the registry."""
    pass


class AccountNotFoundError(ADMZError):
    """Raised when an account ID is not found for a device."""
    pass


class PermissionDeniedError(ADMZError):
    """Raised when access to credentials is denied due to access control rules."""
    pass


class AuthenticationError(ADMZError):
    """Raised when authentication to the backend fails."""
    pass


class ConfigurationError(ADMZError):
    """Raised when there's a configuration problem."""
    pass


class BackendError(ADMZError):
    """Raised when the backend storage system encounters an error."""
    pass
