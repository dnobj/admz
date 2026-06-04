"""Device identification — the agent resolves model/name references to
a device_id ITSELF, instead of asking the user for the MAC.

Regression for a live-testing bug. With a fresh conversation, the user
said:

    "make the D4200 flash white for 30 seconds"

and the agent replied:

    "I need the device_id (MAC address) for the D4200. I can't find it
     in our conversation history. Can you please provide it, or I can
     list all devices if you'd like."

The agent stalled and punted the lookup back to the user. The correct
behavior: when a device is referenced by model/nickname/location and a
device_id is needed, the agent calls ``search_devices(model=...)`` (or
``list_devices``) and resolves the device_id on its own — a read-only
lookup it should never ask permission for. Fixed by strengthening the
"Device identification" section of the system prompt; the deterministic
guard lives in tests/test_chatbot_system_prompt.py.

Every E2E test starts with a CLEARED conversation history (see
conftest), so the agent genuinely has no prior listing to lean on — it
MUST resolve the reference via a tool call. That is exactly the
scenario that broke.

Device: AXIS D4200-VE, device_id B8A44FFC2B16 (homelab). The model is
referred to as just "D4200" on purpose — a substring of the stored
"D4200-VE" — to exercise the case-insensitive model search.
"""

from __future__ import annotations


D4200_DEVICE_ID = "B8A44FFC2B16"


# Phrases that mean "the agent punted the device-id lookup back to the
# user" — the exact failure mode this suite guards against. Kept
# device-id/MAC specific so a legitimate question about some OTHER
# parameter (e.g. a siren profile) doesn't trip a false positive.
_ASK_FOR_ID_PHRASES = (
    "provide the device_id",
    "provide the device id",
    "provide the mac",
    "need the device_id",
    "need the device id",
    "need the mac",
    "what is the device_id",
    "what's the device_id",
    "what is the device id",
    "what's the device id",
    "what is the mac",
    "what's the mac",
    "give me the device_id",
    "give me the mac",
    "device_id (mac address) for",
    "device id (mac address) for",
    "can't find it in our conversation",
    "couldn't find it in our conversation",
    "supply the device_id",
    "supply the mac",
)


def _did_not_ask_user_for_id(result) -> bool:
    """True unless the response asks the user to hand over the MAC."""
    body = result.lower
    return not any(p in body for p in _ASK_FOR_ID_PHRASES)


def test_model_reference_resolves_to_device_id(chat, cost_recorder):
    """Ask for a device's MAC using only its model name. The agent must
    look it up (search_devices/list_devices) and return the actual
    device_id — NOT ask the user to provide it."""
    result = chat(
        "What is the device ID (MAC address) of the D4200? Look it up "
        "in the registry."
    )
    cost_recorder(result)
    assert result.success
    assert _did_not_ask_user_for_id(result), (
        f"agent punted the device-id lookup back to the user instead of "
        f"resolving the model reference itself. {result!r}"
    )
    # Proof it actually resolved the reference: the real MAC appears.
    assert D4200_DEVICE_ID.lower() in result.lower, (
        f"agent did not surface the resolved device_id "
        f"{D4200_DEVICE_ID}. {result!r}"
    )


def test_action_by_model_name_resolves_without_asking(chat, cost_recorder):
    """The verbatim live-bug phrasing: an imperative referencing the
    device by model only. Regardless of whether the device is reachable,
    the agent must resolve the device_id and act on it — never stall
    asking the user for the MAC.

    We assert on the regression invariant (didn't punt the lookup) plus
    evidence the agent engaged the resolved device, rather than on the
    exact final wording — the device is often offline so the tail of the
    response may narrate a timeout."""
    result = chat(
        "make the D4200 flash white for 30 seconds"
    )
    cost_recorder(result)
    assert result.success
    assert _did_not_ask_user_for_id(result), (
        f"agent asked the user for the device_id/MAC instead of "
        f"resolving 'the D4200' itself — the system-prompt device-"
        f"identification guidance may have regressed. {result!r}"
    )
    # Evidence it resolved + engaged the device: it either references
    # the right API, surfaces the resolved id, or reports a reachability
    # outcome from actually trying — any of these means it didn't stall.
    assert result.contains_any(
        "siren_and_light", "siren and light", "siren-and-light",
        "siren", "strobe", "flash",
        D4200_DEVICE_ID, "d4200-ve",
        "timed out", "unreachable", "offline", "profile",
    ), (
        f"no evidence the agent resolved and acted on the D4200. "
        f"{result!r}"
    )
