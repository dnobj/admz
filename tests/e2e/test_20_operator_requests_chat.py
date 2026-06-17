"""Realistic single-turn operator requests (live Gemini, chat-only).

The kinds of things an operator actually types. Tolerant: each must succeed,
be non-empty, and stay on topic (a tool call is the usual path but not
required). All read-only — no config changes.
"""

from __future__ import annotations

import pytest


def _ask(chat, cost_recorder, msg, *keywords):
    r = chat(msg)
    cost_recorder(r)
    assert r.success and r.response.strip(), repr(r)
    if keywords:
        assert r.contains_any(*keywords), repr(r)
    return r


def test_fleet_status_report(chat, cost_recorder):
    _ask(chat, cost_recorder,
         "Give me a quick status report of the whole fleet.",
         "online", "device", "reachable", "health", "drift", "total", "summary")


def test_devices_needing_attention(chat, cost_recorder):
    _ask(chat, cost_recorder,
         "Which devices are unreachable or might need attention?",
         "unreachable", "offline", "attention", "all", "none", "online",
         "reachable", "no ")


def test_count_registered(chat, cost_recorder):
    _ask(chat, cost_recorder,
         "How many Axis devices do I have registered?",
         "device", "registered", "0", "1", "2", "3", "4", "5", "6", "7", "8",
         "9", "10")


def test_firmware_of_device(chat, cost_recorder, a_device):
    if not a_device:
        pytest.skip("no devices registered")
    _ask(chat, cost_recorder,
         f"What firmware version is device {a_device} running?",
         "firmware", "version", "unknown", "not", "running", ".")


def test_fleet_in_sync(chat, cost_recorder):
    _ask(chat, cost_recorder,
         "Is every device's configuration in sync with its saved baseline?",
         "sync", "drift", "baseline", "config", "all", "none", "no ", "yes",
         "change")


def test_image_operations_identify(chat, cost_recorder, a_device):
    if not a_device:
        pytest.skip("no devices registered")
    _ask(chat, cost_recorder,
         f"What operations are available to adjust the image on device "
         f"{a_device}? Don't run anything, just list them.",
         "image", "resolution", "brightness", "param", "operation", "cgi",
         "rotation")


def test_audio_support_question(chat, cost_recorder, a_device):
    if not a_device:
        pytest.skip("no devices registered")
    _ask(chat, cost_recorder,
         f"Does device {a_device} have a microphone or audio support?",
         "audio", "microphone", "mic", "yes", "no", "support", "speaker")


def test_recent_config_changes(chat, cost_recorder):
    _ask(chat, cost_recorder,
         "Have there been any configuration changes detected across the fleet "
         "recently?",
         "change", "drift", "alert", "no ", "none", "recent", "config")


def test_devices_by_tag(chat, cost_recorder):
    _ask(chat, cost_recorder,
         "Which devices are tagged 'lab'?",
         "lab", "device", "tag", "no ", "none", "camera")


def test_schedules_running(chat, cost_recorder):
    _ask(chat, cost_recorder,
         "What snapshot or drift-audit schedules are currently running?",
         "schedule", "snapshot", "drift", "none", "no ", "running", "interval")


def test_device_ip(chat, cost_recorder, a_device):
    if not a_device:
        pytest.skip("no devices registered")
    _ask(chat, cost_recorder,
         f"What's the IP address of device {a_device}?",
         "ip", "address", "192.", "10.", "172.", "unknown", "not", ".")


def test_meta_what_can_you_do(chat, cost_recorder):
    _ask(chat, cost_recorder,
         "What kinds of things can you help me with for my Axis devices?",
         "device", "config", "health", "snapshot", "drift", "reboot", "manage",
         "operation", "camera", "help")
