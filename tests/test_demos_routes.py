"""Route tests for demos (ADR-0046) — CRUD, the rendered readiness, and the
Prepare/End guards.

Uses the real app + a temp-dir registry (same harness as test_api_routes.py), so
the readiness these tests see is assembled by the real service layer from the real
drift/health caches — not a mock of it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolate_admz_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))


@pytest.fixture
def client(isolate_admz_dirs, monkeypatch):
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")
    # Demo writes require an authenticated principal; under the 'none' backend the
    # principal is anonymous, so neutralize that gate (same as the GitHub App tests).
    monkeypatch.setattr("admz.authz.require_authenticated_principal", lambda p: None)
    from admz.api.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def registry():
    import admz.api.main as main_mod
    return main_mod.registry


def _add_device(registry, device_id, *, tags=None, **extra):
    info = {"host": "192.0.2.10", "nickname": device_id, "model": "AXIS TEST",
            "tags": tags or []}
    info.update(extra)
    registry.add_device(device_id, info)
    return device_id


def _mk(client, **kw):
    body = {"name": "Loitering", "narrative": "Walk in."}
    body.update(kw)
    res = client.post("/api/demos", json=body)
    assert res.status_code == 200, res.text
    return res.json()["demo"]


class TestCrud:
    def test_create_list_get_delete(self, client):
        demo = _mk(client, name="Speaker demo")
        assert demo["id"] and demo["name"] == "Speaker demo"
        assert demo["config_source"] == "baseline"
        assert demo["readiness"]["state"] == "empty"  # no devices yet

        listed = client.get("/api/demos").json()["demos"]
        assert [d["name"] for d in listed] == ["Speaker demo"]

        got = client.get(f"/api/demos/{demo['id']}").json()["demo"]
        assert got["narrative"] == "Walk in."

        assert client.delete(f"/api/demos/{demo['id']}").status_code == 200
        assert client.get("/api/demos").json()["demos"] == []

    def test_name_required(self, client):
        assert client.post("/api/demos", json={"name": "  "}).status_code == 400

    def test_missing_is_404(self, client):
        assert client.get("/api/demos/nope").status_code == 404
        assert client.patch("/api/demos/nope", json={}).status_code == 404
        assert client.delete("/api/demos/nope").status_code == 404

    def test_patch_updates_only_sent_fields(self, client):
        demo = _mk(client, name="A", narrative="orig")
        out = client.patch(f"/api/demos/{demo['id']}",
                           json={"roles": {"cam-1": "detector"}}).json()["demo"]
        assert out["roles"] == {"cam-1": "detector"}
        assert out["narrative"] == "orig"  # untouched
        assert out["name"] == "A"


class TestReadinessThroughTheApi:
    def test_tag_scope_resolves_devices(self, client, registry):
        _add_device(registry, "cam-1", tags=["speakers"])
        _add_device(registry, "cam-2", tags=["other"])
        demo = _mk(client, tag="speakers")
        rows = demo["readiness"]["devices"]
        assert [r["device_id"] for r in rows] == ["cam-1"]

    def test_explicit_list_scope_keeps_order_and_drops_unknown(self, client, registry):
        _add_device(registry, "cam-1")
        _add_device(registry, "cam-2")
        demo = _mk(client, device_ids=["cam-2", "cam-1", "ghost"])
        assert [r["device_id"] for r in demo["readiness"]["devices"]] == ["cam-2", "cam-1"]

    def test_no_baseline_device_is_not_ready(self, client, registry):
        _add_device(registry, "cam-1", tags=["speakers"])
        demo = _mk(client, tag="speakers")
        r = demo["readiness"]
        assert r["state"] == "not_ready"
        assert r["devices"][0]["config"]["state"] == "no_baseline"
        assert any("no baseline" in b for b in r["blockers"])

    def test_device_in_someone_elses_scenario_is_on_loan(self, client, registry):
        _add_device(registry, "cam-1", tags=["speakers"])
        registry.set_active_scenario("cam-1", "night-mode")
        demo = _mk(client, tag="speakers")  # a BASELINE demo
        r = demo["readiness"]
        assert r["state"] == "blocked"
        assert r["devices"][0]["config"]["state"] == "on_loan"
        assert any("on loan" in b and "night-mode" in b for b in r["blockers"])


class TestPrepareEndGuards:
    def test_prepare_on_baseline_demo_refuses(self, client, registry):
        _add_device(registry, "cam-1", tags=["speakers"])
        demo = _mk(client, tag="speakers")
        res = client.post(f"/api/demos/{demo['id']}/prepare")
        assert res.status_code == 400
        assert "nothing to load" in res.json()["detail"]

    def test_end_on_baseline_demo_refuses(self, client, registry):
        _add_device(registry, "cam-1", tags=["speakers"])
        demo = _mk(client, tag="speakers")
        res = client.post(f"/api/demos/{demo['id']}/end")
        assert res.status_code == 400
        assert "nothing to end" in res.json()["detail"]

    def test_prepare_without_devices_refuses(self, client):
        demo = _mk(client, config_source="scenario:loiter", tag="nobody")
        res = client.post(f"/api/demos/{demo['id']}/prepare")
        assert res.status_code == 400
        assert "no devices" in res.json()["detail"]

    def test_prepare_refuses_to_steal_a_held_device(self, client, registry):
        # Exclusivity is the point of a scenario: report the conflict, don't
        # silently take the device from the demo that's using it.
        _add_device(registry, "cam-1", tags=["speakers"])
        registry.set_active_scenario("cam-1", "night-mode")
        demo = _mk(client, tag="speakers", config_source="scenario:loiter")
        res = client.post(f"/api/demos/{demo['id']}/prepare")
        assert res.status_code == 409
        assert "night-mode" in res.json()["detail"]

    def test_prepare_delegates_to_the_gated_scenario_core(self, client, registry, monkeypatch):
        # The one write path a demo has must ride the SHARED gated core — not a
        # second, ungated push of its own.
        _add_device(registry, "cam-1", tags=["speakers"])
        demo = _mk(client, tag="speakers", config_source="scenario:loiter")

        seen = {}

        async def _fake(ctx, name, targets, principal, description=None):
            seen["name"] = name
            seen["devices"] = [d.get("device_id") for d in targets]
            seen["description"] = description
            return {"success": True, "applied": [{"device_id": "cam-1"}], "skipped": []}

        monkeypatch.setattr("admz.snapshot.scenarios.activate_scenario_core", _fake)
        res = client.post(f"/api/demos/{demo['id']}/prepare")
        assert res.status_code == 200, res.text
        assert res.json()["demo_id"] == demo["id"]
        assert seen["name"] == "loiter"          # the scenario, not the demo name
        assert seen["devices"] == ["cam-1"]
        assert "Loitering" in seen["description"]

    def test_end_delegates_to_the_gated_return_core(self, client, registry, monkeypatch):
        _add_device(registry, "cam-1", tags=["speakers"])
        demo = _mk(client, tag="speakers", config_source="scenario:loiter")

        seen = {}

        async def _fake(ctx, targets, principal, description=None):
            seen["devices"] = [d.get("device_id") for d in targets]
            return {"success": True, "applied": [{"device_id": "cam-1"}], "skipped": []}

        monkeypatch.setattr("admz.snapshot.scenarios.return_to_baseline_core", _fake)
        res = client.post(f"/api/demos/{demo['id']}/end")
        assert res.status_code == 200, res.text
        assert seen["devices"] == ["cam-1"]


class TestPages:
    def test_list_page_renders_the_verdict(self, client, registry):
        _add_device(registry, "cam-1", tags=["speakers"])
        _mk(client, name="Speaker demo", tag="speakers")
        res = client.get("/demos")
        assert res.status_code == 200
        assert "Speaker demo" in res.text
        assert "Not ready" in res.text  # no baseline → the honest verdict

    def test_empty_list_page(self, client):
        res = client.get("/demos")
        assert res.status_code == 200 and "No demos yet" in res.text

    def test_detail_page(self, client, registry):
        _add_device(registry, "cam-1", tags=["speakers"])
        demo = _mk(client, name="Speaker demo", narrative="The story.", tag="speakers")
        res = client.get(f"/demos/{demo['id']}")
        assert res.status_code == 200
        assert "The story." in res.text
        assert "cam-1" in res.text

    def test_detail_page_names_the_demo_holding_a_device(self, client, registry):
        _add_device(registry, "cam-1", tags=["speakers"])
        # A sidelined demo owns scenario 'night-mode' and has taken the device.
        _mk(client, name="Night mode", tag="speakers", config_source="scenario:night-mode")
        registry.set_active_scenario("cam-1", "night-mode")
        blocked = _mk(client, name="Day demo", tag="speakers")

        res = client.get(f"/demos/{blocked['id']}")
        assert res.status_code == 200
        # Names the demo, not just the scenario string — that's the actionable bit.
        assert "Night mode" in res.text
        assert "end that demo to reclaim it" in res.text.lower()

    def test_detail_404(self, client):
        assert client.get("/demos/nope").status_code == 404


class TestFragmentCapture:
    """ADR-0047 slice 1 — 'Assign to demo' from the drift diff."""

    @pytest.fixture
    def fake_drift(self, monkeypatch):
        """check_drift returns a synthetic report: one assignable param field,
        one not-in-baseline field, and one snapshot-only-facet field."""
        from admz.snapshot.models import DriftField, DriftReport

        async def _fake(self, device_id, baseline_sha=None, family="vapix"):
            return DriftReport(device_id=device_id, has_drift=True, fields=[
                DriftField(facet="other", path="Motion.M0.Enabled",
                           expected="no", actual="yes",
                           canonical_key="root.Motion.M0.Enabled"),
                DriftField(facet="other", path="Brand.New.Key",
                           expected="<missing>", actual="x",
                           canonical_key="root.Brand.New.Key"),
                DriftField(facet="action_rules", path="rules.0.name",
                           expected="a", actual="b",
                           canonical_key="action_rules:rules.0.name"),
            ])

        from admz.snapshot.drift import DriftDetector
        monkeypatch.setattr(DriftDetector, "check_drift", _fake)

    def test_assign_captures_live_values_and_skips_unwritable(
            self, client, registry, fake_drift):
        _add_device(registry, "cam-1", tags=["speakers"])
        demo = _mk(client, name="Frag demo", tag="speakers")
        res = client.post(f"/api/demos/{demo['id']}/fragment", json={
            "fields": [
                {"device_id": "cam-1", "facet": "other", "path": "Motion.M0.Enabled"},
                {"device_id": "cam-1", "facet": "other", "path": "Brand.New.Key"},
                {"device_id": "cam-1", "facet": "action_rules", "path": "rules.0.name"},
                {"device_id": "cam-1", "facet": "other", "path": "Never.Drifted"},
            ],
        })
        assert res.status_code == 200, res.text
        data = res.json()
        # The one writable, in-baseline, actually-drifted field made it in —
        # with the LIVE value (the operator configured the device for the demo).
        assert [a["path"] for a in data["added"]] == ["Motion.M0.Enabled"]
        assert data["added"][0]["value"] == "yes"
        reasons = {s["path"]: s["reason"] for s in data["skipped"]}
        assert reasons["Brand.New.Key"] == "not-in-baseline"
        assert reasons["rules.0.name"] == "read-only"
        assert reasons["Never.Drifted"] == "not-drifted"
        assert data["commit_sha"]
        # Fragment is now visible on the demo.
        frag = data["fragments"]["default"]["facets"]["other"]["set"]
        assert frag["Motion.M0.Enabled"] == "yes"

    def test_assign_binds_device_and_learns_role(self, client, registry, fake_drift):
        _add_device(registry, "cam-1")
        demo = _mk(client, name="Bind demo", device_ids=[])
        res = client.post(f"/api/demos/{demo['id']}/fragment", json={
            "fields": [{"device_id": "cam-1", "facet": "other",
                        "path": "Motion.M0.Enabled"}],
            "role": "Detector Cam",
        })
        assert res.status_code == 200, res.text
        got = client.get(f"/api/demos/{demo['id']}").json()["demo"]
        assert got["roles"]["cam-1"] == "detector-cam"   # normalized
        assert "cam-1" in got["device_ids"]              # pulled into scope
        assert "detector-cam" in got["fragments"]

    def test_assign_requires_fields(self, client):
        demo = _mk(client, name="Empty")
        assert client.post(f"/api/demos/{demo['id']}/fragment",
                           json={"fields": []}).status_code == 400

    def test_remove_entry_and_empty_state(self, client, registry, fake_drift):
        _add_device(registry, "cam-1", tags=["speakers"])
        demo = _mk(client, name="Rm demo", tag="speakers")
        client.post(f"/api/demos/{demo['id']}/fragment", json={
            "fields": [{"device_id": "cam-1", "facet": "other",
                        "path": "Motion.M0.Enabled"}]})
        res = client.post(f"/api/demos/{demo['id']}/fragment/remove", json={
            "role": "default",
            "entries": [{"facet": "other", "path": "Motion.M0.Enabled"}]})
        assert res.status_code == 200
        assert res.json()["fragments"] == {}

    def test_delete_demo_cleans_up_fragments(self, client, registry, fake_drift):
        import admz.api.main as main_mod
        from admz.demos import fragments as fr

        _add_device(registry, "cam-1", tags=["speakers"])
        demo = _mk(client, name="Del demo", tag="speakers")
        client.post(f"/api/demos/{demo['id']}/fragment", json={
            "fields": [{"device_id": "cam-1", "facet": "other",
                        "path": "Motion.M0.Enabled"}]})
        from admz.api.context import get_context
        git = get_context().git_repo
        assert fr.load_all_fragments(git, demo["id"]) != {}
        assert client.delete(f"/api/demos/{demo['id']}").status_code == 200
        assert fr.load_all_fragments(git, demo["id"]) == {}

    def test_detail_page_shows_owned_config(self, client, registry, fake_drift):
        _add_device(registry, "cam-1", tags=["speakers"])
        demo = _mk(client, name="Page demo", tag="speakers")
        client.post(f"/api/demos/{demo['id']}/fragment", json={
            "fields": [{"device_id": "cam-1", "facet": "other",
                        "path": "Motion.M0.Enabled"}]})
        res = client.get(f"/demos/{demo['id']}")
        assert res.status_code == 200
        assert "Owned config" in res.text
        assert "Motion.M0.Enabled" in res.text
