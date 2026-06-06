"""Tests for the survey validation runner (Tier 0 reads, Tier 1 guard)."""

from pathlib import Path

import pytest

from admz.survey.validate import (
    OpSpec,
    ValidationRunner,
    is_lab_device,
    load_ops_for_apis,
    response_shape,
    run_validation,
)


def test_response_shape_keeps_types_not_values():
    shape = response_shape({"a": 1, "b": "x", "c": {"d": True}, "e": [1, 2]})
    assert shape == {"a": "int", "b": "str", "c": {"d": "bool"}, "e": ["int"]}


def _runner_with_http(responses):
    """responses: dict url-substring -> (status, parsed, latency)."""
    calls = []

    def http(method, url, json=None):
        calls.append((method, url, json))
        for key, resp in responses.items():
            if key in url:
                return resp
        return 404, None, 1.0

    r = ValidationRunner("10.0.0.5", "root", "pw", http=http)
    return r, calls


def test_validate_readonly_config_rest_ok():
    op = OpSpec(op_id="demo:getConfig", method="GET", risk_level="read-only",
                generation="config-rest", base_path="/config/rest/demo/v1", path="")
    r, calls = _runner_with_http({"/config/rest/demo/v1": (200, {"data": {"x": 1}}, 12.0)})
    res = r.validate_readonly(op)
    assert res["ok"] is True
    assert res["http_status"] == 200
    assert res["response_shape"] == {"x": "int"}   # value 1 not leaked
    assert calls[0][0] == "GET"


def test_validate_readonly_jsonrpc_detects_error_envelope():
    op = OpSpec(op_id="x.cgi:getThing", method="POST", risk_level="read-only",
                generation="json-rpc", cgi="x.cgi",
                request={"body": {"apiVersion": "1.0", "method": "getThing"}})
    # json-rpc returns 200 but with an error envelope -> ok must be False
    r, _ = _runner_with_http({"/axis-cgi/x.cgi": (200, {"error": {"code": 2104}}, 5.0)})
    res = r.validate_readonly(op)
    assert res["ok"] is False
    assert res["error_code"] == 2104


def test_run_validation_tier0_only_reads():
    reads = OpSpec("a:get", "GET", "read-only", "config-rest", base_path="/config/rest/a/v1")
    writes = OpSpec("a:set", "PATCH", "service-affecting", "config-rest", base_path="/config/rest/a/v1", path="/x")
    danger = OpSpec("a:reboot", "POST", "dangerous", "config-rest", base_path="/config/rest/a/v1", path="/reboot")
    r, _ = _runner_with_http({"/config/rest/a/v1": (200, {"data": {}}, 1.0)})
    results = run_validation(r, [reads, writes, danger], tier=0, lab=False)
    ids = {x["op_id"] for x in results}
    assert ids == {"a:get"}           # writes not eligible at tier 0; dangerous never


def test_run_validation_tier1_requires_lab_and_optin():
    writes = OpSpec("a:set", "PATCH", "service-affecting", "config-rest",
                    base_path="/config/rest/a/v1", path="/x")
    r, _ = _runner_with_http({})
    # tier 1 but not lab -> not eligible (skipped silently)
    assert run_validation(r, [writes], tier=1, lab=False) == []
    # tier 1 + lab but NOT opted in -> recorded skipped, NEVER executed
    res = run_validation(r, [writes], tier=1, lab=True)
    assert len(res) == 1 and res[0]["skipped"]
    assert res[0]["ok"] is None


def test_run_validation_tier1_write_back_opted_in():
    op = OpSpec("a:set", "PATCH", "service-affecting", "config-rest",
                base_path="/config/rest/a/v1", path="/x")
    # GET returns current value; PATCH echoes 200; readback matches -> ok, no net change
    r, calls = _runner_with_http({"/config/rest/a/v1/x": (200, {"data": True}, 3.0)})
    res = run_validation(r, [op], tier=1, lab=True, write_back_ops=["a:set"])
    assert len(res) == 1 and res[0]["ok"] is True
    assert res[0]["error_code"] is None
    methods = [c[0] for c in calls]
    assert methods == ["GET", "PATCH", "GET"]      # read -> write-back -> read-back
    # the write-back body was the original value, not an injected one
    assert calls[1][2] is True


def test_write_back_skips_jsonrpc():
    op = OpSpec("x.cgi:set", "POST", "service-affecting", "json-rpc", cgi="x.cgi")
    r, _ = _runner_with_http({})
    res = run_validation(r, [op], tier=1, lab=True, write_back_ops=["x.cgi:set"])
    assert res[0]["skipped"] and "config-rest" in res[0]["skipped"]


def test_is_lab_device():
    assert is_lab_device({"tags": ["lab"]})
    assert is_lab_device({"tags": ["prod", "test"]})
    assert is_lab_device({"lab": True})
    assert not is_lab_device({"tags": ["prod"]})
    assert not is_lab_device({})


def test_load_ops_for_apis_from_temp_atlas(tmp_path, monkeypatch):
    # build a tiny atlas data tree
    op_dir = tmp_path / "vapix" / "rest" / "demo" / "v1"
    op_dir.mkdir(parents=True)
    (tmp_path / "vapix" / "rest" / "demo" / "_api.yaml").write_text(
        "generation: config-rest\nendpoint: /config/rest/demo/v1\n", encoding="utf-8")
    (op_dir / "getConfig.yaml").write_text(
        "id: demo:getConfig\ncgi: demo\nmethod: GET\nbase_path: /config/rest/demo/v1\n"
        "path: ''\nrisk_level: read-only\n", encoding="utf-8")
    monkeypatch.setenv("ADMZ_CATALOG_PATH", str(tmp_path))
    ops = load_ops_for_apis(["demo"])
    assert len(ops) == 1
    assert ops[0].op_id == "demo:getConfig"
    assert ops[0].generation == "config-rest"
    # an unrelated api yields nothing
    assert load_ops_for_apis(["other"]) == []
