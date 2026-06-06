"""Tests for ADMZ survey/contributor mode (collector, redaction, diff, bundle)."""

import json
from pathlib import Path

import pytest
import yaml

from admz.survey.bundle import DeviceSurvey, assemble_bundle, derive_series
from admz.survey.collector import SurveyCollector
from admz.survey.diff import AtlasIndex, diff_snapshot
from admz.survey.redact import (
    hash_serial,
    is_safe_openapi,
    redact_snapshot,
    redact_validation_result,
)

KEY = b"test-key-0123456789"


# ---------------------------------------------------------------------------
# redaction
# ---------------------------------------------------------------------------


def test_hash_serial_stable_and_irreversible():
    h1 = hash_serial("B8A44F926D2F", KEY)
    h2 = hash_serial("B8A44F926D2F", KEY)
    assert h1 == h2 and h1.startswith("h:")
    assert "B8A44F926D2F" not in h1
    assert hash_serial("OTHER", KEY) != h1


def test_redact_snapshot_hashes_serial_by_default():
    snap = {"firmware": "12.9", "discovered": "2026-06-05", "device_id": "B8A44F926D2F",
            "api_count": 1, "apis": {"demo": "1.0"}, "apis_detail": {"demo": {}}}
    out = redact_snapshot(snap, profile="hash-serial", key=KEY)
    assert out["device_id"].startswith("h:")
    assert "B8A44F926D2F" not in out["device_id"]
    out2 = redact_snapshot(snap, profile="keep-serial", key=KEY)
    assert out2["device_id"] == "B8A44F926D2F"


def test_is_safe_openapi_blocks_model_json_and_param():
    assert is_safe_openapi("demo", "/config/discover/apis/demo/v1/openapi.json")
    assert not is_safe_openapi("demo", "/config/discover/apis/demo/v1/model.json")
    assert not is_safe_openapi("param", "/config/discover/apis/param/v2/openapi.json")


def test_redact_validation_keeps_shape_not_values():
    r = redact_validation_result({
        "op_id": "x:get", "method": "GET", "path": "/x", "http_status": 200,
        "ok": True, "latency_ms": 12, "response_shape": {"a": "int"},
        "secret_value": "leak"})
    assert "secret_value" not in r
    assert r["response_shape"] == {"a": "int"}


# ---------------------------------------------------------------------------
# diff against atlas
# ---------------------------------------------------------------------------


def _make_atlas(tmp: Path):
    (tmp / "capabilities" / "models").mkdir(parents=True)
    (tmp / "vapix" / "rest" / "known-api").mkdir(parents=True)
    (tmp / "vapix" / "cgi" / "known.cgi").mkdir(parents=True)
    (tmp / "capabilities" / "models" / "p1234.yaml").write_text(
        "model: P1234\nsnapshots:\n- firmware: '12.0'\n  apis: {known-api: '1.0'}\n",
        encoding="utf-8")
    return AtlasIndex(data_path=str(tmp))


def test_diff_new_model(tmp_path):
    idx = _make_atlas(tmp_path)
    snap = {"firmware": "12.5", "apis": {"known-api": "1.0"}}
    d = diff_snapshot(snap, model="Z9999-XX", index=idx)
    assert d.new_model and not d.is_empty


def test_diff_new_firmware_and_uncatalogued(tmp_path):
    idx = _make_atlas(tmp_path)
    snap = {"firmware": "12.7", "apis": {"known-api": "1.0", "brand-new-api": "1.0"}}
    d = diff_snapshot(snap, model="P1234", index=idx)
    assert not d.new_model
    assert d.new_firmware
    assert d.uncatalogued_apis == ["brand-new-api"]
    assert "known-api" in d.known_apis


def test_diff_nothing_new(tmp_path):
    idx = _make_atlas(tmp_path)
    snap = {"firmware": "12.0", "apis": {"known-api": "1.0"}}
    d = diff_snapshot(snap, model="P1234", index=idx)
    assert d.is_empty


def test_derive_series():
    assert derive_series("Q9307-LV") == "q93"
    assert derive_series("AXIS M4228-LVE") == "m42"


# ---------------------------------------------------------------------------
# collector + bundle (end to end with fakes)
# ---------------------------------------------------------------------------


class _FakeRegistry:
    def get_credentials(self, device_id, requester=None):
        return {"host": "10.0.0.9", "username": "root", "password": "secretpw"}

    def get_device_info(self, device_id):
        return {"model": "Z9999-XX"}

    def list_devices(self):
        return [{"device_id": "d1"}]


def _fake_snapshot(host, user, password, verify=True, auth="auto"):
    return {
        "model": "Z9999-XX", "firmware": "1.0", "discovered": "2026-06-05",
        "device_id": "B8A44F000000", "api_count": 1,
        "apis": {"demo-rest": "1.0"},
        "apis_detail": {"demo-rest": {"dca": {
            "openapi": "/config/discover/apis/demo-rest/v1/openapi.json",
            "rest_api": "/config/rest/demo-rest/v1beta",
            "major": "v1beta", "state": "beta"}}},
    }


def _fake_spec(host, user, password, verify, path):
    return {"openapi": "3.0.0", "paths": {
        "/demo-rest/v1beta": {"get": {}},
        "/demo-rest/v1beta/profiles": {"get": {}, "post": {}},
        "/demo-rest/v1beta/profiles/{id1}": {"get": {}, "delete": {}},
    }}


def test_collector_surveys_new_device_and_builds_bundle(tmp_path):
    idx = AtlasIndex(data_path=str(tmp_path / "empty_atlas"))
    (tmp_path / "empty_atlas").mkdir()
    collector = SurveyCollector(
        _FakeRegistry(), index=idx,
        snapshot_fn=_fake_snapshot, spec_fetcher=_fake_spec,
        profile="hash-serial")

    survey = collector.survey_device("d1")
    assert survey is not None
    assert survey.model == "Z9999-XX"
    assert survey.new_model
    assert "demo-rest" in survey.openapi_specs
    # serial got hashed in the redacted snapshot
    assert survey.redacted_snapshot["device_id"].startswith("h:")

    root = assemble_bundle(
        tmp_path / "out", [survey],
        profile="hash-serial", contributor="ec-test",
        admz_version="2.0.0", bundle_id="b-test",
        created_utc="2026-06-05T00:00:00Z")

    # bundle structure + content
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["models"] == ["Z9999-XX"]
    assert (root / "capabilities" / "z9999-xx.yaml").is_file()
    assert (root / "openapi" / "demo-rest-v1beta.json").is_file()
    seeded = list((root / "seeded").rglob("*.yaml"))
    names = {p.name for p in seeded}
    assert "_api.yaml" in names
    assert "getConfig.yaml" in names
    assert "listProfiles.yaml" in names    # collection detected
    # the redacted serial must NOT appear anywhere in the bundle
    blob = "\n".join(p.read_text(encoding="utf-8")
                     for p in root.rglob("*") if p.is_file())
    assert "B8A44F000000" not in blob


def test_collector_skips_when_nothing_new(tmp_path):
    # atlas already knows this model+fw+api
    (tmp_path / "capabilities" / "models").mkdir(parents=True)
    (tmp_path / "vapix" / "rest" / "demo-rest").mkdir(parents=True)
    (tmp_path / "capabilities" / "models" / "z9999-xx.yaml").write_text(
        "model: Z9999-XX\nsnapshots:\n- firmware: '1.0'\n  apis: {demo-rest: '1.0'}\n",
        encoding="utf-8")
    idx = AtlasIndex(data_path=str(tmp_path))
    collector = SurveyCollector(
        _FakeRegistry(), index=idx,
        snapshot_fn=_fake_snapshot, spec_fetcher=_fake_spec, profile="hash-serial")
    assert collector.survey_device("d1") is None

    run = collector.survey_fleet(["d1"])
    assert run.surveys == []
    assert "d1" in run.skipped
