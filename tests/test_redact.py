"""Tests for admz.redact — the shared redaction rules (D-2, review 2026-06-10).

One invariant, one module: chat display, MCP audit, and fleet-settings
masking all delegate here. The concrete bug this closes: the audit
sanitizer didn't recurse into lists, so a password inside a list of
dicts reached the audit log in plaintext.
"""

import json

import pytest

from admz.redact import (
    MASK,
    is_sensitive_key,
    redact_structure,
    redact_url,
    sibling_masked_fields,
)
from tests import mcp_harness

SECRET = "hunter2_SECRET_do_not_log"


class TestIsSensitiveKey:
    @pytest.mark.parametrize("key", [
        "password", "PASSWORD", "default_password", "confirm_password_hash",
        "passwd", "secret", "secret_value", "token", "confirm_token",
        "api_key", "apikey", "gemini_api_key",
        "ssh_key", "fernet_key", "private_key", "keyfile",
        "github_pat", "survey_github_pat", "pat",
        # GH #336 — the actual VAPIX wire-query keys that carry a device
        # password: pwdgrp.cgi:add-user/update-user uses `pwd`,
        # networkshare-add.cgi:add uses `pass`.
        "pwd", "PWD", "old_pwd", "new_pwd", "admin.pwd", "admin-pwd",
        "pass", "PASS", "old_pass", "new_pass", "user_pass", "user.pass",
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
        # GH #336 — the false positives a naive substring join of "pass"
        # would have introduced. Each contains "pass" but is not the
        # discrete token: no delimiter separates it from the rest of the
        # word, so it must NOT be masked. This is the exact leak/noise
        # trade #310 already refused for httpx URLs, checked the other way.
        "bypass", "passive", "compass", "passthrough", "surpass",
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


class TestSiblingMaskedFields:
    """#217: sensitivity declared by a sibling, not by the field's own name."""

    def test_sensitive_sibling_selects_value(self):
        assert sibling_masked_fields(
            {"key": "default_password", "value": SECRET}
        ) == frozenset({"value"})

    def test_innocent_sibling_selects_nothing(self):
        assert sibling_masked_fields(
            {"key": "default_username", "value": "root"}
        ) == frozenset()

    def test_name_field_also_qualifies(self):
        """SOAP-style Name/Value, the shape redact_soap_body already handles."""
        assert sibling_masked_fields(
            {"name": "Password", "value": SECRET}
        ) == frozenset({"value"})

    def test_no_value_field_means_nothing_to_mask(self):
        assert sibling_masked_fields({"key": "default_password"}) == frozenset()

    def test_non_mapping_and_non_string_name_are_safe(self):
        assert sibling_masked_fields(None) == frozenset()
        assert sibling_masked_fields(["key", "value"]) == frozenset()
        assert sibling_masked_fields({"key": 42, "value": "x"}) == frozenset()


class TestRedactStructureSiblings:
    def test_the_issue_217_reproduction_now_masks(self):
        """The exact call from #217, which previously passed through intact."""
        out = redact_structure({"key": "default_password", "value": SECRET})
        assert out == {"key": "default_password", "value": MASK}

    def test_key_name_still_visible(self):
        """The `key` exemption is deliberate and preserved: an auditor must
        still be able to answer "which setting was written?"."""
        out = redact_structure({"key": "default_password", "value": SECRET})
        assert out["key"] == "default_password"

    def test_innocent_setting_value_survives(self):
        out = redact_structure({"key": "default_username", "value": "root"})
        assert out == {"key": "default_username", "value": "root"}

    def test_applies_inside_lists_and_nesting(self):
        out = redact_structure(
            {"writes": [{"key": "survey_github_pat", "value": SECRET}]}
        )
        assert out["writes"][0]["value"] == MASK
        assert out["writes"][0]["key"] == "survey_github_pat"


class TestRedactUrl:
    """#157: the shared URL redactor. ``keys=None`` (mask every query value)
    is the fail-closed default; ``keys=<names>`` is the narrower mode kept
    for callers with a closed query vocabulary (admz/modules/acs_pro/firebird.py)."""

    def test_none_and_empty_pass_through(self):
        assert redact_url(None) is None
        assert redact_url("") is None

    def test_plain_url_without_query_is_unchanged(self):
        assert redact_url("https://plain.example/hook") == "https://plain.example/hook"

    def test_userinfo_always_masked_regardless_of_mode(self):
        raw = "https://user:s3cret@admz.local/api/acs/rule-fired"
        expected = "https://***@admz.local/api/acs/rule-fired"
        assert redact_url(raw) == expected
        assert redact_url(raw, keys=("token",)) == expected

    def test_default_mode_masks_every_query_value(self):
        """The fail-closed default: no key list to fall behind, because
        VAPIX callers can inject a query param under any name
        (admz/executor/vapix.py:696-698)."""
        raw = "http://192.168.1.50/axis-cgi/pwdgrp.cgi?action=add&user=admz_tmp&pwd=hunter2&grp=users"
        out = redact_url(raw)
        assert "hunter2" not in out
        assert "admz_tmp" not in out
        assert "add" not in out  # action's value is masked too — the whole point
        assert out == (
            "http://192.168.1.50/axis-cgi/pwdgrp.cgi"
            "?action=%2A%2A%2A&user=%2A%2A%2A&pwd=%2A%2A%2A&grp=%2A%2A%2A"
        )

    def test_keys_mode_masks_only_named_keys(self):
        """The narrower mode: only listed keys are masked, others survive —
        used where the query vocabulary is known and closed."""
        raw = "https://admz.local/hook?rule=Front+Door&apikey=xyz"
        out = redact_url(raw, keys=("apikey", "token"))
        assert out == "https://admz.local/hook?rule=Front+Door&apikey=%2A%2A%2A"

    def test_keys_mode_is_case_insensitive(self):
        raw = "https://admz.local/hook?TOKEN=xyz"
        assert redact_url(raw, keys=("token",)) == "https://admz.local/hook?TOKEN=%2A%2A%2A"

    def test_unparseable_input_fails_closed(self):
        class Unparseable:
            def __str__(self):
                raise ValueError("boom")
        assert redact_url(Unparseable()) == "***"


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

    def test_audit_sanitizer_masks_the_actual_vapix_wire_spellings(self):
        """GH #336, the exact reproduction that opened the issue:
        pwdgrp.cgi:add-user/update-user carry the device password on the
        wire as `pwd`, networkshare-add.cgi:add as `pass` — neither matched
        before this fix, so a device password written through the gated
        catalog path reached the audit log in the clear regardless of the
        (correctly masked) `password` spelling never actually being used on
        the wire for these two operations."""
        from admz.mcp.server import _sanitize_tool_args
        assert _sanitize_tool_args(
            {"params": {"pwd": "hunter2SECRET"}}
        ) == {"params": {"pwd": MASK}}
        assert _sanitize_tool_args(
            {"params": {"pass": "hunter2SECRET"}}
        ) == {"params": {"pass": MASK}}
        # The other direction, in the same surface: an ordinary argument
        # that happens to contain those letters must not be swept up with
        # them, or "we mask secrets" is trivially true for a sanitizer that
        # masks everything.
        assert _sanitize_tool_args(
            {"params": {"bypass": "not-a-secret"}}
        ) == {"params": {"bypass": "not-a-secret"}}

    def test_firebird_redact_url_delegates(self):
        """#157: firebird.py's redact_url is now a thin wrapper over the
        shared implementation, scoped to its own closed key list — the
        existing behavior asserted in test_acs_rule_anatomy.py must survive
        the refactor unchanged."""
        from admz.modules.acs_pro.firebird import redact_url as fb_redact_url
        assert fb_redact_url("https://admz.local/hook?rule=Front+Door&apikey=xyz") == (
            "https://admz.local/hook?rule=Front+Door&apikey=%2A%2A%2A"
        )

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

    def test_chat_display_masks_sibling_declared_value(self):
        """#217: the args card is a display-side twin of redact_structure and
        had the same blindness — it rendered the password to the browser."""
        from admz.chatbot import client
        out = client._redact_for_display(
            {"key": "default_password", "value": SECRET}
        )
        assert out["value"] == MASK
        assert out["key"] == "default_password"


# ---------------------------------------------------------------------------
# #217 end-to-end: the real audit path, not just the redactor
#
# call_tool has THREE audit sites, all recording the same pre-dispatch
# `args_sanitized` (server.py ~1674 invalid-input, ~1717 anonymous-destructive,
# ~1794 finally). A test against redact_structure alone would stay green if a
# wiring change reopened any of them, so each is driven for real here.
# ---------------------------------------------------------------------------


@pytest.fixture
def audited_server(tmp_path, monkeypatch):
    """A real ADMZMCPServer with every DB path inside tmp_path, plus a capture
    list of the audit rows it writes.

    ADMZ_HOME is pinned too: several stores bind their path at import, and a
    writer that escapes tmp_path would write the operator's real database.
    """
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")
    monkeypatch.setenv("ADMZ_PRINCIPAL_NAME", "HOMELAB\\alice")
    monkeypatch.setenv("ADMZ_PRINCIPAL_SOURCE", "windows-local")
    monkeypatch.setenv("ADMZ_PRINCIPAL_GROUPS", "Administrators")

    from admz.audit import audit_log
    from admz.mcp.server import ADMZMCPServer

    rows = []
    monkeypatch.setattr(
        audit_log, "record", lambda **kw: rows.append(kw), raising=True
    )
    return ADMZMCPServer(), rows


async def _drive_call_tool(server, name: str, arguments: dict):
    """Invoke the registered call_tool handler — the real dispatcher,
    including its audit sites."""
    return await mcp_harness.call_tool(server, name, arguments)


def _assert_clean(rows, *, expect_key="default_password"):
    assert len(rows) == 1, f"expected exactly one audit row, got {len(rows)}"
    row = rows[0]
    blob = json.dumps(row, default=str)
    assert SECRET not in blob, f"plaintext secret reached the audit row: {blob}"
    args = row["details"]["args"]
    assert args["value"] == MASK
    # The setting name must survive — that is what makes the row useful.
    assert args["key"] == expect_key
    return row


class TestAuditPathNeverRecordsTheValue:
    @pytest.mark.asyncio
    async def test_finally_site(self, audited_server):
        """The main path: capture-only refusal (#219) still audits the args."""
        server, rows = audited_server
        out = await _drive_call_tool(
            server, "set_fleet_setting",
            {"key": "default_password", "value": SECRET},
        )
        # #219's gate refuses the write...
        assert out["success"] is False
        # ...and #217's rule keeps the refused value out of the durable row.
        row = _assert_clean(rows)
        assert row["success"] is False

    @pytest.mark.asyncio
    async def test_invalid_input_early_return_site(self, audited_server):
        """server.py ~1674 — returns before dispatch, audits independently."""
        server, rows = audited_server
        out = await _drive_call_tool(
            server, "set_fleet_setting",
            {
                "device_id": "../etc/passwd",
                "key": "default_password",
                "value": SECRET,
            },
        )
        assert out["error"] == "InvalidInput"
        _assert_clean(rows)

    @pytest.mark.asyncio
    async def test_anonymous_destructive_early_return_site(
        self, audited_server, monkeypatch
    ):
        """server.py ~1717 — the other pre-dispatch return.

        ``_DESTRUCTIVE_MCP_TOOLS`` is ``frozenset()`` today: ADR-0034 replaced
        the flat anonymous refusal with widget approval, and the mechanism is
        retained empty "in case a future tool is truly unsuitable for widget
        approval" (server.py:216-226). So this site is currently unreachable —
        which is precisely why it is worth pinning. Re-populating that set
        would silently re-open a third audit site, and this test fails if the
        value is not masked when that happens.
        """
        from admz.mcp import server as mcp_server

        server, rows = audited_server
        monkeypatch.setattr(
            mcp_server, "_DESTRUCTIVE_MCP_TOOLS", frozenset({"set_fleet_setting"})
        )
        server.principal.is_anonymous = True
        out = await _drive_call_tool(
            server, "set_fleet_setting",
            {"key": "default_password", "value": SECRET},
        )
        assert out["error"] == "PermissionDenied"
        _assert_clean(rows)

    @pytest.mark.asyncio
    async def test_innocent_setting_still_readable_in_audit(self, audited_server):
        """The fix must not blind the audit log to ordinary settings."""
        server, rows = audited_server
        await _drive_call_tool(
            server, "set_fleet_setting",
            {"key": "default_username", "value": "root"},
        )
        assert len(rows) == 1
        assert rows[0]["details"]["args"] == {
            "key": "default_username", "value": "root",
        }
