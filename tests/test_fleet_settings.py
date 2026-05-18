"""Tests for fleet_settings helpers and the masking primitives that are
shared between the MCP server and the REST API."""

import pytest

from admz.fleet_settings import (
    FleetSettings,
    is_sensitive_setting_key,
    mask_setting_value,
    mask_settings_for_display,
)


@pytest.fixture
def fs(tmp_path):
    """A FleetSettings instance backed by a temp SQLite file."""
    return FleetSettings(db_path=str(tmp_path / "admz.db"))


class TestIsSensitiveSettingKey:
    def test_password_key_is_sensitive(self):
        assert is_sensitive_setting_key("default_password") is True

    def test_password_substring_is_sensitive(self):
        assert is_sensitive_setting_key("vault_password_alt") is True

    def test_password_case_insensitive(self):
        assert is_sensitive_setting_key("Default_Password") is True
        assert is_sensitive_setting_key("DEFAULT_PASSWORD") is True

    def test_username_is_not_sensitive(self):
        assert is_sensitive_setting_key("default_username") is False

    def test_confirm_level_is_not_sensitive(self):
        assert is_sensitive_setting_key("confirm_level_dangerous") is False


class TestMaskSettingValue:
    def test_short_value_masked_with_length_hint(self):
        masked = mask_setting_value("hi")
        assert "hi" not in masked
        assert "(2 chars)" in masked
        assert masked.startswith("**")

    def test_long_value_capped_at_eight_asterisks(self):
        masked = mask_setting_value("a" * 50)
        # Cap on the asterisk count keeps the mask compact
        assert masked.startswith("*" * 8)
        assert "(50 chars)" in masked

    def test_empty_value(self):
        assert mask_setting_value("") == "(empty)"


class TestMaskSettingsForDisplay:
    def test_masks_only_password_keys(self):
        out = mask_settings_for_display({
            "default_password": "secretpass",
            "default_username": "admin",
            "confirm_level_dangerous": "url_and_password",
        })
        assert "secretpass" not in str(out)
        assert out["default_password"].startswith("*")
        assert out["default_username"] == "admin"
        assert out["confirm_level_dangerous"] == "url_and_password"

    def test_empty_dict_passes_through(self):
        assert mask_settings_for_display({}) == {}


class TestFleetSettings:
    """Sanity tests for the FleetSettings SQLite store itself."""

    def test_set_and_get(self, fs):
        fs.set("key1", "value1")
        assert fs.get("key1") == "value1"

    def test_get_missing_returns_none(self, fs):
        assert fs.get("never_set") is None

    def test_overwrite(self, fs):
        fs.set("k", "v1")
        fs.set("k", "v2")
        assert fs.get("k") == "v2"

    def test_delete_existing(self, fs):
        fs.set("k", "v")
        assert fs.delete("k") is True
        assert fs.get("k") is None

    def test_delete_missing(self, fs):
        assert fs.delete("k") is False

    def test_list_all(self, fs):
        fs.set("b", "2")
        fs.set("a", "1")
        out = fs.list_all()
        assert out == {"a": "1", "b": "2"}
