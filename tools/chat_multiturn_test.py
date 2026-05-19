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
MODEL = "gemini-2.5-flash-lite"  # free-tier friendly default for the test driver


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


def scenario_task_planning() -> None:
    """Stated intent → clarification → confirmation flow → recall."""
    run_scenario(
        "Task planning with clarification",
        [
            ("I'd like to snapshot the C1710. What does a snapshot include?", {"use_tools": False}),
            ("Sounds good. Take a snapshot of it.", {}),  # 'it' = C1710
            ("Now do the same for the I8016-LVE.", {}),  # different device
            ("Summarize what we just did.", {"use_tools": False}),  # recap from history
        ],
    )


def scenario_clarification_loop() -> None:
    """Ambiguous question → ask for clarification → continue."""
    run_scenario(
        "Ambiguous query + clarification",
        [
            ("Restart the camera.", {}),  # ambiguous — which camera?
            ("The P3748.", {}),  # disambiguate
            ("Wait, never mind. What about the C1110-E?", {}),  # change subject
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
        scenario_task_planning,
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
