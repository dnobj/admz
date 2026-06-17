"""Read-only REST endpoint coverage (deterministic, no Gemini cost).

The endpoints the MCP tools + UI lean on for inventory, health, and drift. Just
contract checks: 200 + the expected top-level keys. Tolerant of an empty fleet.
"""

from __future__ import annotations


def test_devices_list(api):
    r = api("GET", "/api/devices")
    assert r.status_code == 200, r.text
    data = r.json()
    devices = data if isinstance(data, list) else data.get("devices", [])
    assert isinstance(devices, list)
    if devices:
        assert all(isinstance(d, dict) and "device_id" in d for d in devices)


def test_fleet_health(api):
    r = api("GET", "/api/fleet/health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "devices" in body
    for d in body.get("devices", []):
        assert "device_id" in d and "status" in d


def test_fleet_drift_summary(api):
    r = api("GET", "/api/snapshot/drift")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "count" in body and "drifted" in body and "reports" in body


def test_fleet_drift_status_endpoint(api):
    # The shared drift-status endpoint the roster badges use.
    r = api("GET", "/api/fleet/drift")
    assert r.status_code == 200, r.text


def test_ignore_rules_list(api):
    r = api("GET", "/api/config/ignore-rules")
    assert r.status_code == 200, r.text
    assert isinstance(r.json().get("rules"), list)


def test_catalog_query_contract(api):
    r = api("POST", "/api/catalog/query",
            json={"device_id": "E2E-PROBE", "intent": "reboot the device",
                  "family": "vapix"})
    assert r.status_code == 200, r.text
    body = r.json()
    # the contract the chatbot + UI rely on
    for key in ("operations", "parameter_groups", "risk_summary", "notes"):
        assert key in body
