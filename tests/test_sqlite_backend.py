"""Tests for the SQLite backend."""

import os
import sys

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


class TestMacCollisionGuard:
    """add_device must refuse a second registry row for the same physical
    device (same MAC under a different device_id). Regression for the
    duplicate P8815 row whose device_id was the model name 'P8815-2' instead
    of the MAC."""

    def _dev(self, mac, host="192.168.1.153"):
        return {"host": host, "model": "P8815-2", "mac_address": mac}

    def test_canonical_mac_helper(self):
        from admz.device_registry import canonical_mac
        assert canonical_mac("AC:CC:8E:E6:E7:EE") == "ACCC8EE6E7EE"
        assert canonical_mac("ac-cc-8e-e6-e7-ee") == "ACCC8EE6E7EE"
        assert canonical_mac("ACCC8EE6E7EE") == "ACCC8EE6E7EE"
        assert canonical_mac(None) == ""
        assert canonical_mac("") == ""

    def test_same_mac_different_device_id_rejected(self, registry):
        registry.add_device("ACCC8EE6E7EE", self._dev("AC:CC:8E:E6:E7:EE"))
        # The exact P8815 bug: model name used as device_id, same MAC.
        with pytest.raises(BackendError) as exc:
            registry.add_device("P8815-2", self._dev("AC:CC:8E:E6:E7:EE"))
        # The message should point at the existing canonical row.
        assert "ACCC8EE6E7EE" in str(exc.value)
        # And the duplicate must NOT have been written.
        assert registry.device_exists("P8815-2") is False
        assert len(registry.list_devices()) == 1

    def test_collision_is_format_insensitive(self, registry):
        # Existing row stores the colon form; new add uses the stripped form.
        registry.add_device("ACCC8EE6E7EE", self._dev("AC:CC:8E:E6:E7:EE"))
        with pytest.raises(BackendError):
            registry.add_device("dup", self._dev("accc8ee6e7ee"))

    def test_different_mac_allowed(self, registry):
        registry.add_device("dev-a", self._dev("AC:CC:8E:E6:E7:EE"))
        registry.add_device("dev-b", self._dev("B8:A4:4F:66:1A:2F", host="192.168.1.238"))
        assert len(registry.list_devices()) == 2

    def test_devices_without_mac_not_guarded(self, registry, sample_device):
        # sample_device has no mac_address — the guard is a no-op.
        registry.add_device("cam-01", sample_device)
        registry.add_device("cam-02", {**sample_device, "host": "192.168.1.101"})
        assert len(registry.list_devices()) == 2

    def test_same_device_id_still_raises_first(self, registry):
        registry.add_device("ACCC8EE6E7EE", self._dev("AC:CC:8E:E6:E7:EE"))
        # Re-adding the same id hits the original duplicate-id check, not the
        # MAC guard — behavior unchanged.
        with pytest.raises(BackendError) as exc:
            registry.add_device("ACCC8EE6E7EE", self._dev("AC:CC:8E:E6:E7:EE"))
        assert "already exists" in str(exc.value)


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

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows file ACLs don't map to Unix-style chmod 0o600",
    )
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


class TestShortLivedConnections:
    """Phase 3A: SQLite registry now uses per-call connections.
    Verifies the contract — close() is a no-op (safe to call repeatedly),
    operations still work after close(), and concurrent calls don't
    raise ProgrammingError."""

    def test_close_is_idempotent(self, tmp_path):
        reg = SQLiteDeviceRegistry(
            db_path=str(tmp_path / "admz.db"),
            key_path=str(tmp_path / "admz.key"),
        )
        # close() should be safe to call repeatedly
        reg.close()
        reg.close()

    def test_operations_work_after_close(self, tmp_path):
        """Because connections are per-call, close() is a no-op; the
        registry remains fully usable afterwards."""
        reg = SQLiteDeviceRegistry(
            db_path=str(tmp_path / "admz.db"),
            key_path=str(tmp_path / "admz.key"),
        )
        reg.add_device("cam-01", {"host": "192.168.1.10"})
        reg.close()
        # Still usable
        assert reg.device_exists("cam-01")
        assert reg.list_devices()[0]["device_id"] == "cam-01"

    def test_concurrent_threads_do_not_crash(self, tmp_path):
        """The previous long-lived self._conn would raise
        ProgrammingError under cross-thread use. Per-call connections
        eliminate that."""
        import threading

        reg = SQLiteDeviceRegistry(
            db_path=str(tmp_path / "admz.db"),
            key_path=str(tmp_path / "admz.key"),
        )
        errors = []

        def reader(idx):
            try:
                for _ in range(20):
                    reg.list_devices()
            except Exception as e:
                errors.append((idx, type(e).__name__, str(e)))

        threads = [threading.Thread(target=reader, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == [], f"Concurrent threads raised: {errors}"
