"""Tags as the device-grouping primitive in the web UI (ADR-0032).

Covers:
  * build_nav produces nav.tags (per-tag device counts for the active
    site, exact membership) + an Untagged pseudo-row only when untagged
    devices exist; nav.active_tag mirrors ?tag=.
  * /devices?tag=<t> filters the fleet table; the reserved value
    `untagged` selects devices with no tags.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest


# ---------------------------------------------------------------------------
# build_nav (unit)
# ---------------------------------------------------------------------------


class _FakeReq:
    def __init__(self, query=None, cookies=None):
        self.query_params = query or {}
        self.cookies = cookies or {}
        self.state = SimpleNamespace()


class _FakeRegistry:
    def __init__(self, devices):
        self._devices = devices

    def list_organizations(self):
        return [{"org_id": "default", "name": "Default Organization"}]

    def list_sites(self, org_id=None):
        return [{"site_id": "default", "name": "Default Site", "metadata": {}}]

    def list_devices(self):
        return [dict(d) for d in self._devices]

    def get_device_org_site(self, device_id):
        return {"org_id": "default", "site_id": "default"}


@pytest.fixture
def nav_registry(monkeypatch):
    devices = [
        {"device_id": "cam-1", "tags": ["lab", "camera"]},
        {"device_id": "cam-2", "tags": ["lab"]},
        {"device_id": "spk-1", "tags": []},
    ]
    fake = _FakeRegistry(devices)
    import admz.api.templating as templating
    monkeypatch.setattr(templating, "_registry", lambda: fake)
    return fake


class TestBuildNavTags:
    def test_tag_counts_and_untagged_row(self, nav_registry):
        from admz.api.templating import build_nav
        nav = build_nav(_FakeReq())
        tags = {t["id"]: t["count"] for t in nav["tags"]}
        assert tags == {"lab": 2, "camera": 1, "untagged": 1}

    def test_no_untagged_row_when_all_tagged(self, monkeypatch):
        import admz.api.templating as templating
        fake = _FakeRegistry([{"device_id": "cam-1", "tags": ["lab"]}])
        monkeypatch.setattr(templating, "_registry", lambda: fake)
        from admz.api.templating import build_nav
        nav = build_nav(_FakeReq())
        assert [t["id"] for t in nav["tags"]] == ["lab"]

    def test_active_tag_from_query(self, nav_registry):
        from admz.api.templating import build_nav
        nav = build_nav(_FakeReq(query={"tag": "lab"}))
        assert nav["active_tag"] == "lab"
        # No group concepts in the nav anymore.
        assert "groups" not in nav
        assert "active_group" not in nav


# ---------------------------------------------------------------------------
# /devices?tag= (route)
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    from fastapi.testclient import TestClient
    from admz.api.main import app
    import admz.api.main as main_module
    from admz.backends.sqlite_backend import SQLiteDeviceRegistry

    fresh = SQLiteDeviceRegistry(
        db_path=str(tmp_path / "admz.db"),
        key_path=str(tmp_path / "admz.key"),
    )
    monkeypatch.setattr(main_module, "registry", fresh)
    import admz.api.templating as templating
    monkeypatch.setattr(templating, "_registry", lambda: fresh)

    fresh.add_device("cam-lab", {"host": "10.0.0.1", "nickname": "LabCam",
                                 "tags": ["lab"]})
    fresh.add_device("cam-bare", {"host": "10.0.0.2", "nickname": "BareCam"})

    with TestClient(app) as c:
        yield c


class TestDevicesTagFilter:
    def test_filter_by_tag(self, client):
        resp = client.get("/devices?tag=lab")
        assert resp.status_code == 200
        assert "LabCam" in resp.text
        assert "BareCam" not in resp.text

    def test_untagged_reserved_value(self, client):
        resp = client.get("/devices?tag=untagged")
        assert resp.status_code == 200
        assert "BareCam" in resp.text
        assert "LabCam" not in resp.text

    def test_no_filter_shows_all(self, client):
        resp = client.get("/devices")
        assert resp.status_code == 200
        assert "LabCam" in resp.text
        assert "BareCam" in resp.text
