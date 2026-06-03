"""Inventory queries — list_devices, get_device.

These exercise the most-used read-only MCP tools. They're the
foundation for everything else; if these fail nothing more
complex will work either.
"""

from __future__ import annotations


def test_list_devices_returns_known_ids(chat, cost_recorder):
    """LLM can list devices. We don't assert which devices exist
    (depends on the live registry), only that *some* are returned
    and the response looks like a list rather than an error/apology."""
    result = chat(
        "List the device IDs (MAC addresses) of every camera you can see. "
        "Respond ONLY with the IDs, comma-separated, nothing else."
    )
    cost_recorder(result)
    assert result.success
    # Should contain at least one MAC-shaped substring (12 hex chars).
    import re
    macs = re.findall(r"\b[A-Fa-f0-9]{12}\b", result.response)
    assert len(macs) >= 1, (
        f"expected at least one device-ID-shaped token in response, "
        f"got: {result.response!r}"
    )


def test_get_device_returns_model_and_host(chat, cost_recorder):
    """LLM can look up a specific device and surface its model/host."""
    # P3748-PLVE = B8A44FD0257C on the homelab. If you're running this
    # elsewhere, swap to a device you know exists.
    result = chat(
        "Look up device B8A44FD0257C. Tell me in one short sentence: "
        "what model is it and what IP/host?"
    )
    cost_recorder(result)
    assert result.success
    # Should mention something P3748-shaped (P3748 model) AND something
    # IP-shaped. Tolerate phrasing variation.
    import re
    has_p3748 = "p3748" in result.lower
    has_ip = bool(re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", result.response))
    assert has_p3748 or has_ip, (
        f"expected model 'P3748' or IP address in response, got: {result!r}"
    )


def test_unknown_device_is_reported_clearly(chat, cost_recorder):
    """Asking about a device that doesn't exist should produce a
    'not found' style response, NOT a fabricated answer or an
    unhandled error."""
    result = chat(
        "Tell me everything you know about device DEADBEEFDEAD. "
        "If you can't find it, say so plainly."
    )
    cost_recorder(result)
    assert result.success
    # Should signal not-found — multiple acceptable phrasings.
    assert result.contains_any(
        "not found", "no device", "doesn't exist",
        "could not find", "couldn't find", "can't find", "cannot find",
        "unable to find", "no information",
        "not in", "no record", "no such device",
    ), (
        f"expected a 'not found' style response for fake device, got: "
        f"{result!r}"
    )
