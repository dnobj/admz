"""A factory-reset device the operator asked to recover raises a setup notice.

Since ADR-0068 ADMZ never provisions unattended: provisioning writes the fleet
root password, and a queued recovery fires hours later against whatever
answers at the device's address. Until 2026-09-23 the queued task still tried,
was refused, and failed, while the chat promised a re-provision. It now raises a
``setup`` notice, the notice's review asks the chat to onboard the device (behind
the usual approval), and a successful onboarding closes it.

These pin the words the model and the operator read, which are the other half
of the change.
"""

from pathlib import Path

import admz


def _src(rel):
    return (Path(admz.__file__).parent / rel).read_text(encoding="utf-8")


class TestTheNotice:
    def test_setup_is_a_notice_kind(self):
        from admz.notices.store import KIND_SETUP, KINDS
        assert KIND_SETUP == "setup" and KIND_SETUP in KINDS

    def test_one_live_notice_per_device(self):
        from admz.notices.producers import setup_notice
        a = setup_notice("cam-sn-1", task_id="t1")
        b = setup_notice("cam-sn-1", task_id="t2")
        assert a.id == b.id and b.occurrences == 2

    def test_the_review_note_says_what_onboarding_will_do(self):
        from admz.notices.notes import CLOSING, review_note
        from admz.notices.producers import setup_notice

        note = review_note([setup_notice("cam-sn-2")])
        assert "device cam-sn-2 came back factory-defaulted" in note
        assert "a queued recovery noticed it" in note
        assert "fleet root password" in note and "'admz'" in note
        assert "behind one approval" in note
        assert note.endswith(CLOSING)
        assert "\n" not in note

    def test_the_title_the_strip_shows(self):
        from admz.notices.producers import setup_notice
        assert setup_notice("cam-sn-3").title == "Factory-reset — onboard it to set it up"


class TestTheWordsTheModelReads:
    def test_the_tool_no_longer_promises_a_provision(self):
        from admz.mcp.tools.recovery import TOOLS

        tool = next(t for t in TOOLS if t.name == "queue_device_recovery")
        assert "Console notice" in tool.description
        assert "does NOT set the device up" in tool.description
        assert "onboard_device" in tool.description
        assert "generated" not in tool.description, (
            "the tool still promises a generated-password re-provision")
        assert "username" not in tool.input_schema["properties"]

    def test_the_prompt_sends_a_needs_setup_device_to_onboarding(self):
        src = _src("chatbot/system_prompt.py")
        assert "Re-provision passwords are generated" not in src
        assert "call `onboard_device(device_id)`" in src
        assert "don't queue anything" in src


class TestTheWordsTheOperatorReads:
    def test_the_device_page_offers_to_set_it_up(self):
        page = _src("api/templates/device_detail.html")
        assert "Queue re-provision" not in page
        assert "Queue setup notice" in page
        assert ">Set it up</button>" in page
        assert "create an admin with a generated password" not in page

    def test_the_tasks_page_labels_the_action(self):
        page = _src("api/templates/tasks.html")
        assert "reprovision: { label: 'Setup notice'" in page
        assert "Creates the admin with a generated password" not in page
