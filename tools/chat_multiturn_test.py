"""Drive multi-turn conversations through /api/chat and pretty-print results.

Each scenario clears chat history before starting so the threading is
observable from turn 1. Designed to be human-readable on stdout — not
a pytest test.

Run from C:\\admz\\admz with the server up on :4242 and a Gemini API
key configured:

    .venv\\Scripts\\python.exe tools\\chat_multiturn_test.py
"""

from __future__ import annotations

import json
import sys
import textwrap
import time
from typing import Optional


# Force UTF-8 stdout so the LLM's bullets, emoji, em-dashes etc. don't
# blow up on Windows cp1252. No-op when stdout is already UTF-8.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

try:
    import urllib.request
    import urllib.error
except ImportError:  # pragma: no cover
    print("Missing urllib — should be stdlib")
    sys.exit(1)


BASE = "http://localhost:4242"
# Flash is the right balance for multi-turn driver. Flash-Lite is
# cheap but consistently produces empty responses on follow-up
# "what's its X" questions (its thinking-mode quirks). Flash is
# ~5x the cost per turn but completes the scenarios reliably.
MODEL = "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# HTTP helpers (urllib so this script has no third-party deps)
# ---------------------------------------------------------------------------


def chat(message: str, model: str = MODEL, use_tools: bool = True) -> dict:
    body = json.dumps({"message": message, "model": model, "use_tools": use_tools}).encode()
    req = urllib.request.Request(
        f"{BASE}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        payload = {
            "success": False,
            "error": f"HTTP {e.code}: {e.read().decode()[:200]}",
            "response": "",
            "model": model,
            "input_tokens": 0, "output_tokens": 0, "cost_usd": 0,
            "tool_calls": [],
        }
    except (TimeoutError, urllib.error.URLError) as e:
        # Don't crash the whole driver if one turn hangs — usually
        # means the LLM kicked off a tool that tried to reach an
        # unreachable device.
        payload = {
            "success": False,
            "error": f"Driver timeout / connection error: {e}",
            "response": "",
            "model": model,
            "input_tokens": 0, "output_tokens": 0, "cost_usd": 0,
            "tool_calls": [],
        }
    payload["_elapsed_s"] = round(time.time() - started, 2)
    return payload


def clear_chat() -> None:
    req = urllib.request.Request(f"{BASE}/chat/clear", method="POST")
    try:
        # /chat/clear redirects to /chat, urllib follows by default
        urllib.request.urlopen(req, timeout=5)
    except urllib.error.HTTPError:
        pass  # 303 is "ok"


# ---------------------------------------------------------------------------
# Pretty-print one turn
# ---------------------------------------------------------------------------


def print_turn(n: int, message: str, result: dict) -> None:
    sep = "-" * 78
    print(sep)
    print(f"TURN {n}  ({result['_elapsed_s']}s, "
          f"in={result.get('input_tokens',0)} out={result.get('output_tokens',0)} "
          f"≈${result.get('cost_usd',0):.5f}, "
          f"tools={result.get('tool_calls', []) or '—'})")
    print(sep)
    print(f"USER:\n  {message}")
    print()
    response = result.get("response") or result.get("error") or "(no response)"
    # Indent the response for readability
    for line in response.splitlines() or [""]:
        print(f"BOT:  {line}")
    if result.get("error") and not result.get("success"):
        print(f"\n  !!  ERROR: {result['error'][:200]}")
    print()


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def run_scenario(name: str, turns: list[tuple[str, dict]]) -> None:
    """Run one scenario. ``turns`` is a list of (message, kwargs)."""
    header = f"  SCENARIO: {name}  "
    pad = (78 - len(header)) // 2
    print()
    print("=" * 78)
    print("=" * pad + header + "=" * pad)
    print("=" * 78)
    clear_chat()
    for i, (msg, kw) in enumerate(turns, 1):
        result = chat(msg, **kw)
        print_turn(i, msg, result)


def scenario_drill_down() -> None:
    """Initial query → drill into one device → pronoun reference."""
    run_scenario(
        "Drill-down with pronoun reference",
        [
            ("What devices do I have?", {}),
            ("Tell me more about the AXIS C1710.", {}),
            ("What's its IP address?", {}),  # 'its' should refer to C1710
            ("Is there anything notable about that model?", {"use_tools": False}),
        ],
    )


def scenario_topic_switch_and_return() -> None:
    """General capability question → tangent → return to fleet."""
    run_scenario(
        "Topic switch and return",
        [
            ("What can you do?", {"use_tools": False}),
            ("How does firmware upgrade work in ADMZ?", {"use_tools": False}),
            ("OK enough theory — list my devices.", {}),
            ("Which of those are cameras vs other types?", {"use_tools": False}),  # uses turn-3 list
        ],
    )


def scenario_capability_discovery() -> None:
    """Capability questions that previously hit Bug 4 — does the
    LLM now find non-wrapper operations via query_catalog?

    This replaces the destructive scenario_task_planning. Real
    snapshot/restart calls hit the network and can hang the driver
    if devices are offline; that's an environment issue, not a
    chat-behavior issue.
    """
    run_scenario(
        "Capability discovery (catalog-driven ops)",
        [
            ("Can you reboot a device?", {"use_tools": False}),
            ("What about a firmware upgrade — is that something you can do?", {"use_tools": False}),
            ("List my devices.", {}),
            ("Look at the P3748. Can you tell me about its capabilities? Don't actually do anything to it.", {}),
        ],
    )


def scenario_clarification_loop() -> None:
    """Ambiguous question → disambiguate via history → topic switch.

    Uses 'tell me about' (read-only) instead of 'restart' so we
    don't actually fire writes that need confirmation tokens.
    """
    run_scenario(
        "Ambiguous query + clarification",
        [
            ("List my devices briefly.", {}),
            ("Tell me about the camera.", {}),  # ambiguous — multiple cameras
            ("The P3748.", {}),  # disambiguate
            ("Wait, scratch that — what about the C1110-E?", {}),  # topic switch
            ("Going back to the P3748, what's its IP?", {"use_tools": False}),  # return to earlier topic
        ],
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    print("ADMZ chatbot multi-turn test driver")
    print(f"Model: {MODEL}    Endpoint: {BASE}/api/chat")
    print()

    scenarios = [
        scenario_drill_down,
        scenario_topic_switch_and_return,
        scenario_capability_discovery,
        scenario_clarification_loop,
    ]

    for fn in scenarios:
        try:
            fn()
        except Exception as exc:
            print(f"\n!!! Scenario {fn.__name__} raised: {exc}")
            import traceback
            traceback.print_exc()

    print()
    print("=" * 78)
    print("All scenarios complete.")
