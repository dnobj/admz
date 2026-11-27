"""The dependency locks, and the tool that makes and checks them (ADR-0075).

Before the locks, CI installed from the bounds in ``requirements-dev.txt`` and
resolved afresh on every run. Two things followed. A transitive package nobody
had chosen could arrive between two runs of one commit. And the lab instance
ran versions the suite had never executed: its starlette sat outside the
declared bound for three months (review-2026-11-09, O-2), and nothing noticed,
because nothing built that environment from a fixed list.

A lock fixes that only while four things stay true, and nobody reviews a
thousand hash lines by eye. So each is a test:

* the locks were made from the requirement files as they stand now;
* every declared requirement is pinned inside its own bound, on every platform
  it is declared for;
* the runtime lock sits inside the dev lock, pin for pin and hash for hash, so
  what CI tests is what a build installs;
* CI installs from the dev lock in hash mode, and then checks that the
  environment it is about to test really is that lock.

The rest covers the tool: the reader that refuses what a lock must not hold,
the marker evaluation (checked against ``packaging`` on every marker the locks
contain), and the comparison of an environment with a lock.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
import yaml
from packaging.markers import Marker
from packaging.requirements import Requirement

from tools import lock as locks

REPO = Path(__file__).resolve().parent.parent
ACTION = REPO / ".github" / "actions" / "setup-admz" / "action.yml"

RUNTIME = locks.read_lock(REPO / locks.RUNTIME_LOCK)
DEV = locks.read_lock(REPO / locks.DEV_LOCK)


def _markers(**changes):
    base = {
        "implementation_name": "cpython",
        "implementation_version": "3.12.4",
        "os_name": "nt",
        "platform_machine": "AMD64",
        "platform_python_implementation": "CPython",
        "platform_release": "11",
        "platform_system": "Windows",
        "platform_version": "10.0.26100",
        "python_full_version": "3.12.4",
        "python_version": "3.12",
        "sys_platform": "win32",
    }
    base.update(changes)
    return base


WINDOWS = _markers()
LINUX = _markers(os_name="posix", platform_machine="x86_64", platform_system="Linux",
                 platform_release="6.8.0-1017-azure", platform_version="#20-Ubuntu SMP",
                 sys_platform="linux")
MACOS = _markers(os_name="posix", platform_machine="arm64", platform_system="Darwin",
                 platform_release="24.1.0", platform_version="Darwin Kernel Version 24.1.0",
                 sys_platform="darwin")
PYPY = dict(LINUX, implementation_name="pypy", platform_python_implementation="PyPy",
            implementation_version="7.3.17")
LINUX_313 = dict(LINUX, python_full_version="3.13.1", python_version="3.13",
                 implementation_version="3.13.1")
LINUX_3140 = dict(LINUX, python_full_version="3.14.0", python_version="3.14",
                  implementation_version="3.14.0")
ENVIRONMENTS = {"windows": WINDOWS, "linux": LINUX, "macos": MACOS, "pypy": PYPY,
                "linux-3.13": LINUX_313, "linux-3.14.0": LINUX_3140}

#: The platforms this project is installed on: the lab instance and a build on
#: Windows, CI on both.
SUPPORTED = {"windows": WINDOWS, "linux": LINUX}


# ── the locks that are committed ────────────────────────────────────────────

def _declared(name):
    for raw in (REPO / name).read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            yield Requirement(line)


DECLARED = [(name, req) for name in ("requirements.txt", "requirements-dev.txt")
            for req in _declared(name)]


def test_the_scan_found_the_declared_requirements():
    """Guard the guard: a parser that yields nothing makes the cases below pass."""
    assert len(DECLARED) >= 25, f"only parsed {len(DECLARED)} requirements"
    names = {req.name for _, req in DECLARED}
    assert {"fastapi", "starlette", "pytest", "firebird-driver"} <= names


def test_the_locks_were_made_from_the_requirement_files_as_they_stand():
    assert locks.stale_locks() == [], (
        "A requirements file changed and the locks were not regenerated, so CI "
        "would install the old resolution. Run: python tools/lock.py")


@pytest.mark.parametrize("source,req", DECLARED, ids=[f"{s}:{r.name}" for s, r in DECLARED])
def test_every_declared_requirement_is_pinned_inside_its_bound(source, req):
    targets = {locks.DEV_LOCK: DEV}
    if source == "requirements.txt":
        targets[locks.RUNTIME_LOCK] = RUNTIME
    for lock_name, pins in targets.items():
        found = [pin for pin in pins if pin.name == locks.canonical(req.name)]
        assert found, f"{source} declares {req.name}, and {lock_name} does not pin it"
        for pin in found:
            assert req.specifier.contains(pin.version, prereleases=True), (
                f"{lock_name} pins {req.name}=={pin.version}, outside the bound "
                f"'{req.specifier}' that {source} declares for it")
        for platform, env in SUPPORTED.items():
            declared_here = req.marker is None or locks.marker_applies(str(req.marker), env)
            pinned_here = [pin for pin in found if locks.marker_applies(pin.marker, env)]
            assert len(pinned_here) == (1 if declared_here else 0), (
                f"on {platform}, {source} {'declares' if declared_here else 'does not declare'} "
                f"{req.name}, but {lock_name} has {len(pinned_here)} pin(s) for it there")


def test_the_runtime_lock_sits_inside_the_dev_lock_pin_for_pin():
    """What CI tests has to be what a build installs.

    Same version is not enough. The marker decides where a pin is installed and
    the hashes decide which files are accepted, so both are compared too.
    """
    dev = {(pin.name, pin.marker): pin for pin in DEV}
    for pin in RUNTIME:
        twin = dev.get((pin.name, pin.marker))
        assert twin is not None, (
            f"{locks.RUNTIME_LOCK} pins {pin.name} ({pin.marker or 'everywhere'}), "
            f"and {locks.DEV_LOCK} has no such pin")
        assert twin.version == pin.version, (
            f"{pin.name}: the runtime lock pins {pin.version}, the dev lock {twin.version}")
        assert set(twin.hashes) == set(pin.hashes), f"{pin.name}: the two locks accept different files"
    assert len(DEV) > len(RUNTIME), "the dev lock should add the test tools"


@pytest.mark.parametrize("lock_name,pins", [(locks.RUNTIME_LOCK, RUNTIME), (locks.DEV_LOCK, DEV)])
def test_every_pin_carries_a_sha256_hash(lock_name, pins):
    assert len(pins) >= 60, f"{lock_name} holds only {len(pins)} pins"
    for pin in pins:
        assert pin.hashes, f"{lock_name}: {pin.name} has no hash, so pip would not verify it"
        for digest in pin.hashes:
            assert re.fullmatch(r"sha256:[0-9a-f]{64}", digest), (
                f"{lock_name}: {pin.name} carries {digest!r}, which is not a sha256")


@pytest.mark.parametrize("lock_name,pins", [(locks.RUNTIME_LOCK, RUNTIME), (locks.DEV_LOCK, DEV)])
@pytest.mark.parametrize("platform", sorted(ENVIRONMENTS))
def test_no_package_is_pinned_twice_for_one_platform(lock_name, pins, platform):
    here = [pin.name for pin in pins if locks.marker_applies(pin.marker, ENVIRONMENTS[platform])]
    twice = sorted({name for name in here if here.count(name) > 1})
    assert not twice, f"{lock_name} pins {twice} more than once on {platform}"


@pytest.mark.parametrize("lock_name,pins", [(locks.RUNTIME_LOCK, RUNTIME), (locks.DEV_LOCK, DEV)])
def test_one_lock_serves_windows_and_linux(lock_name, pins):
    """A lock compiled on one machine without ``--universal`` would hold only
    that machine's packages, and the other CI leg would fail to install."""
    def names(env):
        return {pin.name for pin in pins if locks.marker_applies(pin.marker, env)}

    assert "pywin32" in names(WINDOWS) and "pywin32" not in names(LINUX)
    assert "uvloop" in names(LINUX) and "uvloop" not in names(WINDOWS)
    assert "firebird-driver" in names(WINDOWS) and "firebird-driver" not in names(LINUX)


@pytest.mark.parametrize("lock_name,pins", [(locks.RUNTIME_LOCK, RUNTIME), (locks.DEV_LOCK, DEV)])
def test_the_catalog_and_the_application_are_not_in_a_lock(lock_name, pins):
    """The catalog is pinned by commit in setup.py, and pip refuses a git
    reference in hash mode. A lock that named either would not install."""
    names = {pin.name for pin in pins}
    assert not names & {"admz", "axis-api-atlas"}


def test_the_test_tools_are_only_in_the_dev_lock():
    runtime = {pin.name for pin in RUNTIME}
    assert not runtime & {"pytest", "black", "mypy", "flake8", "pytest-xdist"}, (
        "a build installs the runtime lock, and a deployment carries no test tools")
    assert {"pytest", "pytest-xdist", "black", "mypy"} <= {pin.name for pin in DEV}


@pytest.mark.parametrize("lock_name", [locks.RUNTIME_LOCK, locks.DEV_LOCK])
def test_a_lock_names_no_file_outside_the_repository(lock_name):
    """uv notes each constraint file beside the pins it touched. The first lock
    was aligned to a list of the lab instance's packages, which lived in a
    temporary folder under one person's profile; this repository is public."""
    known = {"requirements.txt", "requirements-dev.txt", locks.RUNTIME_LOCK}
    text = (REPO / lock_name).read_text(encoding="utf-8")
    named = set(re.findall(r"^\s*#.*?-[cr] (\S+)", text, re.MULTILINE))
    assert named <= known, f"{lock_name} names {sorted(named - known)}"
    assert not re.search(r"[A-Za-z]:[\\/]|/Users/|/home/", text)


@pytest.mark.parametrize("lock_name", [locks.RUNTIME_LOCK, locks.DEV_LOCK])
def test_a_lock_says_how_it_is_regenerated(lock_name):
    head = (REPO / lock_name).read_text(encoding="utf-8").splitlines()[:4]
    assert any(locks.COMPILE_COMMAND in line for line in head)
    assert any(line.startswith(locks.MARK) for line in head)


def test_the_locks_keep_unix_line_endings_on_every_platform():
    """uv writes LF. Without this a Windows checkout would hold different bytes
    from the file that was generated and from the one the Linux leg installs."""
    rules = (REPO / ".gitattributes").read_text(encoding="utf-8").splitlines()
    assert "requirements*.lock text eol=lf" in rules


# ── the reader refuses what a lock must not hold ────────────────────────────

def _lock(tmp_path, text):
    path = tmp_path / "some.lock"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_reader_returns_names_versions_markers_and_hashes(tmp_path):
    pins = locks.read_lock(_lock(tmp_path, (
        "# a comment\n"
        "Jinja2==3.1.6 \\\n"
        "    --hash=sha256:" + "a" * 64 + " \\\n"
        "    --hash=sha256:" + "b" * 64 + "\n"
        "    # via fastapi\n"
        "python_dotenv==1.2.2 ; sys_platform == 'win32' \\\n"
        "    --hash=sha256:" + "c" * 64 + "\n"
    )))
    assert pins == [
        locks.Pin("jinja2", "3.1.6", "", ("sha256:" + "a" * 64, "sha256:" + "b" * 64)),
        locks.Pin("python-dotenv", "1.2.2", "sys_platform == 'win32'", ("sha256:" + "c" * 64,)),
    ]


@pytest.mark.parametrize("line", [
    "-e .",
    "--index-url https://example.invalid/simple",
    "--extra-index-url https://example.invalid/simple",
    "requests>=2",
    "requests",
    "axis-api-atlas @ git+ssh://git@github.com/example/repo.git@abc",
    "https://example.invalid/pkg-1.0-py3-none-any.whl",
    "-r requirements.txt",
])
def test_the_reader_refuses_anything_that_is_not_a_pin(tmp_path, line):
    """Each of these is something a lock must not contain. A reader that skipped
    the line would hide it from every check above."""
    with pytest.raises(locks.LockError, match="not a comment, a pin or a hash"):
        locks.read_lock(_lock(tmp_path, f"attrs==26.1.0 \\\n    --hash=sha256:{'a' * 64}\n{line}\n"))


def test_the_reader_refuses_a_hash_that_belongs_to_no_pin(tmp_path):
    with pytest.raises(locks.LockError, match="no pin above it"):
        locks.read_lock(_lock(tmp_path, f"# header\n    --hash=sha256:{'a' * 64}\n"))


# ── a lock goes stale when its inputs change ────────────────────────────────

@pytest.fixture
def tree(tmp_path):
    """A copy of the four files, somewhere a test may edit them."""
    for name in ("requirements.txt", "requirements-dev.txt", locks.RUNTIME_LOCK, locks.DEV_LOCK):
        shutil.copy(REPO / name, tmp_path / name)
    return tmp_path


def _rewrite(path, old, new):
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} is not in {path.name}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_a_fresh_copy_is_not_stale(tree):
    assert locks.stale_locks(tree) == []


def test_a_changed_runtime_bound_makes_both_locks_stale(tree):
    _rewrite(tree / "requirements.txt", "jinja2>=3.1.2,<4", "jinja2>=3.1.3,<4")
    problems = locks.stale_locks(tree)
    assert len(problems) == 2
    assert any(p.startswith(locks.RUNTIME_LOCK) for p in problems)
    assert any(p.startswith(locks.DEV_LOCK) for p in problems)
    assert all("python tools/lock.py" in p for p in problems)


def test_a_changed_test_tool_bound_makes_only_the_dev_lock_stale(tree):
    _rewrite(tree / "requirements-dev.txt", "flake8>=7.0.0,<8", "flake8>=7.1.0,<8")
    problems = locks.stale_locks(tree)
    assert len(problems) == 1 and problems[0].startswith(locks.DEV_LOCK)


def test_a_new_requirement_makes_the_locks_stale(tree):
    with (tree / "requirements.txt").open("a", encoding="utf-8") as fh:
        fh.write("\nrich>=13,<14\n")
    assert len(locks.stale_locks(tree)) == 2


def test_rewording_a_comment_does_not_make_a_lock_stale(tree):
    """The notes beside each bound are prose. If editing one forced a
    regeneration, people would stop keeping them true."""
    _rewrite(tree / "requirements.txt", "# installed 3.1.6 (= latest).", "#   a reworded note")
    with (tree / "requirements.txt").open("a", encoding="utf-8") as fh:
        fh.write("\n# a trailing comment\n\n")
    assert locks.stale_locks(tree) == []


def test_a_missing_lock_is_reported(tree):
    (tree / locks.RUNTIME_LOCK).unlink()
    problems = locks.stale_locks(tree)
    assert any(p.startswith(locks.RUNTIME_LOCK) and "does not exist" in p for p in problems)


def test_a_lock_that_does_not_record_its_inputs_is_reported(tree):
    lock = tree / locks.DEV_LOCK
    kept = [l for l in lock.read_text(encoding="utf-8").splitlines() if not l.startswith(locks.MARK)]
    lock.write_text("\n".join(kept) + "\n", encoding="utf-8")
    problems = locks.stale_locks(tree)
    assert len(problems) == 1 and "does not record" in problems[0]


def test_stamping_twice_leaves_one_record_under_the_header(tree):
    lock = tree / locks.RUNTIME_LOCK
    locks.stamp(lock, "1" * 64)
    locks.stamp(lock, "2" * 64)
    lines = lock.read_text(encoding="utf-8").splitlines()
    marks = [n for n, line in enumerate(lines) if line.startswith(locks.MARK)]
    assert len(marks) == 1
    assert locks.recorded_digest(lock) == "2" * 64
    assert all(line.startswith("#") for line in lines[:marks[0]]), "the record belongs in the header"
    assert not lines[marks[0] + 1].startswith("#"), "and directly above the first pin"
    assert b"\r" not in lock.read_bytes()
    assert locks.read_lock(lock) == RUNTIME, "stamping must not change a pin"


# ── environment markers ─────────────────────────────────────────────────────

SYNTHETIC_MARKERS = [
    "python_full_version >= '3.13'",
    "python_full_version < '3.13'",
    "python_full_version == '3.12.4'",
    "python_version == '3.12'",
    "python_version != '3.12'",
    "python_version >= '3.12' and python_version < '3.14'",
    "python_version < '3.13' and sys_platform == 'linux'",
    "(sys_platform == 'win32' or sys_platform == 'darwin') and python_version >= '3.12'",
    "sys_platform == 'win32' or sys_platform == 'darwin' and python_version >= '3.13'",
    "'arm' in platform_machine",
    "platform_machine not in 'x86_64 AMD64'",
    'os_name == "nt"',
    "'win32' == sys_platform",
    "implementation_name == 'cpython' and platform_system != 'Darwin'",
    "implementation_version >= '3.12.4'",
    # 3.14 and 3.14.0 are one version. These four differ on linux-3.14.0 if the
    # shorter side is not padded before comparing.
    "python_full_version == '3.14'",
    "python_full_version != '3.14'",
    "python_full_version > '3.14'",
    "python_full_version <= '3.14'",
]
LOCK_MARKERS = sorted({pin.marker for pin in RUNTIME + DEV if pin.marker})


def test_the_locks_do_carry_markers():
    assert len(LOCK_MARKERS) >= 3, "a universal lock has platform markers; this one has none"


@pytest.mark.parametrize("marker", LOCK_MARKERS + SYNTHETIC_MARKERS)
@pytest.mark.parametrize("platform", sorted(ENVIRONMENTS))
def test_markers_are_read_the_way_pip_reads_them(marker, platform):
    """The tool evaluates markers itself, so that it runs where ``packaging`` is
    not installed. That is only safe while it agrees with ``packaging``, which
    is what pip uses to decide what a lock installs."""
    env = ENVIRONMENTS[platform]
    assert locks.marker_applies(marker, env) is Marker(marker).evaluate(dict(env, extra=""))


def test_a_pin_without_a_marker_applies_everywhere():
    assert locks.marker_applies("", LINUX) is True
    assert locks.marker_applies("   ", WINDOWS) is True


@pytest.mark.parametrize("marker", [
    "python_version ~= '3.12'",                       # an operator it does not implement
    "python_version === '3.12'",
    "sys_platform < 'win32'",                         # ordering of plain text
    "python_full_version < '3.13.0rc1'",              # a version that is not dotted numbers
    "python_full_version >= '3.*'",
    "extra == 'dev'",                                 # a variable no environment reports
    "bogus_variable == 'x'",
    "(sys_platform == 'win32'",                       # an unclosed bracket
    "sys_platform == 'win32' )",                      # something left over
    "sys_platform == 'win32' and",                    # a missing term
    "sys_platform 'win32'",                           # a missing comparison
    "sys_platform == ",                               # a missing value
    "sys_platform not 'win32'",
    "sys_platform == 'win32' && os_name == 'nt'",     # not marker syntax at all
    "== 'win32'",
])
def test_a_marker_it_does_not_understand_is_refused_not_guessed(marker):
    """A wrong answer here reports a healthy environment as broken, or a broken
    one as healthy. Refusing is the only safe reading."""
    with pytest.raises(locks.LockError):
        locks.marker_applies(marker, WINDOWS)


def test_every_term_of_a_marker_is_read_even_when_the_answer_is_already_known():
    """``false and <nonsense>`` must not come back as a confident ``False``."""
    with pytest.raises(locks.LockError):
        locks.marker_applies("sys_platform == 'nope' and bogus_variable == 'x'", WINDOWS)
    with pytest.raises(locks.LockError):
        locks.marker_applies("sys_platform == 'win32' or bogus_variable == 'x'", WINDOWS)


# ── comparing an environment with a lock ────────────────────────────────────

PINS = [
    locks.Pin("jinja2", "3.1.6", "", ("sha256:" + "a" * 64,)),
    locks.Pin("python-dotenv", "1.2.2", "", ("sha256:" + "b" * 64,)),
    locks.Pin("pywin32", "312", "sys_platform == 'win32'", ("sha256:" + "c" * 64,)),
    locks.Pin("uvloop", "0.23.0", "sys_platform != 'win32'", ("sha256:" + "d" * 64,)),
]
MATCHING = {"Jinja2": ["3.1.6"], "python_dotenv": ["1.2.2"], "pywin32": ["312"]}


def _said(found):
    return [str(difference) for difference in found]


def test_an_environment_that_is_the_lock_has_no_differences():
    assert locks.differences(PINS, MATCHING, WINDOWS) == []
    assert locks.applicable(PINS, WINDOWS) == 3


def test_names_are_compared_the_way_an_index_compares_them():
    """``Jinja2`` and ``python_dotenv`` are how those two name themselves."""
    assert locks.canonical("Python_Dotenv.Extra--x") == "python-dotenv-extra-x"
    assert locks.differences(PINS, MATCHING, WINDOWS) == []


def test_a_pin_for_another_platform_is_not_expected_here():
    on_linux = {"jinja2": ["3.1.6"], "python-dotenv": ["1.2.2"], "uvloop": ["0.23.0"]}
    assert locks.differences(PINS, on_linux, LINUX) == []
    assert _said(locks.differences(PINS, MATCHING, LINUX)) == [
        "uvloop is not installed (the lock pins 0.23.0)",
        "pywin32 312 is installed, and the lock does not pin it",
    ]


def test_a_missing_package_is_a_difference():
    have = {k: v for k, v in MATCHING.items() if k != "pywin32"}
    assert _said(locks.differences(PINS, have, WINDOWS)) == [
        "pywin32 is not installed (the lock pins 312)"]


def test_another_version_is_a_difference():
    have = dict(MATCHING, Jinja2=["3.1.5"])
    found = locks.differences(PINS, have, WINDOWS)
    assert _said(found) == ["jinja2 3.1.5 is installed; the lock pins 3.1.6"]
    assert (found[0].kind, found[0].installed, found[0].pinned) == ("version", "3.1.5", "3.1.6")


def test_a_package_the_lock_does_not_pin_is_a_difference():
    """The quiet one: a version nobody chose, running."""
    have = dict(MATCHING, flask=["3.1.2"])
    assert _said(locks.differences(PINS, have, WINDOWS)) == [
        "flask 3.1.2 is installed, and the lock does not pin it"]


@pytest.mark.parametrize("name", sorted(locks.OUTSIDE_A_LOCK))
def test_what_is_installed_by_other_means_is_not_a_difference(name):
    assert locks.differences(PINS, dict(MATCHING, **{name: ["1.0"]}), WINDOWS) == []


def test_only_those_few_are_excused():
    assert set(locks.OUTSIDE_A_LOCK) == {"admz", "axis-api-atlas", "pip", "setuptools", "wheel"}


def test_leftovers_of_an_earlier_install_are_a_difference():
    have = dict(MATCHING, Jinja2=["3.1.6", "3.1.5"])
    assert _said(locks.differences(PINS, have, WINDOWS)) == [
        "jinja2 is installed more than once (3.1.5, 3.1.6); the lock pins 3.1.6"]


def test_a_lock_that_pins_one_package_twice_for_a_platform_is_reported():
    twice = PINS + [locks.Pin("jinja2", "3.1.5", "os_name == 'nt'", ("sha256:" + "e" * 64,))]
    assert _said(locks.differences(twice, MATCHING, WINDOWS)) == [
        "jinja2: the lock pins it more than once for this platform (3.1.5, 3.1.6)"]


def test_this_interpreter_can_be_asked_what_it_holds():
    packages, markers = locks.installed()
    assert "pytest" in {locks.canonical(name) for name in packages}
    assert set(markers) == set(WINDOWS), "every PEP 508 variable, and nothing else"
    assert markers["python_version"].count(".") == 1
    # Asking twice gives the same answer, and it is what the markers need.
    assert locks.marker_applies("python_version >= '3.10'", markers) is True


def test_an_interpreter_that_cannot_be_asked_is_an_error_not_an_empty_answer(tmp_path):
    """An empty answer would read as "every package is missing", or worse, be
    compared and found clean by a caller that only looked for extras."""
    with pytest.raises(locks.LockError, match="could not ask"):
        locks.installed(tmp_path / "no-such-python.exe")


class _Ran:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def test_an_interpreter_that_fails_while_listing_is_an_error(monkeypatch):
    monkeypatch.setattr(locks.subprocess, "run",
                        lambda *a, **k: _Ran(1, "", "Traceback (most recent call last):\nImportError: boom"))
    with pytest.raises(locks.LockError, match="could not list what it has installed: ImportError: boom"):
        locks.installed()


@pytest.mark.parametrize("answer", ["", "not json", '{"packages": {}}', "[]"])
def test_an_answer_that_cannot_be_read_is_an_error(monkeypatch, answer):
    monkeypatch.setattr(locks.subprocess, "run", lambda *a, **k: _Ran(0, answer))
    with pytest.raises(locks.LockError, match="could not be read"):
        locks.installed()


def test_a_build_folder_in_the_current_directory_is_not_reported_as_installed(tmp_path, monkeypatch):
    """``python -c`` puts the current directory on its search path, and package
    metadata lying there is then listed as installed. An editable checkout
    leaves exactly that behind. ``-I`` keeps the answer to the environment."""
    stray = tmp_path / "stray_package-9.9.dist-info"
    stray.mkdir()
    (stray / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: stray-package\nVersion: 9.9\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    packages, _ = locks.installed()
    assert "stray-package" not in {locks.canonical(name) for name in packages}


@pytest.mark.parametrize("which,lock_name", [("runtime", locks.RUNTIME_LOCK), ("dev", locks.DEV_LOCK)])
def test_verify_installed_reads_the_lock_it_was_asked_about(monkeypatch, capsys, which, lock_name):
    pins = locks.read_lock(REPO / lock_name)
    have = {pin.name: [pin.version] for pin in pins if locks.marker_applies(pin.marker, WINDOWS)}
    monkeypatch.setattr(locks, "installed", lambda python=None: (have, WINDOWS))
    assert locks.main(["--verify-installed", which]) == 0
    assert f"this environment is {lock_name}" in capsys.readouterr().out


def test_verify_installed_lists_every_difference_and_fails(monkeypatch, capsys):
    have = {pin.name: [pin.version] for pin in RUNTIME if locks.marker_applies(pin.marker, WINDOWS)}
    have["starlette"] = ["0.52.1"]
    have["flask"] = ["3.1.2"]
    del have["jinja2"]
    asked = []

    def fake(python=None):
        asked.append(python)
        return have, WINDOWS

    monkeypatch.setattr(locks, "installed", fake)
    assert locks.main(["--verify-installed", "runtime", "--python", "some/python.exe"]) == 1
    out = capsys.readouterr().out
    assert f"this environment is NOT {locks.RUNTIME_LOCK}" in out
    assert "starlette 0.52.1 is installed; the lock pins" in out
    assert "flask 3.1.2 is installed, and the lock does not pin it" in out
    assert "jinja2 is not installed" in out
    assert asked == [Path("some/python.exe")], "--python names the environment to ask"


def test_verify_installed_that_cannot_compare_says_so_and_does_not_pass(monkeypatch, capsys):
    def broken(python=None):
        raise locks.LockError("could not ask python what it has installed")

    monkeypatch.setattr(locks, "installed", broken)
    assert locks.main(["--verify-installed", "dev"]) == 2
    assert "cannot compare" in capsys.readouterr().err


# ── regenerating ────────────────────────────────────────────────────────────

class _Recorder:
    def __init__(self):
        self.compiled = []        # one dict per compile, in order
        self.stamped = []         # lock names, in order
        self.rc = {}              # output file -> the return code to give for it


@pytest.fixture
def compiles(monkeypatch):
    """Record what would be compiled and stamped, and touch no real lock."""
    rec = _Recorder()

    def compile_lock(uv, src, out, *, constraints, upgrade, upgrade_packages):
        rec.compiled.append({"src": src, "out": out, "constraints": list(constraints),
                             "upgrade": upgrade, "upgrade_packages": list(upgrade_packages)})
        return rec.rc.get(out, 0)

    monkeypatch.setattr(locks, "compile_lock", compile_lock)
    monkeypatch.setattr(locks, "stamp", lambda lock, digest: rec.stamped.append(lock.name))
    monkeypatch.setattr(locks, "find_uv", lambda: ["uv"])
    return rec


def test_the_dev_lock_is_compiled_with_the_runtime_lock_as_a_constraint(compiles):
    """That constraint is why the two locks cannot disagree about a runtime pin."""
    assert locks.main([]) == 0
    runtime, dev = compiles.compiled
    assert (runtime["src"], runtime["out"], runtime["constraints"]) == (
        "requirements.txt", locks.RUNTIME_LOCK, [])
    assert (dev["src"], dev["out"], dev["constraints"]) == (
        "requirements-dev.txt", locks.DEV_LOCK, [locks.RUNTIME_LOCK])
    assert compiles.stamped == [locks.RUNTIME_LOCK, locks.DEV_LOCK]
    assert not runtime["upgrade"] and not dev["upgrade"], (
        "a plain run keeps every pin that still fits; moving one is asked for by name")


def test_a_failed_runtime_compile_stops_before_the_dev_lock(compiles):
    compiles.rc[locks.RUNTIME_LOCK] = 3
    assert locks.main([]) == 3
    assert [c["out"] for c in compiles.compiled] == [locks.RUNTIME_LOCK]
    assert compiles.stamped == [], "a lock that failed to compile must not be marked current"


def test_a_failed_dev_compile_is_reported(compiles):
    compiles.rc[locks.DEV_LOCK] = 4
    assert locks.main([]) == 4
    assert compiles.stamped == [locks.RUNTIME_LOCK]


def test_upgrades_are_asked_for_and_reach_both_locks(compiles):
    assert locks.main(["--upgrade-package", "httpx", "--upgrade-package", "anyio"]) == 0
    assert [c["upgrade_packages"] for c in compiles.compiled] == [["httpx", "anyio"]] * 2
    assert not any(c["upgrade"] for c in compiles.compiled)
    compiles.compiled.clear()
    assert locks.main(["--upgrade"]) == 0
    assert [c["upgrade"] for c in compiles.compiled] == [True, True]


def test_aligning_to_an_environment_compiles_again_without_its_file(compiles):
    """uv writes the path of each constraint file into the lock. The second,
    plain pass keeps the pins and drops the path."""
    assert locks.main(["--align-to", "lab.txt", "--dev-align-to", "tools.txt"]) == 0
    assert [c["constraints"] for c in compiles.compiled] == [
        ["lab.txt"], [locks.RUNTIME_LOCK, "tools.txt"],
        [], [locks.RUNTIME_LOCK],
    ]
    assert [c["out"] for c in compiles.compiled] == [locks.RUNTIME_LOCK, locks.DEV_LOCK] * 2


def test_without_uv_nothing_is_compiled_and_the_message_says_what_still_works(
        compiles, monkeypatch, capsys):
    monkeypatch.setattr(locks, "find_uv", lambda: None)
    assert locks.main([]) == 2
    assert compiles.compiled == [] and compiles.stamped == []
    err = capsys.readouterr().err
    assert "uv is needed" in err and "--check" in err


def test_check_reports_and_changes_nothing(compiles, monkeypatch, capsys):
    monkeypatch.setattr(locks, "stale_locks", lambda: ["requirements.lock was compiled from ..."])
    assert locks.main(["--check"]) == 1
    assert "STALE: requirements.lock" in capsys.readouterr().out
    monkeypatch.setattr(locks, "stale_locks", lambda: [])
    assert locks.main(["--check"]) == 0
    assert compiles.compiled == [] and compiles.stamped == []


def test_the_compile_command_is_universal_hashed_and_for_the_ci_interpreter(monkeypatch):
    seen = {}

    def run(cmd, cwd=None, **kwargs):
        seen["cmd"], seen["cwd"] = cmd, cwd

        class Done:
            returncode = 0
        return Done()

    monkeypatch.setattr(locks.subprocess, "run", run)
    rc = locks.compile_lock(["uv"], "requirements.txt", locks.RUNTIME_LOCK,
                            constraints=["some.txt"], upgrade=False, upgrade_packages=["httpx"])
    cmd = seen["cmd"]
    assert rc == 0
    assert cmd[:4] == ["uv", "pip", "compile", "requirements.txt"]
    assert "--universal" in cmd, "one file has to serve Windows and Linux"
    assert "--generate-hashes" in cmd
    assert cmd[cmd.index("--python-version") + 1] == locks.PYTHON_VERSION
    assert cmd[cmd.index("-o") + 1] == locks.RUNTIME_LOCK
    assert cmd[cmd.index("-c") + 1] == "some.txt"
    assert cmd[cmd.index("--upgrade-package") + 1] == "httpx"
    assert "--upgrade" not in cmd
    assert cmd[cmd.index("--custom-compile-command") + 1] == locks.COMPILE_COMMAND
    assert seen["cwd"] == locks.REPO, "relative paths in the lock's notes depend on it"


# ── CI installs the lock, and then checks that it did ───────────────────────

def _steps():
    return yaml.safe_load(ACTION.read_text(encoding="utf-8"))["runs"]["steps"]


def _commands(step):
    """The shell lines of a step, without comments and blank lines."""
    lines = [line.strip() for line in (step.get("run") or "").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def test_ci_installs_from_the_dev_lock_in_hash_mode_and_resolves_nothing_else():
    """Every ``pip install`` in the action, in order. A fourth one would bring
    in packages the lock does not pin."""
    installs = [cmd for step in _steps() for cmd in _commands(step) if "pip install" in cmd]
    assert installs == [
        "python -m pip install --upgrade pip",
        "python -m pip install --require-hashes -r requirements-dev.lock",
        'python -m pip install -e ".[atlas]"',
    ]


def test_ci_then_checks_that_the_environment_is_the_lock():
    steps = _steps()
    installing = [n for n, step in enumerate(steps)
                  if any("pip install" in cmd for cmd in _commands(step))]
    verifying = [n for n, step in enumerate(steps)
                 if "python tools/lock.py --verify-installed dev" in _commands(step)]
    assert len(verifying) == 1, "exactly one step compares the environment with the dev lock"
    assert verifying[0] > max(installing), "and it runs after the last install"
    step = steps[verifying[0]]
    assert "if" not in step and "continue-on-error" not in step, (
        "the check must not be skippable: it is what makes 'CI tests the lock' true")


def test_the_pip_cache_is_keyed_on_the_locks():
    setup = next(step for step in _steps() if "setup-python" in step.get("uses", ""))
    keyed = set(setup["with"]["cache-dependency-path"].split())
    assert {locks.RUNTIME_LOCK, locks.DEV_LOCK, "setup.py"} <= keyed, (
        "a changed lock with an unchanged cache key restores the previous packages")


def test_the_locks_are_compiled_for_the_interpreter_ci_runs():
    action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
    assert action["inputs"]["python-version"]["default"] == locks.PYTHON_VERSION
