"""Tests for the drift-alert history surface (FR-DRF-010, issue #23).

The store side (DriftAlertStore.list_alerts) already has unit
coverage in tests/test_drift_alerts.py. This file pins the **read
surface** added in this PR: ``GET /api/drift/alerts`` and the MCP
tool ``get_drift_alerts``.

User-story coverage:
  * US-SCHED-005 (observable outcomes of scheduled jobs) — the
    history must be queryable without going through the DB.
  * US-DM-003 / US-DM-007 — operators need to see what drift has
    been seen, when, and on which device.
"""

from __future__ import annotations

import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient
from tests import mcp_harness


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient over the live FastAPI app with isolated SQLite +
    a fresh DriftAlertStore singleton pointed at the test DB."""
    db_path = tmp_path / "admz.db"
    monkeypatch.setenv("ADMZ_DB_PATH", str(db_path))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")

    # Repoint singletons that captured the prior path at module import.
    from admz import fleet_settings as fs_module
    from admz.api.routes import devices as devices_route
    from admz.api.routes import web as web_route
    from admz.snapshot import drift_alerts as da_module
    _orig_fs = fs_module.fleet_settings
    _orig_devices_fs = devices_route.fleet_settings
    _orig_web_fs = web_route.fleet_settings
    _orig_da = da_module.drift_alerts
    fresh_fs = fs_module.FleetSettings(str(db_path))
    fresh_da = da_module.DriftAlertStore(str(db_path))
    fs_module.fleet_settings = fresh_fs
    devices_route.fleet_settings = fresh_fs
    web_route.fleet_settings = fresh_fs
    da_module.drift_alerts = fresh_da

    # Also repoint the audit singleton so the readback in the audit
    # test sees what the route wrote.
    from admz import audit as audit_module
    fresh_audit = audit_module.AuditLog(db_path=str(db_path))
    monkeypatch.setattr(audit_module, "audit_log", fresh_audit)

    from admz.api.main import app
    try:
        with TestClient(app, follow_redirects=False) as c:
            yield c, fresh_da
    finally:
        fs_module.fleet_settings = _orig_fs
        devices_route.fleet_settings = _orig_devices_fs
        web_route.fleet_settings = _orig_web_fs
        da_module.drift_alerts = _orig_da


def _seed_alerts(store, *rows):
    """Insert synthetic drift_alerts rows directly. ``rows`` are
    tuples of (offset_seconds_ago, device_id, transition, prev, curr,
    sig, summary)."""
    import sqlite3
    # #258: constructing a store no longer creates its schema -- that
    # moved into _connect(). This helper writes with raw sqlite3,
    # bypassing the store, so realise the tables first.
    store._ensure_table()
    conn = sqlite3.connect(store._db_path)
    try:
        now = time.time()
        for offset, device_id, trans, prev, curr, sig, summary in rows:
            conn.execute(
                "INSERT INTO drift_alerts "
                "(timestamp, device_id, transition, previous_count, "
                " current_count, signature, summary) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (now - offset, device_id, trans, prev, curr, sig, summary),
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# REST: GET /api/drift/alerts
# ---------------------------------------------------------------------------


class TestRestDriftAlerts:
    def test_empty_returns_empty_list(self, client):
        c, _ = client
        r = c.get("/api/drift/alerts")
        assert r.status_code == 200
        body = r.json()
        assert body == {"count": 0, "alerts": []}

    def test_returns_seeded_alerts_newest_first(self, client):
        c, store = client
        _seed_alerts(
            store,
            (300, "cam-a", "appeared", 0, 3, "sig-a", "Drift detected: 3 fields"),
            (60, "cam-b", "changed", 3, 5, "sig-b", "Drift changed: 3 → 5 fields"),
            (10, "cam-a", "cleared", 5, 0, "sig-a2", "Drift cleared"),
        )
        body = c.get("/api/drift/alerts").json()
        assert body["count"] == 3
        # Newest first.
        assert body["alerts"][0]["device_id"] == "cam-a"
        assert body["alerts"][0]["transition"] == "cleared"
        assert body["alerts"][1]["device_id"] == "cam-b"
        assert body["alerts"][2]["device_id"] == "cam-a"
        assert body["alerts"][2]["transition"] == "appeared"
        # Timestamp-ISO present (FR-DRF-010 implies a human-readable form).
        assert "timestamp_iso" in body["alerts"][0]

    def test_filter_by_device(self, client):
        c, store = client
        _seed_alerts(
            store,
            (60, "cam-a", "appeared", 0, 1, "x", "a"),
            (50, "cam-b", "appeared", 0, 2, "y", "b"),
        )
        body = c.get("/api/drift/alerts?device_id=cam-a").json()
        assert body["count"] == 1
        assert body["alerts"][0]["device_id"] == "cam-a"

    def test_filter_by_transition(self, client):
        c, store = client
        _seed_alerts(
            store,
            (60, "cam-a", "appeared", 0, 1, "x", "a"),
            (50, "cam-a", "changed", 1, 2, "y", "b"),
            (40, "cam-a", "cleared", 2, 0, "z", "c"),
        )
        body = c.get(
            "/api/drift/alerts?transition=cleared&transition=changed"
        ).json()
        assert body["count"] == 2
        assert {a["transition"] for a in body["alerts"]} == {"changed", "cleared"}

    def test_filter_by_since_iso(self, client):
        c, store = client
        _seed_alerts(
            store,
            (3600, "cam-a", "appeared", 0, 1, "x", "old"),
            (10, "cam-a", "changed", 1, 2, "y", "fresh"),
        )
        from datetime import datetime, timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        # Replace +00:00 with Z to verify our parser accepts both.
        cutoff_z = cutoff.replace("+00:00", "Z")
        body = c.get(f"/api/drift/alerts?since={cutoff_z}").json()
        assert body["count"] == 1
        assert body["alerts"][0]["summary"] == "fresh"

    def test_filter_by_since_unix(self, client):
        c, store = client
        _seed_alerts(
            store,
            (3600, "cam-a", "appeared", 0, 1, "x", "old"),
            (5, "cam-a", "changed", 1, 2, "y", "fresh"),
        )
        cutoff = time.time() - 60
        body = c.get(f"/api/drift/alerts?since={cutoff}").json()
        assert body["count"] == 1
        assert body["alerts"][0]["summary"] == "fresh"

    def test_limit_caps_returned_count(self, client):
        c, store = client
        _seed_alerts(
            store,
            *[(i, f"cam-{i:03d}", "appeared", 0, 1, "s", "x") for i in range(20)],
        )
        body = c.get("/api/drift/alerts?limit=5").json()
        assert body["count"] == 5

    # Validation paths ---------------------------------------------

    def test_invalid_device_id_rejected(self, client):
        c, _ = client
        # CR-5 reuse — path-traversal-shaped IDs refused at the boundary.
        r = c.get("/api/drift/alerts?device_id=../etc/passwd")
        assert r.status_code == 400
        assert "device_id" in r.json()["detail"]

    def test_invalid_transition_rejected(self, client):
        c, _ = client
        r = c.get("/api/drift/alerts?transition=exploded")
        assert r.status_code == 400
        assert "exploded" in r.json()["detail"]

    def test_invalid_since_rejected(self, client):
        c, _ = client
        r = c.get("/api/drift/alerts?since=tomorrow-noon")
        assert r.status_code == 400
        assert "since" in r.json()["detail"]

    def test_limit_clamped_by_fastapi(self, client):
        c, _ = client
        # FastAPI Query(le=1000) — anything above produces 422.
        r = c.get("/api/drift/alerts?limit=99999")
        assert r.status_code == 422

    # Audit path ----------------------------------------------------

    def test_successful_query_is_audited(self, client):
        c, _ = client
        r = c.get("/api/drift/alerts?device_id=cam-a&limit=10")
        assert r.status_code == 200
        from admz import audit as audit_module
        rows = audit_module.audit_log.list_recent(
            action="drift.list_alerts", limit=5,
        )
        assert rows
        assert rows[0].success is True
        assert rows[0].resource == "drift_alerts"
        assert rows[0].details.get("device_id") == "cam-a"

    def test_bad_input_is_audited_as_failure(self, client):
        c, _ = client
        c.get("/api/drift/alerts?device_id=../escape")
        from admz import audit as audit_module
        rows = audit_module.audit_log.list_recent(
            action="drift.list_alerts", limit=5,
        )
        assert rows
        assert rows[0].success is False
        assert "InvalidInput" in rows[0].error_message


# ---------------------------------------------------------------------------
# MCP tool: get_drift_alerts
# ---------------------------------------------------------------------------


@pytest.fixture
def mcp_server(tmp_path, monkeypatch):
    """In-process MCP server pointing at an isolated DB. Repoints the
    drift_alerts singleton so the tool handler reads what we seed."""
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")

    from admz.snapshot import drift_alerts as da_module
    fresh_da = da_module.DriftAlertStore(str(tmp_path / "admz.db"))
    monkeypatch.setattr(da_module, "drift_alerts", fresh_da)

    from admz import audit as audit_module
    fresh_audit = audit_module.AuditLog(db_path=str(tmp_path / "admz.db"))
    monkeypatch.setattr(audit_module, "audit_log", fresh_audit)

    from admz.mcp.server import ADMZMCPServer
    return ADMZMCPServer(), fresh_da


async def _call_tool(server, name: str, arguments: dict):
    return await mcp_harness.call_tool(server, name, arguments)


class TestMcpGetDriftAlerts:
    @pytest.mark.asyncio
    async def test_returns_seeded_alerts(self, mcp_server):
        server, store = mcp_server
        _seed_alerts(
            store,
            (60, "cam-a", "appeared", 0, 3, "x", "a"),
            (10, "cam-a", "cleared", 3, 0, "y", "b"),
        )
        result = await _call_tool(server, "get_drift_alerts", {})
        assert result["success"] is True
        assert result["count"] == 2
        # Newest first.
        assert result["alerts"][0]["transition"] == "cleared"

    @pytest.mark.asyncio
    async def test_filter_by_device(self, mcp_server):
        server, store = mcp_server
        _seed_alerts(
            store,
            (60, "cam-a", "appeared", 0, 1, "x", "a"),
            (50, "cam-b", "appeared", 0, 2, "y", "b"),
        )
        result = await _call_tool(
            server, "get_drift_alerts", {"device_id": "cam-a"},
        )
        assert result["count"] == 1
        assert result["alerts"][0]["device_id"] == "cam-a"

    @pytest.mark.asyncio
    async def test_filter_by_transitions(self, mcp_server):
        server, store = mcp_server
        _seed_alerts(
            store,
            (60, "cam-a", "appeared", 0, 1, "x", "a"),
            (50, "cam-a", "changed", 1, 2, "y", "b"),
            (40, "cam-a", "cleared", 2, 0, "z", "c"),
        )
        result = await _call_tool(
            server, "get_drift_alerts",
            {"transitions": ["cleared"]},
        )
        assert result["count"] == 1
        assert result["alerts"][0]["transition"] == "cleared"

    @pytest.mark.asyncio
    async def test_invalid_transition_rejected(self, mcp_server):
        """The inputSchema's ``enum`` for transitions is enforced before the
        tool handler runs.

        This used to say "enforced by the MCP SDK". That was true under mcp 1.x,
        whose ``@server.call_tool()`` decorator ran
        ``jsonschema.validate(arguments, tool.inputSchema)`` before dispatch.
        mcp 2.x deleted that decorator and validates nothing, so ``call_tool``
        in ``admz/mcp/server.py`` now performs the same check itself rather than
        letting the port drop the gate. The enforcement layer moved; the
        contract asserted here did not.

        The refusal shape did change, deliberately: the SDK emitted bare text,
        ADMZ emits its standard JSON envelope (the chatbot json.loads tool
        output, so plain text was a latent client-side parse failure).

        Scope note, so this is not mistaken for more than it is: ``enum`` is
        *doubly* covered — ``_get_drift_alerts`` validates transitions itself —
        so this test still passes if the schema gate is removed. It pins the
        user-visible contract, not the gate.
        ``test_wrong_type_rejected_before_the_handler`` below is the one that
        fails when the gate goes.
        """
        server, _ = mcp_server
        result = await _call_tool(
            server, "get_drift_alerts", {"transitions": ["exploded"]},
        )
        assert result["error"] == "InvalidInput"
        assert "exploded" in result["message"]
        assert "appeared" in result["message"]  # the allowed values are surfaced

    @pytest.mark.asyncio
    async def test_wrong_type_rejected_before_the_handler(self, mcp_server):
        """A string where the schema demands an array is refused, not iterated.

        Regression guard for what the mcp 2.x port nearly let through. The
        handler's own transition check iterates whatever it is given, so a bare
        string degrades into its characters — passing ``"cleared"`` yielded
        "Unknown transition(s): ['c', 'l', 'e', ...]". Under 1.x the SDK's
        schema validation meant the handler never saw a non-array; nothing but
        this schema gate stands between the two now.
        """
        server, _ = mcp_server
        result = await _call_tool(
            server, "get_drift_alerts", {"transitions": "cleared"},
        )
        assert result["error"] == "InvalidInput"
        assert "array" in result["message"]

    @pytest.mark.asyncio
    async def test_invalid_since_returns_invalid_input(self, mcp_server):
        server, _ = mcp_server
        result = await _call_tool(
            server, "get_drift_alerts", {"since": "yesterday"},
        )
        assert result.get("error") == "InvalidInput"

    @pytest.mark.asyncio
    async def test_invalid_device_id_blocked_by_dispatcher(self, mcp_server):
        server, _ = mcp_server
        # CR-5 validator at the call_tool layer should refuse before
        # we ever reach _get_drift_alerts.
        result = await _call_tool(
            server, "get_drift_alerts",
            {"device_id": "../escape"},
        )
        assert result.get("error") == "InvalidInput"

    @pytest.mark.asyncio
    async def test_limit_works(self, mcp_server):
        server, store = mcp_server
        _seed_alerts(
            store,
            *[(i, f"cam-{i:03d}", "appeared", 0, 1, "s", "x") for i in range(10)],
        )
        result = await _call_tool(
            server, "get_drift_alerts", {"limit": 3},
        )
        assert result["count"] == 3
