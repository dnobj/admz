"""
Tests for Vault backend.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from hvac.exceptions import InvalidPath, Forbidden, VaultError

from admz.backends.vault_backend import VaultDeviceRegistry
from admz.exceptions import (
    DeviceNotFoundError,
    AccountNotFoundError,
    PermissionDeniedError,
    AuthenticationError,
    ConfigurationError,
    BackendError,
)


@pytest.fixture
def mock_vault_client():
    """Create a mock Vault client."""
    client = Mock()
    client.is_authenticated.return_value = True
    return client


@pytest.fixture
def registry(mock_vault_client):
    """Create a VaultDeviceRegistry with mocked client."""
    with patch("admz.backends.vault_backend.hvac.Client") as mock_client_class:
        mock_client_class.return_value = mock_vault_client
        with patch.dict("os.environ", {"VAULT_ADDR": "http://localhost:8200", "VAULT_TOKEN": "test-token"}):
            registry = VaultDeviceRegistry()
            return registry


class TestVaultDeviceRegistry:
    """Test VaultDeviceRegistry class."""

    def test_init_with_token(self, mock_vault_client):
        """Test initialization with token authentication."""
        with patch("admz.backends.vault_backend.hvac.Client") as mock_client_class:
            mock_client_class.return_value = mock_vault_client

            registry = VaultDeviceRegistry(
                vault_addr="http://localhost:8200",
                vault_token="test-token"
            )

            assert registry.vault_addr == "http://localhost:8200"
            assert registry.mount_point == "secret"
            assert registry.path_prefix == "devices"
            assert mock_vault_client.token == "test-token"

    def test_init_with_approle(self, mock_vault_client):
        """Test initialization with AppRole authentication."""
        with patch("admz.backends.vault_backend.hvac.Client") as mock_client_class:
            mock_client_class.return_value = mock_vault_client
            mock_vault_client.auth.approle.login.return_value = {
                "auth": {"client_token": "approle-token"}
            }

            registry = VaultDeviceRegistry(
                vault_addr="http://localhost:8200",
                vault_role_id="test-role-id",
                vault_secret_id="test-secret-id"
            )

            assert mock_vault_client.token == "approle-token"
            mock_vault_client.auth.approle.login.assert_called_once_with(
                role_id="test-role-id",
                secret_id="test-secret-id"
            )

    def test_init_no_vault_addr(self):
        """Test initialization fails without Vault address."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ConfigurationError, match="Vault address not configured"):
                VaultDeviceRegistry()

    def test_init_no_auth(self, mock_vault_client):
        """Test initialization fails without authentication."""
        with patch("admz.backends.vault_backend.hvac.Client") as mock_client_class:
            mock_client_class.return_value = mock_vault_client
            mock_vault_client.is_authenticated.return_value = False

            with patch.dict("os.environ", {"VAULT_ADDR": "http://localhost:8200"}, clear=True):
                with pytest.raises(AuthenticationError, match="No valid authentication method"):
                    VaultDeviceRegistry()

    def test_get_credentials_success(self, registry):
        """Test successful credential retrieval."""
        # Mock device_info response
        registry.client.secrets.kv.v2.read_secret_version.side_effect = [
            {
                "data": {
                    "data": {
                        "username": "aoa_agent",
                        "password": "secret123",
                        "account_type": "service",
                    }
                }
            },
            {
                "data": {
                    "data": {
                        "host": "192.168.1.10",
                        "location": "Main Entrance",
                    }
                }
            },
        ]

        # Mock device_exists check
        with patch.object(registry, "device_exists", return_value=True):
            with patch.object(registry, "account_exists", return_value=True):
                creds = registry.get_credentials("front-door", "aoa-agent")

                assert creds["username"] == "aoa_agent"
                assert creds["password"] == "secret123"
                assert creds["host"] == "192.168.1.10"

    def test_get_credentials_device_not_found(self, registry):
        """Test get_credentials with non-existent device."""
        with patch.object(registry, "device_exists", return_value=False):
            with pytest.raises(DeviceNotFoundError, match="Device 'unknown' not found"):
                registry.get_credentials("unknown", "aoa-agent")

    def test_get_credentials_account_not_found(self, registry):
        """Test get_credentials with non-existent account."""
        with patch.object(registry, "device_exists", return_value=True):
            with patch.object(registry, "account_exists", return_value=False):
                with pytest.raises(AccountNotFoundError, match="Account 'unknown' not found"):
                    registry.get_credentials("front-door", "unknown")

    def test_get_credentials_permission_denied(self, registry):
        """Test get_credentials with permission denied."""
        with patch.object(registry, "device_exists", return_value=True):
            with patch.object(registry, "account_exists", return_value=True):
                registry.client.secrets.kv.v2.read_secret_version.side_effect = Forbidden()

                with pytest.raises(PermissionDeniedError, match="Access denied"):
                    registry.get_credentials("front-door", "aoa-agent")

    def test_get_device_info_success(self, registry):
        """Test successful device info retrieval."""
        registry.client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {
                "data": {
                    "host": "192.168.1.10",
                    "serial_number": "ACCC12345678",
                    "location": "Main Entrance",
                }
            }
        }

        with patch.object(registry, "device_exists", return_value=True):
            device_info = registry.get_device_info("front-door")

            assert device_info["host"] == "192.168.1.10"
            assert device_info["serial_number"] == "ACCC12345678"
            assert device_info["device_id"] == "front-door"

    def test_list_devices_success(self, registry):
        """Test successful device listing."""
        # Mock list response
        registry.client.secrets.kv.v2.list_secrets.return_value = {
            "data": {"keys": ["front-door/", "parking-1/"]}
        }

        # list_devices calls get_device_info per device, which itself calls
        # device_exists first — so each device consumes TWO read_secret_version
        # calls: one existence probe, one actual read. Two devices = four reads.
        front_door = {
            "data": {
                "data": {
                    "host": "192.168.1.10",
                    "location": "Main Entrance",
                }
            }
        }
        parking_1 = {
            "data": {
                "data": {
                    "host": "192.168.1.11",
                    "location": "Parking Lot",
                }
            }
        }
        registry.client.secrets.kv.v2.read_secret_version.side_effect = [
            front_door,  # device_exists("front-door")
            front_door,  # get_device_info("front-door")
            parking_1,   # device_exists("parking-1")
            parking_1,   # get_device_info("parking-1")
        ]

        devices = registry.list_devices()

        assert len(devices) == 2
        assert devices[0]["device_id"] == "front-door"
        assert devices[1]["device_id"] == "parking-1"

    def test_list_devices_empty(self, registry):
        """Test listing devices when none exist."""
        registry.client.secrets.kv.v2.list_secrets.side_effect = InvalidPath()

        devices = registry.list_devices()
        assert devices == []

    def test_list_accounts_success(self, registry):
        """Test successful account listing."""
        # Mock list response
        registry.client.secrets.kv.v2.list_secrets.return_value = {
            "data": {"keys": ["aoa-agent/", "admin/"]}
        }

        # Mock account data for each account
        registry.client.secrets.kv.v2.read_secret_version.side_effect = [
            {
                "data": {
                    "data": {
                        "username": "aoa_agent",
                        "password": "secret123",
                        "account_type": "service",
                    }
                }
            },
            {
                "data": {
                    "data": {
                        "username": "root",
                        "password": "admin456",
                        "account_type": "admin",
                    }
                }
            },
        ]

        with patch.object(registry, "device_exists", return_value=True):
            accounts = registry.list_accounts("front-door")

            assert len(accounts) == 2
            assert accounts[0]["account_id"] == "aoa-agent"
            assert accounts[0]["username"] == "aoa_agent"
            assert "password" not in accounts[0]  # Password should be removed
            assert accounts[1]["account_id"] == "admin"

    def test_device_exists_true(self, registry):
        """Test device_exists returns True for existing device."""
        registry.client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"host": "192.168.1.10"}}
        }

        assert registry.device_exists("front-door") is True

    def test_device_exists_false(self, registry):
        """Test device_exists returns False for non-existent device."""
        registry.client.secrets.kv.v2.read_secret_version.side_effect = InvalidPath()

        assert registry.device_exists("unknown") is False

    def test_account_exists_true(self, registry):
        """Test account_exists returns True for existing account."""
        registry.client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"username": "aoa_agent"}}
        }

        with patch.object(registry, "device_exists", return_value=True):
            assert registry.account_exists("front-door", "aoa-agent") is True

    def test_account_exists_false(self, registry):
        """Test account_exists returns False for non-existent account."""
        registry.client.secrets.kv.v2.read_secret_version.side_effect = InvalidPath()

        with patch.object(registry, "device_exists", return_value=True):
            assert registry.account_exists("front-door", "unknown") is False

    def test_add_device_success(self, registry):
        """Test successful device addition."""
        device_info = {
            "host": "192.168.1.10",
            "serial_number": "ACCC12345678",
        }

        with patch.object(registry, "device_exists", return_value=False):
            registry.add_device("front-door", device_info)

            registry.client.secrets.kv.v2.create_or_update_secret.assert_called_once()

    def test_add_device_already_exists(self, registry):
        """Test adding device that already exists."""
        device_info = {"host": "192.168.1.10"}

        with patch.object(registry, "device_exists", return_value=True):
            with pytest.raises(BackendError, match="already exists"):
                registry.add_device("front-door", device_info)

    def test_add_account_success(self, registry):
        """Test successful account addition."""
        account_data = {
            "username": "aoa_agent",
            "password": "secret123",
        }

        with patch.object(registry, "device_exists", return_value=True):
            with patch.object(registry, "account_exists", return_value=False):
                registry.add_account("front-door", "aoa-agent", account_data)

                registry.client.secrets.kv.v2.create_or_update_secret.assert_called_once()

    def test_remove_device_success(self, registry):
        """Test successful device removal."""
        with patch.object(registry, "device_exists", return_value=True):
            with patch.object(registry, "list_accounts", return_value=[]):
                registry.remove_device("front-door")

                registry.client.secrets.kv.v2.delete_metadata_and_all_versions.assert_called_once()

    def test_remove_account_success(self, registry):
        """Test successful account removal."""
        with patch.object(registry, "device_exists", return_value=True):
            with patch.object(registry, "account_exists", return_value=True):
                registry.remove_account("front-door", "aoa-agent")

                registry.client.secrets.kv.v2.delete_metadata_and_all_versions.assert_called_once()
