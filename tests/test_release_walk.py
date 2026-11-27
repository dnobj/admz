"""The import walk: every module, on the interpreter that will run it.

Two of these tests exist because of things that went wrong once.

``test_a_package_that_fails_to_import_is_reported`` is the silent pass found
during the deploy of 2026-11-13. ``pkgutil.walk_packages`` skips a package whose
``__init__`` raises ImportError and reports nothing, unless it is given a hook.
The walk now does its own descent, and this test is what keeps a later
"simplification" back to ``walk_packages`` from bringing the hole back.

``test_the_walk_refuses_a_real_data_folder`` and its neighbours are the rule
that importing must never be able to reach a real database.

Most tests walk a small package written into a temporary folder. One walks the
real package, in its own process, exactly as an upgrade does.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

import pytest

from admz.release import walk

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def package(tmp_path):
    """Write a package into a new folder; returns ``(source folder, name, write)``."""
    name = f"walked_{uuid.uuid4().hex[:8]}"
    root = tmp_path / "source"
    (root / name).mkdir(parents=True)
    (root / name / "__init__.py").write_text("", encoding="utf-8")

    def write(relative, text):
        path = root / name / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    write("good.py", "VALUE = 1\n")
    write("sub/__init__.py", "")
    write("sub/leaf.py", "from .. import good\n")
    yield root, name, write
    for loaded in [m for m in sys.modules if m == name or m.startswith(name + ".")]:
        del sys.modules[loaded]


@pytest.fixture
def here(package, monkeypatch):
    """The same package, importable in this process."""
    root, name, write = package
    monkeypatch.syspath_prepend(str(root))
    return root, name, write


# ── walking, in this process ────────────────────────────────────────────────

def test_every_module_is_imported(here):
    root, name, _ = here
    result = walk.walk(name, source=root)
    assert result.ok
    assert sorted(result.imported) == [name, f"{name}.good", f"{name}.sub", f"{name}.sub.leaf"]


@pytest.mark.parametrize("body,said", [
    ("import a_module_that_does_not_exist_anywhere\n", "ModuleNotFoundError"),
    ("raise ImportError('missing native library')\n", "ImportError: missing native library"),
    ("raise RuntimeError('side effect at import')\n", "RuntimeError: side effect at import"),
    ("import sys\nsys.exit(3)\n", "SystemExit"),
    ("def broken(:\n", "SyntaxError"),
])
def test_a_module_that_fails_to_import_is_reported(here, body, said):
    root, name, write = here
    write("bad.py", body)
    result = walk.walk(name, source=root)
    assert not result.ok
    assert [failed for failed, _ in result.failures] == [f"{name}.bad"]
    assert said in result.failures[0][1]
    assert f"{name}.good" in result.imported, "one bad module does not stop the walk"


@pytest.mark.parametrize("body", [
    "raise ImportError('this package cannot load')\n",
    "raise RuntimeError('this package cannot load')\n",
])
def test_a_package_that_fails_to_import_is_reported(here, body):
    """``pkgutil.walk_packages`` without a hook skips the ImportError case in silence."""
    root, name, write = here
    write("brokenpkg/__init__.py", body)
    write("brokenpkg/inner.py", "VALUE = 2\n")
    result = walk.walk(name, source=root)
    assert not result.ok
    failed = [module for module, _ in result.failures]
    assert failed == [f"{name}.brokenpkg"], "reported once, and its children are not guessed at"
    assert "this package cannot load" in result.failures[0][1]


def test_a_failure_says_where_it_happened(here):
    root, name, write = here
    write("bad.py", "\n\nraise RuntimeError('boom')\n")
    reason = walk.walk(name, source=root).failures[0][1]
    assert reason == "RuntimeError: boom (bad.py:3)"


def test_a_root_that_cannot_be_imported_is_a_failure_not_an_empty_success(here):
    result = walk.walk("no_such_package_at_all")
    assert not result.ok and result.imported == []
    assert result.failures[0][0] == "no_such_package_at_all"


def test_an_empty_answer_is_not_ok():
    assert walk.WalkResult([], []).ok is False


def test_a_package_imported_from_somewhere_else_is_refused(here, tmp_path):
    """An environment can hold an installed copy of the same package. A walk
    that imported that one would vouch for code nobody asked about."""
    _, name, _ = here
    elsewhere = tmp_path / "another-checkout"
    elsewhere.mkdir()
    result = walk.walk(name, source=elsewhere)
    assert not result.ok and result.imported == []
    assert "not from" in result.failures[0][1] and "wrong code" in result.failures[0][1]


# ── the data folder it may import against ───────────────────────────────────

def test_a_throwaway_folder_named_by_the_variable_is_accepted(tmp_path):
    assert walk.check_home(tmp_path, {"ADMZ_HOME": str(tmp_path), "PATH": "x"}) is None


def test_the_walk_refuses_when_the_variable_is_not_set(tmp_path):
    assert "not set" in walk.check_home(tmp_path, {"PATH": "x"})


def test_the_walk_refuses_when_the_variable_names_another_folder(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    assert "not the folder this walk was told to use" in walk.check_home(
        tmp_path, {"ADMZ_HOME": str(other)})


@pytest.mark.parametrize("data_file", ["admz.db", "admz.key"])
def test_the_walk_refuses_a_real_data_folder(tmp_path, data_file):
    (tmp_path / data_file).write_bytes(b"x")
    assert "that is a data folder, not a throwaway" in walk.check_home(
        tmp_path, {"ADMZ_HOME": str(tmp_path)})


def test_the_walk_refuses_a_folder_that_does_not_exist(tmp_path):
    missing = tmp_path / "missing"
    assert "is not a folder" in walk.check_home(missing, {"ADMZ_HOME": str(missing)})


def test_the_walk_refuses_when_an_override_could_point_elsewhere(tmp_path):
    """``ADMZ_DB_PATH`` wins over ``ADMZ_HOME``, so the folder alone proves nothing."""
    refusal = walk.check_home(tmp_path, {"ADMZ_HOME": str(tmp_path), "ADMZ_DB_PATH": "C:/real.db"})
    assert "ADMZ_DB_PATH" in refusal


def test_main_refuses_before_importing_anything(here, monkeypatch, capsys, tmp_path):
    root, name, write = here
    write("__init__.py", "raise RuntimeError('the package was imported')\n")
    monkeypatch.delenv("ADMZ_HOME", raising=False)
    assert walk.main(["--home", str(tmp_path), "--source", str(root), "--package", name]) == 2
    assert "refused" in json.loads(capsys.readouterr().out)
    assert name not in sys.modules, "the check comes before the first import"


def test_the_clean_environment_drops_everything_that_could_steer_an_import():
    cleaned = walk.clean_environment({
        "PATH": "kept", "SYSTEMROOT": "kept", "ADMZ_HOME": "C:/ProgramData/admz",
        "ADMZ_DB_PATH": "x", "ADMZ_AUTH_BACKEND": "windows-local",
        "PYTHONPATH": "x", "PYTHONHOME": "x"})
    assert cleaned == {"PATH": "kept", "SYSTEMROOT": "kept"}


# ── walking in a child process, as an upgrade does ──────────────────────────

def test_a_child_process_walks_the_package(package):
    root, name, _ = package
    result = walk.run(Path(sys.executable), root, package=name)
    assert result.ok and f"{name}.sub.leaf" in result.imported


def test_a_child_process_reports_what_failed(package):
    root, name, write = package
    write("bad.py", "raise ImportError('missing native library')\n")
    result = walk.run(Path(sys.executable), root, package=name)
    assert [module for module, _ in result.failures] == [f"{name}.bad"]


def test_the_child_sees_a_throwaway_data_folder_and_no_other_setting(package, monkeypatch, tmp_path):
    """The ambient variables belong to whoever opened the shell. On the
    development machine that is the lab instance's data folder."""
    root, name, write = package
    real = tmp_path / "pretend-real-data"
    real.mkdir()
    monkeypatch.setenv("ADMZ_HOME", str(real))
    monkeypatch.setenv("ADMZ_DB_PATH", str(real / "admz.db"))
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "somewhere"))
    write("spy.py", (
        "import json, os, pathlib\n"
        "seen = {k: v for k, v in os.environ.items() if k.startswith('ADMZ_') or k == 'PYTHONPATH'}\n"
        "pathlib.Path(__file__).with_name('seen.json').write_text(json.dumps(seen))\n"))
    assert walk.run(Path(sys.executable), root, package=name).ok
    seen = json.loads((root / name / "seen.json").read_text())
    assert set(seen) == {"ADMZ_HOME"}
    assert Path(seen["ADMZ_HOME"]) != real and "admz-walk-home-" in seen["ADMZ_HOME"]
    assert not Path(seen["ADMZ_HOME"]).exists(), "the throwaway folder is removed afterwards"
    assert list(real.iterdir()) == []


class Done:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def test_the_child_is_started_isolated_as_a_file_in_the_source_folder(tmp_path):
    seen = {}

    def runner(command, **kwargs):
        seen["command"], seen["kwargs"] = command, kwargs
        return Done(0, json.dumps({"imported": ["admz"], "failures": []}))

    walk.run(Path("the/python.exe"), tmp_path, runner=runner)
    command = seen["command"]
    assert command[:2] == [str(Path("the/python.exe")), "-I"], "without the operator's own packages"
    assert Path(command[2]) == Path(walk.__file__).resolve(), "as a file, so nothing is imported first"
    assert "-m" not in command
    assert command[command.index("--source") + 1] == str(tmp_path)
    assert command[command.index("--package") + 1] == "admz"
    env = seen["kwargs"]["env"]
    assert env["ADMZ_HOME"] == command[command.index("--home") + 1]
    assert [k for k in env if k.startswith("ADMZ_")] == ["ADMZ_HOME"]
    assert seen["kwargs"]["cwd"] == str(tmp_path)


@pytest.mark.parametrize("done,said", [
    (Done(2, json.dumps({"refused": "ADMZ_HOME is not set"})), "refused to run: ADMZ_HOME is not set"),
    (Done(1, "", "Traceback\nSyntaxError: invalid syntax"), "no readable answer.*SyntaxError"),
    (Done(0, "not json at all"), "no readable answer"),
    (Done(0, json.dumps({"imported": ["admz"]})), "missing a field"),
    (Done(0, json.dumps(["admz"])), "not an object"),
])
def test_a_child_that_gives_no_usable_answer_is_an_error_not_a_pass(tmp_path, done, said):
    with pytest.raises(walk.WalkError, match=said):
        walk.run(Path(sys.executable), tmp_path, runner=lambda command, **kw: done)


def test_a_child_that_cannot_be_started_is_an_error(tmp_path):
    def runner(command, **kwargs):
        raise FileNotFoundError("no such interpreter")

    with pytest.raises(walk.WalkError, match="could not be run"):
        walk.run(tmp_path / "python.exe", tmp_path, runner=runner)


def test_warnings_printed_before_the_answer_do_not_hide_it(tmp_path):
    out = "DeprecationWarning: something\n" + json.dumps({"imported": ["admz"], "failures": []}) + "\n"
    assert walk.run(Path(sys.executable), tmp_path, runner=lambda c, **k: Done(0, out)).ok


# ── the real package ────────────────────────────────────────────────────────

def test_every_module_of_this_checkout_imports_on_this_interpreter():
    """The check an upgrade makes, made on every commit.

    It runs in its own process against a throwaway data folder, so it is also
    the proof that importing the whole package touches no data folder: the
    ambient ``ADMZ_HOME`` never reaches the child.
    """
    result = walk.run(Path(sys.executable), REPO)
    assert result.failures == []
    assert len(result.imported) > 200, f"only {len(result.imported)} modules were found"
    for expected in ("admz", "admz.api.main", "admz.mcp.server", "admz.release.upgrade",
                     "admz.release.walk", "admz.__main__"):
        assert expected in result.imported
