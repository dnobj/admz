"""Tests for the SQLite backend."""

import os

import pytest

from admz.backends.sqlite_backend import SQLiteDeviceRegistry
from admz.exceptions import (
    AccountNotFoundError,
    BackendError,
    DeviceNotFoundError,
)


@pytest.fixture
def registry(tmp_path):
    db_path = str(tmp_path / "admz.db")
    key_path = str(tmp_path / "admz.key")
    return SQLiteDeviceRegistry(db_path=db_path, key_path=key_path)


@pytest.fixture
def sample_device():
    return {
        "host": "192.168.1.100",
        "model": "AXIS P3245-V",
        "location": "Lobby",
        "tags": ["indoor"],
    }


@pytest.fixture
def sample_account():
    return {
        "username": "admin",
        "password": "supersecret",
        "type": "service",
    }


class TestDeviceOperations:

    def test_add_and_get_device(self, registry, sample_device):
        registry.add_device("cam-01", sample_device)
        info = registry.get_device_info("cam-01")
        assert info["model"] == "AXIS P3245-V"
        assert info["tags"] == ["indoor"]

    def test_add_device_duplicate_raises(self, registry, sample_device):
        registry.add_device("cam-01", sample_device)
        with pytest.raises(BackendError):
            registry.add_device("cam-01", sample_device)

    def test_get_device_info_not_found(self, registry):
        with pytest.raises(DeviceNotFoundError):
            registry.get_device_info("missing")

    def test_device_exists(self, registry, sample_device):
        assert not registry.device_exists("cam-01")
        registry.add_device("cam-01", sample_device)
        assert registry.device_exists("cam-01")

    def test_update_device(self, registry, sample_device):
        registry.add_device("cam-01", sample_device)
        registry.update_device("cam-01", {"location": "Conference Room"})
        info = registry.get_device_info("cam-01")
        assert info["location"] == "Conference Room"
        # Other fields preserved
        assert info["model"] == "AXIS P3245-V"

    def test_update_device_not_found(self, registry):
        with pytest.raises(DeviceNotFoundError):
            registry.update_device("missing", {"location": "X"})

    def test_remove_device(self, registry, sample_device):
        registry.add_device("cam-01", sample_device)
        registry.remove_device("cam-01")
        assert not registry.device_exists("cam-01")

    def test_remove_device_not_found(self, registry):
        with pytest.raises(DeviceNotFoundError):
            registry.remove_device("missing")

    def test_list_devices(self, registry, sample_device):
        registry.add_device("cam-01", sample_device)
        registry.add_device("cam-02", {**sample_device, "host": "1.2.3.5"})
        devices = registry.list_devices()
        assert len(devices) == 2
        device_ids = {d["device_id"] for d in devices}
        assert device_ids == {"cam-01", "cam-02"}


class TestAccountOperations:

    def test_add_and_get_account(self, registry, sample_device, sample_account):
        registry.add_device("cam-01", sample_device)
        registry.add_account("cam-01", "default", sample_account)
        creds = registry.get_credentials("cam-01", "default")
        assert creds["username"] == "admin"
        assert creds["password"] == "supersecret"

    def test_password_is_encrypted_at_rest(
        self, registry, sample_device, sample_account, tmp_path
    ):
        registry.add_device("cam-01", sample_device)
        registry.add_account("cam-01", "default", sample_account)

        with open(str(tmp_path / "admz.db"), "rb") as f:
            content = f.read()
        # Plaintext password should not appear in raw DB bytes
        assert b"supersecret" not in content

    def test_get_credentials_default_account(
        self, registry, sample_device, sample_account
    ):
        registry.add_device("cam-01", sample_device)
        registry.add_account("cam-01", "default", sample_account)
        creds = registry.get_credentials("cam-01")
        assert creds["username"] == "admin"

    def test_list_accounts(self, registry, sample_device, sample_account):
        registry.add_device("cam-01", sample_device)
        registry.add_account("cam-01", "default", sample_account)
        registry.add_account("cam-01", "viewer", {"username": "v", "password": "p"})
        accounts = registry.list_accounts("cam-01")
        assert len(accounts) == 2

    def test_remove_account(self, registry, sample_device, sample_account):
        registry.add_device("cam-01", sample_device)
        registry.add_account("cam-01", "default", sample_account)
        registry.remove_account("cam-01", "default")
        with pytest.raises(AccountNotFoundError):
            registry.get_credentials("cam-01", "default")

    def test_remove_device_cascades_to_accounts(
        self, registry, sample_device, sample_account
    ):
        registry.add_device("cam-01", sample_device)
        registry.add_account("cam-01", "default", sample_account)
        registry.remove_device("cam-01")
        # Re-add device and verify the account is gone
        registry.add_device("cam-01", sample_device)
        accounts = registry.list_accounts("cam-01")
        assert accounts == []


class TestEncryption:

    def test_key_file_created_with_secure_permissions(self, tmp_path):
        db_path = str(tmp_path / "admz.db")
        key_path = str(tmp_path / "admz.key")
        SQLiteDeviceRegistry(db_path=db_path, key_path=key_path)

        assert os.path.exists(key_path)
        mode = os.stat(key_path).st_mode & 0o777
        # Should be 0o600 (owner read/write only)
        assert mode == 0o600

    def test_two_instances_with_different_keys_dont_share(self, tmp_path):
        """Regression: previously a module-global Fernet meant the second
        instance silently reused the first's key."""
        # Build two registries with different key files
        reg1 = SQLiteDeviceRegistry(
            db_path=str(tmp_path / "a.db"),
            key_path=str(tmp_path / "a.key"),
        )
        reg2 = SQLiteDeviceRegistry(
            db_path=str(tmp_path / "b.db"),
            key_path=str(tmp_path / "b.key"),
        )
        # Their Fernet instances must be different
        assert reg1._fernet is not reg2._fernet
        # And their key files must have different bytes
        key1 = open(str(tmp_path / "a.key"), "rb").read()
        key2 = open(str(tmp_path / "b.key"), "rb").read()
        assert key1 != key2
