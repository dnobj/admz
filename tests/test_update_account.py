"""Tests for the registry's update_account() method (Phase: password mgmt).

Adds the missing transactional partial-update for accounts. Replaces
the remove_account + add_account dance in the capture route — the old
pattern had a brief window where the account was observably missing,
and a concurrent reader would see AccountNotFound.

Covers:
  - SQLite backend: round-trip, atomic re-encrypt, error paths
  - ABC default behavior (raises NotImplementedError)
  - Capture route now uses update when account exists
"""

import pytest

from admz.exceptions import AccountNotFoundError, DeviceNotFoundError


@pytest.fixture
def reg(tmp_path, monkeypatch):
    """Fresh SQLite registry per test."""
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    from admz.backends.sqlite_backend import SQLiteDeviceRegistry
    return SQLiteDeviceRegistry(
        db_path=str(tmp_path / "admz.db"),
        key_path=str(tmp_path / "admz.key"),
    )


def _seed(reg, *, device_id="cam-01", account_id="default"):
    reg.add_device(device_id, {"host": "192.0.2.1", "model": "M01"})
    reg.add_account(
        device_id,
        account_id,
        {
            "username": "root",
            "password": "old-secret",
            "account_type": "admin",
            "purpose": "primary",
        },
    )


# ---------------------------------------------------------------------------
# SQLite backend
# ---------------------------------------------------------------------------


class TestSqliteUpdateAccount:
    def test_password_update_round_trip(self, reg):
        _seed(reg)
        reg.update_account("cam-01", "default", {"password": "new-secret"})
        creds = reg.get_credentials("cam-01", "default")
        assert creds["password"] == "new-secret"
        # Other fields preserved.
        assert creds["username"] == "root"
        assert creds["account_type"] == "admin"
        assert creds["purpose"] == "primary"

    def test_partial_update_preserves_other_fields(self, reg):
        _seed(reg)
        reg.update_account("cam-01", "default", {"username": "admin"})
        creds = reg.get_credentials("cam-01", "default")
        assert creds["username"] == "admin"
        assert creds["password"] == "old-secret"  # unchanged

    def test_multiple_fields_at_once(self, reg):
        _seed(reg)
        reg.update_account(
            "cam-01",
            "default",
            {"password": "p2", "purpose": "rotated"},
        )
        creds = reg.get_credentials("cam-01", "default")
        assert creds["password"] == "p2"
        assert creds["purpose"] == "rotated"

    def test_empty_updates_is_a_noop(self, reg):
        _seed(reg)
        reg.update_account("cam-01", "default", {})
        creds = reg.get_credentials("cam-01", "default")
        assert creds["password"] == "old-secret"

    def test_unknown_device_raises(self, reg):
        with pytest.raises(DeviceNotFoundError):
            reg.update_account("nope", "default", {"password": "x"})

    def test_unknown_account_raises(self, reg):
        _seed(reg)
        with pytest.raises(AccountNotFoundError):
            reg.update_account("cam-01", "nonexistent", {"password": "x"})

    def test_password_encrypted_at_rest_after_update(self, reg, tmp_path):
        """The whole point of using Fernet — verify the NEW password
        isn't visible in the raw DB bytes."""
        _seed(reg)
        reg.update_account(
            "cam-01", "default", {"password": "very-distinctive-new-pw"}
        )

        db_file = tmp_path / "admz.db"
        assert db_file.exists()
        raw = db_file.read_bytes()
        assert b"very-distinctive-new-pw" not in raw, (
            "Updated password leaked to raw DB bytes!"
        )
        # And the old one shouldn't still be present either.
        assert b"old-secret" not in raw


# ---------------------------------------------------------------------------
# ABC default
# ---------------------------------------------------------------------------


class TestAbcDefaultRaises:
    def test_abc_update_account_raises_not_implemented(self):
        from admz.device_registry import DeviceRegistry

        class StubRegistry(DeviceRegistry):
            """Bare ABC subclass — should inherit the default NotImplementedError."""

            def get_credentials(self, *a, **kw): return {}
            def get_device_info(self, *a, **kw): return {}
            def get_device_by_nickname(self, *a, **kw): return None
            def list_devices(self, *a, **kw): return []
            def list_accounts(self, *a, **kw): return []
            def device_exists(self, *a, **kw): return True
            def account_exists(self, *a, **kw): return True

        s = StubRegistry()
        with pytest.raises(NotImplementedError):
            s.update_account("d", "a", {"password": "x"})


# ---------------------------------------------------------------------------
# Capture route now uses update_account (atomic) for existing accounts
# ---------------------------------------------------------------------------


@pytest.fixture
def web_client(tmp_path, monkeypatch):
    """Spin up a TestClient against fresh ADMZ state."""
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    # Repoint singletons that captured the prior path at import time.
    # Both the module-level singleton AND the route's captured
    # reference need to be updated — the route did
    # `from admz.api.capture import capture_store` at import time,
    # so it holds its own reference.
    from admz import fleet_settings as fs_module
    from admz.api import capture as cap_module
    from admz.api.routes import capture as cap_route_module
    db_path = str(tmp_path / "admz.db")
    _orig_fs = fs_module.fleet_settings
    _orig_cap = cap_module.capture_store
    _orig_route_cap = cap_route_module.capture_store
    fs_module.fleet_settings = fs_module.FleetSettings(db_path)
    fresh_capture = cap_module.CaptureStore(db_path)
    cap_module.capture_store = fresh_capture
    cap_route_module.capture_store = fresh_capture

    from fastapi.testclient import TestClient
    from admz.api.main import app

    try:
        with TestClient(app, follow_redirects=False) as c:
            import subprocess
            repo_path = str(tmp_path / "config-repo")
            for key, val in [
                ("user.email", "test@test.com"),
                ("user.name", "Test"),
                ("commit.gpgsign", "false"),
            ]:
                subprocess.run(
                    ["git", "config", key, val], cwd=repo_path, check=True
                )
            yield c
    finally:
        fs_module.fleet_settings = _orig_fs
        cap_module.capture_store = _orig_cap
        cap_route_module.capture_store = _orig_route_cap


class TestCaptureRouteUsesUpdate:
    def test_existing_account_gets_updated_not_re_added(self, web_client, tmp_path):
        """Capture flow on an existing account should call
        update_account (atomic) rather than the old remove+add
        dance. Verify by checking that the call site went through
        update_account."""
        from unittest.mock import patch

        # Seed: add a device + a default account
        from admz.api.main import registry
        registry.add_device(
            "cam-99", {"host": "192.0.2.99", "model": "M-test"}
        )
        registry.add_account(
            "cam-99",
            "default",
            {"username": "root", "password": "old", "account_type": "admin", "purpose": "primary"},
        )

        # Create a capture session targeting that account
        from admz.api.capture import capture_store
        session = capture_store.create_session(
            device_id="cam-99",
            account_id="default",
            account_type="admin",
            purpose="rotation test",
        )

        # Spy on both add and update so we can prove which was called
        called = {"update": 0, "add": 0}
        orig_update = registry.update_account
        orig_add = registry.add_account

        def spy_update(*a, **kw):
            called["update"] += 1
            return orig_update(*a, **kw)

        def spy_add(*a, **kw):
            called["add"] += 1
            return orig_add(*a, **kw)

        with patch.object(registry, "update_account", side_effect=spy_update), \
             patch.object(registry, "add_account", side_effect=spy_add):
            r = web_client.post(
                f"/capture/{session.token}",
                data={"username": "root", "password": "new-rotated-pw"},
                # A real browser always sends Origin on a form POST;
                # the capture route now requires it (#3, admz/csrf.py).
                headers={"origin": "http://testserver"},
            )

        assert r.status_code == 200, r.text
        # Should be update, not add, for an existing account.
        assert called["update"] == 1, "expected update_account to be called"
        assert called["add"] == 0, "should NOT call add_account when account exists"

        # And the password really did change.
        creds = registry.get_credentials("cam-99", "default")
        assert creds["password"] == "new-rotated-pw"

    def test_fresh_account_still_uses_add(self, web_client, tmp_path):
        """When the account doesn't exist yet, the capture flow should
        still use add_account (preserving the original behavior)."""
        from unittest.mock import patch

        from admz.api.main import registry
        registry.add_device(
            "cam-100", {"host": "192.0.2.100", "model": "M-test"}
        )

        from admz.api.capture import capture_store
        session = capture_store.create_session(
            device_id="cam-100",
            account_id="default",
            account_type="admin",
            purpose="fresh test",
        )

        called = {"update": 0, "add": 0}
        orig_update = registry.update_account
        orig_add = registry.add_account

        def spy_update(*a, **kw):
            called["update"] += 1
            return orig_update(*a, **kw)

        def spy_add(*a, **kw):
            called["add"] += 1
            return orig_add(*a, **kw)

        with patch.object(registry, "update_account", side_effect=spy_update), \
             patch.object(registry, "add_account", side_effect=spy_add):
            r = web_client.post(
                f"/capture/{session.token}",
                data={"username": "root", "password": "fresh"},                # A real browser always sends Origin on a form POST;
                # the capture route now requires it (#3, admz/csrf.py).
                headers={"origin": "http://testserver"},
            )

        assert r.status_code == 200, r.text
        assert called["add"] == 1
        assert called["update"] == 0


# ---------------------------------------------------------------------------
# Rotate-password web route: button on account_detail creates capture session
# ---------------------------------------------------------------------------


class TestRotatePasswordRoute:
    def test_rotate_creates_capture_session_and_redirects(self, web_client):
        from admz.api.main import registry
        registry.add_device("cam-rot", {"host": "192.0.2.50"})
        registry.add_account(
            "cam-rot",
            "default",
            {"username": "root", "password": "old", "account_type": "admin", "purpose": "p"},
        )

        r = web_client.post(
            "/device/cam-rot/account/default/rotate-password"
        )
        assert r.status_code == 303
        assert r.headers["location"].startswith("/capture/")

        # The new capture session should bind to the same device+account.
        token = r.headers["location"].rsplit("/", 1)[-1]
        from admz.api.capture import capture_store
        session = capture_store.get_session(token)
        assert session is not None
        assert session.device_id == "cam-rot"
        assert session.account_id == "default"

    def test_rotate_on_unknown_account_returns_404(self, web_client):
        from admz.api.main import registry
        registry.add_device("cam-rot2", {"host": "192.0.2.51"})
        # No account added.

        r = web_client.post(
            "/device/cam-rot2/account/missing/rotate-password"
        )
        assert r.status_code == 404
