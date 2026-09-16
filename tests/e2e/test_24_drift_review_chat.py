"""Drift review in the console chat (ADR-0070; live Gemini, chat-only).

Asks the assistant to review a device the drift cache already calls drifted,
and checks the shape of what comes back: it reads the review with
``get_drift_review``, explains before it acts, names the firmware change when
the review carries one, proposes an accept with a note, and any approval card
it mentions really exists. Tolerant of phrasing, strict on those shapes.

SAFE: every write in this flow is a ``url_only`` card that only a human can
approve, and nothing here approves one. The only device traffic is the read
the drift cache already did; ``GET /api/snapshot/drift`` is served from that
cache.
"""

from __future__ import annotations

import re

import pytest

# A reply that says a gated write already happened is the failure this guards.
_CLAIMS = (
    "has been accepted", "have been accepted", "successfully accepted",
    "baseline has been updated", "baseline is now updated",
    "has been reverted", "have been reverted", "successfully reverted",
    "have been excluded", "has been excluded",
)


def _drifted(api):
    r = api("GET", "/api/fleet/drift")
    if r.status_code != 200:
        pytest.skip(f"/api/fleet/drift returned {r.status_code}")
    ids = [d["device_id"] for d in r.json().get("devices", [])
           if d.get("state") == "drifted"]
    if not ids:
        pytest.skip("no device is drifted in the drift cache")
    return ids


def _review(api, device_id):
    r = api("GET", f"/api/snapshot/drift?device_id={device_id}")
    assert r.status_code == 200, r.text
    return r.json()


def _cards_are_real(api, response):
    """Every ``/confirm/<token>`` the reply names is a live session."""
    for token in set(re.findall(r"/confirm/([A-Za-z0-9_-]{8,})", response)):
        status = api("GET", f"/api/confirm/{token}/status").json().get("status")
        assert status != "expired_or_not_found", (
            f"the reply named a card that does not exist: /confirm/{token}")


def test_a_review_reads_the_triage_and_changes_nothing(chat, cost_recorder, api):
    device_id = _drifted(api)[0]
    r = chat(f"Review the configuration drift on device {device_id} with me.")
    cost_recorder(r)
    assert r.success and r.response.strip(), repr(r)
    assert "get_drift_review" in r.tool_calls, r.tool_calls
    # A review explains; it does not revert or exclude on its own.
    assert "revert_drift" not in r.tool_calls, r.tool_calls
    assert "ignore_config_keys" not in r.tool_calls, r.tool_calls
    assert not r.contains_any(*_CLAIMS), repr(r)
    _cards_are_real(api, r.response)


def test_a_firmware_upgrade_is_named(chat, cost_recorder, api):
    for device_id in _drifted(api):
        context = _review(api, device_id).get("triage_context") or {}
        if context.get("firmware_changed") and context.get("live_firmware"):
            break
    else:
        pytest.skip("no drifted device whose firmware moved since its baseline")
    r = chat(f"What changed on device {device_id}, and why?")
    cost_recorder(r)
    assert r.success and r.response.strip(), repr(r)
    assert r.contains_any(context["live_firmware"], "firmware"), repr(r)
    _cards_are_real(api, r.response)


def test_an_accept_request_opens_one_card_with_a_note(chat, cost_recorder, api):
    device_id = _drifted(api)[0]
    r = chat(
        f"The drift on device {device_id} is expected — accept its current "
        "config as the new baseline, and note why."
    )
    cost_recorder(r)
    assert r.success and r.response.strip(), repr(r)
    # The model may read the review first, or ask; if it acted, it acted once,
    # through the card.
    assert r.tool_calls.count("accept_baseline") <= 1, r.tool_calls
    if "accept_baseline" in r.tool_calls:
        assert r.contains_any(
            "approve", "approval", "confirm", "card"), repr(r)
    else:
        assert r.contains_any("?", "confirm", "note", "why"), repr(r)
    assert not r.contains_any(*_CLAIMS), repr(r)
    _cards_are_real(api, r.response)
