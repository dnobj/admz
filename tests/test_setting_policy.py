"""Deny-by-default fleet settings (ADR-0053, GH #212).

Two kinds of test live here.

**The guard** (:class:`TestKeyInventoryScanner`) is the durable one. It walks
``admz/`` with ``ast`` and asserts that every fleet-setting key the code
actually touches has been declared in :mod:`admz.setting_policy`. It exists
because three independent enumerations of the unprotected keys returned 8, 10
and 18 — each missing keys the others found — and every one of those
enumerations matched on *names*. #212's regex needed ``[A-Z]`` at position 0 so
it never saw ``_TOKEN_KEY``; a literal-grep missed keys read through a
module-local ``_settings()`` helper. So this scanner follows call paths and
resolves module-level constants instead, and it carries explicit non-vacuity
controls: a scanner that silently found nothing would pass every assertion
about what it found.

**The behaviour tests** drive ``ADMZMCPServer._set_fleet_setting`` itself
rather than the predicate. That is the #152 lesson repeated: the predicate was
never what was broken — the call site tested set membership directly, so a fix
applied only to the predicate would have reviewed as correct and changed
nothing.
"""

import ast
import asyncio
from pathlib import Path

import pytest

from admz.confirm_policy import _DEFAULT_CONFIRMATION_LEVELS, confirm_level_key
from admz.setting_policy import (
    CAPTURE_ONLY_SETTING_KEYS,
    KNOWN_SETTING_KEYS,
    LLM_WRITABLE_SETTING_KEYS,
    is_capture_only,
    is_llm_writable,
)

ADMZ_ROOT = Path(__file__).resolve().parent.parent / "admz"

# Every key that is declared but not grantable to the LLM. Derived, never
# restated — a literal here would be an iteration source for a coverage claim,
# which is exactly the vacuity GH #152 slipped through.
PROTECTED_KEYS = sorted(KNOWN_SETTING_KEYS - LLM_WRITABLE_SETTING_KEYS)


# --------------------------------------------------------------------------- #
# The scanner
# --------------------------------------------------------------------------- #

#: Attribute names on a fleet-settings store that take a key as arg 0.
_ACCESSOR_ATTRS = {"get", "set", "delete"}

#: A receiver root name containing one of these is a fleet-settings store.
#: ``fleet_settings.get(...)``, ``_settings().get(...)``, ``_fs().get(...)``,
#: ``_fs.fleet_settings.set(...)`` are all in use today.
_RECEIVER_HINTS = ("fleet_settings", "_settings", "_fs")


def _root_name(node):
    """The leftmost ``Name`` of an attribute/call chain, or None."""
    while isinstance(node, (ast.Attribute, ast.Call)):
        node = node.value if isinstance(node, ast.Attribute) else node.func
    return node.id if isinstance(node, ast.Name) else None


def _is_store_access(call: ast.Call) -> bool:
    """True if ``call`` is a fleet-settings get/set/delete."""
    if not isinstance(call.func, ast.Attribute):
        return False
    if call.func.attr not in _ACCESSOR_ATTRS:
        return False
    root = _root_name(call.func.value)
    return bool(root) and any(hint in root for hint in _RECEIVER_HINTS)


def _module_string_constants(tree: ast.Module) -> dict:
    """Module-level ``NAME = "literal"`` bindings.

    This is the part a name-matching scanner cannot do. ``USER_SETTING_KEY``,
    ``_TOKEN_KEY``, ``FLEET_KEY``, ``_FS_GC_ENABLED`` and ``KEY_APP_ID`` are
    all real key-bearing constants in this codebase and share no naming
    convention.
    """
    out = {}
    for node in tree.body:
        targets, value = [], None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            for target in targets:
                if isinstance(target, ast.Name):
                    out[target.id] = value.value
    return out


def _resolve(node, consts: dict, foreign: dict = None):
    """A string literal, a module constant bound to one, or None.

    ``foreign`` maps a module stem to its own constants, so a cross-module
    reference resolves too. That is not hypothetical tidiness:
    ``admz/api/routes/survey.py`` writes
    ``fleet_settings.set(secrets.KEY_SCHEDULE_SECONDS, ...)`` and the constant
    is defined in ``admz/survey/secrets.py``. Without this the scanner reports
    that key as never used — which is how this branch was found.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    if (
        foreign
        and isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
    ):
        return foreign.get(node.value.id, {}).get(node.attr)
    return None


def _store_touching_functions(tree: ast.Module) -> set:
    """Names of functions in this module whose body accesses the store.

    Needed because several modules wrap the store in a local helper and pass
    the key in — ``admz/snapshot/ignore.py`` has ``_fleet_get(setting_key)``
    and ``admz/modules/acs_pro/firebird.py`` has ``_setting(key)``. A scanner
    that only looked at direct accessor calls would resolve nothing in either
    file and silently under-report, which is the failure mode this whole test
    exists to prevent.
    """
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any(
            isinstance(inner, ast.Call) and _is_store_access(inner)
            for inner in ast.walk(node)
        ):
            names.add(node.name)
    return names


def scan_setting_keys() -> dict:
    """Every statically-resolvable fleet-setting key in ``admz/``.

    Returns ``{key: {"path:lineno", ...}}`` so a failure can name the site.

    Known limit, stated rather than papered over: a key built at runtime — an
    f-string, a ``%`` format, a value read from config — is invisible here.
    ``confirm_level_*`` is exactly that case, which is why
    :func:`admz.fleet_settings.is_protected_setting` keeps a *namespace* rule
    alongside this declaration rather than relying on it.
    """
    found: dict = {}

    def record(key, path, lineno):
        found.setdefault(key, set()).add(
            f"{path.relative_to(ADMZ_ROOT.parent).as_posix()}:{lineno}"
        )

    # Pass 1: parse everything once and index each module's string constants
    # by module stem, so pass 2 can resolve `othermodule.SOME_KEY`.
    # `local` is exact, per file. `foreign` is keyed by module *stem* and so
    # must MERGE rather than overwrite: this package has three `config.py` and
    # two `secrets.py`, and keying by stem alone silently gave a module some
    # other module's constants. Merging can in principle conflate two
    # same-named constants in same-named modules; for a guard whose job is to
    # avoid *under*-reporting, erring toward resolving more is the right way
    # to be wrong.
    trees: dict = {}
    local: dict = {}
    foreign: dict = {}
    for path in sorted(ADMZ_ROOT.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - would fail the build anyway
            continue
        trees[path] = tree
        consts = _module_string_constants(tree)
        local[path] = consts
        foreign.setdefault(path.stem, {}).update(consts)

    # Pass 2: find the keys.
    for path, tree in trees.items():
        consts = local[path]
        wrappers = _store_touching_functions(tree)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            direct = _is_store_access(node)
            viawrap = isinstance(node.func, ast.Name) and node.func.id in wrappers
            if not (direct or viawrap):
                continue
            key = _resolve(node.args[0], consts, foreign)
            if key:
                record(key, path, node.lineno)
    return found


class TestKeyInventoryScanner:
    """The guard that makes deny-by-default durable."""

    def test_scanner_is_not_vacuous(self):
        """A scanner that found nothing would pass every test below it.

        Four keys chosen because each defeated at least one previous
        enumeration attempt: ``acs_webhook_token`` hides behind a
        leading-underscore constant (#212's regex missed it), the ignore keys
        are reached through a wrapper function, ``health_verify_credentials``
        is an inline literal in a module with no key constants, and
        ``snapshot_gc_enabled`` hides behind ``_FS_GC_ENABLED``.
        """
        found = scan_setting_keys()
        for key in (
            "acs_webhook_token",
            "config_ignore_patterns",
            "health_verify_credentials",
            "snapshot_gc_enabled",
            "default_password",
            "gemini_api_key",
        ):
            assert key in found, f"scanner failed to find {key} — it is broken"
        assert len(found) >= 30, f"scanner found only {len(found)} keys"

    def test_every_key_in_the_code_is_declared(self):
        """The whole point: adding a setting forces a reviewed decision.

        If this fails, a fleet-setting key was added without deciding whether
        the chat model may write it. Add it to ``KNOWN_SETTING_KEYS`` — and
        only add it to ``LLM_WRITABLE_SETTING_KEYS`` if the model genuinely
        needs to write it, which for the last four settings it did not.
        """
        found = scan_setting_keys()
        undeclared = {
            key: sorted(sites)
            for key, sites in found.items()
            if key not in KNOWN_SETTING_KEYS
        }
        assert not undeclared, (
            "undeclared fleet-setting keys found in admz/:\n"
            + "\n".join(f"  {k}  at {', '.join(v)}" for k, v in sorted(undeclared.items()))
        )

    def test_inventory_has_no_dead_entries(self):
        """The inventory must describe reality in both directions.

        A key listed here but absent from the code is either a typo or a
        leftover, and either way it makes the inventory less trustworthy.
        """
        found = set(scan_setting_keys())
        # Keys legitimately absent from a static scan: written only through a
        # runtime-computed name, or read only via a dataclass attribute.
        dynamic = {
            # admz/capabilities.py reads these as ``cap.setting_key``.
            "event_ingest_enabled",
            "acs_event_ingest_enabled",
            "acs_firebird_enabled",
            "survey_mode_enabled",
        }
        stale = KNOWN_SETTING_KEYS - found - dynamic
        assert not stale, f"declared but never used in admz/: {sorted(stale)}"


# --------------------------------------------------------------------------- #
# The allow-set itself
# --------------------------------------------------------------------------- #


class TestAllowSet:
    def test_allow_set_is_exactly_the_credential_pair(self):
        """Growing the allow-set must be a deliberate edit to this test.

        Two keys, because that is what the system documents the model needing:
        ``mcp/tools/fleet.py`` advertises ``default_password`` and nothing
        else, and ``default_username`` is its documented other half.
        """
        assert LLM_WRITABLE_SETTING_KEYS == frozenset(
            {"default_password", "default_username"}
        )

    def test_capture_only_is_the_password(self):
        assert CAPTURE_ONLY_SETTING_KEYS == frozenset({"default_password"})
        assert CAPTURE_ONLY_SETTING_KEYS <= LLM_WRITABLE_SETTING_KEYS

    def test_unknown_keys_are_denied(self):
        """Deny by default — the property the whole change exists for."""
        assert not is_llm_writable("a_setting_invented_tomorrow")
        assert not is_llm_writable("")

    def test_protected_predicate_inverts(self):
        from admz.fleet_settings import is_protected_setting

        assert not is_protected_setting("default_password")
        assert not is_protected_setting("default_username")
        assert is_protected_setting("anything_else_at_all")

    def test_confirm_level_namespace_survives_inversion(self):
        """Redundant now, kept deliberately.

        A mistaken entry in the allow-set must still not be able to reopen
        GH #152, and runtime-built risk names are invisible to the scanner.
        """
        from admz.fleet_settings import is_protected_setting

        assert is_protected_setting("confirm_level_totally_invented")
        for risk in _DEFAULT_CONFIRMATION_LEVELS:
            assert is_protected_setting(confirm_level_key(risk))


# --------------------------------------------------------------------------- #
# The MCP write path — drive the handler, never just the predicate
# --------------------------------------------------------------------------- #


@pytest.fixture
def mcp_with_isolated_settings(monkeypatch, tmp_path):
    """``admz.mcp.server`` bound to a throwaway DB.

    Test isolation matters more than usual in this repo: several stores bind
    their path at import, so a test that does not do this writes into the
    operator's real database.
    """
    from admz.fleet_settings import FleetSettings
    import admz.mcp.server as mcp_server

    fs = FleetSettings(db_path=str(tmp_path / "settings.db"))
    monkeypatch.setattr(mcp_server, "fleet_settings", fs)
    return mcp_server, fs


class TestMcpRefusesEverythingOutsideTheAllowSet:
    """Parametrised over the derived list, never a literal one.

    ``PROTECTED_KEYS`` is computed from the declaration. A hardcoded tuple
    here would pass forever while the real set grew — the precise defect #176
    found in the test that was supposed to catch #152.
    """

    @pytest.mark.parametrize("key", PROTECTED_KEYS)
    def test_refused(self, key, mcp_with_isolated_settings):
        mcp_server, fs = mcp_with_isolated_settings
        out = asyncio.run(
            mcp_server.ADMZMCPServer._set_fleet_setting(None, key, "PWNED")
        )
        assert out["success"] is False, key
        assert "protected" in out["error"].lower()
        assert fs.get(key) is None, f"{key} was written despite the refusal"

    @pytest.mark.parametrize(
        "key",
        [
            "health_verify_credentials",  # 168
            "acs_pro",                    # 195
            "config_ignore_patterns",     # 203
            "acs_webhook_token",          # 212 amendment
            "event_store_retention_days",  # found by this work
            "acs_fb_fbclient",             # found by this work
        ],
    )
    def test_the_reported_keys_specifically(self, key, mcp_with_isolated_settings):
        """The exact keys from the four issues and this investigation.

        Redundant with the parametrised sweep above, and kept anyway: if the
        derivation ever breaks, these named cases still fail.
        """
        mcp_server, _ = mcp_with_isolated_settings
        out = asyncio.run(
            mcp_server.ADMZMCPServer._set_fleet_setting(None, key, "x")
        )
        assert out["success"] is False, key

    def test_an_invented_key_is_refused(self, mcp_with_isolated_settings):
        mcp_server, _ = mcp_with_isolated_settings
        out = asyncio.run(
            mcp_server.ADMZMCPServer._set_fleet_setting(None, "brand_new_key", "x")
        )
        assert out["success"] is False


class TestMcpStillDoesItsJob:
    """Positive controls. Without these, a handler refusing *everything*
    would satisfy every assertion above."""

    def test_default_username_still_writes(self, mcp_with_isolated_settings):
        mcp_server, fs = mcp_with_isolated_settings
        out = asyncio.run(
            mcp_server.ADMZMCPServer._set_fleet_setting(None, "default_username", "admin")
        )
        assert out["success"] is True
        assert fs.get("default_username") == "admin"

    def test_default_username_can_be_deleted(self, mcp_with_isolated_settings):
        mcp_server, fs = mcp_with_isolated_settings
        fs.set("default_username", "admin")
        out = asyncio.run(
            mcp_server.ADMZMCPServer._set_fleet_setting(None, "default_username", "")
        )
        assert out["success"] is True
        assert fs.get("default_username") is None

    def test_default_password_still_issues_a_capture_url(
        self, mcp_with_isolated_settings
    ):
        """The regression test for the trap documented in ADR-0053.

        ``capture_store.create_fleet_session`` has exactly one caller, and it
        sits *below* the protection gate; ``api/routes/capture.py`` is the only
        non-MCP writer of the credential pair and is reachable only with a
        token that caller mints. Promote ``default_password`` out of the
        allow-set and both keys become settable only by editing SQLite. This
        assertion is what fails first if anyone tries.
        """
        mcp_server, _ = mcp_with_isolated_settings
        out = asyncio.run(
            mcp_server.ADMZMCPServer._set_fleet_setting(None, "default_password")
        )
        assert out["success"] is True
        assert out["action"] == "capture"
        assert "/capture/fleet/" in out["capture_url"]


class TestPasswordValueNeverComesFromChat:
    """FR-MCP-008 and device-onboarding.md:84 required this; the code did not
    enforce it until ADR-0053."""

    def test_supplying_a_password_value_is_refused(self, mcp_with_isolated_settings):
        mcp_server, fs = mcp_with_isolated_settings
        out = asyncio.run(
            mcp_server.ADMZMCPServer._set_fleet_setting(
                None, "default_password", "hunter2"
            )
        )
        assert out["success"] is False
        assert fs.get("default_password") is None
        assert "omitted" in out["error"] or "capture" in out["error"]

    def test_a_non_allowlisted_password_key_cannot_mint_a_session(
        self, mcp_with_isolated_settings
    ):
        """The capture branch used to trigger on ``"password" in key.lower()``
        — a substring test, not an allow-list."""
        mcp_server, _ = mcp_with_isolated_settings
        out = asyncio.run(
            mcp_server.ADMZMCPServer._set_fleet_setting(None, "some_other_password")
        )
        assert out["success"] is False
        assert out.get("action") != "capture"

    def test_capture_only_predicate(self):
        assert is_capture_only("default_password")
        assert not is_capture_only("default_username")


class TestAuditRecordsTheKeyAndTheRefusal:
    def test_resource_carries_the_setting_key(self):
        """Without this an audit query cannot answer 'who changed X?' — the
        key lived only inside details.args."""
        from admz.mcp.server import _tool_resource

        resource = _tool_resource("set_fleet_setting", {"key": "acs_pro"})
        assert "setting:acs_pro" in resource

    def test_resource_is_unchanged_for_other_tools(self):
        """`key` is a generic argument name; scoping matters."""
        from admz.mcp.server import _tool_resource

        assert "setting:" not in _tool_resource("list_devices", {"key": "x"})
