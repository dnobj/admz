"""The advanced-capability registry itself (GH #132).

These tests are about the declaration being true, complete, and legible; the
*call sites* that now delegate to it are covered by
``tests/test_capabilities_migration.py`` and the reveal-gated surface by
``tests/test_advanced_settings_page.py``. Covered here:

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

# #164: `set()` refuses a declared capability key so no route can
# bypass `capabilities.set_enabled`. These tests arrange LEGACY
# on-disk spellings ("yes", "on", "1") that `set_enabled` cannot
# produce — they exercise the READER's tolerance — so they use the
# private `_raw_set` door deliberately.

from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest

from admz import capabilities
from admz.capabilities import CAPABILITIES, Capability
from tests import mcp_harness


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

    def test_survey_contributor_resolves_from_the_setting(
        self, clean_env, isolated_settings
    ):
        """The setting stays the authoritative knob — it is what
        ``/settings/survey`` writes and what existed before the env alias."""
        assert capabilities.is_active("survey.contributor") is False
        isolated_settings._raw_set("survey_mode_enabled", "true")
        assert capabilities.is_active("survey.contributor") is True
        assert capabilities.source_of("survey.contributor") == "setting"

    def test_hybrid_capability_resolves_from_either(self, clean_env, isolated_settings):
        assert capabilities.is_active("events.device_ingest") is False
        isolated_settings._raw_set("event_ingest_enabled", "yes")
        assert capabilities.source_of("events.device_ingest") == "setting"
        isolated_settings._raw_set("event_ingest_enabled", "")
        assert capabilities.is_active("events.device_ingest") is False
        clean_env.setenv("ADMZ_EVENT_INGEST", "1")
        assert capabilities.source_of("events.device_ingest") == "env"

    def test_env_beats_setting(self, clean_env, isolated_settings):
        """A setting can never turn off an env-forced capability — the
        semantics ``events/config.py`` already has."""
        isolated_settings._raw_set("event_ingest_enabled", "false")
        clean_env.setenv("ADMZ_EVENT_INGEST", "1")
        assert capabilities.is_active("events.device_ingest") is True
        assert capabilities.source_of("events.device_ingest") == "env"

    def test_garbage_setting_values_are_off(self, clean_env, isolated_settings):
        for raw in ("maybe", "", "0", "false"):
            isolated_settings._raw_set("event_ingest_enabled", raw)
            assert capabilities.is_active("events.device_ingest") is False, raw

    def test_survey_contributor_gained_its_env_alias(
        self, clean_env, isolated_settings
    ):
        """Slice 1 deliberately did **not** declare ``ADMZ_SURVEY_MODE``,
        because ``survey/secrets.py`` read only the setting and declaring the
        env var would have made the registry report a switch that did nothing.

        Slice 2 added it in the same commit as the call-site delegation, which
        is the first moment the declaration became true — so the assertion that
        matters is not just "the registry sees it" but "the real predicate
        agrees with the registry".
        """
        from admz.survey import secrets

        assert capabilities.is_active("survey.contributor") is False
        clean_env.setenv("ADMZ_SURVEY_MODE", "1")
        assert capabilities.is_active("survey.contributor") is True
        assert capabilities.source_of("survey.contributor") == "env"
        assert secrets.is_enabled() is True

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

    def test_test_suppressors_alone_write_nothing(
        self, clean_env, isolated_settings, tmp_path, monkeypatch
    ):
        """A boot with **only** test-suppressors active writes zero rows.

        This is the state every pytest process is in — ``conftest.py`` sets both
        suppressors before any app exists. A suppressor is a test-harness
        artifact, not a power an operator granted, and every store binds its DB
        path at import: a writer that fired here would pollute the operator's
        real audit log from any test that forgets to isolate ADMZ_HOME.
        """
        monkeypatch.setattr(capabilities, "_BOOT_AUDIT_DONE", False)
        clean_env.setenv("ADMZ_DISABLE_ONBOARDING_PROBES", "1")
        clean_env.setenv("ADMZ_DISABLE_GITHUB_APP_PUSH", "1")

        # They are active, and loud enough to warn about...
        assert capabilities.active_ids() == [
            "test.no_onboarding_probes", "test.no_github_push",
        ]
        assert any(
            lvl == logging.WARNING for lvl, _ in capabilities.startup_lines()
        )

        capabilities.record_boot_audit()

        # ...but they leave no persistent trace.
        from admz.audit import AuditLog

        rows = AuditLog(db_path=str(tmp_path / "admz.db")).list_recent(limit=50)
        assert rows == []

    def test_a_real_capability_still_writes_alongside_a_suppressor(
        self, clean_env, isolated_settings, tmp_path, monkeypatch
    ):
        """The exclusion is per-capability, not all-or-nothing: a suppressor
        must never mask a dev-only or dangerous capability's row."""
        monkeypatch.setattr(capabilities, "_BOOT_AUDIT_DONE", False)
        clean_env.setenv("ADMZ_DISABLE_ONBOARDING_PROBES", "1")
        clean_env.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        clean_env.setenv("ADMZ_ACS_RULE_WRITE", "1")

        capabilities.record_boot_audit()

        from admz.audit import AuditLog

        rows = AuditLog(db_path=str(tmp_path / "admz.db")).list_recent(limit=50)
        assert sorted(r.resource for r in rows) == [
            "capability:acs.rule_write",
            "capability:dev.auto_approve",
        ]

    def test_boot_auditable_covers_every_declared_class(self):
        """Pin the predicate against the whole table, so adding a capability
        makes the audit decision explicit rather than incidental."""
        expected = {
            "dev-only": True,
            "dangerous": True,
            "test-suppressor": False,
            "privileged": False,
            "internal": False,
        }
        for cap in CAPABILITIES:
            assert capabilities._boot_auditable(cap) is expected[cap.danger], cap.id


# ---------------------------------------------------------------------------
# Tests 7, 19 — the write path
# ---------------------------------------------------------------------------


class _Principal:
    """The two attributes ``audit.record_event`` reads off a Principal."""

    def __init__(self, name="ADMZ\\alice", source="windows"):
        self.name = name
        self.source = source


def _audit_rows(tmp_path):
    from admz.audit import AuditLog

    return AuditLog(db_path=str(tmp_path / "admz.db")).list_recent(limit=50)


class TestSetEnabled:
    """``set_enabled`` is the *only* way a capability changes without a service
    restart, so every call leaves an attributed row behind."""

    def test_enabling_writes_the_setting_and_one_audit_row(
        self, clean_env, isolated_settings, tmp_path
    ):
        source = capabilities.set_enabled(
            "events.device_ingest", True, _Principal(),
            reason="watching the loading bay for a demo",
        )

        assert source == "setting"
        assert capabilities.is_active("events.device_ingest") is True
        assert isolated_settings.get("event_ingest_enabled") == "true"

        rows = [r for r in _audit_rows(tmp_path) if r.action == "capability.enable"]
        assert len(rows) == 1
        (row,) = rows
        assert row.resource == "capability:events.device_ingest"
        assert row.requester == "ADMZ\\alice"
        assert row.auth_source == "windows"
        assert row.details["danger"] == "privileged"
        assert row.details["source"] == "setting"
        assert row.details["reason"] == "watching the loading bay for a demo"

    def test_disabling_writes_a_disable_row(
        self, clean_env, isolated_settings, tmp_path
    ):
        capabilities.set_enabled(
            "events.device_ingest", True, _Principal(), reason="on",
        )
        source = capabilities.set_enabled(
            "events.device_ingest", False, _Principal(), reason="chatty at 2am",
        )

        assert source == ""
        assert capabilities.is_active("events.device_ingest") is False
        actions = [r.action for r in _audit_rows(tmp_path)]
        assert actions.count("capability.disable") == 1
        assert actions.count("capability.enable") == 1

    def test_disabling_an_env_forced_capability_reports_it_is_still_on(
        self, clean_env, isolated_settings, tmp_path
    ):
        """The one genuinely surprising outcome, so it is a returned value and
        an audit detail rather than something an operator discovers later."""
        clean_env.setenv("ADMZ_EVENT_INGEST", "1")

        source = capabilities.set_enabled(
            "events.device_ingest", False, _Principal(), reason="trying to stop it",
        )

        assert source == "env"
        assert capabilities.is_active("events.device_ingest") is True
        (row,) = [r for r in _audit_rows(tmp_path) if r.action == "capability.disable"]
        assert row.details["source"] == "env"
        assert row.details["active"] is True

    def test_survey_contributor_is_toggleable_now_that_it_has_a_setting_row(
        self, clean_env, isolated_settings
    ):
        from admz.survey import secrets

        capabilities.set_enabled(
            "survey.contributor", True, _Principal(), reason="privileged install",
        )
        assert secrets.is_enabled() is True

    @pytest.mark.parametrize(
        "cap_id",
        [c.id for c in CAPABILITIES if "setting" not in c.enable_via],
    )
    def test_env_only_capabilities_refuse_to_be_toggled(
        self, cap_id, clean_env, isolated_settings, tmp_path
    ):
        """Test 19. ``dev.auto_approve`` must not be a click, and neither must
        ``acs.rule_write``, the suppressors, or the internal role marker."""
        assert capabilities.is_toggleable(cap_id) is False
        with pytest.raises(capabilities.NotToggleable) as exc:
            capabilities.set_enabled(cap_id, True, _Principal(), reason="nope")

        cap = capabilities.get(cap_id)
        assert cap.env_var in str(exc.value)
        assert "restart" in str(exc.value)
        # Nothing was written, and nothing was audited.
        assert capabilities.is_active(cap_id) is False
        assert _audit_rows(tmp_path) == []

    def test_unknown_id_refuses(self, clean_env, isolated_settings, tmp_path):
        with pytest.raises(capabilities.UnknownCapability):
            capabilities.set_enabled("nope.not_a_thing", True, _Principal(), reason="x")
        assert _audit_rows(tmp_path) == []

    def test_both_refusals_share_a_base_class(self):
        assert issubclass(capabilities.NotToggleable, capabilities.CapabilityError)
        assert issubclass(capabilities.UnknownCapability, capabilities.CapabilityError)

    def test_is_toggleable_matches_the_declaration(self):
        for cap in CAPABILITIES:
            assert capabilities.is_toggleable(cap.id) is ("setting" in cap.enable_via)
        assert capabilities.is_toggleable("nope.not_a_thing") is False


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
# The read shape — one shaping function, two readers (slice 3)
# ---------------------------------------------------------------------------


class TestReadShape:
    """``describe``/``snapshot`` are what both surfaces return.

    Slice 3 added the MCP reader beside slice 2's REST one. These pin that the
    shape is single-sourced rather than duplicated — the failure this prevents
    is the boring one where a field is added to the REST row and the agent's
    view of the same install quietly lacks it.
    """

    def test_describe_carries_declaration_and_live_state(
        self, clean_env, isolated_settings
    ):
        clean_env.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        row = capabilities.describe(capabilities.get("dev.auto_approve"))
        assert row["id"] == "dev.auto_approve"
        assert row["danger"] == "dev-only"
        assert row["severity"] == "red"
        assert row["enabled"] is True
        assert row["source"] == "env"
        assert row["toggleable"] is False
        assert row["production_appropriate"] is False

    def test_the_rest_row_is_the_registry_shape(self):
        """``routes/capabilities._row`` delegates; if someone re-inlines it,
        this fails the moment the two disagree about a field."""
        from admz.api.routes import capabilities as routes_caps

        cap = CAPABILITIES[0]
        assert routes_caps._row(cap) == capabilities.describe(cap)

    def test_severity_covers_every_danger_class(self):
        for cls in capabilities.DANGER_CLASSES:
            assert cls in capabilities.DANGER_SEVERITY

    def test_snapshot_lists_every_capability_and_the_active_ids(
        self, clean_env, isolated_settings
    ):
        clean_env.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        snap = capabilities.snapshot()
        assert [r["id"] for r in snap["capabilities"]] == [c.id for c in CAPABILITIES]
        assert snap["active"] == ["dev.auto_approve"]
        assert snap["active"] == capabilities.active_ids()

    def test_snapshot_carries_the_auth_backend_as_context(self, clean_env):
        clean_env.setenv("ADMZ_AUTH_BACKEND", "none")
        snap = capabilities.snapshot()
        assert snap["auth_backend"]["backend"] == "none"
        assert snap["auth_backend"]["anonymous"] is True
        # Master resolution 5: context, never a row.
        assert not any(
            "AUTH_BACKEND" in (r["env_var"] or "") for r in snap["capabilities"]
        )

    def test_the_registry_never_reads_the_reveal_groups_itself(self, clean_env):
        """``admz.authz`` imports FastAPI, so the web layer passes the groups
        in. Omitting them in the MCP payload is honest: nothing there toggles."""
        assert "reveal_groups" not in capabilities.auth_backend_context()
        passed = capabilities.auth_backend_context(["Administrators"])
        assert passed["reveal_groups"] == ["Administrators"]

    def test_snapshot_never_returns_a_knob_value(self, clean_env, isolated_settings):
        clean_env.setenv("ADMZ_DEV_AUTO_APPROVE", "hunter2")
        assert "hunter2" not in repr(capabilities.snapshot())


# ---------------------------------------------------------------------------
# Test 11 — the MCP surface, and the tool that must never exist (slice 3)
# ---------------------------------------------------------------------------


def _live_mcp_tool_names(tmp_path, monkeypatch):
    """Tool names as the wire sees them, from a real server instance."""
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("DEVICE_REGISTRY_BACKEND", "sqlite")

    import asyncio

    from admz.mcp.server import ADMZMCPServer

    server = ADMZMCPServer()
    names = asyncio.run(
        mcp_harness.tool_names(server)
    )
    return server, names


def _tool_payload():
    """What the handler returns, without paying for a whole server instance.

    ``_get_advanced_capabilities`` touches no instance state — it is a pure
    read of the registry — so calling it unbound exercises the real method
    while keeping the catalog load out of tests that only care about shape.
    """
    from admz.mcp.server import ADMZMCPServer

    return ADMZMCPServer._get_advanced_capabilities(None)


class TestMcpSurface:

    def test_the_inventory_tool_is_advertised(self, tmp_path, monkeypatch):
        _server, names = _live_mcp_tool_names(tmp_path, monkeypatch)
        assert "get_advanced_capabilities" in names

    def test_no_tool_can_enable_a_capability(self, tmp_path, monkeypatch):
        """The load-bearing assertion of this slice.

        A write tool would let the model turn on the switches that decide who
        may satisfy its own confirmation gates. There is none, and this test is
        what stops one being added "for symmetry" later. The check is on the
        LIVE advertised list, so a module tool cannot sneak one in either.
        """
        _server, names = _live_mcp_tool_names(tmp_path, monkeypatch)
        offenders = [n for n in names if re.search(r"set_.*capabilit", n)]
        assert offenders == [], (
            f"a capability WRITE tool is advertised: {offenders}. "
            "See admz/mcp/tools/capabilities.py — this is deliberate, not an "
            "oversight to be corrected."
        )

    def test_the_capability_domain_holds_exactly_one_tool(self):
        from admz.mcp.tools import capabilities as cap_tools

        assert [t.name for t in cap_tools.TOOLS] == ["get_advanced_capabilities"]

    def test_the_dispatch_table_has_one_capability_entry(self):
        from admz.mcp.dispatch import TOOL_HANDLERS

        # `list_rule_capabilities` is a device event-rule tool — an unrelated
        # sense of the word — so match the registry's own naming.
        matching = sorted(n for n in TOOL_HANDLERS if "advanced_capabilit" in n)
        assert matching == ["get_advanced_capabilities"]
        assert not [n for n in TOOL_HANDLERS if re.search(r"set_.*capabilit", n)]

    def test_every_capability_setting_key_is_refused_by_set_fleet_setting(self):
        """The second, independent enforcement (ADR-0020): even the generic
        settings tool refuses these keys, so removing the "no write tool" rule
        alone would still not open the hole."""
        from admz.fleet_settings import is_protected_setting

        for cap in CAPABILITIES:
            if cap.setting_key:
                assert is_protected_setting(cap.setting_key), cap.id

    def test_the_tool_returns_the_rest_read_shape(
        self, clean_env, isolated_settings
    ):
        clean_env.setenv("ADMZ_DEV_AUTO_APPROVE", "1")
        payload = _tool_payload()

        assert payload["success"] is True
        assert set(payload) == {"success", "capabilities", "active", "auth_backend"}
        assert payload["active"] == ["dev.auto_approve"]

        from admz.api.routes import capabilities as routes_caps

        rest_row = routes_caps._row(capabilities.get("dev.auto_approve"))
        tool_row = next(
            r for r in payload["capabilities"] if r["id"] == "dev.auto_approve"
        )
        assert tool_row == rest_row

    def test_the_tool_never_returns_a_knob_value(
        self, clean_env, isolated_settings
    ):
        clean_env.setenv("ADMZ_DEV_AUTO_APPROVE", "hunter2")
        assert "hunter2" not in repr(_tool_payload())

    def test_the_tool_description_says_gates_still_fire(self):
        """ADR-0034 in the one place the model actually reads (ADR-0025: most
        guidance rides on the tool descriptions)."""
        from admz.mcp.tools import capabilities as cap_tools

        desc = cap_tools.TOOLS[0].description
        assert "ADR-0034" in desc
        assert "never removes a confirmation gate" in desc

    def test_the_tool_takes_no_arguments(self):
        from admz.mcp.tools import capabilities as cap_tools

        schema = cap_tools.TOOLS[0].input_schema
        assert schema["type"] == "object"
        assert schema["properties"] == {}
        assert schema["required"] == []


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
    #: documenting the future accurately. What stops it becoming a hiding place
    #: is the companion assertion below.
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

    def test_the_registry_hides_no_unclassified_env_read(self):
        """Since the registry file is excluded from the scan above, it must not
        be a place an unclassified env read could hide.

        Slice 1–2 could assert the strict form — *no* literal read at all —
        because every read went through ``os.environ.get(cap.env_var)``. Slice
        3 gave the file one legitimate literal: ``auth_backend_context`` reports
        ``ADMZ_AUTH_BACKEND`` as read-only context (Master resolution 5), and
        that name is already classified as ``ORDINARY_CONFIG``. So the
        assertion became the one the guard was always *for* — every env name
        read here is classified — and the pattern widened to match: the old one
        missed the ``os.environ.get("ADMZ_…")`` spelling entirely, which is
        exactly the read it now has to catch.
        """
        source = (REPO_ROOT / self._SELF).read_text(encoding="utf-8")
        found = set(re.findall(
            r"os\.(?:getenv|environ)(?:\.get)?[.\[(]*\s*[\"'](ADMZ_[A-Z0-9_]+)",
            source,
        ))
        unclassified = found - self._classified()
        assert not unclassified, (
            f"unclassified env read hiding in {self._SELF}: {sorted(unclassified)}"
        )
        # And it is the read we expect, not a new bespoke one that happens to
        # be classified.
        assert found == {"ADMZ_AUTH_BACKEND"}, sorted(found)

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
