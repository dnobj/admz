"""
Backend implementations for device credential storage.

Backends are imported lazily so that an optional dependency (e.g. ``hvac``
for the Vault backend) does not need to be installed if you're not using
that backend.
"""

__all__ = ["VaultDeviceRegistry", "SQLiteDeviceRegistry"]


def __getattr__(name):
    if name == "VaultDeviceRegistry":
        from admz.backends.vault_backend import VaultDeviceRegistry
        return VaultDeviceRegistry
    if name == "SQLiteDeviceRegistry":
        from admz.backends.sqlite_backend import SQLiteDeviceRegistry
        return SQLiteDeviceRegistry
    raise AttributeError(f"module 'admz.backends' has no attribute {name!r}")
