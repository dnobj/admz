"""
Tests for factory function.
"""

import pytest
from unittest.mock import patch

from admz.factory import create_device_registry
from admz.backends.vault_backend import VaultDeviceRegistry
from admz.exceptions import ConfigurationError


class TestFactory:
    """Test create_device_registry factory function."""

    def test_create_vault_registry_explicit(self):
        """Test creating Vault registry with explicit backend parameter."""
        with patch("admz.factory.VaultDeviceRegistry") as mock_vault:
            create_device_registry("vault", vault_addr="http://localhost:8200", vault_token="test")

            mock_vault.assert_called_once_with(
                vault_addr="http://localhost:8200",
                vault_token="test"
            )

    def test_create_vault_registry_from_env(self):
        """Test creating Vault registry from environment variable."""
        with patch.dict("os.environ", {"DEVICE_REGISTRY_BACKEND": "vault"}):
            with patch("admz.factory.VaultDeviceRegistry") as mock_vault:
                create_device_registry()

                mock_vault.assert_called_once()

    def test_create_vault_registry_default(self):
        """Test creating Vault registry as default."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("admz.factory.VaultDeviceRegistry") as mock_vault:
                create_device_registry()

                mock_vault.assert_called_once()

    def test_create_registry_unknown_backend(self):
        """Test creating registry with unknown backend."""
        with pytest.raises(ConfigurationError, match="Unknown backend"):
            create_device_registry("unknown")

    def test_create_registry_case_insensitive(self):
        """Test backend parameter is case insensitive."""
        with patch("admz.factory.VaultDeviceRegistry") as mock_vault:
            create_device_registry("VAULT")

            mock_vault.assert_called_once()
