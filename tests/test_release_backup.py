"""The copy of the database and its key that an upgrade takes first (FR-DEP-007).

The property that matters most is the one a plain file copy does not have. The
service is running while the copy is taken, the database is in WAL mode, and the
newest writes sit in a second file. ``test_writes_still_in_the_wal_are_in_the_copy``
builds exactly that state and shows both halves: the backup has the rows, and a
file copy of the same database at the same moment does not.

Every test works in a temporary folder. Nothing here opens a real data folder.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone

import pytest

from admz.release import backup as backups

WHEN = datetime(2026, 11, 26, 14, 5, 9, tzinfo=timezone.utc)
KEY = b"0123456789abcdef0123456789abcdef0123456789a="


def _make_db(path, rows=3):
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE devices (id INTEGER PRIMARY KEY, name TEXT)")
    conn.executemany("INSERT INTO devices (name) VALUES (?)", [(f"cam-{n}",) for n in range(rows)])
    conn.commit()
    conn.close()


def _names(path):
    conn = sqlite3.connect(str(path))
    try:
        return [row[0] for row in conn.execute("SELECT name FROM devices ORDER BY id")]
    finally:
        conn.close()


@pytest.fixture
def home(tmp_path):
    folder = tmp_path / "data"
    folder.mkdir()
    _make_db(folder / backups.DB_NAME)
    (folder / backups.KEY_NAME).write_bytes(KEY)
    return folder


def test_a_backup_holds_the_database_the_key_and_a_manifest(home):
    taken = backups.back_up(home, "aaaaaaa-to-bbbbbbb", now=WHEN)
    assert taken.folder == home / "backups" / "20261126T140509Z-aaaaaaa-to-bbbbbbb"
    assert sorted(p.name for p in taken.folder.iterdir()) == [
        backups.DB_NAME, backups.KEY_NAME, backups.MANIFEST_NAME]
    assert _names(taken.folder / backups.DB_NAME) == ["cam-0", "cam-1", "cam-2"]
    assert (taken.folder / backups.KEY_NAME).read_bytes() == KEY

    manifest = json.loads((taken.folder / backups.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["files"] == taken.files
    assert manifest["label"] == "aaaaaaa-to-bbbbbbb" and manifest["source"] == str(home)
    by_name = {entry["name"]: entry for entry in manifest["files"]}
    assert set(by_name) == {backups.DB_NAME, backups.KEY_NAME}
    assert by_name[backups.KEY_NAME]["bytes"] == len(KEY)
    assert len(by_name[backups.DB_NAME]["sha256"]) == 64
    assert backups.verify(taken.folder) == []


def test_writes_still_in_the_wal_are_in_the_copy(home):
    """The reason the backup API is used and the file is never copied."""
    db = home / backups.DB_NAME
    writer = sqlite3.connect(str(db))
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")       # keep the new rows in the WAL
        writer.execute("INSERT INTO devices (name) VALUES ('written-while-running')")
        writer.commit()

        # A file copy at this moment, as a naive backup would take it.
        naive = home.parent / "naive.db"
        shutil.copy(db, naive)
        assert "written-while-running" not in _names(naive), (
            "the test no longer builds the state it is about: the row reached the "
            "main file, so a file copy would have been enough")

        taken = backups.back_up(home, "wal", now=WHEN)
    finally:
        writer.close()
    assert "written-while-running" in _names(taken.folder / backups.DB_NAME)


def test_every_database_at_the_top_of_the_folder_is_copied(home):
    _make_db(home / "events.db", rows=1)
    (home / "nested").mkdir()
    _make_db(home / "nested" / "other.db")
    taken = backups.back_up(home, "all", now=WHEN)
    assert {entry["name"] for entry in taken.files} == {
        backups.DB_NAME, "events.db", backups.KEY_NAME}
    assert _names(taken.folder / "events.db") == ["cam-0"]


def test_the_source_is_left_exactly_as_it_was(home):
    before = {p.name: p.read_bytes() for p in home.iterdir() if p.is_file()}
    backups.back_up(home, "untouched", now=WHEN)
    after = {p.name: p.read_bytes() for p in home.iterdir() if p.is_file()}
    assert after == before, "a backup must not change, add or remove a file beside the database"
    assert sorted(p.name for p in home.iterdir() if p.is_dir()) == ["backups"]


def test_a_folder_without_a_database_is_not_backed_up(tmp_path):
    (tmp_path / backups.KEY_NAME).write_bytes(KEY)
    with pytest.raises(backups.BackupError, match="holds no admz.db"):
        backups.back_up(tmp_path, "x", now=WHEN)
    assert not (tmp_path / "backups").exists()


def test_a_database_without_its_key_is_not_backed_up(home):
    (home / backups.KEY_NAME).unlink()
    with pytest.raises(backups.BackupError, match="holds no admz.key"):
        backups.back_up(home, "x", now=WHEN)
    assert not (home / "backups").exists()


def test_a_database_that_cannot_be_read_stops_the_backup_and_leaves_nothing(home):
    (home / backups.DB_NAME).write_bytes(b"this is not a database " * 400)
    with pytest.raises(backups.BackupError):
        backups.back_up(home, "broken", now=WHEN)
    left = list((home / "backups").iterdir()) if (home / "backups").exists() else []
    assert left == [], "a failed backup must not leave a folder that looks like one"


def test_a_copy_that_fails_sqlites_own_check_is_not_trusted(home):
    """The backup API copies pages; it does not judge them. A database that
    opens and copies cleanly can still be damaged, and the copy inherits it."""
    db = home / backups.DB_NAME
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE INDEX by_name ON devices (name)")
    conn.commit()
    conn.execute("PRAGMA writable_schema=ON")
    conn.execute("DELETE FROM sqlite_master WHERE name='by_name'")   # its pages are now orphans
    conn.commit()
    conn.close()
    check = sqlite3.connect(str(db))
    verdict = [row[0] for row in check.execute("PRAGMA integrity_check")]
    check.close()
    assert verdict != ["ok"], "the test no longer damages the database in a way SQLite reports"

    with pytest.raises(backups.BackupError, match="fails SQLite's integrity check"):
        backups.back_up(home, "damaged", now=WHEN)
    assert list((home / "backups").iterdir()) == []


def test_the_source_is_opened_read_only(home, monkeypatch):
    """A backup must not be able to change what it is protecting."""
    _make_db(home / "events.db", rows=1)
    opened = []
    real = sqlite3.connect

    def connect(target, *args, **kwargs):
        opened.append((str(target).replace("\\", "/"), kwargs.get("uri", False)))
        return real(target, *args, **kwargs)

    monkeypatch.setattr(backups.sqlite3, "connect", connect)
    backups.back_up(home, "ro", now=WHEN)
    sources = [(target, uri) for target, uri in opened if "/backups/" not in target]
    assert len(sources) == 2, "one connection to each database in the data folder"
    for target, uri in sources:
        assert uri is True and target.startswith("file:") and target.endswith("?mode=ro"), target


def test_a_second_database_that_cannot_be_read_also_stops_it(home):
    (home / "events.db").write_bytes(b"\x00" * 5000 + b"garbage")
    with pytest.raises(backups.BackupError):
        backups.back_up(home, "broken", now=WHEN)
    assert list((home / "backups").iterdir()) == []


def test_a_backup_is_never_written_over_another(home):
    first = backups.back_up(home, "same", now=WHEN)
    kept = (first.folder / backups.MANIFEST_NAME).read_bytes()
    with pytest.raises(backups.BackupError, match="already exists"):
        backups.back_up(home, "same", now=WHEN)
    assert (first.folder / backups.MANIFEST_NAME).read_bytes() == kept


def test_a_half_written_folder_from_an_earlier_crash_is_not_reused(home):
    partial = home / "backups" / "20261126T140509Z-same.partial"
    partial.mkdir(parents=True)
    with pytest.raises(backups.BackupError, match="already exists"):
        backups.back_up(home, "same", now=WHEN)
    assert partial.is_dir()


def test_the_label_cannot_name_another_folder(home):
    taken = backups.back_up(home, "../../outside and more", now=WHEN)
    assert taken.folder.parent == home / "backups"
    assert taken.folder.name == "20261126T140509Z-..-..-outside-and-more"
    assert backups.back_up(home, "///", now=WHEN).folder.name == "20261126T140509Z-backup"


def test_verify_notices_a_changed_a_shrunk_and_a_missing_file(home):
    taken = backups.back_up(home, "v", now=WHEN)
    key = taken.folder / backups.KEY_NAME
    key.write_bytes(KEY[:-1] + b"X")                       # same size, other content
    assert backups.verify(taken.folder) == ["admz.key does not match the hash in the manifest"]
    key.write_bytes(KEY[:10])
    assert "bytes, the manifest says" in backups.verify(taken.folder)[0]
    key.unlink()
    assert backups.verify(taken.folder) == ["admz.key is missing"]


def test_verify_says_so_when_there_is_no_manifest(home):
    taken = backups.back_up(home, "v", now=WHEN)
    (taken.folder / backups.MANIFEST_NAME).unlink()
    problems = backups.verify(taken.folder)
    assert len(problems) == 1 and "no readable manifest" in problems[0]
