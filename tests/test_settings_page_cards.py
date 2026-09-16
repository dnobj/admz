"""The Settings page's summary rows — the rest of the design handoff.

Health monitoring shows what the monitor actually runs with. Configuration
repository carries the ignore list and the GitHub mirror as summary rows whose
editors open in place, and Modules is one row per module with its form in
place. The page is rendered through the real app.

Settings are written through the module singleton, which resolves its database
at call time (#258), so this file repoints no store and cannot leave one
repointed for a later test.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")
    # The monitor falls back to these when a key is unset; a developer's shell
    # must not decide what "unset" renders as.
    monkeypatch.delenv("ADMZ_HEALTH_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("ADMZ_HEALTH_TIMEOUT_SECONDS", raising=False)

    import admz.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_ACTIVE_BACKEND", None)

    from admz.api.main import app
    with TestClient(app) as c:
        yield c


def _set(key, value):
    from admz.fleet_settings import fleet_settings
    fleet_settings.set(key, value)


def _page(client, query=""):
    r = client.get("/settings" + query)
    assert r.status_code == 200
    return r.text


def _row(page, row_id):
    """One setting row's markup: from its id to the next row, or the end."""
    start = page.index(f'id="{row_id}"')
    nxt = page.find('class="setting-row"', start + 1)
    return page[start:nxt if nxt != -1 else len(page)]


def _open_tag(page, element_id):
    """The opening tag of the element with this id."""
    start = page.index(f'id="{element_id}"')
    return page[page.rindex("<", 0, start):page.index(">", start) + 1]


# --- Health monitoring --------------------------------------------------------


class TestHealthShowsWhatTheMonitorRuns:
    """The first version guessed defaults in the template and got two wrong: an
    unset interval read "300s" while the monitor ran every 60s (production has
    no interval key), and an unset verify flag hid "verifying credentials"
    although the monitor's default is on."""

    def test_an_unset_interval_reads_as_the_monitors_default(self, client):
        from admz.fleet import health

        row = _row(_page(client), "health-poller")
        assert f"{health._DEFAULT_INTERVAL_SECONDS:g}s</span>" in row
        assert "300s" not in row or health._DEFAULT_INTERVAL_SECONDS == 300

    def test_an_unset_verify_flag_reads_as_on(self, client):
        assert "verifying credentials" in _row(_page(client), "health-poller")

    def test_set_values_are_the_ones_shown(self, client):
        _set("health_monitor_enabled", "true")
        _set("health_check_interval_seconds", "120")
        _set("health_check_timeout_seconds", "7")
        _set("health_verify_credentials", "false")
        row = _row(_page(client), "health-poller")
        assert "120s</span>" in row and "7s</span>" in row
        assert "verifying credentials" not in row
        assert 'data-health-poller="on"' in row

    def test_the_poller_reads_off_until_enabled(self, client):
        assert 'data-health-poller="off"' in _row(_page(client), "health-poller")


# --- Configuration repository ------------------------------------------------


class TestTheIgnoreListIsASummaryRow:
    def test_the_summary_counts_what_is_configured(self, client):
        from admz.snapshot.ignore import (
            USER_SETTING_KEY, _GLOBAL_IGNORE_PATTERNS, _scoped_rules,
        )

        _set(USER_SETTING_KEY, "root.A\n\n  root.B  \n")
        row = _row(_page(client), "config-tracking")
        summary = row.split("data-ignore-summary>")[1].split("</div>")[0]
        n = len(_GLOBAL_IGNORE_PATTERNS)
        if n:
            assert f"{n} built-in ignore{'' if n == 1 else 's'}" in summary
        else:
            # An empty built-in list is not worth "0 built-in ignores" beside
            # eleven seeded rules the operator can see listed.
            assert "built-in" not in summary
        # The store seeds scoped rules of its own, so count what is there.
        s = len(_scoped_rules())
        assert f"{s} scoped rule{'' if s == 1 else 's'}" in summary
        # Blank and whitespace-only lines are not patterns.
        assert "2 custom patterns" in summary

    def test_every_text_input_carries_a_type_the_stylesheet_matches(self, client):
        """admz.css styles `input[type=...]`; an input with no type attribute
        rendered as a bare white browser field in the ACS form. Scoped to the
        page's own cards — the topbar search lives in base.html and has a rule
        of its own."""
        import re

        page = _page(client)
        start = page.index('<div class="stack"')
        cards = page[start:page.index("<script", start)]
        untyped = [tag for tag in re.findall(r"<input\b[^>]*>", cards)
                   if "type=" not in tag]
        assert untyped == []

    def test_the_editor_is_collapsed_until_asked_for(self, client):
        page = _page(client)
        assert "hidden" in _open_tag(page, "ignore-editor")
        assert 'data-toggle="ignore-editor"' in _row(page, "config-tracking")
        assert 'name="patterns"' in page

    def test_the_editor_is_open_after_a_save(self, client):
        """`POST /settings/ignored-fields` redirects to
        `/settings?ignore_saved=1#config-tracking`; the editor the operator
        just used must still be on screen, with its confirmation."""
        page = _page(client, "?ignore_saved=1")
        assert "hidden" not in _open_tag(page, "ignore-editor")
        assert "Ignore list saved." in _row(page, "config-tracking")

    def test_a_link_to_the_anchor_opens_the_editor(self, client):
        """No JavaScript test tooling here, so the hash check is pinned."""
        assert "location.hash === '#config-tracking'" in _page(client)


class TestTheGitHubMirrorIsASummaryRow:
    @pytest.fixture
    def status(self, monkeypatch):
        from admz.github_app import secrets

        def _set_status(**state):
            monkeypatch.setattr(secrets, "status", lambda: state)
        return _set_status

    def test_not_connected_offers_connect(self, client, status):
        status(connected=False)
        row = _row(_page(client), "github-backup")
        assert 'href="/api/github/connect"' in row
        assert 'id="gh-test"' not in row and "Not connected" in row

    def test_connected_offers_test_and_disconnect(self, client, status):
        status(connected=True, slug="admz-backup-app", config_repo="org/configs")
        row = _row(_page(client), "github-backup")
        assert 'id="gh-test"' in row and 'id="gh-disconnect"' in row
        assert "admz-backup-app" in row and "org/configs" in row
        assert "/api/github/connect" not in row

    def test_a_registered_app_offers_finish(self, client, status):
        status(connected=False, app_registered=True, slug="admz-backup-app")
        row = _row(_page(client), "github-backup")
        assert 'id="gh-finish"' in row and "Finish install" in row

    def test_the_connect_flows_flashes_land_on_the_row(self, client, status):
        """The GitHub routes redirect to `/settings?...#github-backup`."""
        status(connected=False)
        ok = _row(_page(client, "?github_connected=1"), "github-backup")
        assert "Connected to GitHub." in ok
        failed = _row(_page(client, "?github_error=install"), "github-backup")
        assert "Connect failed (install)" in failed


# --- Modules ----------------------------------------------------------------


class TestModulesIsASummaryRow:
    def test_the_acs_form_opens_in_place_with_every_control_the_script_uses(self, client):
        page = _page(client)
        assert 'data-toggle="acs-config"' in page and 'id="acs-configure"' in page
        assert "hidden" in _open_tag(page, "acs-config")
        for element_id in ("acs-host", "acs-port", "acs-client", "acs-verify",
                           "acs-enabled", "acs-test", "acs-save", "acs-msg"):
            assert f'id="{element_id}"' in page, element_id

    def test_the_status_badge_follows_the_module(self, client, monkeypatch):
        from admz.modules.acs_pro import config

        monkeypatch.setattr(config, "acs_config", lambda: SimpleNamespace(
            enabled=True, server_url="acs.example", port=29204,
            client_machine_name="", verify_tls=False))
        badge = _page(client).split('id="acs-status"')[1][:160]
        assert 'class="badge green"' in badge and "Connected" in badge


# --- the page as a whole ------------------------------------------------------


class TestTheCardsFollowTheDesign:
    def test_in_order(self, client):
        page = _page(client)
        titles = ["Safety policy", "Provisioning credentials", "Health monitoring",
                  "Configuration repository", "Modules", "Advanced · raw fleet settings"]
        positions = [page.index(f'<span class="title">{t}</span>') for t in titles]
        assert positions == sorted(positions)

    def test_the_network_discovery_card_is_gone(self, client):
        """Its only control linked to the API docs; discovery runs from the
        Devices page and the console."""
        assert "Network discovery" not in _page(client)
