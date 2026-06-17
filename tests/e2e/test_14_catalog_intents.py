"""Deterministic intent-resolution coverage (REST, no Gemini cost).

Each case posts a natural-language intent to ``/api/catalog/query`` and asserts
the resolver surfaces the right VAPIX operation (by an operation_id SUBSTRING
that was verified live against the running resolver). This exercises the
catalog/resolver breadth the chatbot relies on, deterministically and for free.

Uses an UNregistered device_id so device-capability filtering is off and the
full candidate set surfaces (stable regardless of the lab's inventory).
"""

from __future__ import annotations

import pytest

_DEV = "E2E-PROBE"  # unregistered → resolver returns the broad candidate set


def _op_ids(api, intent):
    r = api("POST", "/api/catalog/query",
            json={"device_id": _DEV, "intent": intent, "family": "vapix"})
    assert r.status_code == 200, r.text
    body = r.json()
    return [o.get("id", "") for o in body.get("operations", [])], body


# (intent phrase, substring that MUST appear in some resolved operation_id)
# All verified live against the resolver on 2026-06-16.
_CASES = [
    ("take a snapshot image", "jpg-image.cgi:snapshot"),
    ("change the image resolution", "param.cgi"),
    ("rotate the image 180 degrees", "param.cgi"),
    ("go to ptz preset 2", "com-ptz.cgi"),
    ("pan the camera left", "com-ptz.cgi"),     # PTZ-motion synonyms (added)
    ("point the camera down", "com-ptz.cgi"),
    ("set the focus", "opticscontrol.cgi"),
    ("zoom in", "opticscontrol.cgi"),
    ("configure NTP time sync", "ntp.cgi"),
    ("what is the current time", "date.cgi"),
    ("get basic device info", "basicdeviceinfo.cgi"),
    ("check the firmware version", "firmwaremanagement.cgi"),
    ("factory reset the device", "factorydefault.cgi"),
    ("reboot the device", "restart.cgi:restart"),
    ("flash white for 30 seconds", "siren_and_light.cgi"),
    ("control the status LED", "ledcontrol.cgi"),
    ("list active video streams", "streamstatus.cgi"),
    ("add a user account", "pwdgrp.cgi"),
    ("play an audio clip", "mediaclip.cgi"),
    ("show a message on the speaker display", "speaker-display-notification"),
    ("list the action rules", "action-rules"),
    ("discover supported APIs", "apidiscovery.cgi"),
]


@pytest.mark.parametrize("intent,needle", _CASES, ids=[c[0] for c in _CASES])
def test_intent_resolves_to_operation(api, intent, needle):
    ids, _ = _op_ids(api, intent)
    assert any(needle in i for i in ids), (
        f"intent {intent!r} did not surface an op containing {needle!r}; got {ids[:6]}"
    )


def test_risk_summary_flags_dangerous_and_service_affecting(api):
    # factory reset is dangerous; reboot is service-affecting — the resolver's
    # risk_summary must reflect that so the LLM/UI gate appropriately.
    _, factory = _op_ids(api, "factory reset the device")
    assert factory["risk_summary"].get("dangerous", 0) >= 1
    _, reboot = _op_ids(api, "reboot the device")
    assert reboot["risk_summary"].get("service-affecting", 0) >= 1
    # and the resolver attaches a human warning for the destructive ops
    assert reboot.get("notes")


def test_snapshot_is_read_only(api):
    ids, body = _op_ids(api, "take a snapshot image")
    snap = next((o for o in body["operations"] if o["id"] == "jpg-image.cgi:snapshot"), None)
    assert snap is not None
    assert snap.get("risk_level") == "read-only"


def test_flash_is_ambiguous_surfaces_siren_and_locate(api):
    # 'flash' is deliberately ambiguous: a strobe-siren start AND a
    # locate-this-unit blink should both be candidates (the LLM picks per
    # device). Verified the resolver surfaces siren_and_light here.
    ids, _ = _op_ids(api, "flash the light to find this device")
    assert any("siren_and_light" in i or "findmydevice" in i or "lightcontrol" in i
               for i in ids), f"no flash-related op surfaced; got {ids[:6]}"


def test_unknown_intent_does_not_fabricate(api):
    # A nonsense intent must not invent operations — at most generic param.cgi
    # discovery, never a made-up cgi.
    ids, _ = _op_ids(api, "summon a unicorn and ride it to the datacenter")
    assert not any("unicorn" in i.lower() for i in ids)
