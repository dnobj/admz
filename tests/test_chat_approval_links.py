"""Approval links the chat model did not get from a tool (2026-09-15).

A continuation turn told the operator "the confirmation card for AXIS P8815-2
is ready" with a ``/confirm/`` link it had written itself; no tool had been
called, so there was nothing to approve. The model had seen that shape in its
own earlier replies, which carried real links from earlier turns.

These pin the helpers both defences use, and the first defence: links in the
model's earlier replies are redacted before history is sent back to it. The
second — holding back a reply whose link no tool issued — is pinned in
``test_chatbot_manual_loop.py``, beside the loop it lives in.
"""

from __future__ import annotations

import pytest

from admz.chatbot import action_links as al
from admz.chatbot.client import _build_contents

TOK = "T" * 24


@pytest.mark.parametrize("url", [
    f"/confirm/{TOK}", f"/capture/{TOK}", f"/capture/rule/{TOK}", f"/capture/fleet/{TOK}",
])
def test_every_session_link_shape_is_found(url):
    assert al.tokens_in(f"open `{url}` to approve") == {TOK}


def test_tokens_are_found_inside_a_tool_result():
    assert al.tokens_in({"blocked": True, "confirm_url": f"/confirm/{TOK}"}) == {TOK}


def test_a_short_token_or_a_page_path_is_not_a_link():
    """Control: the {20,} floor and the path shape keep ordinary text out."""
    assert al.tokens_in("see /confirm/abc and /confirm-settings") == set()


def test_unbacked_means_linked_but_not_issued():
    other = "U" * 24
    text = f"`/confirm/{TOK}` and `/confirm/{other}`"
    assert al.unbacked_tokens(text, issued={TOK}) == {other}
    assert al.unbacked_tokens(text, issued={TOK, other}) == set()


def test_an_unserialisable_result_scans_as_empty_rather_than_raising():
    class Opaque:
        def __repr__(self):
            raise RuntimeError("no")

    assert al.tokens_in({"x": Opaque()}) == set()


class TestHistoryReplay:
    def test_links_in_the_models_own_earlier_replies_are_redacted(self):
        history = [
            {"role": "user", "text": "remove the C1710"},
            {"role": "model", "text": f"Approve the card: `/confirm/{TOK}`"},
            {"role": "event", "text": '[console] The user approved "delete_device".'},
        ]
        items = _build_contents(history, "")
        replayed = items[1]["parts"][0]["text"]
        assert TOK not in replayed, "an earlier reply still teaches the link pattern"
        assert al.REDACTED in replayed
        assert replayed.startswith("Approve the card"), "the rest of the reply survives"

    def test_the_live_message_and_console_notes_are_left_alone(self):
        """Control: only the model's own replayed output is redacted."""
        history = [{"role": "event", "text": f"[console] a note naming /confirm/{TOK}"}]
        items = _build_contents(history, f"what was /confirm/{TOK}?")
        assert TOK in items[0]["parts"][0]["text"]
        assert TOK in items[-1]["parts"][0]["text"]
