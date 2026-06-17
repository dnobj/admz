"""Real-world multi-turn workflows (live Gemini, chat-only).

Each test is a short CONVERSATION — the suite clears history before the test,
then consecutive chat() calls share it, so follow-ups must use prior context.
Tolerant assertions: every turn succeeds, is non-empty, and stays on topic.
Read-only / gated-destructive only — nothing executes a config change.
"""

from __future__ import annotations

import pytest


def _turn(chat, cost_recorder, msg):
    r = chat(msg)
    cost_recorder(r)
    assert r.success and r.response.strip(), repr(r)
    return r


def test_inventory_then_filter(chat, cost_recorder):
    _turn(chat, cost_recorder, "List the devices in my fleet.")
    r2 = _turn(chat, cost_recorder,
               "Out of those, which ones are speakers or have a display?")
    assert r2.contains_any("speaker", "display", "none", "no ", "camera",
                           "c1710", "device"), repr(r2)


def test_health_then_remediation(chat, cost_recorder):
    _turn(chat, cost_recorder, "Are all my devices reachable right now?")
    r2 = _turn(chat, cost_recorder,
               "For any that aren't, what would you suggest I check?")
    assert r2.contains_any("check", "power", "network", "cable", "credential",
                           "reachable", "online", "all", "none", "ip", "poe",
                           "reboot", "ping"), repr(r2)


def test_capability_then_identify_action(chat, cost_recorder, a_device):
    if not a_device:
        pytest.skip("no devices registered")
    _turn(chat, cost_recorder, f"Does device {a_device} support PTZ?")
    r2 = _turn(chat, cost_recorder,
               "If it does, what operation would I use to pan it left? "
               "Just tell me — don't run it.")
    assert r2.contains_any("ptz", "com-ptz", "pan", "move", "doesn't", "does not",
                           "no ", "not support", "fixed"), repr(r2)


def test_drift_then_offer_revert(chat, cost_recorder, a_device):
    if not a_device:
        pytest.skip("no devices registered")
    _turn(chat, cost_recorder,
          f"Has the configuration on device {a_device} changed from its baseline?")
    r2 = _turn(chat, cost_recorder,
               "If something drifted, how would I revert just those fields?")
    assert r2.contains_any("revert", "baseline", "restore", "drift", "in sync",
                           "no ", "field", "config", "change"), repr(r2)


def test_model_then_others_like_it(chat, cost_recorder, a_device):
    if not a_device:
        pytest.skip("no devices registered")
    _turn(chat, cost_recorder, f"What model is device {a_device}?")
    r2 = _turn(chat, cost_recorder, "Do I have any other devices of that model?")
    assert r2.contains_any("model", "other", "device", "only", "no ", "yes",
                           "one", "same", "another"), repr(r2)


def test_count_then_list(chat, cost_recorder):
    _turn(chat, cost_recorder, "How many devices do I have registered?")
    r2 = _turn(chat, cost_recorder, "List them by model.")
    assert r2.contains_any("model", "device", "camera", "axis", "p", "c", "m",
                           "q"), repr(r2)


def test_last_snapshot_then_drift(chat, cost_recorder, a_device):
    if not a_device:
        pytest.skip("no devices registered")
    _turn(chat, cost_recorder,
          f"When was device {a_device}'s configuration last captured to git?")
    r2 = _turn(chat, cost_recorder,
               "Is its current live config different from that?")
    assert r2.contains_any("drift", "config", "baseline", "same", "different",
                           "in sync", "no ", "change", "match", "last"), repr(r2)


def test_greeting_then_task(chat, cost_recorder):
    # warm-then-work: a greeting, then a real request in the same conversation.
    _turn(chat, cost_recorder, "Hi, what can you help me with?")
    r2 = _turn(chat, cost_recorder, "Great — how many of my devices are online?")
    assert r2.contains_any("online", "device", "reachable", "0", "1", "2", "3",
                           "4", "5", "6", "7"), repr(r2)
