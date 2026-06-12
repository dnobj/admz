"""Moving a device between sites + the restyled edit page (ADR-0032).

A device always belongs to exactly one Site, so "remove from a site" =
reassign to another. The owning Org is derived from the target Site.
Removing a device from ADMZ entirely is `DELETE /api/devices/{id}`.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from admz.auth import AuthBackend, NoAuth, Principal, set_active_backend


@pytest.fixture
def client(tmp_path, monkeypatch):
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

    # Repoint the audit singleton at the tmp DB (it binds to whatever
    # ADMZ_DB_PATH was at import time; full-suite ordering varies it).
    from admz import audit as audit_module
    monkeypatch.setattr(
        audit_module, "audit_log",
        audit_module.AuditLog(db_path=str(tmp_path / "admz.db")),
    )

    # Two sites under one org; device starts at site-a.
    reg.add_organization("org-a", "Org A", "/tmp/org-a")
    reg.add_site("site-a", "org-a", "Site A")
    reg.add_site("site-b", "org-a", "Site B")
    reg.add_device("cam-1", {"host": "10.0.0.1", "nickname": "Cam1", "tags": ["lab"]})
    reg.set_device_org_site("cam-1", "org-a", "site-a")

    # Authenticated admin (the move endpoint requires it).
    class _Stub(AuthBackend):
        async def authenticate(self, request):
            return Principal(
                name="AXIS\\admin", display_name="admin", source="windows",
                groups=["Administrators"], is_anonymous=False,
            )
    set_active_backend(_Stub())
    try:
        with TestClient(main_module.app) as c:
            yield c, reg
    finally:
        set_active_backend(NoAuth())


class TestMoveDeviceSite:
    def test_move_reassigns_org_and_site(self, client):
        c, reg = client
        r = c.put("/api/devices/cam-1/site", json={"site_id": "site-b"})
        assert r.status_code == 200
        assert r.json()["site_id"] == "site-b"
        assert reg.get_device_org_site("cam-1") == {
            "org_id": "org-a", "site_id": "site-b",
        }

    def test_unknown_site_404(self, client):
        c, _ = client
        r = c.put("/api/devices/cam-1/site", json={"site_id": "nope"})
        assert r.status_code == 404

    def test_unknown_device_404(self, client):
        c, _ = client
        r = c.put("/api/devices/ghost/site", json={"site_id": "site-b"})
        assert r.status_code == 404

    def test_move_audited(self, client):
        c, _ = client
        c.put("/api/devices/cam-1/site", json={"site_id": "site-b"})
        from admz import audit as audit_module
        rows = audit_module.audit_log.list_recent(action="device.move_site", limit=5)
        assert any(e.success and e.details.get("site_id") == "site-b" for e in rows)


class TestEditPageRenders:
    def test_edit_page_has_site_options_and_tag_data(self, client):
        c, _ = client
        body = c.get("/device/cam-1/edit").text
        # Styled (Axis Signal) — card layout, not the old raw form.
        assert "card-header" in body
        assert "Save changes" in body
        # Site selector with both sites; current one preselected.
        assert 'id="site_id"' in body
        assert "Site A" in body and "Site B" in body
        # Tag chips are seeded from the device's tags (client-side JS).
        assert "tag-chips" in body
        assert "lab" in body
