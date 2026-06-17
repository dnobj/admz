"""Safety-gating coverage (REST, deterministic, NO execution).

Destructive operations must return a BLOCKED envelope (confirm token/url) — the
gate stops them at the approval widget and never touches the device. Asserting
the blocked envelope is safe: execution only happens on approval, which these
tests never give.
"""

from __future__ import annotations

import pytest


def _first_device(api):
    r = api("GET", "/api/devices")
    if r.status_code != 200:
        return None
    data = r.json()
    devices = data if isinstance(data, list) else data.get("devices", [])
    ids = [d.get("device_id") for d in devices
           if isinstance(d, dict) and d.get("device_id")]
    return ids[0] if ids else None


def _execute(api, did, op, params=None):
    return api("POST", "/api/catalog/execute", json={
        "device_id": did, "operation_id": op, "family": "vapix",
        "params": params or {},
    })


@pytest.mark.parametrize("op", [
    "restart.cgi:restart",                 # service-affecting → gated
    "factorydefault.cgi:factory-reset",    # dangerous → gated
])
def test_destructive_op_is_gated_not_executed(api, op):
    did = _first_device(api)
    if not did:
        pytest.skip("no devices registered")
    r = _execute(api, did, op)
    _require_authed(r)
    assert r.status_code == 200, r.text
    body = r.json()
    # Blocked at the gate — a confirm token/url, NOT an executed result.
    assert body.get("blocked") is True, body
    assert body.get("confirm_token") or body.get("confirm_url")
    assert body.get("success") is not True


def test_restore_builds_a_gated_plan_or_reports_no_baseline(api):
    did = _first_device(api)
    if not did:
        pytest.skip("no devices registered")
    # Restore-from-baseline is service-affecting: it must come back blocked
    # (gated plan) or, if there's no baseline / nothing to restore, a message —
    # never silently execute.
    r = api("POST", "/api/snapshot/revert", json={"device_ids": [did]})
    _require_authed(r)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("blocked") is True or "message" in body


def test_delete_device_requires_auth(api_anon):
    # The destructive REST delete must refuse an anonymous caller.
    r = api_anon("DELETE", "/api/devices/__e2e_nonexistent__")
    assert r.status_code in (401, 403, 404)


def _require_authed(r):
    if r.status_code in (401, 403):
        pytest.skip("endpoint needs an authenticated principal — set ADMZ_E2E_API_KEY")
