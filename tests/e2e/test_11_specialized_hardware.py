"""Specialized-hardware operation selection — the LLM must pick the
*right* VAPIX API for the device in front of it.

Regression for a live-testing bug: a user asked

    "lets make the D4200 flash white for 30 seconds"

against an AXIS D4200-VE (a network strobe siren), and the LLM chose
``findmydevice.cgi:find`` (the locate-this-unit blink) instead of
``siren_and_light.cgi:start`` (the strobe-siren API that actually
drives colored light patterns).

Root cause (fixed in admz/catalog/resolver.py): the word "flash" had
no intent synonym, so the resolver never surfaced the siren_and_light
operations as candidates — the bare word "device" fell through to the
``find-device`` task. With "flash"/"flash white"/"strobe light" now
mapped to ``control-siren`` (+ ``control-lights``), the proper API is
a candidate and the model can select it.

The deterministic version of this guard lives in
tests/test_resolver_synonyms.py (no API cost). This file is the
operator-facing, real-Gemini drive-through.

Device: AXIS D4200-VE, device_id B8A44FFC2B16 (homelab). If that
device isn't in your registry the assertions still hold — the LLM
resolves the operation from the catalog by intent, not from live
device state.
"""

from __future__ import annotations


# The homelab strobe siren the live bug was found on.
D4200_DEVICE_ID = "B8A44FFC2B16"


def _asserts_siren_and_light(result):
    """Shared assertion: the response names the siren-and-light API and
    does NOT recommend findmydevice as the way to flash a strobe siren.
    Tolerant of the underscore/hyphen/space spellings Gemini uses."""
    siren_named = result.contains_any(
        "siren_and_light", "siren and light", "siren-and-light",
    )
    assert siren_named, (
        f"LLM did not surface the siren_and_light API for a strobe "
        f"siren — resolver synonym ('flash' -> control-siren) or the "
        f"d42 knowledge hint may have regressed. {result!r}"
    )
    # Belt-and-suspenders: it must not have recommended findmydevice:find
    # as the flashing mechanism (siren_named already true, so this only
    # trips if the model named BOTH and led with findmydevice).
    assert "findmydevice.cgi:find" not in result.lower, (
        f"LLM still cited findmydevice.cgi:find to flash a strobe "
        f"siren — the disambiguation hint isn't steering it. {result!r}"
    )


def test_flash_strobe_siren_selects_siren_and_light(chat, cost_recorder):
    """The live-bug question, asked as an identify-don't-execute query
    (the device is often offline; we're testing operation *selection*,
    not reachability). Names the model so the device-type cue is strong.
    """
    result = chat(
        f"I have device {D4200_DEVICE_ID}, an AXIS D4200-VE. To make it "
        f"flash white for 30 seconds, which VAPIX operation should I "
        f"use? Don't run anything — just name the operation ID and its "
        f"API."
    )
    cost_recorder(result)
    assert result.success
    _asserts_siren_and_light(result)


def test_flash_white_without_model_hint_picks_siren(chat, cost_recorder):
    """Harder variant: do NOT name the model, so the LLM must look the
    device up (which surfaces the d42 'use siren_and_light, not
    findmydevice' knowledge hint) rather than leaning on a model cue in
    the prompt. Still identify-don't-execute. This is the stronger guard
    that the catalog/knowledge plumbing — not prompt wording — does the
    steering."""
    result = chat(
        f"For device {D4200_DEVICE_ID}, what VAPIX operation makes it "
        f"flash white? Look it up; don't execute it — just tell me the "
        f"operation ID."
    )
    cost_recorder(result)
    assert result.success
    _asserts_siren_and_light(result)
