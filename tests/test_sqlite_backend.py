"""Tests for the SQLite backend."""

import logging
import os
import subprocess
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


class TestCreatedAt:
    """devices.created_at: stamped on add, surfaced on read, column-managed."""

    def test_created_at_set_on_add(self, registry, sample_device):
        import time
        t0 = time.time()
        registry.add_device("cam-01", sample_device)
        info = registry.get_device_info("cam-01")
        assert "created_at" in info
        assert abs(info["created_at"] - t0) < 5

    def test_created_at_in_list_devices(self, registry, sample_device):
        registry.add_device("cam-01", sample_device)
        assert "created_at" in registry.list_devices()[0]

    def test_created_at_ordering_reflects_insertion(self, registry, sample_device):
        registry.add_device("a", sample_device)
        registry.add_device("b", {**sample_device, "host": "192.168.1.2"})
        ts = {d["device_id"]: d["created_at"] for d in registry.list_devices()}
        assert ts["a"] <= ts["b"]

    def test_created_at_not_duplicated_into_info_blob(self, registry, sample_device, tmp_path):
        import json
        import sqlite3
        registry.add_device("cam-01", sample_device)
        registry.update_device("cam-01", {"location": "Lobby"})
        # The blob must not carry created_at — it's a column.
        raw = sqlite3.connect(str(tmp_path / "admz.db")).execute(
            "SELECT info_json, created_at FROM devices WHERE device_id='cam-01'"
        ).fetchone()
        assert "created_at" not in json.loads(raw[0])
        assert raw[1] is not None
        # ...but reads still surface it (from the column) after an update.
        assert "created_at" in registry.get_device_info("cam-01")

    def test_legacy_null_row_has_no_created_at(self, registry, sample_device, tmp_path):
        import sqlite3
        # Simulate a row that predates the column (created_at NULL).
        conn = sqlite3.connect(str(tmp_path / "admz.db"))
        conn.execute(
            "INSERT INTO devices (device_id, info_json, created_at) VALUES (?, ?, NULL)",
            ("legacy", '{"host": "10.0.0.9", "model": "Z"}'),
        )
        conn.commit()
        info = registry.get_device_info("legacy")
        assert "created_at" not in info  # absent rather than a fake timestamp

    def test_migration_adds_column_to_legacy_db(self, tmp_path):
        import sqlite3
        from admz.backends.sqlite_backend import SQLiteDeviceRegistry
        db = str(tmp_path / "legacy.db")
        # Build a pre-migration devices table (no created_at column).
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE devices (device_id TEXT PRIMARY KEY, info_json TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO devices VALUES (?, ?)", ("old", '{"host": "10.0.0.1"}')
        )
        conn.commit()
        conn.close()
        # Opening the registry migrates the column in.
        reg = SQLiteDeviceRegistry(db_path=db, key_path=str(tmp_path / "k.key"))
        cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(devices)")}
        assert "created_at" in cols
        # Legacy row reads fine; its created_at is unknown (absent).
        assert "created_at" not in reg.get_device_info("old")
        # New adds get stamped.
        reg.add_device("new", {"host": "10.0.0.2"})
        assert "created_at" in reg.get_device_info("new")


class TestConfigBaselineColumns:
    """baseline_sha / latest_observed_sha / last_observed_at: git config
    pointers, column-managed (ADR-0031)."""

    def test_null_on_add(self, registry, sample_device):
        registry.add_device("cam-01", sample_device)
        info = registry.get_device_info("cam-01")
        assert "baseline_sha" not in info
        assert "latest_observed_sha" not in info
        assert "last_observed_at" not in info

    def test_set_config_pointers(self, registry, sample_device):
        import time
        registry.add_device("cam-01", sample_device)
        registry.set_config_pointers(
            "cam-01", baseline_sha="abc", latest_observed_sha="abc",
            last_observed_at=time.time(),
        )
        info = registry.get_device_info("cam-01")
        assert info["baseline_sha"] == "abc"
        assert info["latest_observed_sha"] == "abc"
        assert info["last_observed_at"] is not None

    def test_advance_observed_keeps_baseline(self, registry, sample_device):
        registry.add_device("cam-01", sample_device)
        registry.set_config_pointers(
            "cam-01", baseline_sha="base", latest_observed_sha="base"
        )
        registry.set_config_pointers("cam-01", latest_observed_sha="obs2")
        info = registry.get_device_info("cam-01")
        assert info["baseline_sha"] == "base"  # untouched
        assert info["latest_observed_sha"] == "obs2"

    def test_pointers_in_list_devices(self, registry, sample_device):
        registry.add_device("cam-01", sample_device)
        registry.set_config_pointers("cam-01", baseline_sha="xyz")
        assert registry.list_devices()[0]["baseline_sha"] == "xyz"

    def test_pointers_not_duplicated_into_info_blob(
        self, registry, sample_device, tmp_path
    ):
        import json
        import sqlite3
        registry.add_device("cam-01", sample_device)
        registry.set_config_pointers("cam-01", baseline_sha="abc")
        registry.update_device("cam-01", {"location": "Lobby"})
        raw = sqlite3.connect(str(tmp_path / "admz.db")).execute(
            "SELECT info_json, baseline_sha FROM devices WHERE device_id='cam-01'"
        ).fetchone()
        assert "baseline_sha" not in json.loads(raw[0])
        assert raw[1] == "abc"  # update_device must not wipe the column

    def test_set_pointers_unknown_device_raises(self, registry):
        from admz.exceptions import DeviceNotFoundError
        with pytest.raises(DeviceNotFoundError):
            registry.set_config_pointers("nope", baseline_sha="x")

    def test_migration_adds_pointer_columns(self, tmp_path):
        import sqlite3
        from admz.backends.sqlite_backend import SQLiteDeviceRegistry
        db = str(tmp_path / "legacy.db")
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE devices "
            "(device_id TEXT PRIMARY KEY, info_json TEXT NOT NULL, created_at REAL)"
        )
        conn.commit()
        conn.close()
        SQLiteDeviceRegistry(db_path=db, key_path=str(tmp_path / "k.key"))
        cols = {r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(devices)")}
        assert {"baseline_sha", "latest_observed_sha", "last_observed_at"} <= cols


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
        reason="POSIX mode bits; Windows is covered by the DACL tests below",
    )
    def test_key_file_created_with_secure_permissions(self, tmp_path):
        db_path = str(tmp_path / "admz.db")
        key_path = str(tmp_path / "admz.key")
        SQLiteDeviceRegistry(db_path=db_path, key_path=key_path)

        assert os.path.exists(key_path)
        mode = os.stat(key_path).st_mode & 0o777
        # Should be 0o600 (owner read/write only)
        assert mode == 0o600

    # -- Windows: the DACL, which is what actually governs access there ----
    #
    # These replace the blanket win32 skip that issue #207 filed against.
    #
    # Read this before adding to them. The OBVIOUS assertion — "no ACE
    # grants read to BUILTIN\\Users or Everyone" — is VACUOUS here. A file
    # created in an ordinary temp directory already has a DACL of
    # SYSTEM / Administrators / OWNER RIGHTS and no Users ACE, so that
    # assertion passes on a CI runner with the fix reverted. Measured, not
    # assumed. An allowlist of {owner, Administrators, SYSTEM} is no better
    # on its own: it trips over the unlisted OWNER RIGHTS (S-1-3-4) for a
    # reason that has nothing to do with the code under test.
    #
    # SE_DACL_PROTECTED is what carries the weight. An ordinarily-created
    # file ALWAYS inherits its parent's DACL, in every environment, so
    # protected=True can only hold if code deliberately broke inheritance.
    # The allowlist is then sound as a POST-condition, because after the
    # fix the DACL is authored entirely by ADMZ.

    @pytest.mark.skipif(
        sys.platform != "win32", reason="Windows DACL semantics"
    )
    def test_key_file_dacl_is_protected_from_inheritance(self, tmp_path):
        """The load-bearing assertion: inheritance was explicitly broken."""
        from admz.win_acl import read_file_dacl

        key_path = tmp_path / "admz.key"
        SQLiteDeviceRegistry(
            db_path=str(tmp_path / "admz.db"), key_path=str(key_path)
        )

        # Control: a file written the ordinary way inherits, always.
        control = tmp_path / "control.bin"
        control.write_bytes(b"x")
        assert read_file_dacl(control).protected is False, (
            "control file was already protected — this test can no longer "
            "distinguish the fix from the environment"
        )

        assert read_file_dacl(key_path).protected is True

    @pytest.mark.skipif(
        sys.platform != "win32", reason="Windows DACL semantics"
    )
    def test_key_file_dacl_grants_read_only_to_owner_admins_system(
        self, tmp_path
    ):
        """Post-condition on the DACL the fix authors."""
        from admz.win_acl import (
            SID_ADMINISTRATORS,
            SID_SYSTEM,
            current_user_sid,
            read_file_dacl,
        )

        key_path = tmp_path / "admz.key"
        SQLiteDeviceRegistry(
            db_path=str(tmp_path / "admz.db"), key_path=str(key_path)
        )

        allowed = {SID_SYSTEM, SID_ADMINISTRATORS, current_user_sid()}
        readers = set(read_file_dacl(key_path).read_trustees())

        assert readers, "a DACL granting nobody read would lock ADMZ out"
        assert readers <= allowed, (
            f"key file readable by unexpected principals: "
            f"{sorted(readers - allowed)}"
        )

    @pytest.mark.skipif(
        sys.platform != "win32", reason="Windows DACL semantics"
    )
    def test_key_file_does_not_inherit_permissive_parent(self, tmp_path):
        """The honest fresh-install simulation.

        ``C:\\ProgramData`` grants ``BUILTIN\\Users:(OI)(CI)(RX)``, so a
        newly-created ``ADMZ_HOME`` under it inherits that and every local
        user can read the Fernet master key. ADR-0042 hardens ADMZ_HOME
        with a *setup script*; this asserts the code does it too, for the
        deployment that never ran the script.

        Self-validating: it first proves the parent really is permissive,
        so it cannot quietly degrade into a tautology.
        """
        from admz.win_acl import SID_USERS, read_file_dacl

        home = tmp_path / "programdata-like"
        home.mkdir()
        granted = subprocess.run(
            ["icacls", str(home), "/grant", f"*{SID_USERS}:(OI)(CI)(RX)"],
            capture_output=True,
            text=True,
        )
        if granted.returncode != 0:
            pytest.skip(f"could not set up a permissive parent: {granted.stderr}")

        # Control: an ordinary file here DOES inherit BUILTIN\Users.
        control = home / "control.bin"
        control.write_bytes(b"x")
        assert SID_USERS in read_file_dacl(control).read_trustees(), (
            "parent directory is not actually permissive — this test would "
            "pass even with the fix reverted"
        )

        key_path = home / "admz.key"
        SQLiteDeviceRegistry(
            db_path=str(home / "admz.db"), key_path=str(key_path)
        )

        assert SID_USERS not in read_file_dacl(key_path).read_trustees()

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


class TestDataDirPermissions:
    """#250 — the ADMZ_HOME ``chmod 0o700`` is POSIX-only.

    Be honest about what is assertable here, because it is much less than
    #252 got. On Windows ``os.chmod`` was a *measured no-op* — that was
    the whole defect — so removing it changes no observable file-system
    state. There is nothing to inspect afterwards, by definition. The only
    truthful Windows assertion is therefore that the call is not made, and
    that is a platform-guard test rather than a behavioural one.

    What is NOT asserted, deliberately: that the directory gets a
    protected DACL. It does not, and must not — see
    ``admz.paths._restrict_dir``'s docstring and ADR-0042. A future port of
    ``admz.win_acl`` to this path would collapse the DACL of every file
    inside ADMZ_HOME (measured: ``admz.db`` 4 ACEs -> 0, deny-all).

    These are the *registry-level* tests — they go through
    ``SQLiteDeviceRegistry`` and assert the directory it ends up with. The
    unit tests for the mechanism itself moved to ``tests/test_paths.py``
    in #254, when ``_restrict_data_dir`` moved out of this backend and
    into ``admz/paths.py`` where the path policy belongs.
    """

    @staticmethod
    def _spy(monkeypatch):
        calls = []
        monkeypatch.setattr(
            os, "chmod", lambda p, m, *a, **k: calls.append((str(p), m))
        )
        return calls

    # -- real platform behaviour -------------------------------------------

    @pytest.mark.skipif(
        sys.platform == "win32", reason="POSIX mode bits; no-op on Windows"
    )
    def test_data_dir_is_0700_on_posix(self, tmp_path):
        """The effect, not the call. Previously asserted by nothing at all."""
        home = tmp_path / "admz-home"
        SQLiteDeviceRegistry(
            db_path=str(home / "admz.db"), key_path=str(home / "admz.key")
        )
        assert home.is_dir()
        assert oct(os.stat(home).st_mode & 0o777) == oct(0o700)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
    def test_chmod_not_called_on_data_dir_on_windows(self, tmp_path, monkeypatch):
        home = tmp_path / "admz-home"
        calls = self._spy(monkeypatch)
        SQLiteDeviceRegistry(
            db_path=str(home / "admz.db"), key_path=str(home / "admz.key")
        )
        assert home.is_dir()
        assert [c for c in calls if c[0] == str(home)] == []

    # -- failure is logged, never fatal -------------------------------------

    def test_chmod_failure_does_not_abort_registry_construction(
        self, tmp_path, monkeypatch
    ):
        """Logged, but never fatal — a service that refuses to boot on an
        exotic filesystem is worse than one that boots and says so."""
        real_chmod = os.chmod

        def selective(path, mode, *a, **k):
            if str(path) == str(tmp_path):
                raise OSError(13, "denied")
            return real_chmod(path, mode, *a, **k)

        monkeypatch.setattr(os, "chmod", selective)
        reg = SQLiteDeviceRegistry(
            db_path=str(tmp_path / "admz.db"),
            key_path=str(tmp_path / "admz.key"),
        )
        assert reg.list_devices() == []


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
