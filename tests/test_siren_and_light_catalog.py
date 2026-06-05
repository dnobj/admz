"""siren_and_light.cgi catalog ops build VAPIX-correct request bodies.

Regression for the live-testing bug where the catalog modeled `start`
with fabricated flat params (`id`/`profile`/`duration:int`) that don't
match the real JSON-RPC schema, so every flash request the device
rejected. These tests build the actual request body the executor would
POST (no network) and assert it matches the documented VAPIX shape for
both supported forms:

  * instantaneous / "do this now" — explicit siren/light pattern blocks,
    with duration nested as {"unit","value"} (NOT a flat int);
  * saved profile — params:{profile} only;

plus the profile-management ops (getProfiles / addProfile / removeProfile)
and stop's three target forms (all / ids / profile).

Reference: docs/vapix-docs/vapix-network-video-siren-and-light.md
"""

from __future__ import annotations

from pathlib import Path

import pytest

import axis_api_atlas
from axis_api_atlas.catalog.loader import CatalogLoader
from admz.executor.vapix import VapixExecutor


# Catalog data now ships with the axis-api-atlas package (ADR-0029).
CATALOG = axis_api_atlas.default_data_path()


@pytest.fixture(scope="module")
def loader():
    return CatalogLoader(CATALOG)


@pytest.fixture(scope="module")
def ex():
    # build_request is pure (no network / no auth state needed).
    return VapixExecutor.__new__(VapixExecutor)


def _body(loader, ex, op_id, params):
    op = loader.get_operation("vapix", op_id)
    assert op is not None, f"{op_id} missing from catalog"
    return ex.build_request(op.to_executor_dict(), params).json_body


# ---------------------------------------------------------------------------
# start — instantaneous ("do this now") form
# ---------------------------------------------------------------------------


class TestStartInstantaneous:
    def test_flash_white_light_only(self, loader, ex):
        """The exact scenario under test: flash white for 30 seconds."""
        body = _body(loader, ex, "siren_and_light.cgi:start", {
            "light_pattern": "Steady",
            "light_colors": ["white"],
            "light_intensity": 1,
            "light_duration_unit": "seconds",
            "light_duration_value": 30,
        })
        assert body == {
            "apiVersion": "1.0",
            "method": "start",
            "params": {
                "light": {
                    "pattern": "Steady",
                    "colors": ["white"],
                    "intensity": 1,
                    "duration": {"unit": "seconds", "value": 30},
                }
            },
        }

    def test_no_fabricated_top_level_id(self, loader, ex):
        """The old bug: a top-level `id` param that the API never had."""
        body = _body(loader, ex, "siren_and_light.cgi:start", {
            "light_pattern": "Steady",
            "light_colors": ["white"],
        })
        assert "id" not in body["params"]

    def test_duration_is_nested_object_not_flat_int(self, loader, ex):
        """The 'string not integer' symptom traced back to duration being
        modeled as a flat int. It must be the nested {unit,value} object."""
        body = _body(loader, ex, "siren_and_light.cgi:start", {
            "light_pattern": "Steady",
            "light_duration_unit": "seconds",
            "light_duration_value": 30,
        })
        assert not isinstance(body["params"].get("duration"), int)
        assert body["params"]["light"]["duration"] == {
            "unit": "seconds", "value": 30,
        }

    def test_siren_and_light_together(self, loader, ex):
        body = _body(loader, ex, "siren_and_light.cgi:start", {
            "siren_pattern": "Alarm: Horror",
            "siren_intensity": 5,
            "siren_duration_unit": "seconds",
            "siren_duration_value": 30,
            "light_pattern": "Alternate",
            "light_colors": ["blue", "red"],
            "light_intensity": 1,
        })
        assert body["params"]["siren"] == {
            "pattern": "Alarm: Horror",
            "intensity": 5,
            "duration": {"unit": "seconds", "value": 30},
        }
        assert body["params"]["light"] == {
            "pattern": "Alternate",
            "colors": ["blue", "red"],
            "intensity": 1,
        }
        # No profile key when using the explicit form.
        assert "profile" not in body["params"]

    def test_colors_accepts_json_string_too(self, loader, ex):
        """The LLM may pass colors as a real array OR a JSON string; the
        hardened _coerce_value handles both."""
        body = _body(loader, ex, "siren_and_light.cgi:start", {
            "light_pattern": "Steady",
            "light_colors": '["white"]',
            "light_intensity": 1,
        })
        assert body["params"]["light"]["colors"] == ["white"]

    def test_unsupplied_blocks_are_dropped(self, loader, ex):
        """Light-only request must not carry an empty siren block."""
        body = _body(loader, ex, "siren_and_light.cgi:start", {
            "light_pattern": "Steady",
            "light_colors": ["white"],
        })
        assert "siren" not in body["params"]


# ---------------------------------------------------------------------------
# start — saved-profile form
# ---------------------------------------------------------------------------


class TestStartByProfile:
    def test_profile_only(self, loader, ex):
        body = _body(loader, ex, "siren_and_light.cgi:start", {
            "profile": "Trespassing",
        })
        assert body == {
            "apiVersion": "1.0",
            "method": "start",
            "params": {"profile": "Trespassing"},
        }


# ---------------------------------------------------------------------------
# stop — three target forms
# ---------------------------------------------------------------------------


class TestStop:
    def test_stop_all(self, loader, ex):
        body = _body(loader, ex, "siren_and_light.cgi:stop", {
            "all": ["siren", "light"],
        })
        assert body == {
            "apiVersion": "1.0",
            "method": "stop",
            "params": {"all": ["siren", "light"]},
        }

    def test_stop_by_profile(self, loader, ex):
        body = _body(loader, ex, "siren_and_light.cgi:stop", {
            "profile": "Profile 1",
        })
        assert body["params"] == {"profile": "Profile 1"}

    def test_stop_by_ids(self, loader, ex):
        body = _body(loader, ex, "siren_and_light.cgi:stop", {
            "sirenId": 1, "lightId": 2,
        })
        assert body["params"] == {"sirenId": 1, "lightId": 2}


# ---------------------------------------------------------------------------
# profile management
# ---------------------------------------------------------------------------


class TestProfileManagement:
    def test_get_profiles_no_params(self, loader, ex):
        body = _body(loader, ex, "siren_and_light.cgi:getProfiles", {})
        assert body == {"apiVersion": "1.0", "method": "getProfiles"}

    def test_get_profiles_is_read_only(self, loader, ex):
        op = loader.get_operation("vapix", "siren_and_light.cgi:getProfiles")
        assert op.risk_level == "read-only"

    def test_add_profile(self, loader, ex):
        body = _body(loader, ex, "siren_and_light.cgi:addProfile", {
            "name": "White Flash 30s",
            "light_pattern": "Steady",
            "light_colors": ["white"],
            "light_intensity": 1,
            "light_duration_unit": "seconds",
            "light_duration_value": 30,
        })
        assert body["method"] == "addProfile"
        assert body["params"]["name"] == "White Flash 30s"
        assert body["params"]["light"] == {
            "pattern": "Steady",
            "colors": ["white"],
            "intensity": 1,
            "duration": {"unit": "seconds", "value": 30},
        }

    def test_remove_profile(self, loader, ex):
        body = _body(loader, ex, "siren_and_light.cgi:removeProfile", {
            "name": "White Flash 30s",
        })
        assert body == {
            "apiVersion": "1.0",
            "method": "removeProfile",
            "params": {"name": "White Flash 30s"},
        }


# ---------------------------------------------------------------------------
# _coerce_value hardening (native JSON types vs strings)
# ---------------------------------------------------------------------------


class TestCoerceValue:
    def test_array_native_list(self):
        assert VapixExecutor._coerce_value(["white"], "array") == ["white"]

    def test_array_json_string(self):
        assert VapixExecutor._coerce_value('["white"]', "array") == ["white"]

    def test_bool_native(self):
        assert VapixExecutor._coerce_value(True, "bool") is True

    def test_bool_string(self):
        assert VapixExecutor._coerce_value("true", "bool") is True
        assert VapixExecutor._coerce_value("no", "bool") is False

    def test_int_from_int_or_string(self):
        assert VapixExecutor._coerce_value(30, "int") == 30
        assert VapixExecutor._coerce_value("30", "int") == 30
