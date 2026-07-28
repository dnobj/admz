"""The advanced-capability registry (GH #132, slice 1).

Slice 1 *declares*; it changes no call site. So these tests are about the
declaration being true, complete, and legible:

* the table's own invariants (ids, danger classes, protected setting keys, and
  the env-only-for-the-dangerous-ones asymmetry),
* one truthiness parse, including the ``"0"`` case that the old
  ``if os.getenv(...)`` idiom got backwards,
* resolution from env and from settings, with env winning,
* the startup lines and the ``/api/health`` id list,
* and the drift guard — the test that stops the registry going stale, which is
  the only reason a registry is worth having.

Isolation: every store binds its DB path at import, so anything that touches
``fleet_settings`` or the audit log points at ``tmp_path`` first. ``conftest.py``
sets two capability env vars process-wide for the whole suite, so "clean env"
here means explicitly deleting them.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest

from admz import capabilities
from admz.capabilities import CAPABILITIES, Capability


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def clean_env(monkeypatch):
    """Unset every declared capability env var.

    ``tests/conftest.py`` sets ADMZ_DISABLE_ONBOARDING_PROBES and
    ADMZ_DISABLE_GITHUB_APP_PUSH for the whole session, so without this a
    "nothing is active" assertion would be testing the conftest, not the code.
    """
    for cap in CAPABILITIES:
        if cap.env_var:
            monkeypatch.delenv(cap.env_var, raising=False)
    return monkeypatch


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """A real FleetSettings backed by a temp DB, wired into the registry."""
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    from admz.fleet_settings import FleetSettings

    store = FleetSettings(db_path=str(tmp_path / "admz.db"))
    monkeypatch.setattr(capabilities, "_settings", lambda: store)
    return store


# ---------------------------------------------------------------------------
# Test 12 — table invariants
# ---------------------------------------------------------------------------


class TestTableInvariants:

    def test_ids_are_unique(self):
        ids = [c.id for c in CAPABILITIES]
        assert len(ids) == len(set(ids)), f"duplicate capability ids: {ids}"

    def test_ids_are_dotted_and_stable_looking(self):
        for cap in CAPABILITIES:
            assert re.fullmatch(r"[a-z][a-z0-9]*\.[a-z][a-z0-9_]*", cap.id), cap.id

    def test_every_declared_capability_is_described(self):
        for cap in CAPABILITIES:
            assert cap.title.strip(), cap.id
            assert cap.description.strip(), cap.id
            assert cap.notes.strip(), cap.id
            assert cap.since.strip(), cap.id

    def test_danger_classes_are_from_the_declared_set(self):
        for cap in CAPABILITIES:
            assert cap.danger in capabilities.DANGER_CLASSES, cap.id

    def test_all_nine_capabilities_are_declared(self):
        """The inventory from the plan, in full. A tenth row is fine — a
        *missing* one means a capability went back to being invisible."""
        assert {c.id for c in CAPABILITIES} >= {
            "dev.auto_approve",
            "test.no_onboarding_probes",
            "test.no_github_push",
            "runtime.no_scheduler",
            "acs.firebird_read",
            "events.device_ingest",
            "events.acs_poll",
            "survey.contributor",
            "acs.rule_write",
        }

    def test_enable_via_is_declared_and_non_empty(self):
        for cap in CAPABILITIES:
            assert cap.enable_via, cap.id
            assert set(cap.enable_via) <= {"env", "setting"}, cap.id

    def test_env_var_present_iff_env_enablable(self):
        for cap in CAPABILITIES:
            assert bool(cap.env_var) == ("env" in cap.enable_via), cap.id

    def test_setting_key_present_iff_setting_enablable(self):
        for cap in CAPABILITIES:
            assert bool(cap.setting_key) == ("setting" in cap.enable_via), cap.id

    def test_every_setting_key_is_protected(self):
        """The LLM must not be able to flip a capability through
        ``set_fleet_setting``. That is structural, not policy — the same
        mechanism that already protects the survey keys."""
        from admz.fleet_settings import PROTECTED_SETTING_KEYS

        for cap in CAPABILITIES:
            if cap.setting_key:
                assert cap.setting_key in PROTECTED_SETTING_KEYS, cap.id

    def test_dangerous_classes_are_env_only(self):
        """The asymmetry rule: the ones that must not be a click are env-only,
        so enabling them needs service control on the box, not a browser."""
        for cap in CAPABILITIES:
            if cap.danger in ("dev-only", "dangerous", "test-suppressor", "internal"):
                assert cap.enable_via == ("env",), cap.id

    def test_privileged_capabilities_stay_runtime_toggleable(self):
        """Privileged capabilities run background loops that contact devices.
        If one misbehaves at 2am the operator must be able to stop it without a
        service restart."""
        for cap in CAPABILITIES:
            if cap.danger == "privileged":
                assert "setting" in cap.enable_via, cap.id

    def test_production_verdict_follows_the_danger_class(self):
        for cap in CAPABILITIES:
            expected = cap.danger in ("privileged", "internal")
            assert cap.production_appropriate is expected, cap.id

    def test_env_only_dangerous_capabilities_are_never_production_appropriate(self):
        for cap in CAPABILITIES:
            if cap.danger in ("dev-only", "dangerous"):
                assert cap.production_appropriate is False, cap.id
                assert cap.enable_via == ("env",), cap.id

    def test_capability_is_frozen(self):
        with pytest.raises(Exception):
            CAPABILITIES[0].danger = "internal"  # type: ignore[misc]

    def test_get_returns_the_declaration(self):
        cap = capabilities.get("dev.auto_approve")
        assert isinstance(cap, Capability)
        assert cap.env_var == "ADMZ_DEV_AUTO_APPROVE"
        assert cap.companion_env == (
            "ADMZ_DEV_API_KEY", "ADMZ_DEV_CONFIRM_PASSWORD",
        )


# ---------------------------------------------------------------------------
# Test 2b / 14 — one truthiness parse
# ---------------------------------------------------------------------------


class TestTruthy:

    @pytest.mark.parametrize("raw", ["1", "true", "TRUE", "True", "yes", "on", " on "])
    def test_accepted_spellings(self, raw):
        assert capabilities.truthy(raw) is True

    @pytest.mark.parametrize(
        "raw", [None, "", "   ", "0", "false", "no", "off", "maybe", "2", "-1"]
    )
    def test_rejected_spellings(self, raw):
        assert capabilities.truthy(raw) is False

    def test_zero_is_off(self):
        """The recorded behaviour change. ``if os.getenv(...)`` treated any
        non-empty string as True, so ``ADMZ_DISABLE_ONBOARDING_PROBES=0``
        currently means **on** at the call site. Nobody sets a disable flag to
        ``0`` intending to disable; slice 2 migrates the call site onto this."""
        assert capabilities.truthy("0") is False

    def test_booleans_pass_through(self):
        assert capabilities.truthy(True) is True
        assert capabilities.truthy(False) is False


# ---------------------------------------------------------------------------
# Tests 1, 3, 4, 5 — resolution
# ---------------------------------------------------------------------------


class TestResolution:

    def test_nothing_active_on_a_clean_env(self, clean_env, isolated_settings):
        assert capabilities.active_capabilities() == []
        assert capabilities.active_ids() == []

    def test_env_only_capability_resolves_from_env(self, clean_env, isolated_settings):
        assert capabilities.is_active("dev.auto_approve") is False
        clean_env.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        assert capabilities.is_active("dev.auto_approve") is True
        assert capabilities.source_of("dev.auto_approve") == "env"
        assert capabilities.active_ids() == ["dev.auto_approve"]

    @pytest.mark.parametrize(
        "cap_id",
        [c.id for c in CAPABILITIES if c.enable_via == ("env",)],
    )
    def test_every_env_only_capability_toggles_with_its_var(
        self, cap_id, clean_env, isolated_settings
    ):
        cap = capabilities.get(cap_id)
        assert capabilities.is_active(cap_id) is False
        clean_env.setenv(cap.env_var, "1")
        assert capabilities.is_active(cap_id) is True
        clean_env.setenv(cap.env_var, "0")
        assert capabilities.is_active(cap_id) is False

    def test_setting_only_capability_resolves_from_the_setting(
        self, clean_env, isolated_settings
    ):
        assert capabilities.is_active("survey.contributor") is False
        isolated_settings.set("survey_mode_enabled", "true")
        assert capabilities.is_active("survey.contributor") is True
        assert capabilities.source_of("survey.contributor") == "setting"

    def test_hybrid_capability_resolves_from_either(self, clean_env, isolated_settings):
        assert capabilities.is_active("events.device_ingest") is False
        isolated_settings.set("event_ingest_enabled", "yes")
        assert capabilities.source_of("events.device_ingest") == "setting"
        isolated_settings.set("event_ingest_enabled", "")
        assert capabilities.is_active("events.device_ingest") is False
        clean_env.setenv("ADMZ_EVENT_INGEST", "1")
        assert capabilities.source_of("events.device_ingest") == "env"

    def test_env_beats_setting(self, clean_env, isolated_settings):
        """A setting can never turn off an env-forced capability — the
        semantics ``events/config.py`` already has."""
        isolated_settings.set("event_ingest_enabled", "false")
        clean_env.setenv("ADMZ_EVENT_INGEST", "1")
        assert capabilities.is_active("events.device_ingest") is True
        assert capabilities.source_of("events.device_ingest") == "env"

    def test_garbage_setting_values_are_off(self, clean_env, isolated_settings):
        for raw in ("maybe", "", "0", "false"):
            isolated_settings.set("event_ingest_enabled", raw)
            assert capabilities.is_active("events.device_ingest") is False, raw

    def test_env_var_is_not_read_for_a_setting_only_capability(
        self, clean_env, isolated_settings
    ):
        """survey.contributor declares no env var in slice 1, so the registry
        must not invent one — it would report a switch that does nothing."""
        clean_env.setenv("ADMZ_SURVEY_MODE", "1")
        assert capabilities.is_active("survey.contributor") is False

    def test_active_capabilities_preserves_declaration_order(
        self, clean_env, isolated_settings
    ):
        clean_env.setenv("ADMZ_ACS_RULE_WRITE", "1")
        clean_env.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        assert capabilities.active_ids() == ["dev.auto_approve", "acs.rule_write"]

    def test_active_capability_carries_its_declaration_and_source(
        self, clean_env, isolated_settings
    ):
        clean_env.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        (act,) = capabilities.active_capabilities()
        assert act.id == "dev.auto_approve"
        assert act.source == "env"
        assert act.capability.danger == "dev-only"


# ---------------------------------------------------------------------------
# Tests 13, 15 — failure modes
# ---------------------------------------------------------------------------


class TestFailureModes:

    def test_unknown_id_is_false_and_never_raises(self, caplog):
        with caplog.at_level(logging.WARNING, logger="admz.capabilities"):
            assert capabilities.is_active("nope.not_a_thing") is False
            assert capabilities.source_of("nope.not_a_thing") == ""
        assert capabilities.get("nope.not_a_thing") is None

    def test_unknown_id_logs_only_once(self, caplog):
        capabilities._WARNED_UNKNOWN.discard("nope.only_once")
        with caplog.at_level(logging.WARNING, logger="admz.capabilities"):
            for _ in range(5):
                capabilities.is_active("nope.only_once")
        hits = [r for r in caplog.records if "nope.only_once" in r.getMessage()]
        assert len(hits) == 1

    def test_settings_store_failure_degrades_to_env_only(self, clean_env, monkeypatch):
        """Config must never break a request. A broken settings store means the
        setting side answers "off"; the env side keeps working."""

        def _boom():
            raise RuntimeError("settings store unavailable")

        monkeypatch.setattr(capabilities, "_settings", _boom)

        assert capabilities.is_active("events.device_ingest") is False
        assert capabilities.active_ids() == []

        clean_env.setenv("ADMZ_EVENT_INGEST", "1")
        assert capabilities.is_active("events.device_ingest") is True
        assert capabilities.source_of("events.device_ingest") == "env"


# ---------------------------------------------------------------------------
# Test 8 — startup honesty
# ---------------------------------------------------------------------------


class TestStartupLines:

    def test_exactly_one_info_line_when_clean(self, clean_env, isolated_settings):
        lines = capabilities.startup_lines()
        assert lines == [(logging.INFO, "advanced capabilities: none")]

    def test_one_warning_per_loud_capability(self, clean_env, isolated_settings):
        clean_env.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        clean_env.setenv("ADMZ_ACS_RULE_WRITE", "1")
        lines = capabilities.startup_lines()

        infos = [m for lvl, m in lines if lvl == logging.INFO]
        warnings = [m for lvl, m in lines if lvl == logging.WARNING]
        assert len(infos) == 1
        assert len(warnings) == 2
        assert any("dev.auto_approve" in m for m in warnings)
        assert any("acs.rule_write" in m for m in warnings)
        # The operator needs to know WHICH knob to unset, and from where.
        assert any("ADMZ_DEV_AUTO_APPROVE" in m for m in warnings)
        assert all("via env" in m for m in warnings)

    def test_production_appropriate_capabilities_do_not_warn(
        self, clean_env, isolated_settings
    ):
        """A privileged install is a legitimate profile — amber, not red. And
        an internal runtime marker never chips at all."""
        clean_env.setenv("ADMZ_EVENT_INGEST", "1")
        clean_env.setenv("ADMZ_MCP_NO_SCHEDULER", "1")
        lines = capabilities.startup_lines()

        assert [lvl for lvl, _ in lines] == [logging.INFO]
        (_, summary), = lines
        assert "events.device_ingest" in summary
        assert "runtime.no_scheduler" in summary

    def test_log_startup_lines_uses_the_security_logger(
        self, clean_env, isolated_settings, caplog
    ):
        clean_env.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        with caplog.at_level(logging.INFO, logger="admz.security"):
            capabilities.log_startup_lines()
        levels = {r.levelno for r in caplog.records if r.name == "admz.security"}
        assert levels == {logging.INFO, logging.WARNING}

    def test_api_startup_hook_warns_beside_the_auth_backend_warning(
        self, clean_env, isolated_settings, monkeypatch, caplog
    ):
        """The real hook the lifespan calls, not a stand-in."""
        import admz.api.main as main_mod

        # Boot-audit rows are exercised separately; keep this one log-only.
        monkeypatch.setattr(capabilities, "_BOOT_AUDIT_DONE", True)
        clean_env.setenv("ADMZ_DEV_AUTO_APPROVE", "1")

        with caplog.at_level(logging.INFO, logger="admz.security"):
            main_mod._log_active_capabilities()

        warnings = [
            r.getMessage() for r in caplog.records
            if r.name == "admz.security" and r.levelno == logging.WARNING
        ]
        assert any("dev.auto_approve" in m for m in warnings)

    def test_api_startup_hook_is_silent_when_clean(
        self, clean_env, isolated_settings, monkeypatch, caplog
    ):
        import admz.api.main as main_mod

        monkeypatch.setattr(capabilities, "_BOOT_AUDIT_DONE", True)
        with caplog.at_level(logging.INFO, logger="admz.security"):
            main_mod._log_active_capabilities()

        records = [r for r in caplog.records if r.name == "admz.security"]
        assert len(records) == 1
        assert records[0].levelno == logging.INFO
        assert "none" in records[0].getMessage()

    def test_startup_hook_survives_a_broken_registry(self, monkeypatch, caplog):
        import admz.api.main as main_mod

        monkeypatch.setattr(
            capabilities, "startup_lines",
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        main_mod._log_active_capabilities()  # must not raise


class TestBootAudit:

    def test_writes_one_row_per_loud_capability(
        self, clean_env, isolated_settings, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(capabilities, "_BOOT_AUDIT_DONE", False)
        clean_env.setenv("ADMZ_DEV_AUTO_APPROVE", "1")

        capabilities.record_boot_audit()

        from admz.audit import AuditLog

        rows = AuditLog(db_path=str(tmp_path / "admz.db")).list_recent(limit=50)
        active = [r for r in rows if r.action == "capability.active"]
        assert len(active) == 1
        assert active[0].resource == "capability:dev.auto_approve"
        assert active[0].requester == "system"
        assert active[0].auth_source == "startup"
        assert active[0].details["danger"] == "dev-only"
        assert active[0].details["source"] == "env"

    def test_is_once_per_boot(self, clean_env, isolated_settings, tmp_path, monkeypatch):
        monkeypatch.setattr(capabilities, "_BOOT_AUDIT_DONE", False)
        clean_env.setenv("ADMZ_DEV_AUTO_APPROVE", "1")

        capabilities.record_boot_audit()
        capabilities.record_boot_audit()
        capabilities.record_boot_audit()

        from admz.audit import AuditLog

        rows = AuditLog(db_path=str(tmp_path / "admz.db")).list_recent(limit=50)
        assert len([r for r in rows if r.action == "capability.active"]) == 1

    def test_no_rows_when_only_production_appropriate_capabilities_are_on(
        self, clean_env, isolated_settings, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(capabilities, "_BOOT_AUDIT_DONE", False)
        clean_env.setenv("ADMZ_EVENT_INGEST", "1")

        capabilities.record_boot_audit()

        from admz.audit import AuditLog

        rows = AuditLog(db_path=str(tmp_path / "admz.db")).list_recent(limit=50)
        assert [r for r in rows if r.action == "capability.active"] == []


# ---------------------------------------------------------------------------
# Test 6 — /api/health
# ---------------------------------------------------------------------------


class TestHealthPayload:

    @pytest.fixture
    def client(self, isolated_settings, tmp_path, monkeypatch):
        monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))

        from fastapi.testclient import TestClient
        import admz.api.main as main_mod

        class _StubRegistry:
            def list_devices(self):
                return []

        monkeypatch.setattr(main_mod, "registry", _StubRegistry())
        # No lifespan: this exercises the endpoint, not startup.
        return TestClient(main_mod.app)

    def test_health_lists_active_capability_ids(self, client, clean_env):
        clean_env.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        body = client.get("/api/health").json()
        assert body["status"] == "healthy"
        assert body["advanced_capabilities"] == ["dev.auto_approve"]

    def test_health_is_empty_on_a_clean_install(self, client, clean_env):
        body = client.get("/api/health").json()
        assert body["advanced_capabilities"] == []

    def test_health_never_leaks_values_or_setting_names(self, client, clean_env):
        clean_env.setenv("ADMZ_DEV_AUTO_APPROVE", "hunter2")
        raw = client.get("/api/health").text
        assert "hunter2" not in raw
        assert "ADMZ_DEV_AUTO_APPROVE" not in raw
        assert "survey_mode_enabled" not in raw

    def test_health_survives_a_broken_capability_read(self, client, monkeypatch):
        monkeypatch.setattr(
            capabilities, "active_ids",
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        body = client.get("/api/health").json()
        assert body["advanced_capabilities"] == []
        assert body["status"] == "healthy"


# ---------------------------------------------------------------------------
# Test 12b — the drift guard
# ---------------------------------------------------------------------------


class TestDriftGuard:
    """A registry that drifts from reality is worse than no registry.

    Adding an ``ADMZ_*`` env var must fail here until someone has made a
    one-line, reviewed classification decision — capability or ordinary config.
    That forced decision is the real deliverable of #132.
    """

    _NAME = re.compile(r"ADMZ_[A-Z0-9_]+")

    #: The registry itself is the classification, so scanning it is circular —
    #: naming a *planned* env var in a docstring would fail the guard for
    #: documenting the future accurately. It reads the environment only through
    #: ``os.environ.get(cap.env_var)``, never a literal, so nothing hides here.
    _SELF = "admz/capabilities.py"

    def _scanned_names(self):
        found = {}
        for sub in ("admz", "tools"):
            for path in (REPO_ROOT / sub).rglob("*.py"):
                rel = path.relative_to(REPO_ROOT).as_posix()
                if rel == self._SELF:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                for match in self._NAME.finditer(text):
                    found.setdefault(match.group(0), set()).add(rel)
        return found

    def test_the_registry_never_reads_a_literal_env_var(self):
        """Since the registry file is excluded from the scan above, it must not
        be a place an unclassified env read could hide."""
        source = (REPO_ROOT / self._SELF).read_text(encoding="utf-8")
        assert not re.search(r"os\.(getenv|environ)[.\[(]*\s*[\"']ADMZ_", source)

    def _classified(self):
        known = set(capabilities.ORDINARY_CONFIG) | set(capabilities.NOT_ENV_VARS)
        for cap in CAPABILITIES:
            if cap.env_var:
                known.add(cap.env_var)
            known.update(cap.companion_env)
        return known

    def test_the_scan_actually_finds_things(self):
        """Guard the guard: a broken scanner would make this suite vacuously
        green forever."""
        found = self._scanned_names()
        assert len(found) > 50
        assert "ADMZ_HOME" in found
        assert "ADMZ_DEV_AUTO_APPROVE" in found

    def test_every_env_name_in_source_is_classified(self):
        found = self._scanned_names()
        known = self._classified()
        unclassified = {n: sorted(found[n]) for n in found if n not in known}
        assert not unclassified, (
            "Unclassified ADMZ_* names found in source. Add each to "
            "CAPABILITIES (if it is an advanced capability switch), to "
            "ORDINARY_CONFIG (paths, timeouts, credentials, posture), or to "
            "NOT_ENV_VARS (if it is not an env var at all) in "
            f"admz/capabilities.py: {unclassified}"
        )

    def test_classification_lists_do_not_overlap(self):
        declared = {c.env_var for c in CAPABILITIES if c.env_var}
        companions = {e for c in CAPABILITIES for e in c.companion_env}
        ordinary = set(capabilities.ORDINARY_CONFIG)
        not_env = set(capabilities.NOT_ENV_VARS)

        assert not declared & ordinary
        assert not declared & companions
        assert not ordinary & not_env
        assert not companions & ordinary

    def test_ordinary_config_has_no_stale_entries(self):
        """The inverse rot: a name deleted from source but left in the list.

        Only ORDINARY_CONFIG is checked. A declared *capability* may legitimately
        run ahead of its implementation — ``acs.rule_write`` exists as a row so
        #131 can land as a registration rather than another bespoke env var.
        """
        found = set(self._scanned_names())
        stale = sorted(n for n in capabilities.ORDINARY_CONFIG if n not in found)
        assert not stale, f"ORDINARY_CONFIG names no longer present in source: {stale}"

    def test_classification_lists_have_no_duplicates(self):
        for name, seq in (
            ("ORDINARY_CONFIG", capabilities.ORDINARY_CONFIG),
            ("NOT_ENV_VARS", capabilities.NOT_ENV_VARS),
        ):
            assert len(set(seq)) == len(seq), f"{name} has duplicates"


# ---------------------------------------------------------------------------
# Leaf-light discipline
# ---------------------------------------------------------------------------


def test_capabilities_module_stays_leaf_light():
    """The stdio MCP subprocess, ``operations``, and the nav builder all import
    this. Importing it must not drag in FastAPI, the executor, or the catalog."""
    import subprocess
    import sys

    heavy = ("fastapi", "uvicorn", "admz.api.main", "admz.executor.vapix",
             "axis_api_atlas", "admz.fleet_settings", "admz.audit")
    code = (
        "import admz.capabilities\n"
        "import sys\n"
        f"print(','.join(sorted(m for m in {heavy!r} if m in sys.modules)))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == ""
