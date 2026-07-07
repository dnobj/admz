"""Tests for config scenarios (ADR-0044) — the active_scenario marker + the
IN_SCENARIO drift state (Slice 1). Backend save/activate/return route tests are
added alongside the routes (Slice 2)."""

from __future__ import annotations

import pytest

from admz.backends.sqlite_backend import SQLiteDeviceRegistry
from admz.exceptions import DeviceNotFoundError
from admz.snapshot import drift_status


def _reg(tmp_path):
    return SQLiteDeviceRegistry(
        db_path=str(tmp_path / "t.db"), key_path=str(tmp_path / "t.key"),
    )


# --------------------------------------------------------------------------
# active_scenario column round-trip
# --------------------------------------------------------------------------

class TestActiveScenarioColumn:
    def test_set_and_surface(self, tmp_path):
        reg = _reg(tmp_path)
        reg.add_device("cam1", {"host": "192.0.2.1"})
        # Absent by default (NULL → key omitted).
        assert "active_scenario" not in reg.get_device_info("cam1")

        reg.set_active_scenario("cam1", "demo")
        assert reg.get_device_info("cam1")["active_scenario"] == "demo"
        # Also surfaced in list_devices.
        row = next(d for d in reg.list_devices() if d["device_id"] == "cam1")
        assert row["active_scenario"] == "demo"

    def test_clear(self, tmp_path):
        reg = _reg(tmp_path)
        reg.add_device("cam1", {"host": "192.0.2.1"})
        reg.set_active_scenario("cam1", "demo")
        reg.set_active_scenario("cam1", None)
        assert "active_scenario" not in reg.get_device_info("cam1")

    def test_unknown_device(self, tmp_path):
        reg = _reg(tmp_path)
        with pytest.raises(DeviceNotFoundError):
            reg.set_active_scenario("ghost", "demo")

    def test_survives_baseline_pointer(self, tmp_path):
        # Setting a scenario must not touch baseline_sha, and vice versa.
        reg = _reg(tmp_path)
        reg.add_device("cam1", {"host": "192.0.2.1"})
        reg.set_config_pointers("cam1", baseline_sha="abc123")
        reg.set_active_scenario("cam1", "demo")
        info = reg.get_device_info("cam1")
        assert info["baseline_sha"] == "abc123"
        assert info["active_scenario"] == "demo"


# --------------------------------------------------------------------------
# drift_status_for → IN_SCENARIO supersedes drift
# --------------------------------------------------------------------------

class TestInScenarioStatus:
    def test_in_scenario_supersedes_drifted(self):
        info = {"baseline_sha": "abc", "active_scenario": "demo"}
        sig = {"field_count": 12, "updated_at": 111.0}  # would be "drifted"
        st = drift_status.drift_status_for(info, sig)
        assert st["state"] == drift_status.IN_SCENARIO
        assert st["scenario_name"] == "demo"
        assert st["checked_at"] == 111.0

    def test_in_scenario_without_signature(self):
        info = {"baseline_sha": "abc", "active_scenario": "night"}
        st = drift_status.drift_status_for(info, None)
        assert st["state"] == drift_status.IN_SCENARIO
        assert st["scenario_name"] == "night"

    def test_no_scenario_falls_through_to_drift(self):
        info = {"baseline_sha": "abc"}
        assert drift_status.drift_status_for(info, {"field_count": 3, "updated_at": 1})["state"] \
            == drift_status.DRIFTED
        assert drift_status.drift_status_for(info, {"field_count": 0, "updated_at": 1})["state"] \
            == drift_status.IN_SYNC
        assert drift_status.drift_status_for(info, None)["state"] == drift_status.UNCHECKED
        assert drift_status.drift_status_for({}, None)["state"] == drift_status.NONE

    def test_in_scenario_in_states_tuple(self):
        assert drift_status.IN_SCENARIO in drift_status.STATES


# --------------------------------------------------------------------------
# Route tests — save / activate / return-to-baseline (Slice 2)
# Auth + the gated push plan are neutralized so we isolate selection, the
# active_scenario marker, and the baseline-stable guarantee.
# --------------------------------------------------------------------------

import types  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def scen_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")

    import admz.api.main as main_module
    reg = SQLiteDeviceRegistry(
        db_path=str(tmp_path / "admz.db"), key_path=str(tmp_path / "admz.key"))
    reg.add_device("cam1", {"host": "192.0.2.1", "tags": ["lab"]})
    reg.set_config_pointers("cam1", baseline_sha="b1")
    reg.save_named_baseline("cam1", "demo", "e1")
    reg.add_device("cam2", {"host": "192.0.2.2", "tags": ["lab"]})  # no 'demo'
    reg.set_config_pointers("cam2", baseline_sha="b2")
    reg.add_device("cam3", {"host": "192.0.2.3", "tags": ["other"]})
    reg.set_config_pointers("cam3", baseline_sha="b3")
    reg.save_named_baseline("cam3", "demo", "e3")
    monkeypatch.setattr(main_module, "registry", reg)

    monkeypatch.setattr("admz.authz.require_authenticated_principal", lambda p: None)

    async def _fake_gated(engine, plan_id):
        return {"blocked": True, "confirm_url": "/confirm/x", "plan_id": plan_id}
    monkeypatch.setattr("admz.operations.execute_gated_plan", _fake_gated)
    # Default: no push steps -> routes take the "no-push" branch, isolating the
    # marker/selection logic (individual tests override for the gated path).
    monkeypatch.setattr(
        "admz.snapshot.restore.RestoreBuilder.build_restore_plan",
        lambda self, did, ref=None, **kw: {"steps": []})

    with TestClient(main_module.app, follow_redirects=False) as c:
        yield c, reg, monkeypatch


class TestScenarioActivate:
    def test_activate_across_tag_marks_and_keeps_baseline(self, scen_client):
        c, reg, _ = scen_client
        body = c.post("/api/snapshot/scenario/activate",
                      json={"name": "demo", "tag": "lab"}).json()
        assert [a["device_id"] for a in body["applied"]] == ["cam1"]
        assert body["skipped"] == ["cam2"]           # in lab, no 'demo'
        # marker set on cam1, baseline UNCHANGED (the whole point)
        info = reg.get_device_info("cam1")
        assert info["active_scenario"] == "demo"
        assert info["baseline_sha"] == "b1"
        # cam3 (tag 'other') out of scope entirely
        assert "cam3" not in body["skipped"]
        assert reg.get_device_info("cam3").get("active_scenario") is None

    def test_activate_single_device(self, scen_client):
        c, reg, _ = scen_client
        body = c.post("/api/snapshot/scenario/activate",
                      json={"name": "demo", "device_id": "cam1"}).json()
        assert [a["device_id"] for a in body["applied"]] == ["cam1"]
        assert reg.get_device_info("cam1")["active_scenario"] == "demo"

    def test_activate_none_matched(self, scen_client):
        c, reg, _ = scen_client
        body = c.post("/api/snapshot/scenario/activate",
                      json={"name": "nope", "tag": "lab"}).json()
        assert body["applied"] == []
        assert "No devices" in body["message"]

    def test_activate_gated_when_push_needed(self, scen_client):
        c, reg, monkeypatch = scen_client
        monkeypatch.setattr(
            "admz.snapshot.restore.RestoreBuilder.build_restore_plan",
            lambda self, did, ref=None, **kw: {"steps": [{"operation_id": "x", "device_id": did}]})
        monkeypatch.setattr(
            "admz.plans.engine.PlanEngine.create_plan",
            lambda self, **kw: types.SimpleNamespace(plan_id="p1"))
        body = c.post("/api/snapshot/scenario/activate",
                      json={"name": "demo", "tag": "lab"}).json()
        assert body.get("blocked") is True
        assert body["confirm_url"] == "/confirm/x"
        assert [a["device_id"] for a in body["applied"]] == ["cam1"]

    def test_requires_exactly_one_target(self, scen_client):
        c, reg, _ = scen_client
        r = c.post("/api/snapshot/scenario/activate", json={"name": "demo"})
        assert r.status_code == 400


class TestScenarioReturn:
    def test_return_clears_markers(self, scen_client):
        c, reg, _ = scen_client
        reg.set_active_scenario("cam1", "demo")
        reg.set_active_scenario("cam2", "demo")
        body = c.post("/api/snapshot/scenario/return-to-baseline",
                      json={"tag": "lab"}).json()
        assert sorted(a["device_id"] for a in body["applied"]) == ["cam1", "cam2"]
        assert reg.get_device_info("cam1").get("active_scenario") is None
        assert reg.get_device_info("cam2").get("active_scenario") is None
        # baseline pointers untouched
        assert reg.get_device_info("cam1")["baseline_sha"] == "b1"


class TestScenarioSave:
    def test_save_across_tag_no_baseline_move(self, scen_client):
        c, reg, monkeypatch = scen_client

        async def _fake_snap(self, device_id, message=None, family="vapix", bless=True):
            assert bless is False   # scenario save must not bless
            return types.SimpleNamespace(git_sha=f"snap-{device_id}")
        monkeypatch.setattr("admz.snapshot.engine.SnapshotEngine.snapshot_device", _fake_snap)
        monkeypatch.setattr("admz.snapshot.git_repo.GitRepo.list_facets_at",
                            lambda self, did, ref: ["image"])

        body = c.post("/api/snapshot/scenario/save",
                      json={"name": "night", "tag": "lab"}).json()
        assert sorted(body["saved"]) == ["cam1", "cam2"]
        # both devices now have a 'night' scenario, baselines unchanged
        for did in ("cam1", "cam2"):
            names = {b["name"] for b in reg.list_named_baselines(did)}
            assert "night" in names
        assert reg.get_device_info("cam1")["baseline_sha"] == "b1"


class TestListScenarios:
    def test_list_counts_across_tag(self, scen_client):
        c, reg, _ = scen_client
        body = c.get("/api/snapshot/scenarios?tag=lab").json()
        assert body["devices"] == 2
        names = {s["name"]: s["count"] for s in body["scenarios"]}
        assert names.get("demo") == 1   # only cam1 in lab has 'demo'


class TestScenarioRender:
    """Real Jinja render (custom filters + new UI) via the web pages."""

    def test_group_toolbar_renders_under_tag(self, scen_client):
        c, reg, _ = scen_client
        html = c.get("/devices?tag=lab").text
        assert 'id="scenario-toolbar"' in html
        assert "Return to baseline" in html

    def test_device_page_shows_in_scenario_badge(self, scen_client):
        c, reg, _ = scen_client
        reg.set_active_scenario("cam1", "demo")
        html = c.get("/device/cam1").text
        assert "In scenario: demo" in html
        assert 'ddReturnToBaseline' in html
