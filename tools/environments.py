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

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "ENVIRONMENTS.md"

#: Packages whose version has actually broken something here, so worth showing.
WATCHED = ("starlette", "fastapi", "mcp", "axis-api-atlas")

#: What an unset ADMZ_HOME resolves to. The whole point of the launch-config
#: audit: an ABSENT value is invisible in the file and lands on production.
ADMZ_HOME_DEFAULT = r"C:\ProgramData\admz"


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
        return "?"
    kind, _, detail = (r.stdout.strip() or "unknown:").partition(":")
    if kind == "commit":
        return f"git@{detail[:7]}"
    if kind == "editable":
        return f"EDITABLE from {detail}"
    if kind == "copy":
        return f"copy of {detail}"
    if kind == "index":
        return "FROM AN INDEX (see #179)"
    return "?"


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
                effective = home or f"{ADMZ_HOME_DEFAULT}  <-- UNSET, i.e. PRODUCTION"
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
