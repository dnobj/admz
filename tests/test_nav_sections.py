"""Data-driven sidebar sections (ADR-0038, nav decision 2026-06-19).

The sidebar is now a list of sections rendered by base.html:
  * Core — pinned, no header: Console, Devices, Tasks, Audit log, Settings.
  * Tags move UNDER Devices as a child sub-nav (no standalone "Tags" section).
  * Module sections (PR2+) are divider-separated with a header; none in PR1.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


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
    import admz.api.templating as templating
    monkeypatch.setattr(templating, "_registry", lambda: _FakeRegistry(devices))


def _core(nav):
    return nav["sections"][0]


class TestNavSections:
    def test_core_is_pinned_first_with_fixed_order(self, nav_registry):
        from admz.api.templating import build_nav

        nav = build_nav(_FakeReq())
        core = _core(nav)
        assert core["id"] == "core"
        assert core["title"] == ""  # no header / divider above Core
        assert [it["key"] for it in core["items"]] == [
            "console", "fleet", "tasks", "auditlog", "settings",
        ]

    def test_console_is_accent(self, nav_registry):
        from admz.api.templating import build_nav

        console = _core(build_nav(_FakeReq()))["items"][0]
        assert console["key"] == "console"
        assert console["accent"] is True

    def test_tags_are_children_of_devices_not_a_section(self, nav_registry):
        from admz.api.templating import build_nav

        nav = build_nav(_FakeReq())
        # No standalone titled "Tags" section — only Core in PR1.
        assert all(s["title"] != "Tags" for s in nav["sections"])
        assert [s["id"] for s in nav["sections"]] == ["core"]

        devices = next(it for it in _core(nav)["items"] if it["key"] == "fleet")
        labels = [c["label"] for c in devices["children"]]
        assert labels[0] == "All devices"
        assert set(labels[1:]) == {"camera", "lab", "Untagged"}
        # Device badge mirrors the active site's device count.
        assert devices["badge"] == 3

    def test_child_tag_attr_drives_active_state(self, nav_registry):
        from admz.api.templating import build_nav

        devices = next(
            it for it in _core(build_nav(_FakeReq()))["items"] if it["key"] == "fleet"
        )
        children = {c["label"]: c for c in devices["children"]}
        # "All devices" has tag=None so it matches when no ?tag is selected.
        assert children["All devices"]["tag"] is None
        assert children["lab"]["tag"] == "lab"
        assert children["Untagged"]["tag"] == "untagged"
        # Each child also carries its own active key (the device page key).
        assert all(c["key"] == "fleet" for c in devices["children"])

    def test_no_site_means_no_device_children(self, monkeypatch):
        import admz.api.templating as templating

        # An empty fleet → active_site present but zero devices still yields a
        # site; simulate "no hierarchy" by making list_organizations raise.
        class _NoHierReg:
            def list_organizations(self):
                raise NotImplementedError

        monkeypatch.setattr(templating, "_registry", lambda: _NoHierReg())
        from admz.api.templating import build_nav

        nav = build_nav(_FakeReq())
        devices = next(
            it for it in _core(nav)["items"] if it["key"] == "fleet"
        )
        assert devices["children"] == []
        assert devices["badge"] is None
