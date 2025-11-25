"""
Exceptions for the ADMZ (Axis Device Manager) library.
"""


class AxisSecretsError(Exception):
    """Base exception for all ADMZ errors."""
    pass


class DeviceNotFoundError(AxisSecretsError):
    """Raised when a device ID is not found in the registry."""
    pass


class AccountNotFoundError(AxisSecretsError):
    """Raised when an account ID is not found for a device."""
    pass


class PermissionDeniedError(AxisSecretsError):
    """Raised when access to credentials is denied due to access control rules."""
    pass


class AuthenticationError(AxisSecretsError):
    """Raised when authentication to the backend fails."""
    pass


class ConfigurationError(AxisSecretsError):
    """Raised when there's a configuration problem."""
    pass


class BackendError(AxisSecretsError):
    """Raised when the backend storage system encounters an error."""
    pass
