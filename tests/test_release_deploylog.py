"""The deploy log on the host (ADR-0075, FR-DEP-006).

ADR-0054 asked for it in August and it was never built, so the lab instance
could not say what it was running or since when. These tests hold the two
properties that make it worth having: every attempt leaves a line, and a line
is never lost or invented.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from admz.release import deploylog

A, B = "a" * 40, "b" * 40
WHEN = datetime(2026, 11, 26, 14, 5, 9, tzinfo=timezone.utc)


def _append(home, outcome="ok", **more):
    return deploylog.append(home, action="upgrade", outcome=outcome, source=A, target=B,
                            now=WHEN, **more)


def test_one_attempt_is_one_json_line(tmp_path):
    written = _append(tmp_path, detail="", backup="C:/data/backups/x", seconds=8.2)
    raw = (tmp_path / deploylog.LOG_NAME).read_bytes()
    assert raw.endswith(b"\n") and raw.count(b"\n") == 1 and b"\r" not in raw
    assert json.loads(raw) == written
    assert written["at"] == "2026-11-26T14:05:09Z"
    assert (written["action"], written["outcome"], written["from"], written["to"]) == (
        "upgrade", "ok", A, B)
    assert written["backup"] == "C:/data/backups/x" and written["seconds"] == 8.2
    assert written["operator"] and written["host"] is not None


def test_lines_are_appended_and_read_back_oldest_first(tmp_path):
    _append(tmp_path, "refused", detail="the tree has local changes")
    _append(tmp_path, "rolled-back", detail="not healthy within 90s")
    _append(tmp_path, "ok")
    assert [r["outcome"] for r in deploylog.read(tmp_path)] == ["refused", "rolled-back", "ok"]


@pytest.mark.parametrize("outcome", deploylog.OUTCOMES)
def test_every_way_an_attempt_can_end_is_accepted(tmp_path, outcome):
    assert _append(tmp_path, outcome)["outcome"] == outcome


def test_an_outcome_nobody_defined_is_refused_and_nothing_is_written(tmp_path):
    with pytest.raises(ValueError, match="unknown outcome"):
        _append(tmp_path, "probably-fine")
    assert not (tmp_path / deploylog.LOG_NAME).exists()


def test_a_data_folder_that_does_not_exist_is_not_created(tmp_path):
    """A mistyped folder must fail, not gain a log that nobody will ever read."""
    missing = tmp_path / "typo"
    with pytest.raises(FileNotFoundError, match="does not create one"):
        _append(missing)
    assert not missing.exists()


def test_no_log_reads_as_no_history(tmp_path):
    assert deploylog.read(tmp_path) == []
    assert deploylog.last_success(tmp_path) is None


def test_a_line_that_cannot_be_read_is_returned_not_dropped(tmp_path):
    _append(tmp_path, "ok")
    with open(tmp_path / deploylog.LOG_NAME, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("half a li\n\n[1, 2]\n")
    _append(tmp_path, "refused")
    records = deploylog.read(tmp_path)
    assert [r.get("outcome") for r in records] == ["ok", None, None, "refused"]
    assert records[1] == {"unreadable": "half a li"}
    assert records[2] == {"unreadable": "[1, 2]"}


def test_the_last_success_skips_what_did_not_change_the_instance(tmp_path):
    _append(tmp_path, "ok", detail="first")
    _append(tmp_path, "ok", detail="second")
    _append(tmp_path, "rolled-back")
    _append(tmp_path, "refused")
    assert deploylog.last_success(tmp_path)["detail"] == "second"


def test_text_outside_ascii_survives(tmp_path):
    _append(tmp_path, "refused", detail="Zugriff verweigert — überprüfen")
    assert deploylog.read(tmp_path)[0]["detail"] == "Zugriff verweigert — überprüfen"


def test_an_account_with_no_name_is_recorded_as_unknown(tmp_path, monkeypatch):
    def nobody():
        raise OSError("no username")

    monkeypatch.setattr(deploylog.getpass, "getuser", nobody)
    assert _append(tmp_path)["operator"] == "unknown"
