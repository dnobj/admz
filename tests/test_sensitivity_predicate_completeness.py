"""Structural guard against hand-rolled sensitivity predicates (#158).

`/fleet-settings` masked with a hand-rolled ``"password" in key.lower()``
test instead of calling the canonical ``is_sensitive_setting_key``
(admz/redact.py's D-2 consolidation, already shared by the MCP tool, the
REST endpoint, the audit sanitizer, and the chat display layer). Any key
that is sensitive but doesn't literally contain "password" —
``gemini_api_key``, ``acs_webhook_token`` — rendered in plaintext, on a page
with no authorization gate of its own.

This is the **fourth** instance of the same failure shape
``admz/setting_policy.py:10-17`` documents for "which fleet-setting keys are
sensitive": three independent enumeration attempts there found 8, 10, and 18
keys, each missing ones the others found. The fix there wasn't a fourth
list — it was a scanner (``tests/test_setting_policy.py``) that walks
``admz/`` with ``ast`` and cross-checks call sites against a closed
declaration. #322 applied the same idea to system-prompt section builders.
This file applies it to sensitivity classification.

**Where this guard is honestly weaker than #322's.** Prompt-section builders
all live as uniformly-named top-level functions in one module
(``admz/chatbot/context.py``), so a scanner could mechanically enumerate
"every possible section" via reflection with zero human list-maintenance.
Sensitivity-masking decisions have no equivalent architectural seam — they
are inline conditionals scattered across route handlers, MCP tool handlers,
and Jinja templates, in different files, with no shared naming convention.
There is no way to mechanically enumerate "every possible display surface"
the way ``inspect.getmembers(context, isfunction)`` enumerates prompt
sections. So this file does NOT claim a fully self-discovering guard exists
for new, not-yet-imagined surfaces — that claim would be false, and stating
it honestly is the point of writing this docstring rather than deleting it.

What IS built, in decreasing order of how "self-maintaining" each part is:

1. ``TestKnownSensitiveKeysAreRecognized`` — fully self-maintaining. Every
   key ``admz/setting_policy.py`` already declares encrypted-at-rest is
   checked against ``is_sensitive_setting_key``. Adding a new encrypted key
   requires no test edit; this keeps checking it.
2. ``TestNoHandRolledSensitivityPredicate`` — a narrow, calibrated source
   scanner (the shape the issue itself suggested): flags any
   ``"password"/"secret"/"token"/"api_key"/"apikey" in <expr>`` substring
   test anywhere in ``admz/`` outside ``redact.py``, with an explicit,
   justified allowlist for the two remaining matches that are a different
   pattern entirely (fixed-schema dict-key presence, not open-ended
   sensitivity classification). New code that reimplements the anti-pattern
   fails this test immediately; new code that calls the canonical predicate
   doesn't. Requires no list of "surfaces" — it sees all of ``admz/``.
3. ``TestLeakSweepAcrossKnownSurfaces`` — behavioral, not textual: seeds one
   real distinctive secret and asserts it never appears unmasked on any of
   the surfaces this test knows about, however each one's masking logic is
   implemented internally. This is the part with a real, stated limit: a
   brand-new future surface (a new route, a new MCP tool) has to be added to
   this test by a human before it's covered — the same "remembering" this
   whole issue is about, one level up. (2) covers new surfaces that reuse
   the anti-pattern; it does not cover a new surface that leaks through some
   third mechanism entirely (logging the raw dict, an error message
   embedding a value, etc.) unless that mechanism also happens to hand-roll
   a matching substring test.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_ADMZ_ROOT = Path(__file__).resolve().parent.parent / "admz"

# ---------------------------------------------------------------------------
# 1. Every key declared encrypted-at-rest must be recognized as sensitive
#    for DISPLAY purposes too — the store encrypting a key and the display
#    layer masking it are two different decisions that could drift from
#    each other exactly like this issue's two predicates did.
# ---------------------------------------------------------------------------


class TestKnownSensitiveKeysAreRecognized:
    def test_store_and_module_encrypted_keys_are_all_sensitive(self):
        from admz.redact import is_sensitive_key
        from admz.setting_policy import (
            MODULE_ENCRYPTED_SETTING_KEYS,
            STORE_ENCRYPTED_SETTING_KEYS,
        )

        not_recognized = {
            key for key in (STORE_ENCRYPTED_SETTING_KEYS | MODULE_ENCRYPTED_SETTING_KEYS)
            if not is_sensitive_key(key)
        }
        assert not not_recognized, (
            f"{not_recognized} are encrypted at rest but "
            "admz.redact.is_sensitive_key does not flag them as sensitive — "
            "they would be encrypted in the DB and then decrypted and shown "
            "in plaintext by any display surface using the canonical "
            "predicate correctly. Add a matching substring to "
            "admz.redact._SENSITIVE_KEY_PARTS, or explain why the key name "
            "doesn't need to."
        )

    def test_the_two_reported_keys_specifically(self):
        """Positive control: the exact keys #158 reported."""
        from admz.redact import is_sensitive_key

        assert is_sensitive_key("gemini_api_key") is True
        assert is_sensitive_key("acs_webhook_token") is True


# ---------------------------------------------------------------------------
# 2. No hand-rolled "sensitive word in key" test outside redact.py
# ---------------------------------------------------------------------------

#: The narrow shape of the anti-pattern: one of redact.py's own sensitive
#: substrings, tested as membership against some lowered key/name
#: expression. Deliberately narrow — not "anything mentioning password" —
#: to avoid flagging unrelated code and becoming exactly the kind of test
#: that gets deleted in six months for crying wolf.
_HAND_ROLLED_RE = re.compile(
    r"""['"](password|passwd|secret|token|api_key|apikey)['"]\s+in\s+\w""",
    re.IGNORECASE,
)

#: Files allowed to contain a match, with the reason it is a DIFFERENT
#: pattern rather than a #158-shaped one — a grant, the same way
#: LLM_WRITABLE_SETTING_KEYS is a grant: it should read as "here's why this
#: one is fine", not as bookkeeping. Value is the expected hit count, so a
#: NEW hand-rolled check added to an already-allowed file still fails loud.
_ALLOWED_HITS = {
    # dict-key-presence checks on a FIXED, known device-account record
    # ("does this record have its one password field") — not a classify-
    # an-open-ended-key-name-as-sensitive predicate. The #158 bug class
    # needs an open-ended key vocabulary (fleet-setting names are arbitrary
    # strings); a fixed schema field name isn't that.
    "backends/sqlite_backend.py": 2,
}


def _scan_for_hand_rolled_hits(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    count = 0
    for m in _HAND_ROLLED_RE.finditer(text):
        line_no = text.count("\n", 0, m.start())
        line = lines[line_no]
        stripped = line.strip()
        # Skip comments and prose that QUOTES the anti-pattern (this file's
        # own module docstring above does exactly that) rather than
        # containing it as executable code or template logic. Backtick
        # quoting is this codebase's own convention for referencing code in
        # docstrings/comments, so a real hit never has one nearby.
        if stripped.startswith("#") or "`" in line:
            continue
        count += 1
    return count


class TestNoHandRolledSensitivityPredicate:
    def test_scanner_finds_only_the_allowed_hits(self):
        hits = {}
        for path in list(_ADMZ_ROOT.rglob("*.py")) + list(_ADMZ_ROOT.rglob("*.html")):
            if path.name == "redact.py":
                continue  # the canonical home for this exact pattern
            n = _scan_for_hand_rolled_hits(path)
            if n:
                hits[str(path.relative_to(_ADMZ_ROOT)).replace("\\", "/")] = n

        unexplained = {f: n for f, n in hits.items() if _ALLOWED_HITS.get(f) != n}
        assert not unexplained, (
            f"{unexplained} hand-roll a 'sensitive word in key' test instead "
            "of calling admz.redact.is_sensitive_key / "
            "admz.fleet_settings.is_sensitive_setting_key. If this is a "
            "genuine new instance of the #158 bug class, call the canonical "
            "predicate instead. If it's a different pattern entirely (like "
            "a fixed-schema dict-key presence check), add it to "
            "_ALLOWED_HITS above with a one-line reason."
        )

    def test_scanner_is_not_vacuous(self):
        """A scanner that silently matched nothing would pass every
        assertion above for the wrong reason (#212's own documented
        lesson). Prove it actually finds text matching its own pattern."""
        assert _HAND_ROLLED_RE.search('if "password" in key.lower():')
        assert _scan_for_hand_rolled_hits(
            _ADMZ_ROOT / "backends" / "sqlite_backend.py"
        ) == 2

    def test_comment_and_backtick_quoting_are_correctly_excluded(self, tmp_path):
        """The false-positive this scanner had to be calibrated against:
        prose explaining the OLD bug (this PR's own commit messages and
        docstrings do exactly this) must not trip it."""
        probe = tmp_path / "probe.py"
        probe.write_text(
            '# old code used to do `"password" in key.lower()` here\n'
            '"""This used to be decided by ``"password" in key.lower()``."""\n'
        )
        assert _scan_for_hand_rolled_hits(probe) == 0


# ---------------------------------------------------------------------------
# 3. The mcp/server.py echo — a direct, mutation-checkable regression test
#    for the fourth instance found while sweeping (#158's own question).
# ---------------------------------------------------------------------------


@pytest.fixture
def mcp_with_isolated_settings(monkeypatch, tmp_path):
    """``admz.mcp.server`` bound to a throwaway DB, same pattern as
    tests/test_setting_policy.py."""
    from admz.fleet_settings import FleetSettings
    import admz.mcp.server as mcp_server

    fs = FleetSettings(db_path=str(tmp_path / "settings.db"))
    monkeypatch.setattr(mcp_server, "fleet_settings", fs)
    return mcp_server, fs


class TestMcpSetFleetSettingEchoIsMasked:
    """admz/mcp/server.py:_set_fleet_setting echoed the raw value back in
    its own tool result using the same hand-rolled predicate. Currently
    unreachable with a real secret (only default_username/default_password
    can ever pass the ADR-0053 allow-list gate above this code, and
    default_password is diverted to the capture flow before reaching it) —
    but that was true only because of the allow-list, not because this
    predicate was correct, so the allow-list monkeypatch below drives the
    line directly rather than trusting that gate to keep protecting it
    forever."""

    def test_sensitive_key_echo_is_masked_if_it_ever_reaches_here(
        self, mcp_with_isolated_settings, monkeypatch
    ):
        mcp_server, fs = mcp_with_isolated_settings
        # Bypass the allow-list gate for this test only, to exercise the
        # masking line even though no real allow-listed key is sensitive
        # today — proving the CODE is correct independent of the gate.
        monkeypatch.setattr(mcp_server, "is_protected_setting", lambda key: False)

        marker = "MARKER-SECRET-DO-NOT-LEAK-abc123"
        out = asyncio.run(
            mcp_server.ADMZMCPServer._set_fleet_setting(None, "gemini_api_key", marker)
        )
        assert out["success"] is True
        assert marker not in out["value"]
        assert out["value"].startswith("*")
        # The write itself is real and unmasked — only the ECHO is masked.
        assert fs.get("gemini_api_key") == marker

    def test_non_sensitive_key_echo_is_unmasked(
        self, mcp_with_isolated_settings, monkeypatch
    ):
        mcp_server, fs = mcp_with_isolated_settings
        monkeypatch.setattr(mcp_server, "is_protected_setting", lambda key: False)

        out = asyncio.run(
            mcp_server.ADMZMCPServer._set_fleet_setting(None, "default_username", "root")
        )
        assert out["value"] == "root"


# ---------------------------------------------------------------------------
# 4. Behavioral leak sweep across the surfaces known to render fleet
#    settings today. Seeds one real distinctive secret, asserts it never
#    appears unmasked anywhere except through the gated reveal fetch.
# ---------------------------------------------------------------------------

_MARKER_SECRET = "MARKER-SECRET-DO-NOT-LEAK-xyz789"


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient with an isolated DB + repointed fleet_settings
    singletons in every module that holds its own reference (each route
    module imports the singleton at module scope, so each needs repointing
    — same pattern as tests/test_reveal_group_gate.py)."""
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")
    monkeypatch.delenv("ADMZ_REVEAL_GROUPS", raising=False)

    from admz import fleet_settings as fs_module
    from admz.api.routes import devices as devices_route
    from admz.api.routes import web as web_route

    db_path = str(tmp_path / "admz.db")
    fresh_fs = fs_module.FleetSettings(db_path)
    monkeypatch.setattr(fs_module, "fleet_settings", fresh_fs)
    monkeypatch.setattr(devices_route, "fleet_settings", fresh_fs)
    monkeypatch.setattr(web_route, "fleet_settings", fresh_fs)

    from admz.auth import NoAuth, set_active_backend
    set_active_backend(NoAuth())

    from admz.api.main import app
    try:
        with TestClient(app) as c:
            yield c
    finally:
        # admz.auth._ACTIVE_BACKEND is a bare module-level global with no
        # per-test reset (get_active_backend() only rebuilds it when it's
        # None) — a test that swaps it (the positive-control reveal test
        # below does, to drive an authorized principal) leaks a fake
        # identity into every later test in the SAME pytest process
        # otherwise. This is exactly the #257/#260 shape and is what broke
        # tests/test_tasks_routes.py the first time this file ran before it
        # in a session: reset unconditionally on teardown, regardless of
        # what the test body did to the backend.
        set_active_backend(NoAuth())


@pytest.fixture(autouse=True)
def _seed_marker(client):
    """Every test in this section starts with the marker secret stored
    under a real, currently-sensitive, currently-encrypted-at-rest key —
    the exact key the issue reported (gemini_api_key)."""
    from admz.fleet_settings import fleet_settings
    fleet_settings.set("gemini_api_key", _MARKER_SECRET)
    fleet_settings.set("default_username", "not-a-secret")
    return _MARKER_SECRET


class TestLeakSweepAcrossKnownSurfaces:
    def test_json_list_endpoint_does_not_leak(self, client):
        r = client.get("/api/fleet/settings")
        assert r.status_code == 200
        assert _MARKER_SECRET not in r.text

    def test_json_single_endpoint_does_not_leak(self, client):
        r = client.get("/api/fleet/settings/gemini_api_key")
        assert r.status_code == 200
        assert _MARKER_SECRET not in r.text

    def test_html_page_does_not_leak(self, client):
        """The #158 finding itself: this page's own hand-rolled predicate
        used to let this straight through, with no gate at all."""
        r = client.get("/fleet-settings")
        assert r.status_code == 200
        assert _MARKER_SECRET not in r.text
        # Non-sensitive values still render plainly — the fix must not
        # make the page useless.
        assert "not-a-secret" in r.text

    def test_mcp_get_fleet_settings_does_not_leak(self, client, monkeypatch, tmp_path):
        import admz.mcp.server as mcp_server
        from admz.fleet_settings import fleet_settings

        monkeypatch.setattr(mcp_server, "fleet_settings", fleet_settings)
        out = asyncio.run(mcp_server.ADMZMCPServer._get_fleet_settings(None))
        assert _MARKER_SECRET not in str(out)

    def test_positive_control_reveal_endpoint_does_return_it_when_authorized(self, client):
        """Proves the sweep isn't passing because the whole pipeline (e.g.
        the DB write itself) is broken — the gated path must still work."""
        from admz.auth import Principal, set_active_backend

        class _Stub:
            async def authenticate(self, request):
                return Principal(
                    name="AXIS\\alice", display_name="alice", domain="AXIS",
                    groups=["Administrators"], source="windows",
                )

        set_active_backend(_Stub())
        r = client.get("/api/fleet/settings/gemini_api_key/reveal")
        assert r.status_code == 200
        assert r.json()["value"] == _MARKER_SECRET
