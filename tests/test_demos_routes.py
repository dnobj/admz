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
    # These tests exercise the CONSOLE-USER flow: a signed-in windows principal
    # clicking the web UI writes directly. The widget-gated (non-interactive)
    # path is covered separately by TestDriftAffectingGate.
    monkeypatch.setattr("admz.demos.gated.is_interactive", lambda p: True)
    from admz.api.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def api_client(isolate_admz_dirs, monkeypatch):
    """Same app, but the caller is NON-interactive (api key / chat) — the
    drift-affecting writes must gate behind the approval widget."""
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")
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


class TestDriftAffectingGate:
    """ADR-0047 policy: assign-fragment + adopt gate behind the approval widget
    for NON-interactive principals (api key / chat). Drives the REAL confirm
    endpoint, so approval executes the registered action executors."""

    @pytest.fixture
    def fake_drift(self, monkeypatch):
        from admz.snapshot.models import DriftField, DriftReport

        async def _fake(self, device_id, baseline_sha=None, family="vapix"):
            return DriftReport(device_id=device_id, has_drift=True, fields=[
                DriftField(facet="other", path="Motion.M0.Enabled",
                           expected="no", actual="yes",
                           canonical_key="root.Motion.M0.Enabled"),
            ])

        from admz.snapshot.drift import DriftDetector
        monkeypatch.setattr(DriftDetector, "check_drift", _fake)

    def _mk_api(self, api_client, **kw):
        body = {"name": "Gated demo", "narrative": ""}
        body.update(kw)
        res = api_client.post("/api/demos", json=body)
        assert res.status_code == 200, res.text
        return res.json()["demo"]

    def test_assign_gates_then_approval_executes(self, api_client, registry,
                                                 fake_drift):
        from admz.demos import fragments as fr
        from admz.api.context import get_context

        _add_device(registry, "cam-1", tags=["speakers"])
        demo = self._mk_api(api_client, tag="speakers")
        res = api_client.post(f"/api/demos/{demo['id']}/fragment", json={
            "fields": [{"device_id": "cam-1", "facet": "other",
                        "path": "Motion.M0.Enabled"}]})
        assert res.status_code == 200
        data = res.json()
        assert data["blocked"] is True and data["confirm_url"]
        # NOT written yet — the widget holds it.
        assert fr.load_all_fragments(get_context().git_repo, demo["id"]) == {}

        # Approve at the real endpoint → the action executor runs the core.
        ok = api_client.post(f"/api/chat/confirm/{data['confirm_token']}",
                             json={})
        assert ok.status_code == 200, ok.text
        outcome = ok.json().get("outcome") or {}
        assert outcome.get("success") is True, ok.json()
        frags = fr.load_all_fragments(get_context().git_repo, demo["id"])
        assert frags["default"]["other"]["set"]["Motion.M0.Enabled"] == "yes"

    def test_adopt_gates_then_approval_executes(self, api_client, registry,
                                                fake_drift):
        _add_device(registry, "cam-1", tags=["speakers"])
        demo = self._mk_api(api_client, tag="speakers")
        res = api_client.post(f"/api/demos/{demo['id']}/adopt")
        assert res.status_code == 200
        data = res.json()
        assert data["blocked"] is True and data["confirm_token"]
        from admz.api.context import get_context
        assert get_context().demo_store.get(demo["id"]).active is False

        ok = api_client.post(f"/api/chat/confirm/{data['confirm_token']}",
                             json={})
        assert ok.status_code == 200, ok.text
        assert get_context().demo_store.get(demo["id"]).active is True

    def test_adopt_apply_time_guard_recheck(self, api_client, registry,
                                            fake_drift):
        # Approve an adopt AFTER a conflicting demo went active — the executor
        # re-runs the guards and fails cleanly instead of slipping through.
        from admz.api.context import get_context
        from admz.demos import fragments as fr

        _add_device(registry, "cam-1", tags=["speakers"])
        a = self._mk_api(api_client, name="Demo A", tag="speakers")
        b = self._mk_api(api_client, name="Demo B", tag="speakers")
        ctx = get_context()
        for d in (a, b):
            demo_obj = ctx.demo_store.get(d["id"])
            fr.add_entries(ctx.git_repo, demo_obj, "default",
                           [{"facet": "other", "path": "Motion.M0.Enabled",
                             "value": "yes"}])

        # Gate B's adopt, then A becomes active before B is approved.
        env = api_client.post(f"/api/demos/{b['id']}/adopt").json()
        assert env["blocked"] is True
        demo_a = ctx.demo_store.get(a["id"])
        demo_a.active = True
        ctx.demo_store.update(demo_a)

        ok = api_client.post(f"/api/chat/confirm/{env['confirm_token']}",
                             json={})
        outcome = ok.json().get("outcome") or {}
        assert outcome.get("success") is False, ok.json()
        assert "Demo A" in (outcome.get("error") or str(outcome))
        assert ctx.demo_store.get(b["id"]).active is False

    def test_deactivate_and_metadata_stay_direct(self, api_client, registry):
        # Only the drift-affecting writes gate — create/update/delete and
        # deactivate answer directly even for non-interactive callers.
        demo = self._mk_api(api_client)
        r = api_client.patch(f"/api/demos/{demo['id']}",
                             json={"narrative": "updated"})
        assert r.status_code == 200 and "blocked" not in r.json()
        r = api_client.post(f"/api/demos/{demo['id']}/deactivate")
        assert r.status_code == 200 and r.json()["success"] is True
        assert api_client.delete(f"/api/demos/{demo['id']}").status_code == 200


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

    def test_adopt_and_deactivate(self, client, registry, fake_drift):
        _add_device(registry, "cam-1", tags=["speakers"])
        demo = _mk(client, name="Adopt demo", tag="speakers")
        client.post(f"/api/demos/{demo['id']}/fragment", json={
            "fields": [{"device_id": "cam-1", "facet": "other",
                        "path": "Motion.M0.Enabled"}]})
        res = client.post(f"/api/demos/{demo['id']}/adopt")
        assert res.status_code == 200, res.text
        assert res.json()["demo"]["active"] is True
        # Idempotent.
        assert client.post(f"/api/demos/{demo['id']}/adopt").status_code == 200
        res = client.post(f"/api/demos/{demo['id']}/deactivate")
        assert res.status_code == 200
        assert res.json()["demo"]["active"] is False

    def test_adopt_conflicts_on_shared_key(self, client, registry, fake_drift):
        # v1 forbids ALL same-key overlap between active demos — even equal
        # values — so deactivation is trivially "push base".
        _add_device(registry, "cam-1", tags=["speakers"])
        a = _mk(client, name="Demo A", tag="speakers")
        b = _mk(client, name="Demo B", tag="speakers")
        for d in (a, b):
            client.post(f"/api/demos/{d['id']}/fragment", json={
                "fields": [{"device_id": "cam-1", "facet": "other",
                            "path": "Motion.M0.Enabled"}]})
        assert client.post(f"/api/demos/{a['id']}/adopt").status_code == 200
        res = client.post(f"/api/demos/{b['id']}/adopt")
        assert res.status_code == 409
        assert "Demo A" in res.json()["detail"]

    def test_adopt_blocked_by_legacy_scenario(self, client, registry, fake_drift):
        _add_device(registry, "cam-1", tags=["speakers"])
        demo = _mk(client, name="Legacy blocked", tag="speakers")
        client.post(f"/api/demos/{demo['id']}/fragment", json={
            "fields": [{"device_id": "cam-1", "facet": "other",
                        "path": "Motion.M0.Enabled"}]})
        registry.set_active_scenario("cam-1", "night-mode")
        res = client.post(f"/api/demos/{demo['id']}/adopt")
        assert res.status_code == 409
        assert "night-mode" in res.json()["detail"]

    def test_accept_baseline_guard(self, client, registry, fake_drift):
        # THE trap (ADR-0047 H1): accepting an observation while an active demo
        # owns keys would bake the demo's config into base forever.
        _add_device(registry, "cam-1", tags=["speakers"])
        demo = _mk(client, name="Guard demo", tag="speakers")
        client.post(f"/api/demos/{demo['id']}/fragment", json={
            "fields": [{"device_id": "cam-1", "facet": "other",
                        "path": "Motion.M0.Enabled"}]})
        client.post(f"/api/demos/{demo['id']}/adopt")

        res = client.post("/api/snapshot/accept-baseline",
                          json={"device_id": "cam-1"})
        assert res.status_code == 409
        assert "Guard demo" in res.json()["detail"]

        # Bulk: skip-and-report, not a hard failure.
        res = client.post("/api/snapshot/accept-baseline-bulk",
                          json={"device_ids": ["cam-1"]})
        assert res.status_code == 200
        [skip] = res.json()["skipped"]
        assert skip["reason"] == "active-demo-config"

        # Deactivated -> accept proceeds past the guard (fails later only on
        # no-observation, which is fine — the guard is what we're testing).
        client.post(f"/api/demos/{demo['id']}/deactivate")
        res = client.post("/api/snapshot/accept-baseline",
                          json={"device_id": "cam-1"})
        assert res.status_code != 409

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
