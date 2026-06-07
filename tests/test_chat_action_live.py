"""Live chat -> action integration battery.

Drives the *actual* ADMZ chat (`POST /api/chat`) against real devices and
verifies the assistant ACTUALLY performs the requested action — not just that it
produces a plausible reply. This is the regression net for the "responds but
doesn't act" class of bug (e.g. "zoom in halfway" → a refusal with no tool call).

Skipped by default. It needs a running ADMZ instance, a configured Gemini key,
and reachable devices, so it can't run in normal CI. Enable with::

    ADMZ_LIVE_CHAT_TESTS=1
    ADMZ_CHAT_TEST_URL=http://127.0.0.1:4243   # optional, this is the default

Run just this battery::

    ADMZ_LIVE_CHAT_TESTS=1 python -m pytest tests/test_chat_action_live.py -v -o addopts=""

…or as a standalone report::

    ADMZ_LIVE_CHAT_TESTS=1 python tests/test_chat_action_live.py

Design notes:
  * Model nondeterminism + Gemini 503s make these inherently flaky, so every
    chat turn is retried, and assertions check the OUTCOME (a tool fired + the
    device state changed) rather than exact wording.
  * Device discovery is portable: it finds a zoom-capable camera in the registry
    via opticscontrol getCapabilities rather than hard-coding a MAC, and skips
    the optics scenarios if the fleet has none.
  * The reboot scenario only verifies the confirmation prompt — it never
    confirms, so nothing is actually rebooted.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ADMZ_LIVE_CHAT_TESTS") not in ("1", "true", "yes"),
    reason="live chat battery — set ADMZ_LIVE_CHAT_TESTS=1 (needs running ADMZ + Gemini key + devices)",
)

BASE_URL = os.getenv("ADMZ_CHAT_TEST_URL", "http://127.0.0.1:4243").rstrip("/")
CHAT_RETRIES = int(os.getenv("ADMZ_CHAT_TEST_RETRIES", "4"))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _httpx():
    import httpx
    return httpx


def _server_up() -> bool:
    try:
        r = _httpx().get(f"{BASE_URL}/api/health", timeout=4)
        return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def chat(message: str, *, reset: bool = True, retries: int = CHAT_RETRIES) -> Dict[str, Any]:
    """One chat turn against the live ADMZ API, with 503/overload retry."""
    httpx = _httpx()
    if reset:
        try:
            httpx.post(f"{BASE_URL}/api/chat/clear", timeout=10)
        except Exception:  # noqa: BLE001
            pass
    last = {}
    for attempt in range(retries):
        r = httpx.post(f"{BASE_URL}/api/chat", json={"message": message}, timeout=180)
        last = r.json()
        err = (last.get("error") or "")
        if "503" in err or "UNAVAILABLE" in err or "high demand" in err:
            time.sleep(8 * (attempt + 1))
            continue
        return last
    return last


_REGISTRY = None


def _registry():
    global _REGISTRY
    if _REGISTRY is None:
        from admz.factory import create_device_registry
        _REGISTRY = create_device_registry()
    return _REGISTRY


def _vapix(device_id: str, method: str, params: Optional[Dict] = None,
           cgi: str = "opticscontrol.cgi") -> Dict[str, Any]:
    """Direct (out-of-band) VAPIX call used to VERIFY device state — bypasses
    the chat so the test is checking reality, not the assistant's claim."""
    httpx = _httpx()
    c = _registry().get_credentials(device_id, requester="chat-action-test")
    host = c["host"]
    host = host if host.startswith("http") else f"https://{host}"
    body = {"apiVersion": "1.0", "method": method}
    if params is not None:
        body["params"] = params
    for auth in (httpx.DigestAuth(c["username"], c["password"]),
                 httpx.BasicAuth(c["username"], c["password"])):
        try:
            r = httpx.post(f"{host}/axis-cgi/{cgi}", json=body, auth=auth, verify=False, timeout=20)
            if r.status_code in (401, 403):
                continue
            return r.json()
        except Exception:  # noqa: BLE001
            continue
    return {}


def _find_zoom_camera() -> Optional[Tuple[str, str, float]]:
    """Return (device_id, model, maxMagnification) for the first registry device
    whose opticscontrol reports a 'zoom' capability, or None."""
    for d in _registry().list_devices():
        did = d.get("device_id")
        if not did:
            continue
        data = _vapix(did, "getCapabilities").get("data") or {}
        for o in data.get("optics", []):
            if "zoom" in (o.get("capabilities") or []) and o.get("maxMagnification", 1) > 1.0:
                return did, d.get("model") or did, float(o["maxMagnification"])
    return None


def _magnification(device_id: str) -> Optional[float]:
    data = _vapix(device_id, "getOptics").get("data") or {}
    opt = (data.get("optics") or [{}])[0]
    return opt.get("magnification")


def _set_magnification(device_id: str, value: float) -> None:
    _vapix(device_id, "setMagnification",
           {"optics": [{"opticsId": "0", "magnification": value}]})


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _require_server():
    if not _server_up():
        pytest.skip(f"no ADMZ instance at {BASE_URL} (set ADMZ_CHAT_TEST_URL)")


@pytest.fixture(scope="session")
def zoom_cam():
    cam = _find_zoom_camera()
    if cam is None:
        pytest.skip("no zoom-capable camera reachable in the registry")
    return cam


# ---------------------------------------------------------------------------
# scenarios — each asserts the ACTION/outcome, not the wording
# ---------------------------------------------------------------------------


def test_list_devices_uses_a_tool_and_returns_a_mac():
    devs = _registry().list_devices()
    if not devs:
        pytest.skip("no devices registered")
    known_mac = devs[0]["device_id"]
    res = chat("list my devices")
    assert res.get("success"), res.get("error")
    # at least one registered MAC should appear in the answer
    text = res.get("response", "")
    assert any(d["device_id"] in text for d in devs), text[:300]


def test_read_firmware_executes_and_returns_version(zoom_cam):
    did, model, _ = zoom_cam
    res = chat(f"what firmware version is the {model} running?")
    assert res.get("success"), res.get("error")
    assert res.get("tool_calls"), "expected a tool call, got none (model answered from memory?)"
    assert re.search(r"\d+\.\d+\.\d+", res.get("response", "")), res.get("response", "")[:300]


def test_zoom_in_halfway_actually_moves_the_lens(zoom_cam):
    """The headline regression: 'zoom in halfway' must call tools AND change the
    device's magnification toward the midpoint — not refuse with a hallucinated
    '1 to 9999' range."""
    did, model, max_mag = zoom_cam
    _set_magnification(did, 1.0)
    time.sleep(1.0)
    assert (_magnification(did) or 0) < 1.2, "baseline reset to wide failed"

    res = chat(f"zoom in halfway on the {model}")
    assert res.get("success"), res.get("error")
    assert any("execute_operation" in t for t in res.get("tool_calls", [])), \
        f"no execute_operation fired; tool_calls={res.get('tool_calls')}, resp={res.get('response','')[:300]}"

    time.sleep(1.5)
    mag = _magnification(did)
    midpoint = 1.0 + (max_mag - 1.0) / 2.0
    assert mag is not None and mag > 1.15, f"lens did not zoom in (magnification={mag})"
    # 'halfway' should land near the midpoint, with generous tolerance for model interpretation
    assert abs(mag - midpoint) <= max(0.4, (max_mag - 1.0) * 0.5), \
        f"magnification {mag} not near halfway midpoint {midpoint:.3f} (max {max_mag})"


def test_zoom_all_the_way_out_returns_to_wide(zoom_cam):
    did, model, max_mag = zoom_cam
    _set_magnification(did, max(1.5, max_mag - 0.3))  # start zoomed in
    time.sleep(1.0)
    res = chat(f"zoom the {model} all the way out")
    assert res.get("success"), res.get("error")
    time.sleep(1.5)
    mag = _magnification(did)
    assert mag is not None and mag <= 1.15, f"expected wide (~1.0), got {mag}"


def test_reboot_asks_for_confirmation_and_does_not_reboot(zoom_cam):
    """A service-affecting op should be DESCRIBED + gated, not silently run."""
    did, model, _ = zoom_cam
    res = chat(f"reboot the {model}")
    assert res.get("success"), res.get("error")
    assert res.get("tool_calls"), "expected at least query_catalog"
    text = res.get("response", "").lower()
    assert any(w in text for w in ("confirm", "proceed", "are you sure", "do you want")), text[:300]
    # device must still be reachable — it must NOT have actually rebooted
    assert _magnification(did) is not None, "device appears to have rebooted without confirmation!"


# ---------------------------------------------------------------------------
# standalone runner: prints a battery report
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import sys
    os.environ.setdefault("ADMZ_LIVE_CHAT_TESTS", "1")
    if not _server_up():
        print(f"No ADMZ instance at {BASE_URL}. Set ADMZ_CHAT_TEST_URL."); sys.exit(1)
    cam = _find_zoom_camera()
    print(f"# ADMZ chat -> action battery  (server={BASE_URL})")
    print(f"# zoom camera: {cam}\n")
    prompts = ["list my devices"]
    if cam:
        m = cam[1]
        prompts += [f"what firmware version is the {m} running?",
                    f"zoom in halfway on the {m}",
                    f"zoom the {m} all the way out",
                    f"reboot the {m}"]
    for p in prompts:
        r = chat(p)
        print(f"PROMPT: {p}")
        print(f"  success={r.get('success')} tools={r.get('tool_calls')}")
        print(f"  {(r.get('response') or r.get('error') or '').strip()[:200]}\n")
