"""Tests for the device-registry factory function."""

import pytest
from unittest.mock import patch

from admz.factory import create_device_registry
from admz.exceptions import ConfigurationError


# Patch target must match the actual import site. The factory does
# `from admz.backends.{sqlite,vault}_backend import ...` *inside* the function,
# so we patch where the name is looked up at call time, not in admz.factory.


class TestFactory:
    """create_device_registry: backend selection and kwargs forwarding."""

    # ----- SQLite (default) -----

    def test_default_backend_is_sqlite(self):
        """No backend arg and no env var → SQLite (the documented default)."""
        with patch.dict("os.environ", {}, clear=True):
            with patch(
                "admz.backends.sqlite_backend.SQLiteDeviceRegistry"
            ) as mock_sqlite:
                create_device_registry()
                mock_sqlite.assert_called_once_with()

    def test_explicit_sqlite_backend(self):
        """`create_device_registry("sqlite")` selects the SQLite backend."""
        with patch(
            "admz.backends.sqlite_backend.SQLiteDeviceRegistry"
        ) as mock_sqlite:
            create_device_registry("sqlite", db_path="/tmp/foo.db")
            mock_sqlite.assert_called_once_with(db_path="/tmp/foo.db")

    def test_sqlite_from_env(self):
        """DEVICE_REGISTRY_BACKEND=sqlite selects the SQLite backend."""
        with patch.dict(
            "os.environ", {"DEVICE_REGISTRY_BACKEND": "sqlite"}, clear=True
        ):
            with patch(
                "admz.backends.sqlite_backend.SQLiteDeviceRegistry"
            ) as mock_sqlite:
                create_device_registry()
                mock_sqlite.assert_called_once()

    # ----- Vault -----

    def test_explicit_vault_backend(self):
        """`create_device_registry("vault", ...)` selects the Vault backend
        and forwards kwargs."""
        with patch(
            "admz.backends.vault_backend.VaultDeviceRegistry"
        ) as mock_vault:
            create_device_registry(
                "vault",
                vault_addr="http://localhost:8200",
                vault_token="test",
            )
            mock_vault.assert_called_once_with(
                vault_addr="http://localhost:8200",
                vault_token="test",
            )

    def test_vault_from_env(self):
        """DEVICE_REGISTRY_BACKEND=vault selects the Vault backend."""
        with patch.dict(
            "os.environ", {"DEVICE_REGISTRY_BACKEND": "vault"}, clear=True
        ):
            with patch(
                "admz.backends.vault_backend.VaultDeviceRegistry"
            ) as mock_vault:
                create_device_registry()
                mock_vault.assert_called_once()

    # ----- Misc -----

    def test_case_insensitive_backend_name(self):
        """Backend names are normalized to lowercase."""
        with patch(
            "admz.backends.vault_backend.VaultDeviceRegistry"
        ) as mock_vault:
            create_device_registry("VAULT")
            mock_vault.assert_called_once()
        with patch(
            "admz.backends.sqlite_backend.SQLiteDeviceRegistry"
        ) as mock_sqlite:
            create_device_registry("SQLite")
            mock_sqlite.assert_called_once()

    def test_unknown_backend_raises(self):
        """Unknown backend name raises ConfigurationError with a helpful message."""
        with pytest.raises(ConfigurationError, match="Unknown backend"):
            create_device_registry("postgres")

    def test_explicit_backend_overrides_env(self):
        """Explicit backend argument wins over DEVICE_REGISTRY_BACKEND env."""
        with patch.dict(
            "os.environ", {"DEVICE_REGISTRY_BACKEND": "vault"}, clear=True
        ):
            with patch(
                "admz.backends.sqlite_backend.SQLiteDeviceRegistry"
            ) as mock_sqlite:
                create_device_registry("sqlite")
                mock_sqlite.assert_called_once()
