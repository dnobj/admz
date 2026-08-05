"""Unit tests for admz.executor.vapix.secret_param_names (#334).

execute_gated_operation uses this to decide which params of a VAPIX
operation are catalog-declared secret-shaped (e.g. a new device password)
and must be stripped from a confirm session before it is ever persisted.
It is deliberately a narrow, EXACT-match vocabulary scoped to the catalog's
own placeholder names — NOT a reuse of admz.redact.is_sensitive_key's
substring match, because the catalog uses "*Token"-suffixed and bare
{token}/{Token} placeholders throughout for legitimate non-secret resource
identifiers (PTZ presets, relay/input references, ONVIF door IDs). The
required negative pin (finding 6) lives here: a {PresetToken}-shaped param
must never be flagged.
"""

from __future__ import annotations

from admz.executor.vapix import (
    _WHOLE_VALUE_PLACEHOLDER_RE,
    secret_param_names,
)


class _Op:
    """A minimal stand-in for an axis_api_atlas Operation — only .request
    is read by secret_param_names."""

    def __init__(self, request):
        self.request = request


# --- the catalog's two known secret-shaped placeholders --------------------


def test_pwdgrp_cgi_password_param_recognised_by_key_and_by_placeholder():
    """pwdgrp.cgi:update-user's template is {"pwd": "{password}"} — the
    wire key ("pwd") and the placeholder name ("password") are DIFFERENT
    strings, and _build_legacy_cgi's fallback loop accepts a caller-supplied
    params key spelled either way, so both must be recognised."""
    op = _Op({"query": {"action": "update", "user": "{username}", "pwd": "{password}"}})
    assert secret_param_names(op, {"pwd": "x", "password": "y", "user": "root"}) == {
        "pwd", "password",
    }
    # A caller that only supplied one spelling only gets that one flagged —
    # this function reports which of THIS CALL's params are secret-shaped,
    # not the full candidate set.
    assert secret_param_names(op, {"pwd": "x", "user": "root"}) == {"pwd"}
    assert secret_param_names(op, {"user": "root"}) == set()


def test_networkshare_add_cgi_pass_param_recognised():
    """networkshare-add.cgi's template uses {"pass": "{pass}"} — key and
    placeholder name are the SAME string here, unlike pwdgrp.cgi."""
    op = _Op({"body": {"host": "{host}", "pass": "{pass}"}})
    assert secret_param_names(op, {"host": "nas", "pass": "secret"}) == {"pass"}


def test_is_case_insensitive_on_the_placeholder_name():
    op = _Op({"query": {"pwd": "{Password}"}})
    assert secret_param_names(op, {"pwd": "x"}) == {"pwd"}


# --- the required negative pin: catalog "*Token" placeholders ---------------


def test_preset_token_placeholder_is_not_treated_as_secret():
    """#334 finding 6, the hard requirement: {PresetToken} is a PTZ preset
    resource identifier, not a credential. A substring match on "token"
    (admz.redact.is_sensitive_key's rule, correct for free-form setting
    keys) would misfire here; this function must not."""
    op = _Op({"query": {"preset": "{PresetToken}"}})
    assert secret_param_names(op, {"preset": "preset-1"}) == set()


def test_relay_input_video_source_token_placeholders_are_not_secret():
    op = _Op({
        "query": {
            "relay": "{RelayToken}",
            "input": "{InputToken}",
            "source": "{VideoSourceConfigurationToken}",
        }
    })
    params = {"relay": "r1", "input": "i1", "source": "v1"}
    assert secret_param_names(op, params) == set()


def test_bare_token_placeholder_is_not_secret():
    """ONVIF door-control ops (AccessDoor, BlockDoor, LockDoor, ...) key a
    door by a bare {Token}/{token} placeholder — identifies WHICH door, not
    a credential."""
    op = _Op({"body": {"DoorToken": "{Token}"}})
    assert secret_param_names(op, {"DoorToken": "door-1"}) == set()

    op2 = _Op({"body": {"door": "{token}"}})
    assert secret_param_names(op2, {"door": "door-1"}) == set()


# --- shape / degradation ----------------------------------------------------


def test_dict_shaped_operation_accepted():
    """Callers/tests that only have the executor-dict shape (not a real
    axis_api_atlas Operation) are supported too."""
    op = {"id": "pwdgrp.cgi:update-user", "request": {"query": {"pwd": "{password}"}}}
    assert secret_param_names(op, {"pwd": "x"}) == {"pwd"}


def test_operation_with_no_request_attribute_degrades_to_empty_set():
    """A _FakeOp-style test double with no .request at all must not raise —
    it degrades to 'nothing to strip', same as every other malformed shape
    this function tolerates."""
    class _NoRequest:
        pass

    assert secret_param_names(_NoRequest(), {"password": "x"}) == set()


def test_non_dict_request_degrades_to_empty_set():
    op = _Op("not-a-dict")
    assert secret_param_names(op, {"password": "x"}) == set()


def test_embedded_placeholder_is_not_matched():
    """Only WHOLE-VALUE placeholders are handled — a stated, known limit,
    not a silent gap: no operation in the pinned catalog embeds a secret
    placeholder inside a larger string today."""
    op = _Op({"query": {"pwd": "prefix-{password}-suffix"}})
    assert secret_param_names(op, {"pwd": "x"}) == set()


def test_empty_params_and_empty_request_are_both_safe():
    assert secret_param_names(_Op({}), {}) == set()
    assert secret_param_names(_Op({"query": {}, "body": {}}), {"pwd": "x"}) == set()


# --- regex consistency with VapixExecutor._resolve_template ----------------


def test_whole_value_placeholder_regex_matches_resolve_template_semantics():
    """_WHOLE_VALUE_PLACEHOLDER_RE is a separate constant from
    VapixExecutor._resolve_template's own inline regex (duplicated so this
    stays a plain function needing no VapixExecutor instance) and must
    agree with it on every shape _resolve_template itself handles, matched
    with fullmatch the same way."""
    import re
    resolve_template_re = re.compile(r"\{(\w+)(?::(\w+))?(?:=([^{}]*))?\}")

    samples_that_match = [
        "{password}", "{PresetToken}", "{name:type}", "{name=default}",
        "{name:type=default}", "{a}", "{A1}",
    ]
    samples_that_dont_match = [
        "prefix-{password}", "{password}-suffix", "{pass word}", "{}",
        "plain string", "",
    ]
    for s in samples_that_match:
        assert bool(_WHOLE_VALUE_PLACEHOLDER_RE.fullmatch(s)) is True, s
        assert bool(resolve_template_re.fullmatch(s)) is True, s
    for s in samples_that_dont_match:
        assert bool(_WHOLE_VALUE_PLACEHOLDER_RE.fullmatch(s)) is False, s
        assert bool(resolve_template_re.fullmatch(s)) is False, s
