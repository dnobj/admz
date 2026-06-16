"""REST-level E2E for the config-tracking features added in the drift /
targeted-revert / scoped-exclude / ACAP work — exercised against the LIVE
server + real devices, but WITHOUT the chatbot (deterministic, no Gemini cost,
fast).

Covers:
  * ``/api/config/ignore-rules``  — scoped add / list / remove + validation
  * ``/api/snapshot/drift``        — canonical_key + revertable annotation shape
  * ``/api/snapshot/revert``       — targeted revert path (gated plan or in-sync)
  * ``/api/catalog/execute``       — ACAP applications-list.cgi:list run-state

Auth-aware via the ``api`` fixture (Bearer dev key when the deployment enforces
auth — ADR-0033 windows-local). Device-discovering + tolerant: skips cleanly
when the fleet is empty, a device is unreachable, or no API key is configured.
"""

from __future__ import annotations

import pytest


def _first_device(api):
    r = api("GET", "/api/devices")
    if r.status_code != 200:
        return None
    data = r.json()
    devices = data if isinstance(data, list) else data.get("devices", [])
    ids = [
        d.get("device_id")
        for d in devices
        if isinstance(d, dict) and d.get("device_id")
    ]
    return ids[0] if ids else None


def _require_authed(r):
    """Endpoints that change config / fleet state require an authenticated
    principal. Skip (don't fail) when no usable API key is configured."""
    if r.status_code in (401, 403):
        pytest.skip(
            "endpoint needs an authenticated principal — set ADMZ_E2E_API_KEY "
            "or ADMZ_DEV_API_KEY (or have ~/.admz/dev-api-key.txt)."
        )


# Namespaced so a failed cleanup never collides with real config; the scopes
# reference non-existent devices/tags so a stray rule can never match a live
# device.
_E2E_KEY = "root.__admz_e2e_marker__.Field"
_E2E_SCOPE = "device:__admz_e2e_nonexistent__"


class TestIgnoreRulesRest:
    def test_add_list_remove_scoped(self, api):
        try:
            r = api("POST", "/api/config/ignore-rules",
                    json={"add": [{"key": _E2E_KEY, "scope": _E2E_SCOPE}]})
            _require_authed(r)
            assert r.status_code == 200, r.text
            keys = {(x["key"], x["scope"]) for x in r.json()["rules"]}
            assert (_E2E_KEY, _E2E_SCOPE) in keys

            g = api("GET", "/api/config/ignore-rules")
            assert g.status_code == 200
            assert any(x["key"] == _E2E_KEY for x in g.json()["rules"])
        finally:
            rm = api("POST", "/api/config/ignore-rules",
                     json={"remove": [{"key": _E2E_KEY, "scope": _E2E_SCOPE}]})
            if rm.status_code == 200:
                assert (_E2E_KEY, _E2E_SCOPE) not in {
                    (x["key"], x["scope"]) for x in rm.json()["rules"]}

    def test_all_scope_forms_accepted(self, api):
        for scope in ("global", "tag:__admz_e2e__", "device:__admz_e2e__"):
            r = api("POST", "/api/config/ignore-rules",
                    json={"add": [{"key": _E2E_KEY, "scope": scope}]})
            _require_authed(r)
            assert r.status_code == 200, (scope, r.text)
            api("POST", "/api/config/ignore-rules",
                json={"remove": [{"key": _E2E_KEY, "scope": scope}]})

    def test_bad_scope_rejected(self, api):
        # Pydantic validation (422) happens before auth, so this holds for any
        # principal.
        r = api("POST", "/api/config/ignore-rules",
                json={"add": [{"key": "root.X", "scope": "nonsense"}]})
        assert r.status_code == 422


class TestDriftRest:
    def test_drift_summary_and_annotation(self, api):
        did = _first_device(api)
        if not did:
            pytest.skip("no devices registered")
        r = api("GET", f"/api/snapshot/drift?device_id={did}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "has_drift" in body and "drifted_fields" in body
        # Every drifted field carries the exclude/revert annotations.
        for f in body["drifted_fields"]:
            assert "canonical_key" in f
            assert "revertable" in f


class TestTargetedRevertRest:
    def test_revert_path_gated_or_in_sync(self, api):
        did = _first_device(api)
        if not did:
            pytest.skip("no devices registered")
        r = api("POST", "/api/snapshot/revert", json={"device_ids": [did]})
        _require_authed(r)
        assert r.status_code == 200, r.text
        body = r.json()
        # Either a gated plan (drift present) or a "nothing to revert" message.
        assert body.get("blocked") is True or "message" in body

    def test_empty_field_selection_is_noop(self, api):
        did = _first_device(api)
        if not did:
            pytest.skip("no devices registered")
        r = api("POST", "/api/snapshot/revert",
                json={"device_ids": [did], "fields": []})
        _require_authed(r)
        assert r.status_code == 200, r.text
        body = r.json()
        # Empty selection selects nothing → no gated plan, just a message.
        assert body.get("confirm_url") is None
        assert "message" in body


class TestApplicationsFacetRest:
    def test_acap_list_runstate(self, api):
        did = _first_device(api)
        if not did:
            pytest.skip("no devices registered")
        r = api("POST", "/api/catalog/execute", json={
            "device_id": did,
            "operation_id": "applications-list.cgi:list",
            "family": "vapix",
            "params": {},
        })
        _require_authed(r)
        assert r.status_code == 200, r.text
        body = r.json()
        if not body.get("success"):
            pytest.skip(f"device {did}: ACAP list unavailable (offline / no ACAP)")
        data = body.get("data")
        assert isinstance(data, dict)
        apps = data.get("application")
        if isinstance(apps, dict):
            apps = [apps]
        if apps:
            # Installed apps expose a run-state — the autostart-on-boot signal.
            assert any(("@Status" in a) or ("Status" in a) for a in apps)
