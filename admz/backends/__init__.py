"""
Backend implementations for device credential storage.
"""

from admz.backends.vault_backend import VaultDeviceRegistry
from admz.backends.sqlite_backend import SQLiteDeviceRegistry

__all__ = ["VaultDeviceRegistry", "SQLiteDeviceRegistry"]
