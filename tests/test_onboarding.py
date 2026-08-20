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

    def update_account(self, did, aid, data):
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
        spec = state["confirm"].pop(0) if state["confirm"] else (None, {})
        # Cases below script 2-tuples for readability; _confirm_credentials
        # returns (ok, facts, learned) since GH #149.
        return spec if len(spec) == 3 else (*spec, None)

    async def _ready(*a, **k):
        return state["systemready"]

    async def _provision(*a, **k):
        state["provision_called"] = True
        return state["provision"]

    # ADR-0061 / #411 slice 2: a verified entry credential is now used to
    # CREATE ADMZ's own per-device account rather than being stored itself.
    state["adopt"] = {"success": True, "status": "admz_account_created",
                      "username": "admz"}

    async def _adopt(*a, **k):
        state["adopt_called"] = k.get("entry")
        return {**state["adopt"], "device_id": k.get("device_id")}

    monkeypatch.setattr("admz.fleet.health._confirm_credentials", _confirm)
    monkeypatch.setattr("admz.fleet.systemready.read_systemready", _ready)
    monkeypatch.setattr(
        "admz.provisioning.provision_factory_default", _provision
    )
    monkeypatch.setattr("admz.provisioning.adopt_with_admz_account", _adopt)
    return state


class TestResolutionOrder:
    def test_stored_creds_verify_wins(self, patch_probes, monkeypatch):
        patch_probes["confirm"] = [(True, {})]
        reg = _Registry(stored={"username": "root", "password": "existing"})
        out = _run(registry=reg)
        assert out["status"] == "already_credentialed"
        assert "provision_called" not in patch_probes

    def test_needsetup_provisions_from_fleet_when_approved(self, patch_probes):
        """ADR-0059: provisioning a factory-defaulted device now requires an
        approval. This test kept its subject — "the fleet default is used and
        the write happens" — and gained the approval the operator would give;
        the *unapproved* half is pinned in test_provisioning_gate.py."""
        from admz.approval_context import approved

        patch_probes["systemready"] = {"needsetup": True, "systemready": True,
                                       "bootid": None, "uptime": 1}
        with approved("register_discovered_device", "tok-test"):
            out = _run()
        assert out["status"] == "provisioned"
        assert out["password_source"] == "fleet_default"
        assert patch_probes.get("provision_called")

    def test_needsetup_gates_when_not_approved(self, patch_probes):
        """The other side of the same branch, here so this file's reader sees
        the gate exists rather than wondering why the test above wraps."""
        patch_probes["systemready"] = {"needsetup": True, "systemready": True,
                                       "bootid": None, "uptime": 1}
        out = _run()
        assert out["status"] == "approval_required"
        assert not patch_probes.get("provision_called")

    def test_provision_failure_reported(self, patch_probes):
        from admz.approval_context import approved

        patch_probes["systemready"] = {"needsetup": True, "systemready": True,
                                       "bootid": None, "uptime": 1}
        patch_probes["provision"] = {"success": False, "error": "vapix said no"}
        with approved("register_discovered_device", "tok-test"):
            out = _run()
        assert out["status"] == "provision_failed"
        assert "vapix said no" in out["error"]

    def test_fleet_pair_saved_when_it_authenticates(self, patch_probes, monkeypatch):
        monkeypatch.setattr(
            onboarding.fleet_settings, "get",
            lambda k: {"default_password": FLEET_PW, "default_username": "admin"}.get(k),
        )
        from admz.approval_context import approved

        patch_probes["confirm"] = [(True, {"model": "P3408-VE",
                                           "firmware_version": "11.11.0"})]
        reg = _Registry()
        with approved("register_discovered_device", "tok-test"):
            out = _run(registry=reg)
        # ADR-0061: the entry credential gets ADMZ in; ADMZ then creates its
        # own account. This used to store the fleet pair itself, which made one
        # shared password the standing key to every device onboarded this way.
        assert out["status"] == "admz_account_created"
        assert out["username"] == "admz"
        assert out["entry_username"] == "admin"
        # the entry credential is what authenticated the account write…
        assert patch_probes["adopt_called"]["password"] == FLEET_PW
        # …and the verify response still backfilled device facts
        assert reg.info_updates.get("model") == "P3408-VE"

    def test_stale_stored_creds_repaired_by_fleet_pair(self, patch_probes, monkeypatch):
        monkeypatch.setattr(
            onboarding.fleet_settings, "get",
            lambda k: {"default_password": FLEET_PW}.get(k),
        )
        # stored creds rejected, fleet pair accepted
        patch_probes["confirm"] = [(False, {}), (True, {})]
        from admz.approval_context import approved

        reg = _Registry(stored={"username": "root", "password": "stale"})
        with approved("register_discovered_device", "tok-test"):
            out = _run(registry=reg)
        assert out["status"] == "admz_account_created"
        assert patch_probes["adopt_called"]["password"] == FLEET_PW

    def test_adoption_GATES_when_not_approved(self, patch_probes, monkeypatch):
        """ADR-0061's second decision point. An entry credential that works is
        about to create a root admin account on a device that already has an
        owner. Same approval as the factory-default path — not a second one —
        but it MUST be there: a device merely being adopted must not get an
        account created just because it answered a password."""
        monkeypatch.setattr(
            onboarding.fleet_settings, "get",
            lambda k: {"default_password": FLEET_PW}.get(k),
        )
        patch_probes["confirm"] = [(True, {})]
        out = _run()
        assert out["status"] == "approval_required"
        assert "confirm_url" in out or "confirm_token" in out
        assert "adopt_called" not in patch_probes, "the account write ran ungated"
        # The card names what is about to happen, not a generic "onboard".
        assert "admz" in out.get("reason", "").lower()

    def test_adoption_does_NOT_gate_when_no_credential_works(self, patch_probes, monkeypatch):
        """Control: the gate sits at the decision point, not the entry. An add
        that falls through to capture must not raise a widget for an account
        write that never happens — that is the every-add gate ADR-0059 refuses."""
        monkeypatch.setattr(
            onboarding.fleet_settings, "get",
            lambda k: {"default_password": FLEET_PW}.get(k),
        )
        patch_probes["confirm"] = [(False, {})]
        out = _run()
        assert out["status"] == "credentials_needed"
        assert "adopt_called" not in patch_probes

    def test_adoption_falls_back_to_the_entry_credential_if_the_account_write_fails(
        self, patch_probes, monkeypatch
    ):
        """A managed device on a shared credential beats an unmanaged one — but
        the status must say which happened, so nobody reads it as the good path."""
        from admz.approval_context import approved

        monkeypatch.setattr(
            onboarding.fleet_settings, "get",
            lambda k: {"default_password": FLEET_PW}.get(k),
        )
        patch_probes["confirm"] = [(True, {})]
        patch_probes["adopt"] = {"success": False, "error": "device said no"}
        reg = _Registry()
        with approved("register_discovered_device", "tok-test"):
            out = _run(registry=reg)
        assert out["status"] == "fleet_credentials_saved"
        assert out["admz_account_error"] == "device said no"
        assert reg.accounts["default"]["password"] == FLEET_PW
        assert "not created" in reg.accounts["default"]["purpose"]

    # ---- adopt in place (#411): existing devices onto their own account ----

    def test_stored_creds_verify_and_adopt_NOT_requested_leaves_it_alone(self, patch_probes):
        """The default. Every existing caller -- register paths, health-triggered
        re-onboarding -- must keep getting this. Creating accounts on live
        devices because something re-ran onboarding is a decision, not a
        consequence."""
        patch_probes["confirm"] = [(True, {})]
        reg = _Registry(stored={"username": "root", "password": "existing"})
        out = _run(registry=reg)
        assert out["status"] == "already_credentialed"
        assert "adopt_called" not in patch_probes

    def test_adopt_in_place_GATES_when_not_approved(self, patch_probes):
        """Same decision point, same approval as every other account write.
        The card must say the current credential is KEPT -- that is what makes
        this safe for a device whose stored password exists nowhere else."""
        patch_probes["confirm"] = [(True, {})]
        reg = _Registry(stored={"username": "root", "password": "existing"})
        out = _run(registry=reg, adopt=True)
        assert out["status"] == "approval_required"
        assert "adopt_called" not in patch_probes
        assert "recovery" in out.get("reason", "").lower()

    def test_adopt_in_place_creates_admz_and_KEEPS_the_old_credential(self, patch_probes):
        """The whole point. Some stored passwords are ADMZ-generated and exist
        nowhere else; a wipe would lose them, and so would an adoption that
        overwrote the default account without keeping a copy."""
        from admz.approval_context import approved

        patch_probes["confirm"] = [(True, {})]
        reg = _Registry(stored={"username": "root", "password": "generated-once"})
        with approved("register_discovered_device", "tok-test"):
            out = _run(registry=reg, adopt=True)
        assert out["status"] == "admz_account_created"
        assert out["adopted_in_place"] is True
        assert out["entry_username"] == "root"
        # the stored credential is what authenticated the account write...
        assert patch_probes["adopt_called"] == {"username": "root", "password": "generated-once"}
        # ...and it was kept as the recovery account BEFORE anything replaced it
        rec = reg.accounts.get("recovery")
        assert rec and rec["password"] == "generated-once"
        assert "recovery" in rec["purpose"].lower()

    def test_adopt_in_place_is_a_no_op_when_already_on_admz(self, patch_probes):
        """Control: adopting twice must not create a second account or a
        recovery copy of ADMZ's own generated password."""
        from admz.approval_context import approved

        patch_probes["confirm"] = [(True, {})]
        reg = _Registry(stored={"username": "admz", "password": "ours"})
        with approved("register_discovered_device", "tok-test"):
            out = _run(registry=reg, adopt=True)
        assert out["status"] == "already_credentialed"
        assert "adopt_called" not in patch_probes
        assert "recovery" not in reg.accounts

    def test_adopt_in_place_failure_leaves_the_stored_credential_working(self, patch_probes):
        """If the account write fails the device must not be worse off: still
        credentialed, and the outcome says why the switch did not happen."""
        from admz.approval_context import approved

        patch_probes["confirm"] = [(True, {})]
        patch_probes["adopt"] = {"success": False, "error": "device said no"}
        reg = _Registry(stored={"username": "root", "password": "existing"})
        with approved("register_discovered_device", "tok-test"):
            out = _run(registry=reg, adopt=True)
        assert out["status"] == "already_credentialed"
        assert out["admz_account_error"] == "device said no"

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
        assert "entry credentials" in out["reason"]

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
# Strict credential verification — a connection-level error must never be
# mistaken for proof that a password works (the P3408 false positive).
# ---------------------------------------------------------------------------


class TestStrictVerification:
    def _confirm(self, result, strict):
        from admz.fleet.health import _confirm_credentials

        op = MagicMock()
        op.to_executor_dict.return_value = {"id": "basicdeviceinfo"}
        catalog = MagicMock()
        catalog.get_operation.return_value = op
        executor = MagicMock()

        async def _exec(*a, **k):
            return result

        executor.execute = _exec
        return asyncio.run(_confirm_credentials(
            catalog=catalog, executor=executor, device_info={"host": "h"},
            device_id="d", credentials={"username": "u", "password": "p"},
            timeout_seconds=5.0, strict=strict,
        ))

    def test_connection_error_is_unknown_in_strict_mode(self):
        # success=False, status None — the executor couldn't complete the
        # request. Lenient mode says True ("not rejected"); strict says
        # unknown, so onboarding won't save a password off it.
        result = MagicMock(success=False, status_code=None, parsed_data=None)
        assert self._confirm(result, strict=True) == (None, {}, None)
        ok, _, _learned = self._confirm(result, strict=False)
        assert ok is True  # health keeps the lenient behavior

    def test_non_2xx_answer_is_unknown_in_strict_mode(self):
        result = MagicMock(success=False, status_code=500, parsed_data=None)
        assert self._confirm(result, strict=True) == (None, {}, None)

    def test_explicit_401_is_rejected_in_both_modes(self):
        result = MagicMock(success=False, status_code=401, parsed_data=None)
        assert self._confirm(result, strict=True)[0] is False
        assert self._confirm(result, strict=False)[0] is False

    def test_authenticated_2xx_is_true_in_strict_mode(self):
        result = MagicMock(success=True, status_code=200,
                           parsed_data={"data": {"propertyList": {}}})
        ok, _, _learned = self._confirm(result, strict=True)
        assert ok is True


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


class TestSurveyEnqueueWiring:
    """ADR-0063 S2 (#452) — the capability-survey enqueue is wired to the
    REAL success exits, not just unit-tested on `_with_survey` (#455 review,
    MINOR-4: unwrapping a call site survived the suite before this class)."""

    def _survey_tasks(self, device_id):
        from admz.device_capabilities import SURVEY_ACTION_TYPE
        from admz.tasks.store import tasks_store
        return [t for t in tasks_store.list_active_for(device_id)
                if t.action_type == SURVEY_ACTION_TYPE]

    @pytest.fixture
    def isolated_tasks(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))

    def test_provisioned_exit_enqueues_a_survey(
        self, patch_probes, isolated_tasks
    ):
        from admz.approval_context import approved

        patch_probes["systemready"] = {"needsetup": True, "systemready": True,
                                       "bootid": None, "uptime": 1}
        with approved("register_discovered_device", "tok-test"):
            out = _run()
        assert out["status"] == "provisioned"
        assert len(self._survey_tasks("dev-1")) == 1

    def test_already_credentialed_first_sight_enqueues(
        self, patch_probes, isolated_tasks
    ):
        patch_probes["confirm"] = [(True, {})]
        reg = _Registry(stored={"username": "root", "password": "existing"})
        out = _run(registry=reg)
        assert out["status"] == "already_credentialed"
        assert len(self._survey_tasks("dev-1")) == 1
        # Second onboard of the same healthy device: rows unrelated, but the
        # pending-task dedupe keeps it at one.
        patch_probes["confirm"] = [(True, {})]
        _run(registry=reg)
        assert len(self._survey_tasks("dev-1")) == 1

    def test_gated_exit_enqueues_nothing(self, patch_probes, isolated_tasks):
        patch_probes["systemready"] = {"needsetup": True, "systemready": True,
                                       "bootid": None, "uptime": 1}
        out = _run()  # no approval in context → the gate fires
        assert out["status"] == "approval_required"
        assert self._survey_tasks("dev-1") == []
