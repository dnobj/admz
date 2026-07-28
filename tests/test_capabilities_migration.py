"""Call-site migration: the *real* predicates still behave exactly as before.

GH #132 slice 2 rewrote nine bespoke env reads into one-line delegations to
``admz.capabilities.is_active``. Backward compatibility is the load-bearing
requirement of that change, and a promise is not a test — so every migrated
call site is exercised here through its **public predicate**, with only the
**old** knob set, asserting the **old** answer.

The one deliberate exception is recorded rather than discovered:
``ADMZ_DISABLE_ONBOARDING_PROBES=0`` used to mean *on* (``onboarding.py`` tested
a bare ``if os.getenv(...)``, so any non-empty string was true) and now means
*off*. ``tests/conftest.py`` sets ``"1"``, so the suite is unaffected.

Isolation: every store binds its DB path at import, so anything that reaches
``fleet_settings`` is pointed at ``tmp_path`` first, and ``conftest.py``'s two
suite-wide suppressor env vars are explicitly deleted before "clean env" means
anything.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest

from admz import capabilities
from admz.capabilities import CAPABILITIES


@pytest.fixture
def clean_env(monkeypatch):
    for cap in CAPABILITIES:
        if cap.env_var:
            monkeypatch.delenv(cap.env_var, raising=False)
    return monkeypatch


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """A real FleetSettings on a temp DB, wired into the registry's read path."""
    monkeypatch.setenv("ADMZ_HOME", str(tmp_path))
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    from admz.fleet_settings import FleetSettings

    store = FleetSettings(db_path=str(tmp_path / "admz.db"))
    monkeypatch.setattr(capabilities, "_settings", lambda: store)
    return store


# ---------------------------------------------------------------------------
# Test 2 — legacy parity, one per migrated flag
# ---------------------------------------------------------------------------


class _RaisingRegistry:
    """Any registry at all: the assertion is only about *where* onboarding
    stopped, and a lookup failure is the first thing past the kill switch."""

    def get_device_info(self, device_id):
        raise RuntimeError("no such device")


class TestOnboardingProbes:
    """``ADMZ_DISABLE_ONBOARDING_PROBES`` → ``test.no_onboarding_probes``."""

    def _onboard(self):
        from admz.onboarding import onboard_device_credentials

        return asyncio.run(
            onboard_device_credentials(
                device_id="cam-1",
                registry=_RaisingRegistry(),
                catalog=None,
                executors={},
            )
        )

    def test_the_old_env_var_still_suppresses_the_probes(
        self, clean_env, isolated_settings
    ):
        clean_env.setenv("ADMZ_DISABLE_ONBOARDING_PROBES", "1")
        out = self._onboard()
        assert out["status"] == "credentials_needed"
        assert out["reason"] == "onboarding probes disabled in this environment"

    def test_without_it_onboarding_runs(self, clean_env, isolated_settings):
        out = self._onboard()
        assert out["status"] == "credentials_needed"
        # It got PAST the kill switch and failed on the device lookup instead.
        assert "device lookup failed" in out["reason"]

    @pytest.mark.parametrize("raw", ["1", "true", "yes", "on", "TRUE"])
    def test_every_accepted_spelling_suppresses(
        self, raw, clean_env, isolated_settings
    ):
        clean_env.setenv("ADMZ_DISABLE_ONBOARDING_PROBES", raw)
        assert "disabled in this environment" in self._onboard()["reason"]

    # -- test 2b: the one recorded behaviour change --------------------------

    def test_zero_now_means_off(self, clean_env, isolated_settings):
        """**The intentional change.** Before slice 2 this read as *enabled*,
        because the call site was ``if os.getenv(...)`` and ``"0"`` is a
        non-empty string. Nobody sets a disable flag to ``0`` intending to
        disable, so the shared parse fixes it — loudly, here."""
        clean_env.setenv("ADMZ_DISABLE_ONBOARDING_PROBES", "0")

        assert capabilities.is_active("test.no_onboarding_probes") is False
        out = self._onboard()
        assert out["reason"] != "onboarding probes disabled in this environment"
        assert "device lookup failed" in out["reason"]

    @pytest.mark.parametrize("raw", ["0", "false", "no", "off", ""])
    def test_the_other_falsey_spellings_agree(
        self, raw, clean_env, isolated_settings
    ):
        clean_env.setenv("ADMZ_DISABLE_ONBOARDING_PROBES", raw)
        assert capabilities.is_active("test.no_onboarding_probes") is False

    def test_the_conftest_value_still_behaves(self, isolated_settings):
        """``tests/conftest.py:25`` sets ``"1"`` process-wide before any import.
        That is the value the whole suite depends on; if the parse change ever
        broke it, thousands of tests would start probing the local LAN."""
        import os

        assert os.environ.get("ADMZ_DISABLE_ONBOARDING_PROBES") == "1"
        assert capabilities.is_active("test.no_onboarding_probes") is True
        assert "disabled in this environment" in self._onboard()["reason"]


class TestGithubAppPush:
    """``ADMZ_DISABLE_GITHUB_APP_PUSH`` → ``test.no_github_push``."""

    def test_the_old_env_var_still_short_circuits(
        self, clean_env, isolated_settings, monkeypatch
    ):
        from admz.github_app import push

        def _explode():
            raise AssertionError("the store must not be touched")

        monkeypatch.setattr("admz.github_app.secrets.is_connected", _explode)
        clean_env.setenv("ADMZ_DISABLE_GITHUB_APP_PUSH", "1")

        assert push.installation_token_for_push() is None

    def test_without_it_the_store_is_consulted(
        self, clean_env, isolated_settings, monkeypatch
    ):
        from admz.github_app import push

        seen = []
        monkeypatch.setattr(
            "admz.github_app.secrets.is_connected",
            lambda: (seen.append(True), False)[1],
        )
        assert push.installation_token_for_push() is None
        assert seen == [True]

    def test_the_conftest_value_still_behaves(self, isolated_settings):
        import os

        assert os.environ.get("ADMZ_DISABLE_GITHUB_APP_PUSH") == "1"
        assert capabilities.is_active("test.no_github_push") is True


class TestMcpScheduler:
    """``ADMZ_MCP_NO_SCHEDULER`` → ``runtime.no_scheduler``.

    Exercised through the real ``ADMZMCPServer.run`` coroutine with the stdio
    transport stubbed, because the whole point of the flag is what ``run``
    does with it — H-1, the duplicate-scheduler fix.
    """

    class _Scheduler:
        def __init__(self):
            self.started = self.stopped = 0

        async def start(self):
            self.started += 1

        async def stop(self):
            self.stopped += 1

    class _Server:
        async def run(self, *_a, **_kw):
            return None

        def create_initialization_options(self):
            return {}

    def _run(self, monkeypatch):
        import admz.mcp.server as srv

        @asynccontextmanager
        async def _fake_stdio():
            yield (None, None)

        monkeypatch.setattr(srv, "stdio_server", _fake_stdio)

        class _Fake:
            pass

        fake = _Fake()
        fake.scheduler = self._Scheduler()
        fake.server = self._Server()

        async def _idle():
            await asyncio.sleep(3600)

        fake._temp_credential_cleanup_loop = _idle

        asyncio.run(srv.ADMZMCPServer.run(fake))
        return fake.scheduler

    def test_the_old_env_var_still_suppresses_the_scheduler(
        self, clean_env, isolated_settings, monkeypatch
    ):
        clean_env.setenv("ADMZ_MCP_NO_SCHEDULER", "1")
        sched = self._run(monkeypatch)
        assert (sched.started, sched.stopped) == (0, 0)

    def test_without_it_the_scheduler_runs(
        self, clean_env, isolated_settings, monkeypatch
    ):
        sched = self._run(monkeypatch)
        assert (sched.started, sched.stopped) == (1, 1)

    def test_the_value_admz_actually_sets_is_the_one_that_works(self):
        """``mcp_pool.py`` and ``voice.py`` both set the literal ``"1"``; the
        migration must not have made that spelling stop meaning anything."""
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        for rel in ("admz/chatbot/mcp_pool.py", "admz/chatbot/voice.py"):
            text = (root / rel).read_text(encoding="utf-8")
            assert re.search(r'ADMZ_MCP_NO_SCHEDULER"\]?\s*[:=]\s*"1"', text), rel
        assert capabilities.truthy("1") is True


class TestFirebird:
    """``ADMZ_ACS_FIREBIRD`` / ``acs_firebird_enabled`` → ``acs.firebird_read``."""

    def test_env_var(self, clean_env, isolated_settings):
        from admz.modules.acs_pro import firebird as fb

        assert fb.firebird_enabled() is False
        clean_env.setenv("ADMZ_ACS_FIREBIRD", "1")
        assert fb.firebird_enabled() is True

    @pytest.mark.parametrize("raw", ["1", "true", "yes", "on"])
    def test_setting_accepts_every_spelling_it_used_to(
        self, raw, clean_env, isolated_settings
    ):
        from admz.modules.acs_pro import firebird as fb

        isolated_settings.set("acs_firebird_enabled", raw)
        assert fb.firebird_enabled() is True

    def test_env_beats_a_disabled_setting(self, clean_env, isolated_settings):
        from admz.modules.acs_pro import firebird as fb

        isolated_settings.set("acs_firebird_enabled", "false")
        clean_env.setenv("ADMZ_ACS_FIREBIRD", "1")
        assert fb.firebird_enabled() is True


class TestEventIngest:
    """``ADMZ_EVENT_INGEST`` / ``ADMZ_ACS_EVENT_INGEST`` and their settings."""

    def test_device_ingest_env(self, clean_env, isolated_settings):
        from admz.events import config as cfg

        assert cfg.event_ingest_enabled() is False
        clean_env.setenv("ADMZ_EVENT_INGEST", "1")
        assert cfg.event_ingest_enabled() is True

    def test_device_ingest_setting(self, clean_env, isolated_settings):
        from admz.events import config as cfg

        isolated_settings.set("event_ingest_enabled", "true")
        assert cfg.event_ingest_enabled() is True

    def test_acs_poll_env(self, clean_env, isolated_settings):
        from admz.events import config as cfg

        assert cfg.acs_event_ingest_enabled() is False
        clean_env.setenv("ADMZ_ACS_EVENT_INGEST", "1")
        assert cfg.acs_event_ingest_enabled() is True

    def test_acs_poll_setting(self, clean_env, isolated_settings):
        from admz.events import config as cfg

        isolated_settings.set("acs_event_ingest_enabled", "on")
        assert cfg.acs_event_ingest_enabled() is True

    def test_a_broken_settings_store_still_answers_false(
        self, clean_env, monkeypatch
    ):
        """The never-raise contract these two predicates always had: a
        settings-store failure must not break startup."""
        from admz.events import config as cfg

        def _boom():
            raise RuntimeError("settings unavailable")

        monkeypatch.setattr(capabilities, "_settings", _boom)
        assert cfg.event_ingest_enabled() is False
        assert cfg.acs_event_ingest_enabled() is False


class TestSurveyMode:
    """``survey_mode_enabled`` → ``survey.contributor``, plus its new alias."""

    def test_the_setting_is_still_authoritative(self, clean_env, isolated_settings):
        from admz.survey import secrets

        assert secrets.is_enabled() is False
        isolated_settings.set(secrets.KEY_ENABLED, "true")
        assert secrets.is_enabled() is True

    @pytest.mark.parametrize("raw", ["1", "true", "yes", "on", "True"])
    def test_every_spelling_the_old_predicate_accepted(
        self, raw, clean_env, isolated_settings
    ):
        from admz.survey import secrets

        isolated_settings.set(secrets.KEY_ENABLED, raw)
        assert secrets.is_enabled() is True

    @pytest.mark.parametrize("raw", ["", "0", "false", "no", "maybe"])
    def test_every_spelling_it_rejected(self, raw, clean_env, isolated_settings):
        from admz.survey import secrets

        isolated_settings.set(secrets.KEY_ENABLED, raw)
        assert secrets.is_enabled() is False

    def test_the_new_env_alias_is_additive(self, clean_env, isolated_settings):
        """The reason slice 1 refused to declare it: the registry may not
        report a switch the code does not read. Now the code reads it."""
        from admz.survey import secrets

        clean_env.setenv("ADMZ_SURVEY_MODE", "1")
        assert secrets.is_enabled() is True
        assert capabilities.source_of("survey.contributor") == "env"

    def test_the_key_constant_is_unchanged(self):
        from admz.survey import secrets

        assert secrets.KEY_ENABLED == "survey_mode_enabled"
        assert capabilities.get("survey.contributor").setting_key == secrets.KEY_ENABLED


# ---------------------------------------------------------------------------
# Test 16 — the LLM cannot flip a capability through set_fleet_setting
# ---------------------------------------------------------------------------


class TestProtectedFromMcp:

    @pytest.mark.parametrize(
        "setting_key", [c.setting_key for c in CAPABILITIES if c.setting_key]
    )
    def test_mcp_set_fleet_setting_refuses_every_capability_key(self, setting_key):
        """Structural, not policy: the MCP tool refuses ``PROTECTED_SETTING_KEYS``
        outright, so no capability can be enabled from a chat turn. This is the
        second of the three independent mechanisms (the others: no MCP write
        tool exists, and the REST toggle is reveal-gated)."""
        from admz.mcp.server import ADMZMCPServer

        out = asyncio.run(
            ADMZMCPServer._set_fleet_setting(None, setting_key, "true")
        )
        assert out["success"] is False
        assert "protected" in out["error"].lower()

    def test_every_toggleable_capability_is_protected(self):
        from admz.fleet_settings import is_protected_setting

        for cap in CAPABILITIES:
            if capabilities.is_toggleable(cap.id):
                assert is_protected_setting(cap.setting_key), cap.id
