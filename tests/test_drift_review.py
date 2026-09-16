"""ADR-0070 §2 — one review annotator for every drift surface.

The REST route and the MCP tool must show an operator the same annotations,
on the cached path and on the live path. These tests drive both surfaces and
look at what comes back, so removing either call site fails here — the
literal-text checks that used to stand in for this are gone.
"""

from __future__ import annotations

import subprocess

import pytest
from fastapi.testclient import TestClient

from admz.snapshot import review
from admz.snapshot.drift_alerts import DriftAlertStore
from admz.snapshot.models import DriftField, DriftReport
from tests import mcp_harness

DEVICE = "cam-review"

#: Keys every reviewed summary carries, whichever path produced it.
REVIEW_KEYS = {"triage_context", "summary_by_class", "highest_importance",
               "applicable_ignore_rules", "ignore_rule_count"}
#: Keys every reviewed row carries.
ROW_KEYS = {"triage", "revertable", "canonical_key"}


def _report(*, baseline="base1", observed="obs1", fields=None):
    fields = fields if fields is not None else [
        DriftField(facet="image", path="I0.Appearance.Brightness",
                   expected="50", actual="60"),
        DriftField(facet="image", path="I0.MaxResolution",
                   expected="<missing>", actual="3840x2160"),
    ]
    return DriftReport(device_id=DEVICE, has_drift=bool(fields), fields=list(fields),
                       baseline_sha=baseline, observed_sha=observed)


# --------------------------------------------------------------------------- #
# The annotator itself
# --------------------------------------------------------------------------- #
class _Registry:
    def __init__(self, info=None):
        self.info = {"host": "192.0.2.9", "baseline_sha": "base1", **(info or {})}

    def get_device_info(self, device_id):
        return dict(self.info)


@pytest.fixture
def ignore_store(monkeypatch):
    """An in-memory settings store for the ignore rules."""
    import admz.snapshot.ignore as ig
    store = {}
    monkeypatch.setattr(ig, "_fleet_get", lambda k: store.get(k))
    monkeypatch.setattr(ig, "_fleet_set", lambda k, v: store.__setitem__(k, v))

    def save(rules):
        import json
        store[ig.RULES_SETTING_KEY] = json.dumps(rules)
    monkeypatch.setattr(ig, "_save_scoped", save)
    return store


class TestAnnotateReview:
    def test_every_layer_lands(self, ignore_store):
        summary = review.annotate_review(
            _report().to_summary(), registry=_Registry(), device_id=DEVICE)
        assert REVIEW_KEYS <= set(summary)
        for fld in summary["drifted_fields"]:
            assert ROW_KEYS <= set(fld)

    def test_triage_reads_the_revertable_flag_set_before_it(self, ignore_store):
        """Revertable runs first. An application's version moving without the
        firmware is read_only only because the facet cannot write it back —
        run triage first and the row reads uncategorized."""
        report = _report(fields=[
            DriftField(facet="image", path="I0.Appearance.Brightness",
                       expected="50", actual="60"),
            DriftField(facet="applications", path="objectanalytics.version",
                       expected="1.2", actual="1.3"),
        ])
        summary = review.annotate_review(
            report.to_summary(), registry=_Registry(), device_id=DEVICE)
        brightness, app = summary["drifted_fields"]
        assert brightness["revertable"] is True
        assert brightness["canonical_key"] == "root.Image.I0.Appearance.Brightness"
        assert brightness["triage"]["class"] == "service_config"
        assert app["revertable"] is False
        assert app["canonical_key"] == "applications:objectanalytics.version"
        assert app["triage"]["class"] == "read_only"

    def test_the_rules_that_apply_to_this_device(self, ignore_store):
        import admz.snapshot.ignore as ig
        ig.add_rules([
            {"key": "root.A", "scope": "global"},
            {"key": "root.B", "scope": f"device:{DEVICE}"},
            {"key": "root.C", "scope": "device:someone-else"},
            {"key": "root.D", "scope": "tag:lobby"},
        ])
        summary = review.annotate_review(
            _report().to_summary(), registry=_Registry({"tags": ["lobby"]}),
            device_id=DEVICE)
        keys = [r["key"] for r in summary["applicable_ignore_rules"]]
        assert keys == ["root.A", "root.B", "root.D"]
        assert summary["ignore_rule_count"] == 3

    def test_the_rule_list_is_capped_and_the_count_is_not(self, ignore_store):
        import admz.snapshot.ignore as ig
        ig.add_rules([{"key": f"root.K{i}", "scope": "global"} for i in range(25)])
        summary = review.annotate_review(
            _report().to_summary(), registry=_Registry(), device_id=DEVICE)
        assert len(summary["applicable_ignore_rules"]) == review.MAX_REVIEW_IGNORE_RULES
        assert summary["ignore_rule_count"] == 25

    def test_the_firmware_context_is_read_through_the_git_repo(self, ignore_store):
        class Repo:
            def get_file(self, path, ref):
                if path.endswith("device.yaml"):
                    return {"base1": "firmware_version: 12.9.57\n",
                            "obs1": "firmware_version: 12.11.77\n"}.get(ref)
                return None
        summary = review.annotate_review(
            _report().to_summary(), registry=_Registry(), git_repo=Repo(),
            device_id=DEVICE)
        assert summary["triage_context"]["firmware_changed"] is True


# --------------------------------------------------------------------------- #
# The cached report and the revert selection
# --------------------------------------------------------------------------- #
@pytest.fixture
def alerts(tmp_path, monkeypatch):
    from admz.snapshot import drift_alerts as da_module
    store = DriftAlertStore(str(tmp_path / "admz.db"))
    monkeypatch.setattr(da_module, "drift_alerts", store)
    return store


class _Detector:
    def __init__(self, report):
        self.report = report
        self.calls = []

    async def check_drift(self, device_id):
        self.calls.append(device_id)
        return self.report


def _with_buckets():
    fields = [
        DriftField(facet="image", path="I0.A", expected="1", actual="2"),
        DriftField(facet="image", path="I0.B", expected="demo", actual="live",
                   bucket="demo_broken", base_value="base"),
        DriftField(facet="image", path="I0.C", expected="1", actual="9",
                   bucket="demo_set", base_value="1"),
    ]
    return _report(fields=fields)


class TestCachedDriftReport:
    def test_a_cache_for_the_current_baseline_is_served(self, alerts):
        alerts.store_report(_report())
        cached = review.cached_drift_report(_Registry(), DEVICE)
        assert cached["observed_sha"] == "obs1"

    def test_a_cache_for_an_old_baseline_is_not(self, alerts):
        alerts.store_report(_report(baseline="base0"))
        assert review.cached_drift_report(_Registry(), DEVICE) is None

    def test_no_cache(self, alerts):
        assert review.cached_drift_report(_Registry(), DEVICE) is None


class TestRevertFieldsFor:
    @pytest.mark.asyncio
    async def test_the_cached_diff_without_demo_set_and_with_base_value(self, alerts):
        alerts.store_report(_with_buckets())
        detector = _Detector(None)
        fields, not_found = await review.revert_fields_for(
            _Registry(), detector, DEVICE)
        assert [(f.path, f.bucket) for f in fields] == [
            ("I0.A", "unclaimed"), ("I0.B", "demo_broken")]
        assert fields[1].base_value == "base"
        assert not_found == []
        assert detector.calls == []  # served from the cache

    @pytest.mark.asyncio
    async def test_a_live_check_when_nothing_is_cached(self, alerts):
        detector = _Detector(_with_buckets())
        fields, _ = await review.revert_fields_for(_Registry(), detector, DEVICE)
        assert detector.calls == [DEVICE]
        assert [f.path for f in fields] == ["I0.A", "I0.B"]

    @pytest.mark.asyncio
    async def test_a_selection_narrows_and_reports_what_is_not_in_the_diff(
            self, alerts):
        alerts.store_report(_with_buckets())
        fields, not_found = await review.revert_fields_for(
            _Registry(), _Detector(None), DEVICE,
            selected=[("image", "I0.B"), ("image", "I0.Z"), ("image", "I0.B")])
        assert [f.path for f in fields] == ["I0.B"]
        assert not_found == [("image", "I0.Z")]

    @pytest.mark.asyncio
    async def test_a_selected_demo_set_row_is_neither_reverted_nor_not_found(
            self, alerts):
        """It is in the diff — the caller reports it as skipped."""
        alerts.store_report(_with_buckets())
        fields, not_found = await review.revert_fields_for(
            _Registry(), _Detector(None), DEVICE, selected=[("image", "I0.C")])
        assert fields == []
        assert not_found == []


# --------------------------------------------------------------------------- #
# Both surfaces
# --------------------------------------------------------------------------- #
@pytest.fixture
def client(tmp_path, monkeypatch, alerts):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")
    monkeypatch.setenv("ADMZ_AUTO_PUSH", "false")
    from admz.api.main import app
    with TestClient(app, follow_redirects=False) as c:
        from admz.api.context import get_context
        ctx = get_context()
        ctx.registry.add_device(DEVICE, {"host": "192.0.2.9"})
        ctx.registry.set_config_pointers(DEVICE, baseline_sha="base1")
        c.ctx = ctx
        yield c


def _shape(summary):
    return (set(summary) & (REVIEW_KEYS | {"drifted_fields"}),
            [set(f) & ROW_KEYS for f in summary["drifted_fields"]])


class TestRestRoute:
    def test_cached_and_live_carry_the_same_annotations(
            self, client, alerts, monkeypatch):
        alerts.store_report(_report())
        cached = client.get(f"/api/snapshot/drift?device_id={DEVICE}").json()
        assert cached["cached"] is True

        monkeypatch.setattr(client.ctx.drift_detector, "check_drift",
                            _Detector(_report()).check_drift)
        live = client.get(
            f"/api/snapshot/drift?device_id={DEVICE}&refresh=true").json()
        assert live["cached"] is False

        assert _shape(cached) == _shape(live)
        assert REVIEW_KEYS <= set(cached)
        assert [f["triage"]["class"] for f in cached["drifted_fields"]] == [
            "service_config", "added_key"]

    def test_the_annotations_are_not_written_into_the_cache(self, client, alerts):
        alerts.store_report(_report())
        client.get(f"/api/snapshot/drift?device_id={DEVICE}")
        stored = alerts.get_report(DEVICE)["report"]
        assert "triage" not in stored["drifted_fields"][0]
        assert "summary_by_class" not in stored


@pytest.fixture
def mcp_server(tmp_path, monkeypatch, alerts):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    monkeypatch.setenv("ADMZ_PRINCIPAL_NAME", "HOMELAB\\alice")
    monkeypatch.setenv("ADMZ_PRINCIPAL_SOURCE", "windows-local")
    from admz.mcp.server import ADMZMCPServer
    server = ADMZMCPServer()
    repo = str(tmp_path / "config-repo")
    for k, v in [("user.email", "t@t.com"), ("user.name", "T"),
                 ("commit.gpgsign", "false")]:
        subprocess.run(["git", "config", k, v], cwd=repo, check=True)
    server.registry.add_device(DEVICE, {"host": "192.0.2.9"})
    server.registry.set_config_pointers(DEVICE, baseline_sha="base1")
    return server


class TestMcpTool:
    @pytest.mark.asyncio
    async def test_check_drift_carries_the_review(self, mcp_server, monkeypatch):
        monkeypatch.setattr(mcp_server.drift_detector, "check_drift",
                            _Detector(_report()).check_drift)
        result = await mcp_harness.call_tool(
            mcp_server, "check_drift", {"device_id": DEVICE})
        assert result["success"] is True
        assert REVIEW_KEYS <= set(result)
        assert [f["triage"]["class"] for f in result["drifted_fields"]] == [
            "service_config", "added_key"]
        assert [f["revertable"] for f in result["drifted_fields"]] == [True, False]

    @pytest.mark.asyncio
    async def test_the_fleet_form_is_unchanged(self, mcp_server, monkeypatch):
        async def fleet(tag_filter=None):
            return [_report()]
        monkeypatch.setattr(mcp_server.drift_detector, "check_fleet_drift", fleet)
        result = await mcp_harness.call_tool(mcp_server, "check_drift", {})
        assert result["count"] == 1
        assert "triage" not in result["reports"][0]["drifted_fields"][0]
