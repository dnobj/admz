"""Structural guard: every system-prompt section builder must be classified
as fenced or trusted, and the classification must match what actually
happens (#320's design question).

The background: #167 (device roster), #191 (demos section), and #320
(inference proposals) are three independent instances of the same miss — a
new admz/chatbot/context.py builder rendered device/user-supplied free text
into the system prompt, and nobody remembered to fence it, until an audit
loop found each one separately. That is exactly the failure shape
admz/setting_policy.py documents for fleet-setting keys: three independent
enumeration attempts at "which keys are sensitive" found 8, 10, and 18 keys,
each missing ones the others found — the fix there was a scanner test that
enumerates from *behavior* (every call site) and cross-checks against a
closed, exhaustive classification, so a new site can't go unclassified
silently.

This file is that scanner, applied to admz.chatbot.context's section
builders instead of fleet-setting keys:

  - FENCED_SECTIONS / TRUSTED_SECTIONS together must equal EVERY ``build_*``
    function context.py defines — not a subset. Add a function, forget to
    add it to either registry, and ``test_every_section_builder_is_classified``
    fails immediately, in CI, before merge — not months later in an audit.
  - The classification is then checked BEHAVIORALLY (not by reading source
    text, which is fragile): a section declared FENCED must actually come
    back wrapped in system_prompt.py's fence when given a marker payload; a
    section declared TRUSTED must NOT.

This does not make a new section safe automatically — someone still has to
decide, correctly, which bucket it belongs in. What it removes is the
ability to forget the decision entirely and have nothing notice.

Known limitation, stated rather than papered over: this scanner only
reaches admz/chatbot/context.py's own top-level ``build_*`` functions.
``build_module_prompt_sections`` delegates to per-module prompt
contributors (admz/modules/*/__init__.py, ADR-0039) that this scanner
cannot see inside of — if a module ever renders device-supplied data
through its own prompt section, it needs its own fencing and its own
guard, not coverage from this file.
"""

from __future__ import annotations

import inspect

import pytest

from admz.chatbot import context as ctx_module
from admz.chatbot.system_prompt import build_system_prompt

#: Section builders whose output can contain device-, demo-, or
#: model-written free text and MUST be wrapped in system_prompt.py's
#: _fence() before insertion. Maps function name -> (build_system_prompt
#: kwarg, fence label used in system_prompt.py).
FENCED_SECTIONS = {
    "build_device_roster": ("device_roster", "DEVICE ROSTER DATA"),
    "build_demos_section": ("demos_section", "DEMOS DATA"),
    "build_inference_section": ("inference_section", "INFERENCE PROPOSALS DATA"),
}

#: Section builders whose output is ADMZ's own computed narration or a
#: module's own declared guidance — never raw device/user free text — and
#: are deliberately NOT fenced. Maps function name -> build_system_prompt
#: kwarg, with the one-line reason recorded inline below.
TRUSTED_SECTIONS = {
    # Registry-declared capability id/description/env-var (admz/capabilities.py) —
    # a fixed, code-defined table, not device-supplied text.
    "build_capabilities_section": "capabilities_section",
    # Catalog operation_ids resolved through the resolver — structured
    # identifiers, not free text a device or model chose.
    "build_common_ops_reference": "common_ops",
    # Module-authored guidance (ADR-0039) — see the module docstring's
    # "known limitation" note: this scanner does not reach inside it.
    "build_module_prompt_sections": "module_sections",
}


def _all_section_builders():
    """Every top-level ``build_*`` function admz.chatbot.context defines."""
    return {
        name for name, _fn in inspect.getmembers(ctx_module, inspect.isfunction)
        if name.startswith("build_") and _fn.__module__ == ctx_module.__name__
    }


class TestClassificationIsExhaustive:
    def test_every_section_builder_is_classified(self):
        """The guard: a new build_* function that is in neither registry
        fails this test, rather than shipping unfenced until an audit
        finds it (the #167/#191/#320 pattern)."""
        known = set(FENCED_SECTIONS) | set(TRUSTED_SECTIONS)
        actual = _all_section_builders()
        missing = actual - known
        assert not missing, (
            f"{missing} render into the system prompt but are not classified "
            "in tests/test_prompt_fencing_completeness.py. If it can render "
            "device/demo/model-supplied free text, add it to FENCED_SECTIONS "
            "and wrap it with _fence() in system_prompt.py. Otherwise add it "
            "to TRUSTED_SECTIONS with a one-line reason."
        )

    def test_registries_do_not_overlap(self):
        overlap = set(FENCED_SECTIONS) & set(TRUSTED_SECTIONS)
        assert not overlap, f"{overlap} classified as both fenced and trusted"

    def test_no_stale_entries(self):
        """The reverse miss: a registry entry for a function that no longer
        exists (renamed/removed) would silently stop meaning anything."""
        known = set(FENCED_SECTIONS) | set(TRUSTED_SECTIONS)
        actual = _all_section_builders()
        stale = known - actual
        assert not stale, f"{stale} listed here but no longer exist in context.py"


class TestFencedSectionsAreActuallyFenced:
    """Behavioral check, not source-text parsing: a section declared FENCED
    must come back wrapped in a real fence when build_system_prompt is
    handed a marker payload for it."""

    @pytest.mark.parametrize("kwarg,label", FENCED_SECTIONS.values())
    def test_marker_payload_comes_back_fenced(self, kwarg, label):
        marker = "distinctive-marker-xyz"
        prompt = build_system_prompt("alice", **{kwarg: marker})
        assert f"<<<UNTRUSTED DATA - {label} -" in prompt
        assert f"<<<END UNTRUSTED DATA - {label} -" in prompt
        assert marker in prompt  # value still present, just fenced


class TestTrustedSectionsAreNotFenced:
    """The opposite check: a section declared TRUSTED must render its
    content WITHOUT a fence wrapper — proving the classification isn't
    just asserted but actually matches system_prompt.py's behavior."""

    @pytest.mark.parametrize("kwarg", TRUSTED_SECTIONS.values())
    def test_marker_payload_comes_back_unfenced(self, kwarg):
        marker = "distinctive-marker-xyz"
        prompt = build_system_prompt("alice", **{kwarg: marker})
        assert marker in prompt
        assert "<<<UNTRUSTED DATA" not in prompt
        assert "<<<END UNTRUSTED DATA" not in prompt
