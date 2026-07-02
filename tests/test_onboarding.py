"""Credential onboarding (admz/onboarding.py) — resolution order + secrecy.

Order: stored creds verify → keep; needsetup → provision from fleet
settings; fleet pair authenticates → save silently; else credentials_needed.
No outcome dict may ever carry a password.
"""

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from admz import onboarding
from admz.onboarding import onboard_device_credentials

FLEET_PW = "fleet-secret-42"


class _Registry:
    def __init__(self, stored=None):
        self._stored = stored
        self.accounts = {}
        self.info_updates = {}

    def get_device_info(self, did):
        return {"host": "192.0.2.9", "model": ""}

    def get_credentials(self, did):
        if self._stored is None:
            raise KeyError("no account")
        return self._stored

    def account_exists(self, did, aid):
        return aid in self.accounts

    def remove_account(self, did, aid):
        self.accounts.pop(aid, None)

    def add_account(self, did, aid, data):
        self.accounts[aid] = data

    def update_device_info(self, did, changed):
        self.info_updates.update(changed)


def _run(**kw):
    defaults = dict(
        device_id="dev-1",
        registry=kw.pop("registry", _Registry()),
        catalog=MagicMock(),
        executors={"vapix": MagicMock()},
    )
    defaults.update(kw)
    return asyncio.run(onboard_device_credentials(**defaults))


@pytest.fixture
def patch_probes(monkeypatch):
    """Scriptable stand-ins for the device probes (incl. TCP preflight)."""
    monkeypatch.delenv("ADMZ_DISABLE_ONBOARDING_PROBES", raising=False)

    async def _tcp_up(host, port, timeout):
        return 5  # ms — device answers TCP

    monkeypatch.setattr("admz.fleet.health._tcp_probe", _tcp_up)

    state = {
        "confirm": [],          # queue of (ok, facts) per call
        "systemready": None,    # dict or None
        "provision": {"success": True, "username": "root",
                      "password_source": "fleet_default"},
    }

    async def _confirm(**kwargs):
        state.setdefault("confirm_calls", []).append(kwargs["credentials"])
        return state["confirm"].pop(0) if state["confirm"] else (None, {})

    async def _ready(*a, **k):
        return state["systemready"]

    async def _provision(*a, **k):
        state["provision_called"] = True
        return state["provision"]

    monkeypatch.setattr("admz.fleet.health._confirm_credentials", _confirm)
    monkeypatch.setattr("admz.fleet.systemready.read_systemready", _ready)
    monkeypatch.setattr(
        "admz.provisioning.provision_factory_default", _provision
    )
    return state


class TestResolutionOrder:
    def test_stored_creds_verify_wins(self, patch_probes, monkeypatch):
        patch_probes["confirm"] = [(True, {})]
        reg = _Registry(stored={"username": "root", "password": "existing"})
        out = _run(registry=reg)
        assert out["status"] == "already_credentialed"
        assert "provision_called" not in patch_probes

    def test_needsetup_provisions_from_fleet(self, patch_probes):
        patch_probes["systemready"] = {"needsetup": True, "systemready": True,
                                       "bootid": None, "uptime": 1}
        out = _run()
        assert out["status"] == "provisioned"
        assert out["password_source"] == "fleet_default"
        assert patch_probes.get("provision_called")

    def test_provision_failure_reported(self, patch_probes):
        patch_probes["systemready"] = {"needsetup": True, "systemready": True,
                                       "bootid": None, "uptime": 1}
        patch_probes["provision"] = {"success": False, "error": "vapix said no"}
        out = _run()
        assert out["status"] == "provision_failed"
        assert "vapix said no" in out["error"]

    def test_fleet_pair_saved_when_it_authenticates(self, patch_probes, monkeypatch):
        monkeypatch.setattr(
            onboarding.fleet_settings, "get",
            lambda k: {"default_password": FLEET_PW, "default_username": "admin"}.get(k),
        )
        patch_probes["confirm"] = [(True, {"model": "P3408-VE",
                                           "firmware_version": "11.11.0"})]
        reg = _Registry()
        out = _run(registry=reg)
        assert out["status"] == "fleet_credentials_saved"
        assert out["username"] == "admin"
        # saved server-side with an accurate purpose…
        assert reg.accounts["default"]["password"] == FLEET_PW
        assert "onboarding" in reg.accounts["default"]["purpose"]
        # …and the verify response backfilled device facts
        assert reg.info_updates.get("model") == "P3408-VE"

    def test_stale_stored_creds_repaired_by_fleet_pair(self, patch_probes, monkeypatch):
        monkeypatch.setattr(
            onboarding.fleet_settings, "get",
            lambda k: {"default_password": FLEET_PW}.get(k),
        )
        # stored creds rejected, fleet pair accepted
        patch_probes["confirm"] = [(False, {}), (True, {})]
        reg = _Registry(stored={"username": "root", "password": "stale"})
        out = _run(registry=reg)
        assert out["status"] == "fleet_credentials_saved"
        assert reg.accounts["default"]["password"] == FLEET_PW

    def test_fleet_pair_rejected_needs_capture(self, patch_probes, monkeypatch):
        monkeypatch.setattr(
            onboarding.fleet_settings, "get",
            lambda k: {"default_password": FLEET_PW}.get(k),
        )
        patch_probes["confirm"] = [(False, {})]
        out = _run()
        assert out["status"] == "credentials_needed"
        assert "rejected" in out["reason"]

    def test_no_fleet_password_needs_capture(self, patch_probes, monkeypatch):
        monkeypatch.setattr(onboarding.fleet_settings, "get", lambda k: None)
        out = _run()
        assert out["status"] == "credentials_needed"
        assert "default_password" in out["reason"]

    def test_unknown_device_degrades(self, patch_probes):
        class _Boom(_Registry):
            def get_device_info(self, did):
                raise LookupError("nope")

        out = _run(registry=_Boom())
        assert out["status"] == "credentials_needed"

    def test_missing_executor_degrades(self, patch_probes):
        out = _run(executors={})
        assert out["status"] == "credentials_needed"


# ---------------------------------------------------------------------------
# REST wiring — create runs onboarding inline; /onboard covers existing rows
# ---------------------------------------------------------------------------


@pytest.fixture
def rest_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    # conftest sets ADMZ_DISABLE_ONBOARDING_PROBES=1 → deterministic
    # credentials_needed without touching the network.
    from fastapi.testclient import TestClient

    from admz.api.main import app

    with TestClient(app) as c:
        yield c


class TestRestOnboarding:
    def test_create_returns_onboarding_block(self, rest_client):
        r = rest_client.post("/api/devices", json={
            "device_id": "cam-new", "host": "192.0.2.50",
        })
        assert r.status_code == 201
        ob = r.json().get("onboarding")
        assert ob is not None
        assert ob["status"] == "credentials_needed"
        assert ob["capture_url"].startswith("/capture/")

    def test_onboard_endpoint_existing_device(self, rest_client):
        rest_client.post("/api/devices", json={
            "device_id": "cam-x", "host": "192.0.2.51",
        })
        r = rest_client.post("/api/devices/cam-x/onboard")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "credentials_needed"
        assert body["capture_url"].startswith("/capture/")

    def test_onboard_endpoint_unknown_device_404(self, rest_client):
        r = rest_client.post("/api/devices/ghost/onboard")
        assert r.status_code == 404


class TestSecrecy:
    def test_no_outcome_ever_contains_a_password(self, patch_probes, monkeypatch):
        monkeypatch.setattr(
            onboarding.fleet_settings, "get",
            lambda k: {"default_password": FLEET_PW}.get(k),
        )
        scenarios = [
            [(True, {})],            # fleet saved
            [(False, {})],           # rejected
        ]
        for confirm in scenarios:
            patch_probes["confirm"] = list(confirm)
            out = _run(registry=_Registry())
            assert FLEET_PW not in json.dumps(out)
