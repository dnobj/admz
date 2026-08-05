"""Recipient secrets must never reach the confirm-session payload (#194).

`param_choices` is serialised verbatim into `confirm_sessions.action_json` with no
redaction, and a *completed* session is never cleaned up (#266) — so a credential
landing there stays on disk indefinitely, in the same SQLite file as the device
registry, while the audit log looks clean (`is_sensitive_key` masks it there).

Two paths defeated the old `param_choices.pop(p.name)` strip, which was exact and
case-sensitive:

* `{"Password": ...}` — the strip matched only the SOAP name, exactly, while the
  atlas resolver matches name OR ui_label case-insensitively and the tool schema
  advertises "keyed by the param's label or SOAP name". Narrower on two axes than
  both the thing that consumes the value and the thing that invites it.
* `proxy_password` / `pop_password` — advertised as capture-needed by
  `capture_param_names`, never members of `primary_recipient_secret_fields`, so
  never popped at all, and with no capture form to collect them.

These tests execute the REAL `_create_action_rule` (bound to a stub `self`, so the
MCP server never has to be constructed) and read the REAL confirm store back.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from types import SimpleNamespace as NS

import pytest


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _param(name, ui_label=None, capture_note=""):
    return NS(name=name, ui_label=ui_label, capture_note=capture_note)


# An HTTP-notification-shaped action: the primary pair plus the secondary
# credential that has no capture channel. This mirrors the shipped survey data —
# `password`, `proxy_password` and `pop_password` are the only password-family
# param names across every surveyed model.
ACTION = NS(soap_params=[_param("login"), _param("password"),
                         _param("proxy_password"), _param("message")])


# ── GH #336 item 2: param_is_secret now uses the canonical vocabulary ────────
class TestParamIsSecretUsesCanonicalVocabulary:
    """param_is_secret used to check a private _SECRET_HINTS = ("password",
    "passwd") tuple, narrower than admz.redact.is_sensitive_key. Not
    reachable against any currently-surveyed device (see
    test_union_keeps_what_the_old_exact_strip_removed and the ACTION fixture
    above — every real recipient credential is password-family), but a
    predicate whose correctness depends on which devices happen to be
    surveyed is not a control. Pins both directions."""

    def test_previously_missed_spellings_are_now_recognized(self):
        from admz.rules import capabilities as C
        for name in ("secret", "token", "api_key", "apikey", "pwd", "pass",
                     "webhook_secret", "api_token", "bearer_token",
                     "PWD", "old_pass"):
            assert C.param_is_secret(_param(name)) is True, name

    def test_ordinary_names_are_still_not_swept_up(self):
        """The other direction — otherwise 'we widened it' is trivially
        true for a predicate that now flags everything."""
        from admz.rules import capabilities as C
        for name in ("message", "topic", "device_id", "bypass", "passive",
                     "compass", "passthrough"):
            assert C.param_is_secret(_param(name)) is False, name

    def test_capture_note_still_wins_regardless_of_name(self):
        from admz.rules import capabilities as C
        assert C.param_is_secret(_param("message", capture_note="flagged")) is True

    def test_empty_name_is_not_secret(self):
        from admz.rules import capabilities as C
        assert C.param_is_secret(_param("")) is False


# ── the matcher ──────────────────────────────────────────────────────────────
class TestSecretChoiceKeys:
    def test_matches_the_way_the_atlas_resolver_does(self):
        from admz.rules import capabilities as C
        assert C.secret_choice_keys(ACTION, {"password": "x"}) == ["password"]
        assert C.secret_choice_keys(ACTION, {"Password": "x"}) == ["Password"]
        assert C.secret_choice_keys(ACTION, {"PROXY_PASSWORD": "x"}) == ["PROXY_PASSWORD"]

    def test_leaves_ordinary_params_alone(self):
        """Rejecting a param that is not a secret is its own failure mode."""
        from admz.rules import capabilities as C
        assert C.secret_choice_keys(ACTION, {"message": "hi"}) == []
        assert C.secret_choice_keys(ACTION, {}) == []
        assert C.secret_choice_keys(None, {"password": "x"}) == []

    def test_union_keeps_what_the_old_exact_strip_removed(self):
        """`username` is in the primary pair but matches no hint — widening to
        the advertised set alone would have started letting it through."""
        from admz.rules import capabilities as C
        a = NS(soap_params=[_param("username"), _param("password")])
        assert set(C.sensitive_param_names(a)) == {"username", "password"}
        assert C.secret_choice_keys(a, {"Username": "bob"}) == ["Username"]

    def test_ui_label_keys_are_covered(self):
        """Not reachable in today's corpus — no password-family param defines a
        ui_label — but the resolver honours labels, so the guard must too."""
        from admz.rules import capabilities as C
        a = NS(soap_params=[_param("password", ui_label="Mail password")])
        assert C.secret_choice_keys(a, {"mail PASSWORD": "x"}) == ["mail PASSWORD"]


# ── the real tool path ───────────────────────────────────────────────────────
@pytest.fixture
def server(monkeypatch):
    """A stub `self` for the real `_create_action_rule`, so the MCP server (whose
    constructor is unrelated to this defect) never has to be built."""
    from admz.rules import capabilities as C

    monkeypatch.setattr(C, "build", lambda *a, **k: NS(available=True, error=None))
    monkeypatch.setattr(C, "action_for", lambda *a, **k: ACTION)
    monkeypatch.setattr(C, "condition_for", lambda *a, **k: NS(topic="tns1:X"))
    monkeypatch.setattr(C, "device_applications", lambda *a, **k: [])
    monkeypatch.setattr(C, "check_condition_publisher", lambda *a, **k: None)
    monkeypatch.setattr(C, "condition_caution", lambda *a, **k: None)
    monkeypatch.setattr(C, "describe_rule", lambda *a, **k: "create a rule")
    return NS(
        registry=NS(device_exists=lambda d: True,
                    get_device_info=lambda d: {"model": "C1710", "nickname": "Cam"}),
        git_repo=None,
    )


def _call(server, param_choices):
    from admz.mcp.server import ADMZMCPServer
    return _run(ADMZMCPServer._create_action_rule(
        server, device_id="d1", condition_id="c1",
        action_token="com.axis.action.fixed.notification.http",
        param_choices=param_choices, rule_name="R"))


def _rows():
    from admz.api.confirm_store import confirm_store
    # #258: schema creation moved from __init__ into _connect(). This reads
    # with raw sqlite3, bypassing the store, so realise the tables first.
    confirm_store._ensure_table()
    conn = sqlite3.connect(confirm_store._db_path)
    try:
        return [r[0] for r in conn.execute(
            "SELECT action_json FROM confirm_sessions").fetchall()]
    finally:
        conn.close()


class TestFailsClosed:
    def test_primary_password_is_rejected_naming_the_key(self, server):
        before = len(_rows())
        out = _call(server, {"Password": "hunter2", "message": "hi"})
        # The DEFECT first, so a regression fails here rather than on the error
        # shape: pre-fix a session row is created and holds the password verbatim.
        assert "hunter2" not in "\n".join(_rows())
        # Rejected, not silently dropped — no row was created at all.
        assert len(_rows()) == before
        assert out["success"] is False
        assert out["rejected_params"] == ["Password"]
        assert "Password" in out["error"]

    def test_proxy_password_is_rejected_and_the_advice_is_honest(self, server):
        before = len(_rows())
        out = _call(server, {"proxy_password": "sekrit"})
        assert "sekrit" not in "\n".join(_rows())     # the defect, first
        assert len(_rows()) == before
        assert out["success"] is False
        assert out["rejected_params"] == ["proxy_password"]
        # proxy_* has NO capture form, so "use the secure form" would be a lie.
        assert "no capture form" in out["error"]

    def test_every_secret_is_named_not_just_the_first(self, server):
        out = _call(server, {"Password": "a", "proxy_password": "b", "message": "hi"})
        assert out["rejected_params"] == ["Password", "proxy_password"]


class TestLegitimateFlowSurvives:
    """Anti-vacuity: "no secret in the payload" is trivially true if nothing is
    stored at all, or if the capture flow is broken. These pin both."""

    def test_ordinary_params_still_reach_the_stored_payload(self, server):
        out = _call(server, {"message": "hello"})
        assert out.get("needs_recipient_credentials") is True   # capture flow armed
        stored = json.loads(_rows()[-1])

        # (3) a non-secret param still flows — deleting param_choices wholesale
        # would pass "no secret present", so this is the guard against that.
        assert stored["param_choices"] == {"message": "hello"}

        # (4) secret_fields survives UN-redacted. `redact_structure` masks it to
        # '***' (the key contains "secret"), and rule_capture.py reads it back to
        # render the capture form — so a blanket redaction of this payload would
        # break the very mechanism #194 protects. This test fails if anyone adds
        # one.
        assert [f["name"] for f in stored["secret_fields"]] == ["login", "password"]
        assert stored["secret_fields"][1]["kind"] == "password"

    def test_no_credential_appears_anywhere_in_the_stored_payloads(self, server):
        _call(server, {"message": "hello"})
        _call(server, {"Password": "hunter2-PRIMARY"})       # rejected
        _call(server, {"proxy_password": "sekrit-PROXY"})    # rejected
        blob = "\n".join(_rows())
        assert "hunter2-PRIMARY" not in blob
        assert "sekrit-PROXY" not in blob
        assert "hello" in blob                                # ...and it isn't empty
