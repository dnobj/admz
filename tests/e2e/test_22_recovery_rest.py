"""Factory-defaulted handling + deferred-recovery REST coverage.

Deterministic, no Gemini cost. Covers what PR #70/#71 shipped:

  - ``needs_setup`` is a distinct health state (NOT ``auth_failed``), with a
    ``needs_setup`` bucket in the /api/fleet/health counts.
  - the single-device drift report says ``unreadable_reason: needs_setup`` for a
    factory-defaulted device (instead of false-flagging every baseline field).
  - the recovery queue -> list -> cancel lifecycle.
  - the auth + validation gates on the queue/cancel endpoints.

SAFE BY CONSTRUCTION: the lifecycle test arms + cancels a pending action on an
ONLINE device (whose ``on_needs_setup`` trigger can never match, so nothing ever
fires) and always cancels in a ``finally``. No device is ever mutated.
"""

from __future__ import annotations

import pytest


def _health(api):
    r = api("GET", "/api/fleet/health")
    assert r.status_code == 200, r.text
    return r.json()


def _by_status(api, status):
    return [d for d in _health(api).get("devices", []) if d.get("status") == status]


@pytest.fixture
def online_device(api):
    """A device the health monitor reports ONLINE — safe to arm a recovery on
    because the ``on_needs_setup`` trigger can never match it. Skips if none."""
    online = _by_status(api, "online")
    if not online:
        pytest.skip("no online device to safely arm a recovery on")
    return online[0]["device_id"]


@pytest.fixture
def needs_setup_device(api):
    """A factory-defaulted device id, or None (the homelab Q3538 normally
    supplies this; tests skip when nothing is currently needs_setup)."""
    ns = _by_status(api, "needs_setup")
    return ns[0]["device_id"] if ns else None


# --- needs_setup detection (Slice 1) ---------------------------------------


def test_health_has_needs_setup_count_bucket(api):
    body = _health(api)
    counts = body.get("counts") or {}
    assert "needs_setup" in counts, f"no needs_setup bucket in counts: {counts}"


def test_needs_setup_is_distinct_from_auth_failed(api, needs_setup_device):
    if not needs_setup_device:
        pytest.skip("no needs_setup device in the fleet right now")
    rec = next(d for d in _health(api)["devices"]
               if d["device_id"] == needs_setup_device)
    # The whole point of Slice 1: it is needs_setup, not auth_failed.
    assert rec["status"] == "needs_setup"
    err = (rec.get("last_error") or "").lower()
    assert "factory" in err or "needsetup" in err, (
        f"needs_setup last_error should explain the factory-default state: {err!r}"
    )


def test_drift_reports_needs_setup_reason(api, needs_setup_device):
    if not needs_setup_device:
        pytest.skip("no needs_setup device in the fleet right now")
    r = api("GET", f"/api/snapshot/drift?device_id={needs_setup_device}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("unreadable") is True
    assert body.get("unreadable_reason") == "needs_setup", body


# --- recovery queue -> list -> cancel lifecycle (Slices 2+3) ---------------


def test_queue_list_cancel_lifecycle(api, online_device):
    pid = None
    try:
        r = api("POST", f"/api/devices/{online_device}/recovery",
                json={"intent": "reprovision"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("success") is True and body.get("pending_id"), body
        pid = body["pending_id"]

        # the queued action shows up in the device's pending list
        r = api("GET", f"/api/devices/{online_device}/pending")
        assert r.status_code == 200, r.text
        mine = [p for p in r.json().get("pending", []) if p.get("id") == pid]
        assert mine, f"queued action {pid} not in pending list"
        assert (mine[0].get("action") or {}).get("action") == "reprovision"
        assert mine[0].get("trigger") == "on_needs_setup"
    finally:
        if pid:
            c = api("POST",
                    f"/api/devices/{online_device}/pending/{pid}/cancel")
            assert c.status_code == 200, c.text

    # after cancel it is gone from the active list
    r = api("GET", f"/api/devices/{online_device}/pending")
    assert not [p for p in r.json().get("pending", []) if p.get("id") == pid]


# --- auth + validation gates -----------------------------------------------


def test_queue_requires_authenticated_principal(api_anon, online_device):
    r = api_anon("POST", f"/api/devices/{online_device}/recovery",
                 json={"intent": "reprovision"})
    assert r.status_code in (401, 403), r.text


def test_queue_unknown_device_404(api):
    r = api("POST", "/api/devices/NO-SUCH-DEVICE-XYZ/recovery",
            json={"intent": "reprovision"})
    assert r.status_code == 404, r.text


def test_queue_rejects_non_reprovision_intent(api, online_device):
    # 'remove' is immediate via DELETE, not queueable here -> 400.
    r = api("POST", f"/api/devices/{online_device}/recovery",
            json={"intent": "remove"})
    assert r.status_code == 400, r.text


def test_cancel_unknown_pending_404(api, online_device):
    r = api("POST", f"/api/devices/{online_device}/pending/deadbeefcafe/cancel")
    assert r.status_code == 404, r.text


def test_pending_list_contract(api, a_device):
    if not a_device:
        pytest.skip("no devices registered")
    r = api("GET", f"/api/devices/{a_device}/pending")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "pending" in body and isinstance(body["pending"], list)
