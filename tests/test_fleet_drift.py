"""Tests for the Fleet drift glance — shared status helper, the
`GET /api/fleet/drift` cache-read endpoint, and Fleet/Configuration
agreement (the de-dup guarantee).

The drift *detail* + transition history live in test_drift_alerts*.py;
this pins the last-known roster signal both views read.
"""

from __future__ import annotations

import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from admz.snapshot.drift_status import (
    DRIFTED,
    IN_SYNC,
    NONE,
    UNCHECKED,
    drift_status_for,
)


# ---------------------------------------------------------------------------
# Pure helper — the four states + freshness passthrough
# ---------------------------------------------------------------------------


class TestDriftStatusFor:
    def test_no_baseline_is_none(self):
        out = drift_status_for({"device_id": "c"}, None)
        assert out == {"state": NONE, "count": 0, "checked_at": None}

    def test_baseline_but_no_signature_is_unchecked(self):
        out = drift_status_for({"baseline_sha": "abc"}, None)
        assert out == {"state": UNCHECKED, "count": 0, "checked_at": None}

    def test_zero_fields_is_in_sync(self):
        out = drift_status_for(
            {"baseline_sha": "abc"},
            {"field_count": 0, "updated_at": 1700.0},
        )
        assert out == {"state": IN_SYNC, "count": 0, "checked_at": 1700.0}

    def test_nonzero_fields_is_drifted_with_count(self):
        out = drift_status_for(
            {"baseline_sha": "abc"},
            {"field_count": 3, "updated_at": 1800.0},
        )
        assert out == {"state": DRIFTED, "count": 3, "checked_at": 1800.0}

    def test_no_baseline_wins_even_with_a_signature(self):
        # Defensive: a stale signature without a blessed baseline must not
        # masquerade as drift state.
        out = drift_status_for({}, {"field_count": 9, "updated_at": 1.0})
        assert out["state"] == NONE


# ---------------------------------------------------------------------------
# GET /api/fleet/drift — pure cache read over the fleet
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient over the real app with an isolated DB, a fresh
    DriftAlertStore singleton, and the `none` auth backend."""
    db_path = tmp_path / "admz.db"
    monkeypatch.setenv("ADMZ_DB_PATH", str(db_path))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")

    from admz.snapshot import drift_alerts as da_module
    fresh_da = da_module.DriftAlertStore(str(db_path))
    monkeypatch.setattr(da_module, "drift_alerts", fresh_da)

    import admz.api.main as main_module
    from admz.backends.sqlite_backend import SQLiteDeviceRegistry
    reg = SQLiteDeviceRegistry(
        db_path=str(db_path), key_path=str(tmp_path / "admz.key"),
    )
    monkeypatch.setattr(main_module, "registry", reg)

    with TestClient(main_module.app, follow_redirects=False) as c:
        yield c, reg, fresh_da


def _set_signature(store, device_id, field_count):
    """Write a drift_signatures row directly (what process_report persists)."""
    conn = sqlite3.connect(store._db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO drift_signatures "
            "(device_id, signature, field_count, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (device_id, f"sig-{device_id}", field_count, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


class TestFleetDriftEndpoint:
    def test_states_and_counts(self, client):
        c, reg, store = client
        # none: no baseline
        reg.add_device("cam-none", {"host": "192.0.2.1"})
        # unchecked: baseline, no signature
        reg.add_device("cam-unchecked", {"host": "192.0.2.2"})
        reg.set_config_pointers("cam-unchecked", baseline_sha="b1")
        # in_sync: baseline + zero-field signature
        reg.add_device("cam-sync", {"host": "192.0.2.3"})
        reg.set_config_pointers("cam-sync", baseline_sha="b2")
        _set_signature(store, "cam-sync", 0)
        # drifted: baseline + non-zero signature
        reg.add_device("cam-drift", {"host": "192.0.2.4"})
        reg.set_config_pointers("cam-drift", baseline_sha="b3")
        _set_signature(store, "cam-drift", 4)

        body = c.get("/api/fleet/drift").json()
        assert body["total"] == 4
        assert body["counts"] == {
            "none": 1, "unchecked": 1, "in_sync": 1, "drifted": 1,
        }
        by_id = {d["device_id"]: d for d in body["devices"]}
        assert by_id["cam-none"]["state"] == "none"
        assert by_id["cam-unchecked"]["state"] == "unchecked"
        assert by_id["cam-sync"]["state"] == "in_sync"
        assert by_id["cam-drift"]["state"] == "drifted"
        assert by_id["cam-drift"]["count"] == 4
        # Freshness stamp present once a check has run, absent otherwise.
        assert by_id["cam-drift"]["checked_at"] is not None
        assert by_id["cam-unchecked"]["checked_at"] is None

    def test_empty_fleet(self, client):
        c, _, _ = client
        body = c.get("/api/fleet/drift").json()
        assert body["total"] == 0
        assert body["counts"]["drifted"] == 0
        assert body["devices"] == []

    def test_fleet_and_devices_page_agree(self, client):
        """The de-dup guarantee: the unified Devices roster and the Fleet
        API derive the same state for the same device from the same source."""
        c, reg, store = client
        reg.add_device("cam-x", {"host": "192.0.2.9"})
        reg.set_config_pointers("cam-x", baseline_sha="bx")
        _set_signature(store, "cam-x", 2)

        api_state = {
            d["device_id"]: d["state"]
            for d in c.get("/api/fleet/drift").json()["devices"]
        }["cam-x"]

        # The Devices roster renders drift server-side from the same helper.
        page = c.get("/devices?filter=drifted").text
        assert api_state == "drifted"
        assert "Drifted (2)" in page

    def test_configuration_redirects_to_devices(self, client):
        """The Configuration page was merged into /devices; the old route
        307-redirects, preserving the query string."""
        c, _, _ = client
        r = c.get("/configuration")
        assert r.status_code == 307
        assert r.headers["location"] == "/devices"
        r2 = c.get("/configuration?filter=drifted")
        assert r2.status_code == 307
        assert r2.headers["location"] == "/devices?filter=drifted"

    def test_device_detail_drift_card_reflects_state(self, client):
        """Regression: the detail page's drift card was a hardcoded
        'No baseline yet' stub; it must now show the real last-known state."""
        c, reg, store = client
        reg.add_device("cam-d", {"host": "192.0.2.20"})
        reg.set_config_pointers("cam-d", baseline_sha="bd")
        _set_signature(store, "cam-d", 5)

        page = c.get("/device/cam-d").text
        assert "Drifted (5 field" in page
        assert "No baseline yet" not in page

    def test_device_detail_no_baseline_still_prompts_snapshot(self, client):
        c, reg, _ = client
        reg.add_device("cam-nb", {"host": "192.0.2.21"})
        page = c.get("/device/cam-nb").text
        assert "No baseline yet" in page
