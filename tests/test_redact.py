"""Tests for admz.redact — the shared redaction rules (D-2, review 2026-06-10).

One invariant, one module: chat display, MCP audit, and fleet-settings
masking all delegate here. The concrete bug this closes: the audit
sanitizer didn't recurse into lists, so a password inside a list of
dicts reached the audit log in plaintext.
"""

import pytest

from admz.redact import MASK, is_sensitive_key, redact_structure


class TestIsSensitiveKey:
    @pytest.mark.parametrize("key", [
        "password", "PASSWORD", "default_password", "confirm_password_hash",
        "passwd", "secret", "secret_value", "token", "confirm_token",
        "api_key", "apikey", "gemini_api_key",
        "ssh_key", "fernet_key", "private_key", "keyfile",
        "github_pat", "survey_github_pat", "pat",
    ])
    def test_sensitive(self, key):
        assert is_sensitive_key(key) is True

    @pytest.mark.parametrize("key", [
        "key",            # the bare arg carries a setting NAME, not a secret
        "file_path",      # 'pat' must not substring-match
        "upgrade_path",
        "pattern",
        "device_id", "operation_id", "username", "default_username",
        "host", "intent", "value",
    ])
    def test_not_sensitive(self, key):
        assert is_sensitive_key(key) is False


class TestRedactStructure:
    def test_masks_flat_dict(self):
        out = redact_structure({"username": "u", "password": "hunter2"})
        assert out == {"username": "u", "password": MASK}

    def test_masks_nested_dict(self):
        out = redact_structure({"creds": {"username": "u", "password": "x"}})
        assert out == {"creds": {"username": "u", "password": MASK}}

    def test_masks_dict_inside_list(self):
        """The audit list-recursion hole: a password inside a list of
        dicts must be masked."""
        out = redact_structure({
            "accounts": [
                {"username": "root", "password": "leaked1"},
                {"username": "viewer", "password": "leaked2"},
            ],
        })
        assert out["accounts"][0]["password"] == MASK
        assert out["accounts"][1]["password"] == MASK
        assert out["accounts"][0]["username"] == "root"

    def test_recurses_tuples(self):
        out = redact_structure(({"token": "t"},))
        assert out == [{"token": MASK}]

    def test_leaves_pass_through(self):
        assert redact_structure("plain") == "plain"
        assert redact_structure(42) == 42
        assert redact_structure(None) is None

    def test_depth_guard(self):
        deep = {"a": {"b": {"c": {"d": {"e": {"f": "x"}}}}}}
        out = redact_structure(deep, max_depth=3)
        assert out["a"]["b"]["c"] == {"d": MASK}


class TestCrossSurfaceDelegation:
    """The three surfaces must apply the same rules."""

    def test_audit_sanitizer_masks_password_in_list(self):
        """Regression for the concrete D-2 hole."""
        from admz.mcp.server import _sanitize_tool_args
        out = _sanitize_tool_args({
            "steps": [{"params": {"password": "leaked"}}],
        })
        assert out["steps"][0]["params"]["password"] == MASK

    def test_audit_sanitizer_keeps_old_behavior(self):
        from admz.mcp.server import _sanitize_tool_args
        out = _sanitize_tool_args({"username": "u", "password": "x"})
        assert out == {"username": "u", "password": MASK}
        assert _sanitize_tool_args("plain") == "plain"
        assert _sanitize_tool_args(None) is None

    def test_fleet_settings_delegates(self):
        from admz.fleet_settings import is_sensitive_setting_key
        assert is_sensitive_setting_key("default_password") is True
        assert is_sensitive_setting_key("survey_github_pat") is True
        assert is_sensitive_setting_key("default_username") is False
        # New coverage the old inline rule missed:
        assert is_sensitive_setting_key("gemini_api_key") is True

    def test_chat_display_delegates(self):
        from admz.chatbot import client
        out = client._redact_for_display({
            "password": "x",
            "accounts": [{"password": "y", "username": "u"}],
        })
        assert out["password"] == MASK
        assert out["accounts"][0]["password"] == MASK
        assert out["accounts"][0]["username"] == "u"
