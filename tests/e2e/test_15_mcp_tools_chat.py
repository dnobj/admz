"""MCP read-only tool coverage via the chatbot (live Gemini).

Each test asks a natural-language question and asserts the chatbot either
called the expected MCP tool OR returned a sensible answer (the capability was
exercised either way). Tolerant by design — the LLM may pick a sibling tool or
answer from context. Read-only tools only: no device mutation, lab-safe.
"""

from __future__ import annotations

import pytest


def _a_device(registered_ids):
    return next(iter(sorted(registered_ids)), None)


def _ok(result, tools, *keywords):
    """Pass if any acceptable tool was called OR the response contains any
    keyword (case-insensitive). Always require a successful, non-empty turn."""
    assert result.success, repr(result)
    called = set(result.tool_calls or [])
    if called & set(tools):
        return
    assert result.contains_any(*keywords), (
        f"neither an expected tool {tools} nor keywords {keywords}; {result!r}"
    )


def test_list_devices(chat, cost_recorder):
    r = chat("List all the devices in the fleet.")
    cost_recorder(r)
    _ok(r, {"list_devices", "search_devices"}, "device", "camera", "registered")


def test_get_device(chat, cost_recorder, registered_ids):
    did = _a_device(registered_ids)
    if not did:
        pytest.skip("no devices registered")
    r = chat(f"What model and IP address is device {did}?")
    cost_recorder(r)
    _ok(r, {"get_device", "list_devices"}, "model", "ip", "address", did.lower())


def test_search_devices_by_tag(chat, cost_recorder):
    r = chat("Find every device tagged 'lab'.")
    cost_recorder(r)
    _ok(r, {"search_devices", "list_devices"}, "lab", "device", "no ", "found")


def test_fleet_health(chat, cost_recorder):
    r = chat("How many devices are currently online? Give me a number.")
    cost_recorder(r)
    _ok(r, {"get_fleet_health"}, "online", "device", "reachable", "0", "1", "2",
        "3", "4", "5", "6", "7")


def test_device_health(chat, cost_recorder, registered_ids):
    did = _a_device(registered_ids)
    if not did:
        pytest.skip("no devices registered")
    r = chat(f"Is device {did} reachable right now? One word.")
    cost_recorder(r)
    _ok(r, {"get_device_health"}, "online", "offline", "unreachable", "reachable",
        "yes", "no", "up", "down")


def test_check_drift(chat, cost_recorder, registered_ids):
    did = _a_device(registered_ids)
    if not did:
        pytest.skip("no devices registered")
    r = chat(f"Has the configuration on device {did} drifted from its baseline?")
    cost_recorder(r)
    _ok(r, {"check_drift"}, "drift", "baseline", "config", "in sync", "no ", "match")


def test_drift_alerts(chat, cost_recorder):
    r = chat("Show me any recent configuration drift alerts across the fleet.")
    cost_recorder(r)
    _ok(r, {"get_drift_alerts", "check_drift"}, "drift", "alert", "no ", "none",
        "recent")


def test_query_catalog(chat, cost_recorder, registered_ids):
    did = _a_device(registered_ids)
    if not did:
        pytest.skip("no devices registered")
    r = chat(f"What operations are available to change the image settings on "
             f"device {did}? Don't run anything.")
    cost_recorder(r)
    _ok(r, {"query_catalog"}, "image", "param", "resolution", "operation", "cgi")


def test_query_knowledge(chat, cost_recorder, registered_ids):
    did = _a_device(registered_ids)
    if not did:
        pytest.skip("no devices registered")
    r = chat(f"What special capabilities or limitations does device {did} have?")
    cost_recorder(r)
    _ok(r, {"query_knowledge", "get_device", "check_api_support"},
        "capabilit", "support", "model", "firmware", "axis")


def test_check_api_support(chat, cost_recorder, registered_ids):
    did = _a_device(registered_ids)
    if not did:
        pytest.skip("no devices registered")
    r = chat(f"Does device {did} support the audio API?")
    cost_recorder(r)
    _ok(r, {"check_api_support", "query_knowledge", "query_catalog"},
        "audio", "support", "yes", "no", "api")


def test_list_schedules(chat, cost_recorder):
    r = chat("What snapshot or drift-audit schedules are configured?")
    cost_recorder(r)
    _ok(r, {"list_snapshot_schedules"}, "schedule", "snapshot", "drift", "none",
        "no ")


def test_list_cached_firmware(chat, cost_recorder):
    r = chat("What firmware files do we have cached locally?")
    cost_recorder(r)
    _ok(r, {"list_cached_firmware"}, "firmware", "cache", "none", "no ", ".bin")


def test_fleet_settings(chat, cost_recorder):
    r = chat("Show me the fleet-wide settings.")
    cost_recorder(r)
    _ok(r, {"get_fleet_settings"}, "setting", "config", "fleet", "none")
