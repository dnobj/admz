"""Replace-hardware rebind (ADR-0036): point a stable slot at a new unit,
re-probe its facts, keep device_id so config/baseline follow.
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

    # Slot whose device_id is the FIRST unit's MAC, with a blessed baseline.
    reg.add_device("B8A44F0C5B32", {
        "host": "192.0.2.1", "nickname": "Slot1",
        "model": "OLD-MODEL", "firmware_version": "1.0",
    })
    reg.set_config_pointers("B8A44F0C5B32", baseline_sha="abc123")

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


def _mock_probe(monkeypatch, *, success=True, props=None):
    from admz import operations
    from admz.executor.models import StepResult

    async def fake_tail(*, device_id, operation_id, family, params,
                        catalog, registry, executors):
        return StepResult(
            operation_id=operation_id, device_id=device_id, success=success,
            parsed_data={"data": {"propertyList": props or {}}},
        )
    monkeypatch.setattr(operations, "run_execution_tail", fake_tail)


class TestReplaceHardware:
    def test_rebind_keeps_device_id_updates_unit(self, web):
        c, reg, monkeypatch = web
        _mock_probe(monkeypatch, props={
            "ProdNbr": "NEW-MODEL",
            "SerialNumber": "ACCC8EE6E7EE",
            "Version": "12.5.0",
        })
        r = c.post("/api/devices/B8A44F0C5B32/replace-hardware",
                   json={"host": "192.0.2.99"})
        assert r.status_code == 200
        body = r.json()
        assert body["rebound"] is True
        assert body["has_baseline"] is True   # baseline follows the slot
        # device_id (the slot) is unchanged; unit attributes are the new unit.
        info = reg.get_device_info("B8A44F0C5B32")
        assert info["host"] == "192.0.2.99"
        assert info["model"] == "NEW-MODEL"
        assert info["serial_number"] == "ACCC8EE6E7EE"
        assert info["firmware_version"] == "12.5.0"
        assert info["mac_address"] == "ACCC8EE6E7EE"  # new unit's MAC (from serial)
        assert info["baseline_sha"] == "abc123"        # baseline untouched

    def test_unreachable_new_unit_points_host_but_flags_failure(self, web):
        c, reg, monkeypatch = web
        _mock_probe(monkeypatch, success=False)
        r = c.post("/api/devices/B8A44F0C5B32/replace-hardware",
                   json={"host": "192.0.2.99"})
        assert r.status_code == 200
        body = r.json()
        assert body["rebound"] is False
        assert body["has_baseline"] is True
        # Host was pointed at the new unit, but the stale facts are unchanged.
        info = reg.get_device_info("B8A44F0C5B32")
        assert info["host"] == "192.0.2.99"
        assert info["model"] == "OLD-MODEL"

    def test_unknown_slot_404(self, web):
        c, _, monkeypatch = web
        _mock_probe(monkeypatch, props={"ProdNbr": "x"})
        r = c.post("/api/devices/ghost/replace-hardware", json={"host": "192.0.2.99"})
        assert r.status_code == 404

    def test_audited(self, web):
        c, _, monkeypatch = web
        _mock_probe(monkeypatch, props={"ProdNbr": "NEW", "SerialNumber": "ACCC8EE6E7EE"})
        c.post("/api/devices/B8A44F0C5B32/replace-hardware", json={"host": "192.0.2.99"})
        from admz import audit as audit_module
        rows = audit_module.audit_log.list_recent(action="device.replace_hardware", limit=5)
        assert any(e.success for e in rows)

    def test_ui_button_enabled(self, web):
        c, _, _ = web
        body = c.get("/device/B8A44F0C5B32").text
        assert 'id="replace-hw-btn"' in body
        assert "disabled" not in body.split("replace-hw-btn")[1][:40]
        assert "replace-hw-panel" in body
