#!/usr/bin/env python3
"""Report what the environments on this machine ACTUALLY are (GH #398).

``docs/ENVIRONMENTS.md`` declares them. This observes them and prints the two
side by side, exiting non-zero when they disagree.

The declaration is parsed out of the doc rather than restated here, because two
copies of an environment table is precisely how the last one drifted — see the
table of four wrong claims at the top of that page.

READ-ONLY, and deliberately so: port state comes from ``netstat``, not from
connecting, so running this touches nothing. Production manages real devices;
a diagnostic that pokes it is not a diagnostic.

    python tools/environments.py
"""

from __future__ import annotations

import functools
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "ENVIRONMENTS.md"
SETUP_PY = REPO / "setup.py"

#: Where the atlas source repo lives, so the installed copy can be compared
#: against the pin. Overridable because it is a sibling by convention, not by
#: rule. Absent → the revision check degrades to "cannot verify", never to a
#: false pass (GH #424).
ATLAS_REPO_ENV = "ADMZ_ATLAS_REPO"
ATLAS_DATA_PREFIX = "src/axis_api_atlas/data"

#: Packages whose version has actually broken something here, so worth showing.
WATCHED = ("starlette", "fastapi", "mcp", "axis-api-atlas")

#: What an unset ADMZ_HOME resolves to. The whole point of the launch-config
#: audit: an ABSENT value is invisible in the file and lands on production.
#:
#: This constant was first given a name with the same prefix as the variable it
#: describes, and the drift guard in ``tests/test_advanced_capabilities.py`` —
#: which scans source for that prefix — correctly reported it as an
#: unclassified environment variable. A constant that looks like an env var
#: will be read as one, by tools and by people; registering a variable that
#: does not exist, to accommodate the name, would have been the wrong way round.
#:
#: The offending name is deliberately not repeated here. Writing it into this
#: very comment re-tripped the guard on the next run, because the scan reads
#: source text and cannot tell an explanation from a declaration.
HOME_WHEN_UNSET = r"C:\ProgramData\admz"


# ── the declaration ─────────────────────────────────────────────────────────

def load_declaration(doc: Path = DOC) -> dict:
    """The ``environments:`` mapping from the fenced yaml block in the doc."""
    import yaml

    text = doc.read_text(encoding="utf-8")
    blocks = re.findall(r"^```yaml\n(.*?)^```", text, re.MULTILINE | re.DOTALL)
    for block in blocks:
        data = yaml.safe_load(block)
        if isinstance(data, dict) and "environments" in data:
            return data["environments"]
    raise SystemExit(
        f"{doc}: no fenced ```yaml block containing an 'environments:' key. "
        f"The doc IS the source of truth; this tool has nothing to check against."
    )


# ── observation ─────────────────────────────────────────────────────────────

def listening_ports() -> dict:
    """{port: pid} for listening TCP sockets. Empty dict if netstat is absent."""
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=30
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    found = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0] == "TCP" and parts[3] == "LISTENING":
            addr = parts[1]
            if ":" in addr:
                try:
                    found[int(addr.rsplit(":", 1)[1])] = parts[4]
                except ValueError:
                    pass
    return found


def git(checkout: str, *args: str) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", checkout, *args],
            capture_output=True, text=True, timeout=30,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def checkout_state(path: str | None) -> str:
    if not path:
        return "-"
    if not Path(path).exists():
        return "MISSING"
    head = git(path, "rev-parse", "--short", "HEAD") or "?"
    behind = git(path, "rev-list", "--count", "HEAD..origin/master")
    detached = git(path, "symbolic-ref", "-q", "HEAD") == ""
    bits = [head]
    if detached:
        bits.append("detached")
    if behind and behind != "0":
        bits.append(f"{behind} behind origin/master")
    return ", ".join(bits)


def venv_state(path: str | None) -> str:
    if not path:
        return "none declared"
    py = Path(path) / "Scripts" / "python.exe"
    if not py.exists():
        py = Path(path) / "bin" / "python"
    if not py.exists():
        return "MISSING"
    code = (
        "import importlib.metadata as m, json\n"
        "out={}\n"
        f"for p in {list(WATCHED)!r}:\n"
        "    try: out[p]=m.version(p)\n"
        "    except Exception: out[p]=None\n"
        "print(json.dumps(out))\n"
    )
    try:
        r = subprocess.run(
            [str(py), "-c", code], capture_output=True, text=True, timeout=60
        )
        vers = json.loads(r.stdout.strip() or "{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        return "present (version probe failed)"
    shown = ", ".join(
        f"{p}={vers.get(p) or 'MISSING'}" for p in WATCHED if p != "axis-api-atlas"
    )
    return f"{shown}\n                 atlas: {atlas_provenance(py)}"


@functools.lru_cache(maxsize=None)
def install_kind(python: Path) -> tuple[str, str]:
    """``(kind, detail)`` from PEP 610 metadata.

    ``commit`` | ``editable`` | ``copy`` | ``index`` | ``unknown``. Split out so
    the provenance line and the revision verdict agree about what they are
    looking at instead of probing separately (#424).
    """
    code = (
        "import importlib.metadata as m, json\n"
        "try:\n"
        "    raw = m.distribution('axis-api-atlas').read_text('direct_url.json') or '{}'\n"
        "    d = json.loads(raw)\n"
        "    vcs = (d.get('vcs_info') or {}).get('commit_id')\n"
        "    if vcs: print('commit:' + vcs)\n"
        "    elif 'dir_info' in d:\n"
        "        kind = 'editable' if (d['dir_info'] or {}).get('editable') else 'copy'\n"
        "        print(kind + ':' + (d.get('url') or ''))\n"
        "    else: print('index:')\n"
        "except Exception as e: print('unknown:' + type(e).__name__)\n"
    )
    try:
        r = subprocess.run(
            [str(python), "-c", code], capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown", ""
    kind, _, detail = (r.stdout.strip() or "unknown:").partition(":")
    return kind, detail


def atlas_provenance(python: Path) -> str:
    """Where this interpreter's atlas came from — the only meaningful "version".

    Its version string is ``0.1.0`` forever, which is why #232 pinned by SHA.

    Three outcomes, and the distinction is load-bearing. ADR-0054 requires
    production's copy to be **non-editable**, so reporting a local-directory
    install as "editable" would accuse it of the exact coupling the dev/prod
    split removed. PEP 610 marks a real editable install with
    ``dir_info: {"editable": true}``; a plain ``dir_info`` is a *copy* taken
    from that directory, which is a different thing entirely.
    """
    kind, detail = install_kind(python)
    if kind == "commit":
        # A VCS install records the commit, so the CI script's revision check
        # already covers it. Nothing to compare by content.
        return f"git@{detail[:7]}"
    if kind == "editable":
        return f"EDITABLE from {detail}{_revision_suffix(python)}"
    if kind == "copy":
        return f"copy of {detail}{_revision_suffix(python)}"
    if kind == "index":
        return "FROM AN INDEX (see #179)"
    return "?"


# ── which atlas commit is this, really (GH #424) ─────────────────────────────
#
# A directory install records ``dir_info`` and NO commit, so
# ``.github/scripts/assert_atlas_provenance.py``'s revision check explicitly
# skips it — a decision made so developer laptops keep working, which silently
# covers production too, because ADR-0054's non-editable install is also a
# directory install. Production therefore ran an atlas whose commit nothing
# could name, and an ungated ``pwdgrp.cgi:add-user`` (risk_level normal ->
# confirmation level none) sat live for six days after the fix merged.
#
# The commit cannot be recovered from metadata, so this compares CONTENT: the
# installed data tree against the tree at ``ATLAS_SHA``. That is stronger than
# a stamp — a stamp records what an installer *intended*, this observes what is
# actually on disk, and it cannot be fooled by a source directory that has
# moved on since.

def expected_atlas_sha() -> str | None:
    """``ATLAS_SHA`` from setup.py — the single source of truth for the pin.

    Deliberately the same regex as ``_expected_sha()`` in
    ``.github/scripts/assert_atlas_provenance.py``. Two parsers of one literal
    is two things to break, so ``tests/test_atlas_revision.py`` asserts the two
    return the same value rather than trusting them to stay in step.
    """
    try:
        src = SETUP_PY.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'^ATLAS_SHA\s*=\s*"([0-9a-fA-F]{40})"', src, re.MULTILINE)
    return match.group(1).lower() if match else None


def _normalize(raw: bytes) -> bytes:
    """Content, with line endings flattened.

    A git blob holds LF; a Windows checkout with ``core.autocrlf=true`` writes
    CRLF, and the installed copy is taken from a checkout. Comparing raw bytes
    would report every file as different on this machine, which is a false
    mismatch — the worst outcome, because it trains a reader to ignore the
    check. Binary content is hashed as-is.
    """
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    return raw.replace(b"\r\n", b"\n")


def _digest(entries: dict[str, bytes]) -> str:
    """One digest over {relative path: content}. Order-independent by sorting."""
    h = hashlib.sha256()
    for path in sorted(entries):
        h.update(path.encode("utf-8"))
        h.update(b"\0")
        h.update(hashlib.sha256(_normalize(entries[path])).digest())
    return h.hexdigest()


def installed_atlas_digest(python: Path) -> tuple[str | None, int]:
    """Digest of the atlas data tree this interpreter would actually load."""
    code = (
        "import axis_api_atlas, pathlib\n"
        "print(pathlib.Path(axis_api_atlas.__file__).parent / 'data')\n"
    )
    try:
        r = subprocess.run(
            [str(python), "-c", code], capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError):
        return None, 0
    root = Path(r.stdout.strip())
    if not r.stdout.strip() or not root.is_dir():
        return None, 0
    entries: dict[str, bytes] = {}
    for path in root.rglob("*"):
        if path.is_file():
            try:
                entries[path.relative_to(root).as_posix()] = path.read_bytes()
            except OSError:
                return None, 0
    return (_digest(entries), len(entries)) if entries else (None, 0)


def _atlas_repo() -> Path | None:
    override = os.environ.get(ATLAS_REPO_ENV)
    candidates = [Path(override)] if override else []
    candidates.append(REPO.parent / "axis-api-atlas")
    for path in candidates:
        if (path / ".git").exists():
            return path
    return None


def atlas_digest_at(sha: str) -> tuple[str | None, int, str | None]:
    """``(digest, file count, reason it failed)`` for the data tree at ``sha``.

    ``git archive`` rather than a checkout: it needs no working tree, cannot
    disturb the shared clone's branch, and emits blob content (LF), which
    ``_normalize`` accounts for.

    The reasons are separated deliberately. Collapsing them into one "no atlas
    repo" message sent an operator after a repo that was present, while the real
    fix — fetch the clone, the pin was bumped — went unnamed. Worse, a repo
    layout change would have disabled the whole mechanism permanently while
    still blaming a missing repo, so that case is reported as BROKEN rather than
    unverifiable.
    """
    repo = _atlas_repo()
    if repo is None:
        return None, 0, f"no atlas repo beside this one (set {ATLAS_REPO_ENV})"
    try:
        have = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"],
            capture_output=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, 0, f"git unusable in {repo}: {type(exc).__name__}"
    if have.returncode != 0:
        return None, 0, (
            f"pin {sha[:7]} is not in {repo} — fetch that clone "
            f"(the pin moved and this copy has not caught up)"
        )
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "archive", "--format=tar", sha, ATLAS_DATA_PREFIX],
            capture_output=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, 0, f"git archive failed: {type(exc).__name__}"
    if r.returncode != 0 or not r.stdout:
        # The commit exists, so the pathspec is what did not resolve.
        return None, 0, (
            f"BROKEN: {ATLAS_DATA_PREFIX!r} matches nothing at {sha[:7]} — "
            f"atlas layout moved and this check is disabled until the prefix "
            f"is updated"
        )
    entries: dict[str, bytes] = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(r.stdout), mode="r:") as tar:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                fh = tar.extractfile(member)
                if fh is None:
                    continue
                rel = member.name[len(ATLAS_DATA_PREFIX):].lstrip("/")
                entries[rel] = fh.read()
    except (tarfile.TarError, OSError) as exc:
        return None, 0, f"BROKEN: archive of {sha[:7]} is unreadable ({type(exc).__name__})"
    if not entries:
        return None, 0, f"BROKEN: {ATLAS_DATA_PREFIX!r} is empty at {sha[:7]}"
    return _digest(entries), len(entries), None


#: What ``atlas_revision`` concluded. ``broken`` means the check itself cannot
#: run and must be repaired; ``unverifiable`` means this machine lacks something
#: to compare against, which is a reason to look rather than to block.
MATCH, MISMATCH, UNREADABLE, UNVERIFIABLE, BROKEN = (
    "match", "mismatch", "unreadable", "unverifiable", "broken"
)


@functools.lru_cache(maxsize=None)
def atlas_revision(python: Path) -> tuple[str, str]:
    """``(message, status)`` for the installed atlas versus the pin.

    Cached because the report prints it and ``main()`` re-asks in order to fail
    the run — hashing 800-odd files twice per environment for one answer.
    """
    sha = expected_atlas_sha()
    if not sha:
        return "pin unreadable (setup.py has no ATLAS_SHA)", UNVERIFIABLE

    # A VCS install DOES record its commit, so compare that directly. The CI
    # provenance script does the same check — but only in CI, against CI's own
    # venv, so it says nothing about this machine. Trusting it here is how a
    # production venv pinned at a stale commit would have passed clean.
    kind, detail = install_kind(python)
    if kind == "commit":
        if detail.lower() == sha:
            return f"git install at pin {sha[:7]}", MATCH
        return (
            f"git install at {detail[:7]}, but the pin is {sha[:7]} — see #424",
            MISMATCH,
        )

    installed, n_installed = installed_atlas_digest(python)
    if installed is None:
        return (
            "installed data tree is missing, empty or unreadable — "
            "nothing to compare",
            UNREADABLE,
        )
    pinned, n_pinned, reason = atlas_digest_at(sha)
    if pinned is None:
        assert reason is not None
        status = BROKEN if reason.startswith("BROKEN") else UNVERIFIABLE
        return f"cannot verify against {sha[:7]} — {reason}", status
    if installed == pinned:
        return f"content MATCHES pin {sha[:7]} ({n_installed} files)", MATCH
    return (
        f"content DOES NOT MATCH pin {sha[:7]} "
        f"(installed {n_installed} files, pin has {n_pinned}) — see #424",
        MISMATCH,
    )


def _revision_suffix(python: Path) -> str:
    return f"\n                 revision: {atlas_revision(python)[0]}"


def atlas_problem(name: str, venv: str | None, declared: str | None) -> str | None:
    """The atlas fact worth failing the run over, or ``None``.

    ``declared`` is the environment's ``atlas:`` key — ``copy``, ``editable`` or
    ``none``. Reading it from the declaration rather than from the installation
    is the whole point: the first version of this asked the *installed* package
    what kind it was and only checked it if the answer was ``copy``, so every
    way an install could deviate — reinstalled editable, pinned at a stale
    commit, atlas missing entirely — turned the check off. A gate keyed on the
    thing it is inspecting is not a gate.

    Rules, in order:

    * observed kind ≠ declared kind → **fail**, whichever way round. That is the
      ADR-0054 violation the environments page exists to catch.
    * declared ``copy``: a mismatch, an unreadable tree, or a BROKEN check all
      fail. For a deployment, "I cannot read what is on disk" is at least as
      alarming as "it is the wrong thing".
    * declared ``editable``: only a BROKEN check fails. A content mismatch is
      ordinary atlas development, and failing on it would train every reader to
      skip the line — worse than not having it.
    * ``unverifiable`` never fails, for either. No atlas repo on this machine,
      or a pin this clone has not fetched, is a reason to look, not to block.
    """
    if not venv or declared in (None, "none"):
        return None
    python = Path(venv) / "Scripts" / "python.exe"
    if not python.exists():
        python = Path(venv) / "bin" / "python"
    if not python.exists():
        return None

    observed = install_kind(python)[0]
    if observed == "index":
        return f"{name}: atlas was installed FROM AN INDEX (see #179)"
    expected_kinds = {"copy": ("copy",), "editable": ("editable",)}.get(declared, ())
    if observed not in expected_kinds:
        return (
            f"{name}: declares atlas {declared!r} but the installed one is "
            f"{observed!r} — see ADR-0054 and #424"
        )

    message, status = atlas_revision(python)
    if status == BROKEN:
        return f"{name}: atlas {message}"
    if declared == "copy" and status in (MISMATCH, UNREADABLE):
        return f"{name}: atlas {message}"
    return None


# ── launch configs ──────────────────────────────────────────────────────────

def audit_launch_configs(roots) -> list:
    """Every launch.json, and the ADMZ_HOME each config would ACTUALLY use."""
    rows = []
    for root in roots:
        for path in Path(root).glob("**/.claude/launch.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                rows.append((str(path), "?", "?", f"unreadable: {exc}"))
                continue
            for cfg in data.get("configurations", []):
                env = cfg.get("env") or {}
                home = env.get("ADMZ_HOME")
                effective = home or f"{HOME_WHEN_UNSET}  <-- UNSET, i.e. PRODUCTION"
                rows.append(
                    (str(path), cfg.get("name", "?"), str(cfg.get("port", "?")), effective)
                )
    return rows


# ── report ──────────────────────────────────────────────────────────────────

def main() -> int:
    declared = load_declaration()
    ports = listening_ports()
    problems = []

    print("ENVIRONMENTS — declared in docs/ENVIRONMENTS.md, observed here\n")
    for name, spec in declared.items():
        port = spec.get("port")
        want_listening = bool(spec.get("expect_listening"))
        pid = ports.get(port) if port else None
        is_listening = pid is not None

        print(f"  {name}")
        print(f"    touch      : {spec.get('touch', '-')}")
        if port:
            state = f"LISTENING (pid {pid})" if is_listening else "not listening"
            print(f"    port {port:<5} : {state}   (declared: "
                  f"{'listening' if want_listening else 'not listening'})")
            if is_listening != want_listening:
                problems.append(
                    f"{name}: port {port} is "
                    f"{'listening' if is_listening else 'not listening'}, "
                    f"declared {'listening' if want_listening else 'not listening'}"
                )
        else:
            print("    port       : none declared (not a service)")

        print(f"    ADMZ_HOME  : {spec.get('admz_home') or 'per-run (isolate it)'}")
        print(f"    checkout   : {spec.get('checkout')}  ->  "
              f"{checkout_state(spec.get('checkout'))}")

        venv = spec.get("venv")
        observed_venv = venv_state(venv)
        print(f"    venv       : {observed_venv}")
        if venv and observed_venv == "MISSING":
            problems.append(f"{name}: declares a venv at {venv}, which does not exist")
        if not venv and Path(str(spec.get('checkout') or ''), ".venv").exists():
            problems.append(
                f"{name}: declared to have no venv, but one exists in its checkout"
            )

        if observed_venv != "MISSING":
            atlas_issue = atlas_problem(name, venv, spec.get("atlas"))
            if atlas_issue:
                problems.append(atlas_issue)
        print()

    rows = audit_launch_configs([r"C:\admz"])
    print("LAUNCH CONFIGS — what each would actually run\n")
    if not rows:
        print("  (none found)\n")
    for path, cfg_name, port, effective in rows:
        print(f"  {cfg_name}  port {port}")
        print(f"    from  : {path}")
        print(f"    home  : {effective}")
        if "UNSET" in effective:
            problems.append(
                f"launch config {cfg_name!r} ({path}) sets no ADMZ_HOME, so starting it "
                f"runs against PRODUCTION data"
            )
    print()

    if problems:
        print("MISMATCHES")
        for p in problems:
            print(f"  ! {p}")
        return 1
    print("observed state matches the declaration")
    return 0


if __name__ == "__main__":
    sys.exit(main())
