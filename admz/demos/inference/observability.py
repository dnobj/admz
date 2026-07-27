"""Firing observability for an ACS action rule — *pure*, no I/O (#124).

ACS emits **no universal signal** when an action rule fires (proven live,
2026-07-22): there is no push, and every log/alarm facade read returns an opaque
400. Detecting "did this rule fire" is therefore a **union of per-shape
channels**, each derived from what the rule triggers on and what it does. This
module is the deterministic classifier over ``firebird.rule_anatomy()`` rows.

| Rule shape | Channel | Fidelity |
|---|---|---|
| Trigger is DeviceEvent / Motion / ObjectDetection | ``device_event_direct`` | trigger |
| Action records | ``recording_sequence`` | rule |
| Action raises an alarm | ``acs_log_alarm`` | rule |
| Action sets an I/O output | ``device_event`` | action |
| Action is an HTTP notify aimed at ADMZ | ``webhook`` | rule |
| Mobile notify / door-station / PTZ only | ``blind`` | — |

``device_event_direct`` is the important one: for a device-originated trigger
ADMZ subscribes to the **same device event directly** over its own event stream
(ADR-0041 ``ws-data-stream``) — zero ACS touch, no rule edit, no mirror, so no
corruption risk. It is strictly better than instrumenting the rule.

**Fidelity caveat** (carried into every report): observing the trigger event is
*not* proof the rule's full condition passed — ``require_all_triggers`` across
several triggers, the schedule gate and every content filter still apply. A
``trigger``-fidelity channel answers *"did the triggering condition occur"*,
which for a single-trigger demo rule is usually equivalent. Only ``rule``-
fidelity channels name the rule in the signal itself.

Remediating a ``blind`` rule (adding an alarm or HTTP-notify action to it) is
deliberately out of scope — that is a write, and it belongs to #127.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# ── channels ────────────────────────────────────────────────────────────────
DEVICE_EVENT_DIRECT = "device_event_direct"
RECORDING_SEQUENCE = "recording_sequence"
ACS_LOG_ALARM = "acs_log_alarm"
DEVICE_EVENT = "device_event"
WEBHOOK = "webhook"
BLIND = "blind"

#: Most trustworthy first. The verdict is the highest-precedence channel found;
#: ``rule``-fidelity channels (the signal names the rule) outrank ``action``
#: (the effect is observed but not attributed) which outranks ``trigger``.
CHANNEL_PRECEDENCE = (WEBHOOK, ACS_LOG_ALARM, RECORDING_SEQUENCE,
                      DEVICE_EVENT, DEVICE_EVENT_DIRECT)

FIDELITY = {
    WEBHOOK: "rule",
    ACS_LOG_ALARM: "rule",
    RECORDING_SEQUENCE: "rule",
    DEVICE_EVENT: "action",
    DEVICE_EVENT_DIRECT: "trigger",
}

FIDELITY_CAVEAT = (
    "Observing the trigger event is not proof the rule's full condition "
    "(require_all_triggers, schedule gate, all content filters) passed — it "
    "answers 'did the triggering condition occur', which for a single-trigger "
    "demo rule is usually equivalent."
)

#: Trigger kinds that originate on a device, so ADMZ can subscribe to the same
#: event directly (``firebird.rule_anatomy`` strips the ``…TriggerEntity`` suffix).
DEVICE_ORIGIN_TRIGGERS = ("DeviceEvent", "MotionDetection", "ObjectDetection")

#: Action kinds with no observable side channel of their own.
BLIND_ACTION_KINDS = ("MobileAppNotification", "DoorStation", "Ptz", "PTZ",
                      "SendEmail", "Email", "Sound", "Overlay", "LiveView",
                      "Bookmark", "AccessControl")

#: The ADMZ inbound webhook path (mirrors ``modules.acs_pro.webhook.WEBHOOK_PATH``;
#: duplicated as a literal to keep this module import-free and pure).
ADMZ_WEBHOOK_PATH = "/api/acs/rule-fired"


def _channel(name: str, detail: str, **extra: Any) -> Dict[str, Any]:
    entry = {"channel": name, "fidelity": FIDELITY[name], "detail": detail}
    entry.update(extra)
    return entry


def _is_admz_webhook(url: Optional[str]) -> bool:
    return bool(url) and ADMZ_WEBHOOK_PATH in str(url)


def classify_rule(rule: Dict[str, Any]) -> Dict[str, Any]:
    """Classify one ``rule_anatomy`` entry's firing observability.

    Returns ``{verdict, channels[], blind, notes[], fidelity_caveat}`` where
    ``verdict`` is the highest-precedence channel name (see
    ``CHANNEL_PRECEDENCE``) or ``"blind"`` when nothing observes this rule, and
    ``channels`` lists **every** applicable channel with its own fidelity and the
    evidence that produced it. Pure: no I/O, no ACS, no device.
    """
    rule = rule or {}
    channels: List[Dict[str, Any]] = []
    notes: List[str] = []
    seen: set = set()

    def add(name: str, detail: str, **extra: Any) -> None:
        if name in seen:
            return
        seen.add(name)
        channels.append(_channel(name, detail, **extra))

    for trig in rule.get("triggers") or []:
        kind = (trig or {}).get("kind") or ""
        if kind not in DEVICE_ORIGIN_TRIGGERS:
            continue
        device = trig.get("device") or {}
        mac = device.get("mac")
        if not mac:
            notes.append(
                f"trigger {trig.get('id')} is device-originated ({kind}) but its "
                "device did not resolve to a MAC — cannot subscribe directly"
            )
            continue
        topic = trig.get("topic") or trig.get("subscription_filter") or kind
        add(DEVICE_EVENT_DIRECT,
            f"subscribe directly to {topic} on {mac} (ADR-0041 ws-data-stream, "
            "zero ACS touch)",
            device_mac=mac, topic=trig.get("topic"), trigger_id=trig.get("id"))

    for act in rule.get("actions") or []:
        kind = (act or {}).get("kind") or ""
        params = act.get("params") or {}
        target = act.get("target_device") or {}
        if kind == "Record":
            add(RECORDING_SEQUENCE,
                "record action — ACS_RECORDINGS.RECORDING_SEQUENCE rows are "
                "rule-attributed (RULE_NAME + ACTION_ID)",
                action_id=act.get("id"), device_mac=target.get("mac"))
        elif kind == "Alarm":
            add(ACS_LOG_ALARM,
                "alarm action — ACS_LOGS.LOG AlarmEntity rows name the rule "
                "(RULE_ID <> 0); the shipped poller already reads them",
                action_id=act.get("id"))
        elif kind == "IO":
            port = (params.get("port") or {})
            if target.get("mac"):
                add(DEVICE_EVENT,
                    "I/O output action — observe the target device's own output "
                    f"event on {target.get('mac')}"
                    + (f" port {port.get('identifier') or port.get('id')}"
                       if port else ""),
                    action_id=act.get("id"), device_mac=target.get("mac"),
                    port=port.get("identifier") or port.get("id"))
            else:
                notes.append(
                    f"action {act.get('id')} drives an I/O output but its target "
                    "device did not resolve to a MAC"
                )
        elif kind == "HttpNotification":
            if _is_admz_webhook(params.get("url")):
                add(WEBHOOK,
                    "HTTP-notify action already aimed at ADMZ — real-time and "
                    "rule-named, no correlation needed",
                    action_id=act.get("id"))
            else:
                notes.append(
                    f"action {act.get('id')} is an HTTP notify aimed elsewhere — "
                    "not observable by ADMZ without re-pointing it (#127)"
                )
        elif kind in BLIND_ACTION_KINDS:
            notes.append(f"action {act.get('id')} ({kind}) has no observable side channel")

    channels.sort(key=lambda c: CHANNEL_PRECEDENCE.index(c["channel"]))
    blind = not channels
    if blind:
        notes.append(
            "no observable channel — remediation is to instrument the rule with "
            "an extra alarm or HTTP-notify action (#127), which is a write and "
            "out of scope here"
        )
    return {
        "verdict": channels[0]["channel"] if channels else BLIND,
        "channels": channels,
        "blind": blind,
        "notes": notes,
        "fidelity_caveat": FIDELITY_CAVEAT,
    }


def summarize(rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Per-channel counts over many rules + the ``blind`` count (the #127 hand-off)."""
    counts: Dict[str, int] = {name: 0 for name in CHANNEL_PRECEDENCE}
    blind = 0
    for rule in rules or []:
        verdict = classify_rule(rule)
        if verdict["blind"]:
            blind += 1
        for chan in verdict["channels"]:
            counts[chan["channel"]] += 1
    counts[BLIND] = blind
    counts["total"] = len(rules or [])
    return counts
