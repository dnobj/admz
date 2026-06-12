"""Observed device facts (model/serial/firmware) are read-only on the edit
form and refreshed by re-reading the device, not hand-edited.

POST /api/devices/{id}/refresh-info re-probes basicdeviceinfo (with the
device's stored creds, server-side) and writes the result back.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from admz.auth import AuthBackend, NoAuth, Principal, set_active_backend


@pytest.fixture
def web(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    import admz.api.main as main_module
    from admz.backends.sqlite_backend import SQLiteDeviceRegistry
    reg = SQLiteDeviceRegistry(
        db_path=str(tmp_path / "admz.db"), key_path=str(tmp_path / "admz.key"),
    )
    monkeypatch.setattr(main_module, "registry", reg)
    import admz.api.templating as templating
    monkeypatch.setattr(templating, "_registry", lambda: reg)
    from admz import audit as audit_module
    monkeypatch.setattr(
        audit_module, "audit_log",
        audit_module.AuditLog(db_path=str(tmp_path / "admz.db")),
    )

    # Device with stale facts + stored creds.
    reg.add_device("cam-r", {
        "host": "192.0.2.5", "nickname": "CamR",
        "model": "stale-model", "firmware_version": "1.0", "tags": ["lab"],
    })
    reg.add_account("cam-r", "default",
                    {"username": "root", "password": "pw", "account_type": "admin"})

    class _Stub(AuthBackend):
        async def authenticate(self, request):
            return Principal(name="AXIS\\admin", display_name="admin",
                             source="windows", groups=["Administrators"],
                             is_anonymous=False)
    set_active_backend(_Stub())
    try:
        with TestClient(main_module.app) as c:
            yield c, reg, monkeypatch
    finally:
        set_active_backend(NoAuth())


def _mock_exec(monkeypatch, *, success=True, props=None):
    """Mock the executor tail the refresh endpoint runs. ``props`` are the
    basicdeviceinfo properties (ProdNbr/SerialNumber/Version)."""
    from admz import operations
    from admz.executor.models import StepResult

    async def fake_tail(*, device_id, operation_id, family, params,
                        catalog, registry, executors):
        return StepResult(
            operation_id=operation_id, device_id=device_id, success=success,
            parsed_data={"data": {"propertyList": props or {}}},
        )
    monkeypatch.setattr(operations, "run_execution_tail", fake_tail)


class TestRefreshInfo:
    def test_refresh_updates_observed_facts(self, web):
        c, reg, monkeypatch = web
        _mock_exec(monkeypatch, props={
            "ProdNbr": "AXIS P3288-LVE",
            "SerialNumber": "E827251FFB8D",
            "Version": "12.0.1",
        })
        r = c.post("/api/devices/cam-r/refresh-info")
        assert r.status_code == 200
        body = r.json()
        assert body["updated"]["model"] == "AXIS P3288-LVE"
        assert body["updated"]["firmware_version"] == "12.0.1"
        info = reg.get_device_info("cam-r")
        assert info["model"] == "AXIS P3288-LVE"
        assert info["serial_number"] == "E827251FFB8D"
        assert info["firmware_version"] == "12.0.1"

    def test_unreachable_returns_message_no_change(self, web):
        c, reg, monkeypatch = web
        _mock_exec(monkeypatch, success=False)
        r = c.post("/api/devices/cam-r/refresh-info")
        assert r.status_code == 200
        assert r.json()["updated"] == {}
        assert "couldn't read" in r.json()["message"].lower()
        # Stale facts untouched.
        assert reg.get_device_info("cam-r")["model"] == "stale-model"

    def test_unknown_device_404(self, web):
        c, _, monkeypatch = web
        _mock_exec(monkeypatch, props={"ProdNbr": "x"})
        r = c.post("/api/devices/ghost/refresh-info")
        assert r.status_code == 404

    def test_refresh_audited(self, web):
        c, _, monkeypatch = web
        _mock_exec(monkeypatch, props={"ProdNbr": "AXIS P3288-LVE"})
        c.post("/api/devices/cam-r/refresh-info")
        from admz import audit as audit_module
        rows = audit_module.audit_log.list_recent(action="device.refresh_info", limit=5)
        assert any(e.success for e in rows)


class TestEditFormObservedReadOnly:
    def test_observed_facts_are_read_only(self, web):
        c, _, _ = web
        body = c.get("/device/cam-r/edit").text
        # Observed panel present with the values shown read-only.
        assert "Observed · from the device" in body
        assert "Refresh from device" in body
        assert 'id="ob-model"' in body
        # No free-text inputs for the observed facts or location anymore.
        assert 'id="model"' not in body
        assert 'id="firmware_version"' not in body
        assert 'id="serial_number"' not in body
        assert 'id="location"' not in body
        # Operator-owned fields still editable.
        assert 'id="nickname"' in body
        assert 'id="host"' in body
        assert "tag-chips" in body
