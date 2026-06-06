"""opticscontrol.cgi:setMagnification builds a VAPIX-correct body, and the
executor's placeholder engine supports defaults.

Regression for the live-testing bug: a chat user asked to "zoom in" on a
Q3538-SLVE. The catalog modeled the body as
``params.optics[0] = {opticsId, magnification}`` but ``opticsId`` had no
default, so when the LLM supplied only a magnification the optics entry was
emitted WITHOUT opticsId and the device rejected it with
``2103 Required parameter missing``. Separately the LLM guessed a magnification
of 5000 (it had no parameter docs); the real value is a float in
[1.0, maxMagnification] (≈2.03 on that lens).

Fix: a placeholder default syntax ``{opticsId=0}`` in the body template (so the
single-optics id is present without the caller supplying it, but stays
overridable), plus a ``parameters`` block documenting the magnification range.

These tests build the request body the executor would POST (no network) and
assert the shape, plus unit-test the default-placeholder engine directly.

Reference: docs/vapix-docs/vapix-network-video-optics-control.md
"""

from __future__ import annotations

import pytest

import axis_api_atlas
from axis_api_atlas.catalog.loader import CatalogLoader
from admz.executor.vapix import VapixExecutor

CATALOG = axis_api_atlas.default_data_path()


@pytest.fixture(scope="module")
def loader():
    return CatalogLoader(CATALOG)


@pytest.fixture(scope="module")
def ex():
    # build_request / _resolve_template are pure (no network / auth state).
    return VapixExecutor.__new__(VapixExecutor)


def _body(loader, ex, op_id, params):
    op = loader.get_operation("vapix", op_id)
    assert op is not None, f"{op_id} missing from catalog"
    return ex.build_request(op.to_executor_dict(), params).json_body


# ---------------------------------------------------------------------------
# setMagnification body construction
# ---------------------------------------------------------------------------


class TestSetMagnification:
    def test_opticsid_defaults_to_zero(self, loader, ex):
        """The bug: only a magnification was supplied, so opticsId went missing
        and the device returned 2103. opticsId must default to '0'."""
        body = _body(loader, ex, "opticscontrol.cgi:setMagnification", {
            "magnification": 1.5,
        })
        assert body == {
            "apiVersion": "1.0",
            "method": "setMagnification",
            "params": {"optics": [{"opticsId": "0", "magnification": 1.5}]},
        }

    def test_optics_entry_always_has_opticsid(self, loader, ex):
        body = _body(loader, ex, "opticscontrol.cgi:setMagnification", {
            "magnification": 2.0,
        })
        entry = body["params"]["optics"][0]
        assert "opticsId" in entry, "optics entry must carry opticsId (else 2103)"
        assert entry["opticsId"] == "0"

    def test_opticsid_is_overridable(self, loader, ex):
        body = _body(loader, ex, "opticscontrol.cgi:setMagnification", {
            "magnification": 1.8, "opticsId": "1",
        })
        assert body["params"]["optics"][0]["opticsId"] == "1"

    def test_magnification_is_float_not_string(self, loader, ex):
        body = _body(loader, ex, "opticscontrol.cgi:setMagnification", {
            "magnification": "1.5",  # LLM may pass a string
        })
        mag = body["params"]["optics"][0]["magnification"]
        assert isinstance(mag, float) and mag == 1.5

    def test_notes_document_real_range(self, loader):
        """The LLM guessed 1-9999 because the op had no surfaced param docs.
        ``notes`` (the channel the resolver actually surfaces to the LLM) must
        steer it to the float zoom-factor range and warn off big numbers."""
        op = loader.get_operation("vapix", "opticscontrol.cgi:setMagnification")
        notes = (op.notes or "").lower()
        assert notes, "setMagnification must carry notes guiding the LLM"
        assert "maxmagnification" in notes or "wide" in notes
        assert "factor" in notes  # zoom FACTOR, not a percentage / step count
        assert "0" in notes and "opticsid" in notes  # opticsId default documented


# ---------------------------------------------------------------------------
# Placeholder default-syntax engine ({name=default} / {name:type=default})
# ---------------------------------------------------------------------------


class TestOpticsControlFamilyDefaultsOpticsId:
    """All opticscontrol ops that take an optics[] entry had the same missing
    opticsId default — they'd 2103 if the LLM didn't supply opticsId. Every one
    must now default opticsId to '0'."""

    def test_perform_autofocus_defaults_opticsid(self, loader, ex):
        body = _body(loader, ex, "opticscontrol.cgi:performAutofocus", {})
        assert body["params"]["optics"][0] == {"opticsId": "0"}

    def test_set_focus_defaults_opticsid(self, loader, ex):
        body = _body(loader, ex, "opticscontrol.cgi:setFocus", {"position": 0.5})
        assert body["params"]["optics"][0]["opticsId"] == "0"
        assert body["params"]["optics"][0]["position"] == 0.5

    def test_reset_defaults_opticsid(self, loader, ex):
        body = _body(loader, ex, "opticscontrol.cgi:reset", {"zoom": True, "focus": True})
        entry = body["params"]["optics"][0]
        assert entry["opticsId"] == "0"
        assert entry["zoom"] is True and entry["focus"] is True


class TestResolveTemplateDefaults:
    def test_string_default_used_when_absent(self, ex):
        assert ex._resolve_template("{opticsId=0}", {}) == "0"

    def test_default_overridden_by_param(self, ex):
        assert ex._resolve_template("{opticsId=0}", {"opticsId": "2"}) == "2"

    def test_typed_default_is_coerced(self, ex):
        assert ex._resolve_template("{mag:float=1.0}", {}) == 1.0
        assert isinstance(ex._resolve_template("{mag:float=1.0}", {}), float)

    def test_no_default_still_omits(self, ex):
        # Backward-compat: a typed placeholder with no default + no value -> None
        assert ex._resolve_template("{mag:float}", {}) is None

    def test_plain_placeholder_backward_compat(self, ex):
        assert ex._resolve_template("{name}", {"name": "x"}) == "x"
        assert ex._resolve_template("{name}", {}) is None

    def test_typed_placeholder_backward_compat(self, ex):
        assert ex._resolve_template("{n:int}", {"n": "5"}) == 5

    def test_dict_walk_drops_only_defaultless_missing(self, ex):
        tmpl = {"opticsId": "{opticsId=0}", "magnification": "{magnification:float}"}
        # magnification missing + no default -> dropped; opticsId default kept
        assert ex._resolve_template(tmpl, {}) == {"opticsId": "0"}
