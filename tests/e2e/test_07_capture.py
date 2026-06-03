"""Capture URL flow — asking to set credentials should produce
a /capture/{token} URL, not put the password into the LLM
context.
"""

from __future__ import annotations

import re


P3748_DEVICE_ID = "B8A44FD0257C"


def test_capture_request_returns_url(chat, cost_recorder):
    """Asking the LLM to provision credentials for a device should
    invoke ``capture_credentials`` and surface a `/capture/<token>`
    URL. The LLM must NOT ask the user to type the password in
    chat (which would land it in LLM context — the cardinal sin).
    """
    # Be very directive about the tool to call. Without this, Gemini
    # sometimes claims "couldn't find the device" instead of calling
    # the tool, even when the device exists in the registry. The
    # test isn't about ambiguity-resolution skill — it's about
    # the credential-capture flow producing the right artifact.
    result = chat(
        f"I want to set credentials for device {P3748_DEVICE_ID} "
        f"(an AXIS P3748-PLVE that's already registered in my "
        f"system). Use the `capture_credentials` MCP tool — it "
        f"returns a one-time URL I'll open in a browser to enter "
        f"the password securely. Just call the tool and give me "
        f"back the URL it returns. Don't ask me to type the "
        f"password in chat."
    )
    cost_recorder(result)
    assert result.success

    # Must contain a /capture/ URL (the auth token will be at least
    # 20 chars of url-safe base64).
    capture_url_pattern = re.compile(r"/capture/[A-Za-z0-9_-]{20,}")
    assert capture_url_pattern.search(result.response), (
        f"expected /capture/<token> URL in response, got: {result!r}"
    )

    # Must NOT prompt the user to type a password in chat. Common
    # bad phrasings:
    bad_phrases = [
        "type your password", "enter your password",
        "send me the password", "give me the password",
        "tell me the password", "what is the password",
        "what's the password",
    ]
    assert not any(p in result.lower for p in bad_phrases), (
        f"LLM asked the user to type the password in chat — would "
        f"land plaintext credentials in LLM context. {result!r}"
    )
