"""The entry list — "try this" credentials — is edited from Fleet Settings.

FR-CRED-011/012. Before these routes the list had two writers: the capture
form's promote box, which only offers a password a device has just accepted,
and ``python -m admz settings set entry_credentials``, which takes the whole
list — passwords included — as a command-line argument, so it lands in shell
history. Neither covers the common case: an operator who knows the root
password someone set by hand on devices ADMZ has not met yet.

Adding widens what ADMZ tries against every device it adopts, so both routes
carry the break-glass form's protections, pinned here: same-origin before any
side effect; reveal-group membership, with refusals audited; the password typed
twice, never echoed, never in an audit row, and encrypted at rest. The cap and
the prompt-always posture belong to ``admz.entry_credentials`` and are only
surfaced.

Removal is pinned against a stale page: each Remove carries the list revision
it was rendered with, and nothing is removed once anything has written the list
since — a second tab, another writer, or the same form resubmitted by a reload.

The ``client`` fixture repoints every module-level ``fleet_settings`` reference
at once — ``admz.entry_credentials``' own included — for the reason
``test_fleet_root_password_gui.py`` gives (#350).
"""

from __future__ import annotations

import json
import re
import sqlite3

import pytest
from fastapi.testclient import TestClient

from admz import entry_credentials as ec
from admz.auth import AuthBackend, NoAuth, Principal, set_active_backend

PW = "Entry-Pass-gui-51c9"
SAME_ORIGIN = {"Origin": "http://testserver"}
ADD = {"entry_username": "root", "entry_password": PW,
       "confirm_entry_password": PW, "entry_label": "batch A"}
REMOVE_FORM = r'<form[^>]*action="/fleet-settings/entry-credentials/remove".*?</form>'


class StubBackend(AuthBackend):
    def __init__(self, principal: Principal):
        self.principal = principal

    async def authenticate(self, request):
        return self.principal


def _anon() -> Principal:
    return Principal(name="anonymous", display_name="anonymous",
                     source="none", is_anonymous=True)


def _windows(name: str, groups=None) -> Principal:
    return Principal(name=f"AXIS\\{name}", display_name=name, domain="AXIS",
                     groups=list(groups or []), source="windows")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMZ_DB_PATH", str(tmp_path / "admz.db"))
    monkeypatch.setenv("ADMZ_KEY_PATH", str(tmp_path / "admz.key"))
    monkeypatch.setenv("ADMZ_CONFIG_REPO_PATH", str(tmp_path / "config-repo"))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("ADMZ_AUTH_BACKEND", "none")
    monkeypatch.delenv("ADMZ_REVEAL_GROUPS", raising=False)

    from admz import fleet_settings as fs_module
    from admz.api.routes import devices as devices_route
    from admz.api.routes import survey as survey_route
    from admz.api.routes import web as web_route

    fresh_fs = fs_module.FleetSettings(str(tmp_path / "admz.db"))
    originals = [
        (fs_module, "fleet_settings", fs_module.fleet_settings),
        (devices_route, "fleet_settings", devices_route.fleet_settings),
        (web_route, "fleet_settings", web_route.fleet_settings),
        (survey_route, "fleet_settings", survey_route.fleet_settings),
        (ec, "fleet_settings", ec.fleet_settings),
    ]
    for mod, attr, _ in originals:
        setattr(mod, attr, fresh_fs)

    backend = StubBackend(_anon())
    set_active_backend(backend)

    from admz.api.main import app
    app.state._stub_backend = backend
    try:
        with TestClient(app, follow_redirects=False) as c:
            c.fs = fresh_fs
            c.db_path = tmp_path / "admz.db"
            yield c
    finally:
        for mod, attr, val in originals:
            setattr(mod, attr, val)
        set_active_backend(NoAuth())


def _as(principal: Principal) -> None:
    from admz.api.main import app
    app.state._stub_backend.principal = principal


def _admin():
    """In the default reveal group."""
    return _windows("alice", ["Administrators"])


def _outsider():
    """Signed in, but in no reveal group."""
    return _windows("bob", groups=[])


def _rows():
    """Every entry-list audit row."""
    from admz.audit import AuditLog
    return [r for r in AuditLog().list_recent(limit=100)
            if (r.action or "").startswith("entry_credential.")]


def _add(client, headers=SAME_ORIGIN, **overrides):
    return client.post("/fleet-settings/entry-credentials",
                       data={**ADD, **overrides}, headers=headers)


def _remove(client, position, revision, headers=SAME_ORIGIN):
    return client.post("/fleet-settings/entry-credentials/remove",
                       data={"position": str(position), "revision": revision},
                       headers=headers)


def _listed():
    """What the list holds, read through the library rather than the page."""
    return [(c.username, c.password, c.label) for c in ec.list_entry_credentials()]


def _section(page: str) -> str:
    """The entry list's own table — the settings table above it also renders
    ``default_username``, so the page as a whole proves nothing."""
    return page.split('id="entry-credentials"')[1].split("</table>")[0]


def _three():
    for i in range(3):
        ec.add_entry_credential(f"u{i}", f"zz-pw-{i}", f"batch {i}")


# --- who may change the list -------------------------------------------------


class TestTheGate:
    def test_anonymous_may_neither_add_nor_remove(self, client):
        ec.add_entry_credential("keep", "zz-keep-pw", "kept")
        assert _add(client).status_code == 403
        assert _remove(client, 0, ec.list_revision()).status_code == 403
        assert _listed() == [("keep", "zz-keep-pw", "kept")]

    def test_authenticated_but_not_in_a_reveal_group_is_refused_and_audited(self, client):
        """The case a merely-authenticated gate gets wrong. Adding is an oracle
        for "is this password already on the list" — a duplicate is reported —
        and that answer belongs only to someone who may reveal the list."""
        ec.add_entry_credential("keep", "zz-keep-pw", "kept")
        _as(_outsider())
        assert _add(client).status_code == 403
        assert _remove(client, 0, ec.list_revision()).status_code == 403
        assert _listed() == [("keep", "zz-keep-pw", "kept")]
        rows = _rows()
        assert sorted(r.action for r in rows) == [
            "entry_credential.add_refused", "entry_credential.remove_refused"]
        assert all(r.success is False for r in rows)
        assert all((r.error_message or "").startswith("reveal-denied") for r in rows)
        assert PW not in repr(rows) and "zz-keep-pw" not in repr(rows)

    def test_the_403_is_not_swallowed_into_a_rendered_page(self, client):
        _as(_outsider())
        r = _add(client)
        assert r.status_code == 403
        assert "Entry credentials" not in r.text

    def test_a_reveal_group_member_may_add_and_remove(self, client):
        _as(_admin())
        assert _add(client).status_code == 200
        assert _listed() == [("root", PW, "batch A")]
        assert _remove(client, 0, ec.list_revision()).status_code == 200
        assert _listed() == []


class TestCrossOrigin:
    @pytest.mark.parametrize("route", ["add", "remove"])
    def test_a_cross_site_post_is_refused_before_any_side_effect(self, client, route):
        """Checked first — so a forged request cannot even write a refusal row.

        Posted as someone outside the reveal groups: the reveal check audits
        its denials, so only for such a caller does "no row" prove which check
        ran first."""
        ec.add_entry_credential("keep", "zz-keep-pw", "kept")
        _as(_outsider())
        evil = {"Origin": "http://evil.example"}
        r = (_add(client, headers=evil) if route == "add"
             else _remove(client, 0, ec.list_revision(), headers=evil))
        assert r.status_code == 403
        assert _listed() == [("keep", "zz-keep-pw", "kept")]
        assert _rows() == [], "a cross-site request reached the audit log"


# --- adding --------------------------------------------------------------------


class TestAdding:
    def test_it_is_added_shown_and_never_echoed(self, client):
        _as(_admin())
        r = _add(client)
        assert r.status_code == 200, r.text
        assert 'data-flash="success"' in r.text
        section = _section(r.text)
        assert "root" in section and "batch A" in section
        assert PW not in r.text
        assert PW not in client.get("/fleet-settings").text

    def test_the_audit_row_names_the_username_and_label_never_the_password(self, client):
        _as(_admin())
        _add(client)
        rows = _rows()
        assert [(r.action, r.success) for r in rows] == [("entry_credential.added", True)]
        assert rows[0].resource == "fleet_settings:entry_credentials", \
            "the same resource the capture form's promotion records"
        assert rows[0].details["username"] == "root"
        assert rows[0].details["label"] == "batch A"
        assert PW not in repr(rows)

    def test_it_is_encrypted_at_rest(self, client):
        """Against the raw row, not through `get()`, which would decrypt."""
        _as(_admin())
        _add(client)
        con = sqlite3.connect(client.db_path)
        try:
            raw = con.execute("SELECT value FROM fleet_settings WHERE key=?",
                              (ec.SETTING_KEY,)).fetchone()
        finally:
            con.close()
        assert raw is not None, "CONTROL: nothing was stored at all"
        assert PW not in raw[0]
        from admz import setting_crypto
        assert setting_crypto.looks_encrypted(raw[0])

    @pytest.mark.parametrize("overrides,tag", [
        ({"entry_username": ""}, "incomplete"),
        ({"entry_username": "   "}, "incomplete"),
        ({"entry_password": "", "confirm_entry_password": ""}, "incomplete"),
        ({"confirm_entry_password": PW + "x"}, "mismatch"),
        ({"entry_password": " " + PW, "confirm_entry_password": " " + PW},
         "surrounding-whitespace"),
    ])
    def test_a_bad_submission_is_refused_audited_and_stores_nothing(self, client, overrides, tag):
        _as(_admin())
        r = _add(client, **overrides)
        assert r.status_code == 200
        assert 'data-flash="error"' in r.text
        assert _listed() == []
        rows = _rows()
        assert [(x.action, x.success, x.error_message) for x in rows] == [
            ("entry_credential.add_refused", False, tag)]
        assert PW not in repr(rows) and PW not in r.text

    def test_a_label_past_the_limit_is_refused(self, client):
        from admz.api.routes.web import _ENTRY_LABEL_MAX_LENGTH

        _as(_admin())
        _add(client, entry_label="x" * (_ENTRY_LABEL_MAX_LENGTH + 1))
        assert _listed() == []
        assert [x.error_message for x in _rows()] == ["label-too-long"]
        _add(client, entry_label="x" * _ENTRY_LABEL_MAX_LENGTH)
        assert len(_listed()) == 1, "CONTROL: exactly at the limit is accepted"

    def test_the_username_is_trimmed_and_the_password_is_not(self, client):
        """A username is shown back on the page, so trimming it is visible; a
        password is not, so a padded one is refused (above), never changed. The
        audit row is checked as well as the list, because the library trims too
        and only the row proves the route did."""
        _as(_admin())
        _add(client, entry_username="  root  ")
        assert _listed() == [("root", PW, "batch A")]
        assert _rows()[0].details["username"] == "root"

    def test_a_duplicate_is_reported_and_changes_nothing(self, client):
        _as(_admin())
        _add(client)
        r = _add(client)
        assert 'data-flash="warning"' in r.text
        assert "already on the entry list" in " ".join(r.text.split())
        assert len(_listed()) == 1
        assert [x.action for x in _rows()] == ["entry_credential.added"], \
            "a no-op is not audited, as for a duplicate promotion"

    def test_the_cap_is_surfaced_and_the_form_withdrawn(self, client):
        for i in range(ec.MAX_STORED):
            ec.add_entry_credential(f"u{i}", f"zz-pw-{i}")
        _as(_admin())
        r = _add(client)
        assert 'data-flash="error"' in r.text
        assert len(_listed()) == ec.MAX_STORED
        assert [x.error_message for x in _rows()] == [ec.REFUSED_CAP]
        assert 'data-entry-add="full"' in r.text
        assert 'id="entry-credential-form"' not in r.text

    def test_the_legacy_pair_takes_a_slot_on_the_page_too(self, client):
        client.fs.set(ec.LEGACY_PASS_KEY, "zz-legacy-pw")
        for i in range(ec.MAX_STORED - 1):
            ec.add_entry_credential(f"u{i}", f"zz-pw-{i}")
        page = client.get("/fleet-settings").text
        assert 'data-entry-add="full"' in page

    def test_the_prompt_always_posture_refuses_and_the_form_is_withdrawn(self, client):
        client.fs.set(ec.PROMPT_ALWAYS_KEY, "true")
        _as(_admin())
        r = _add(client)
        assert 'data-flash="error"' in r.text
        assert ec.describe()["stored"] == []
        assert [x.error_message for x in _rows()] == [ec.REFUSED_PROMPT_ALWAYS]
        assert 'data-entry-add="posture"' in r.text
        assert 'id="entry-credential-form"' not in r.text

    @pytest.mark.parametrize("how", ["undecryptable", "not a list", "a half-written pair"])
    def test_a_list_that_cannot_be_read_in_full_is_never_rewritten(self, client, how):
        """Every write rewrites the whole list from what it read, and each of
        these reads as (partly) empty — so one submission would lose what the
        reader skipped. An undecryptable value is also one `setting_crypto`
        promises to leave alone, so that restoring the key recovers it."""
        from cryptography.fernet import Fernet

        if how == "undecryptable":
            client.fs._raw_set(ec.SETTING_KEY,
                               Fernet(Fernet.generate_key()).encrypt(b"[]").decode())
        elif how == "not a list":
            client.fs.set(ec.SETTING_KEY, '{"username": "u", "password": "zz-pw"}')
        else:
            client.fs.set(ec.SETTING_KEY, json.dumps(
                [{"username": "u0", "password": "zz-pw-0"}, {"username": "half"}]))
        before = client.fs._raw_get(ec.SETTING_KEY)
        _as(_admin())
        page = client.get("/fleet-settings").text
        assert 'data-entry-list="unreadable"' in page
        assert 'data-entry-add="unreadable"' in page
        r = _add(client)
        assert 'data-flash="error"' in r.text
        assert client.fs._raw_get(ec.SETTING_KEY) == before
        assert [x.error_message for x in _rows()] == [ec.REFUSED_UNREADABLE]

    def test_the_fields_do_not_invite_browser_autofill(self, client):
        """Browsers ignore `autocomplete="off"` on password fields and would
        fill in the operator's own saved login."""
        page = client.get("/fleet-settings").text
        form = page.split('id="entry-credential-form"')[1].split("</form>")[0]
        fields = re.findall(r'<input[^>]*type="password"[^>]*>', form)
        assert len(fields) == 2
        assert all('autocomplete="new-password"' in f for f in fields)


# --- removing ------------------------------------------------------------------


class TestRemoving:
    def test_the_row_shown_is_the_row_removed_and_the_rest_keep_their_order(self, client):
        _three()
        _as(_admin())
        r = _remove(client, 1, ec.list_revision())
        assert r.status_code == 200, r.text
        assert 'data-flash="success"' in r.text
        assert _listed() == [("u0", "zz-pw-0", "batch 0"), ("u2", "zz-pw-2", "batch 2")]

    def test_it_is_audited_from_the_stored_row_without_the_password(self, client):
        _three()
        _as(_admin())
        _remove(client, 1, ec.list_revision())
        rows = _rows()
        assert [(x.action, x.success) for x in rows] == [("entry_credential.removed", True)]
        assert rows[0].details["username"] == "u1"
        assert rows[0].details["label"] == "batch 1"
        assert rows[0].details["legacy_pair"] is False
        assert "zz-pw" not in repr(rows)

    def test_a_resubmitted_remove_does_not_take_a_second_credential(self, client):
        """Rows often look identical — the username defaults to `root` and the
        label is optional — and a browser reload resubmits the POST without the
        confirm dialog. By position alone the second submit would remove the
        OTHER credential, which by then sits where the first one was."""
        ec.add_entry_credential("root", "zz-pw-first")
        ec.add_entry_credential("root", "zz-pw-second")
        _as(_admin())
        shown = ec.list_revision()
        assert _remove(client, 0, shown).status_code == 200
        r = _remove(client, 0, shown)
        assert 'data-flash="error"' in r.text
        assert _listed() == [("root", "zz-pw-second", "")]
        assert [x.error_message for x in _rows() if not x.success] == [ec.REFUSED_STALE]

    def test_a_write_elsewhere_after_the_page_rendered_refuses_the_removal(self, client):
        """A second tab, the CLI, a promotion: anything that writes the list
        between the render and the submit."""
        ec.add_entry_credential("u0", "zz-pw-0", "batch 0")
        ec.add_entry_credential("u1", "zz-pw-1", "batch 1")
        _as(_admin())
        shown = ec.list_revision()
        ec.add_entry_credential("u2", "zz-pw-2", "batch 2")
        _remove(client, 0, shown)
        assert len(_listed()) == 3
        assert [x.error_message for x in _rows()] == [ec.REFUSED_STALE]

    def test_the_legacy_pair_appearing_after_the_render_refuses_the_removal(self, client):
        """Position 0 means the legacy pair once `default_password` is set — so a
        page rendered before something set it must not delete the legacy
        settings when it meant the list's first entry."""
        ec.add_entry_credential("root", "zz-pw-0", ec.LEGACY_LABEL)
        _as(_admin())
        shown = ec.list_revision()
        client.fs.set(ec.LEGACY_PASS_KEY, "zz-legacy-pw")
        _remove(client, 0, shown)
        assert client.fs.get(ec.LEGACY_PASS_KEY) == "zz-legacy-pw"
        assert ("root", "zz-pw-0", ec.LEGACY_LABEL) in _listed()
        assert [x.error_message for x in _rows()] == [ec.REFUSED_STALE]

    @pytest.mark.parametrize("position", ["one", "", "-1", "7"])
    def test_a_position_that_does_not_exist_removes_nothing(self, client, position):
        _three()
        _as(_admin())
        r = _remove(client, position, ec.list_revision())
        assert r.status_code == 200
        assert 'data-flash="error"' in r.text
        assert len(_listed()) == 3
        assert [(x.action, x.error_message) for x in _rows()] == [
            ("entry_credential.remove_refused", ec.REFUSED_STALE)]

    def test_a_forged_revision_removes_nothing(self, client):
        _three()
        _as(_admin())
        _remove(client, 0, "0" * 32)
        assert len(_listed()) == 3
        assert [x.error_message for x in _rows()] == [ec.REFUSED_STALE]

    def test_the_legacy_pair_is_removed_by_deleting_its_settings(self, client):
        client.fs.set(ec.LEGACY_USER_KEY, "operator")
        client.fs.set(ec.LEGACY_PASS_KEY, "zz-legacy-pw")
        ec.add_entry_credential("u0", "zz-pw-0", "batch 0")
        _as(_admin())
        r = _remove(client, 0, ec.list_revision())
        assert r.status_code == 200, r.text
        assert client.fs.get(ec.LEGACY_PASS_KEY) is None
        assert client.fs.get(ec.LEGACY_USER_KEY) is None
        assert _listed() == [("u0", "zz-pw-0", "batch 0")]
        rows = _rows()
        assert rows[0].details["legacy_pair"] is True
        assert rows[0].details["username"] == "operator"
        assert "zz-legacy-pw" not in repr(rows)

    def test_positions_after_the_legacy_pair_are_offset_by_it(self, client):
        client.fs.set(ec.LEGACY_PASS_KEY, "zz-legacy-pw")
        ec.add_entry_credential("u0", "zz-pw-0", "batch 0")
        _as(_admin())
        _remove(client, 1, ec.list_revision())
        assert client.fs.get(ec.LEGACY_PASS_KEY) == "zz-legacy-pw"
        assert ec.describe()["stored"] == [{"username": "root", "label": ec.LEGACY_LABEL}]

    def test_removal_is_allowed_under_the_prompt_always_posture(self, client):
        """It narrows what ADMZ tries; only widening is refused."""
        ec.add_entry_credential("u0", "zz-pw-0", "batch 0")
        client.fs.set(ec.PROMPT_ALWAYS_KEY, "true")
        _as(_admin())
        _remove(client, 0, ec.list_revision())
        assert ec.describe()["stored"] == []

    def test_each_row_carries_its_position_and_the_revision_and_no_password(self, client):
        _three()
        page = client.get("/fleet-settings").text
        forms = re.findall(REMOVE_FORM, page, flags=re.S)
        assert len(forms) == 3
        revision = ec.list_revision()
        for i, form in enumerate(forms):
            assert f'name="position" value="{i}"' in form
            assert f'name="revision" value="{revision}"' in form
            assert "zz-pw" not in form

    def test_a_remove_button_works_as_rendered(self, client):
        """End to end: the token the page renders is the one the route checks."""
        _three()
        _as(_admin())
        second = re.findall(REMOVE_FORM, client.get("/fleet-settings").text, flags=re.S)[1]
        position = re.search(r'name="position" value="([^"]*)"', second).group(1)
        revision = re.search(r'name="revision" value="([^"]*)"', second).group(1)
        assert _remove(client, position, revision).status_code == 200
        assert [u for u, _, _ in _listed()] == ["u0", "u2"]

    def test_a_render_that_migrated_a_value_still_removes(self, client):
        """Reading a legacy-plaintext secret rewrites it encrypted, which changes
        the stored state. The page takes its token after its own reads, so the
        buttons of that very render still work."""
        ec.add_entry_credential("u0", "zz-pw-0", "batch 0")
        client.fs._raw_set(ec.LEGACY_PASS_KEY, "zz-legacy-plain")
        _as(_admin())
        page = client.get("/fleet-settings").text
        assert client.fs._raw_get(ec.LEGACY_PASS_KEY) != "zz-legacy-plain", \
            "CONTROL: the render migrated the legacy value"
        revision = re.search(r'name="revision" value="([^"]*)"', page).group(1)
        assert _remove(client, 1, revision).status_code == 200
        assert _listed() == [("root", "zz-legacy-plain", ec.LEGACY_LABEL)]


# --- what the page marks and counts --------------------------------------------


class TestThePageMarksWhatIsActuallyTried:
    def test_of_two_identical_credentials_only_the_first_is_marked_tried(self, client):
        """An exact duplicate is tried once. Matched on username and label, the
        page marked the first two rows tried and the third — the only other
        credential actually put to a device — "never tried", inviting its
        removal."""
        client.fs.set(ec.SETTING_KEY, json.dumps([
            {"username": "root", "password": "zz-pw-1"},
            {"username": "root", "password": "zz-pw-1"},
            {"username": "root", "password": "zz-pw-2"},
        ]))
        page = client.get("/fleet-settings").text
        assert re.findall(r'data-entry="(tried|never-tried)"', page) == [
            "tried", "never-tried", "tried"]

    def test_the_break_glass_attempt_is_named_not_counted_as_an_entry(self, client):
        """ADR-0068 appends ADMZ's break-glass root password to every pass.
        Counted as an entry, the page said "4 (at most 3)" beside a full list."""
        for i in range(ec.MAX_STORED):
            ec.add_entry_credential(f"u{i}", f"zz-pw-{i}")
        client.fs.set("fleet_root_password", "BreakGlass-entry-gui-1")
        page = " ".join(client.get("/fleet-settings").text.split())
        assert (f"{ec.MAX_STORED} (at most {ec.MAX_ATTEMPTS_PER_PASS}), "
                "then ADMZ's break-glass root password") in page
        assert page.count('data-entry="tried"') == ec.MAX_STORED

    def test_without_a_break_glass_password_it_is_not_mentioned(self, client):
        ec.add_entry_credential("u0", "zz-pw-0")
        page = " ".join(client.get("/fleet-settings").text.split())
        assert f"1 (at most {ec.MAX_ATTEMPTS_PER_PASS})" in page
        assert "then ADMZ's break-glass root password" not in page
