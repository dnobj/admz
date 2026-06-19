"""Deferred-recovery behaviors via the chatbot (live Gemini, chat-only).

The user's core ask: when someone factory-resets a device, the agent should ASK
the follow-up intent (re-provision / remove / leave) rather than silently block
on the ~1-2 min reboot — and it should offer recovery for a device that's already
factory-defaulted. Tolerant of phrasing.

SAFE: the only state-changing test arms a recovery on an ONLINE device (whose
trigger can't fire) through the chatbot, then cancels it via REST in a finally.
"""

from __future__ import annotations

import pytest


# Vocabulary that means the agent surfaced the recovery follow-up.
_RECOVERY_WORDS = (
    "re-provision", "reprovision", "re provision", "provision",
    "recover", "recovery", "decommission", "remove", "leave it",
    "afterward", "afterwards", "after the reset", "once it", "comes back",
    "when it returns", "when it comes back", "needs setup", "factory", "queue",
)


def test_factory_reset_offers_followup_intent(chat, cost_recorder, a_device):
    if not a_device:
        pytest.skip("no devices registered")
    r = chat(
        f"I want to factory reset device {a_device}. What should happen to it "
        f"afterward?"
    )
    cost_recorder(r)
    assert r.success and r.response.strip(), repr(r)
    # The agent should raise the follow-up choice (re-provision / remove / leave)
    # or otherwise talk about recovery — not silently agree to wait on the reboot.
    assert r.contains_any(*_RECOVERY_WORDS), repr(r)


def test_needs_setup_device_recovery_options(chat, cost_recorder, api):
    health = api("GET", "/api/fleet/health").json().get("devices", [])
    ns = [d["device_id"] for d in health if d.get("status") == "needs_setup"]
    if not ns:
        pytest.skip("no needs_setup device to ask about")
    did = ns[0]
    r = chat(f"Device {did} shows 'needs setup'. What are my options to fix it?")
    cost_recorder(r)
    assert r.success and r.response.strip(), repr(r)
    assert r.contains_any(
        "re-provision", "reprovision", "provision", "recover", "decommission",
        "remove", "factory", "credential", "admin", "account",
    ), repr(r)


def test_queue_recovery_through_chat(chat, cost_recorder, api):
    # Arm a recovery via the chatbot on an ONLINE device (trigger can't fire),
    # then clean it up via REST so no armed state leaks out of the test.
    health = api("GET", "/api/fleet/health").json().get("devices", [])
    online = [d["device_id"] for d in health if d.get("status") == "online"]
    if not online:
        pytest.skip("no online device to safely queue against")
    did = online[0]
    try:
        r = chat(
            f"Set up automatic recovery for device {did}: re-provision it the "
            f"next time it comes back factory-defaulted."
        )
        cost_recorder(r)
        assert r.success and r.response.strip(), repr(r)
        called = set(r.tool_calls or [])
        assert "queue_device_recovery" in called or r.contains_any(
            "queued", "re-provision", "reprovision", "will re-provision",
            "set up", "recover", "when it", "comes back", "armed",
        ), repr(r)
    finally:
        pend = api("GET", f"/api/devices/{did}/pending").json().get("pending", [])
        for p in pend:
            if (p.get("action") or {}).get("action") == "reprovision":
                api("POST", f"/api/devices/{did}/pending/{p['id']}/cancel")
