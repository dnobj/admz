"""Setup script for ADMZ — Axis Device Management Zone.

Most metadata is duplicated in the README and the package's ``__init__.py``.
The single source of truth for the version is ``admz/__init__.py:__version__``;
this file imports that value rather than hard-coding it.
"""

import re
from pathlib import Path

from setuptools import setup, find_packages


HERE = Path(__file__).parent


# --- axis-api-atlas: the one place the reference is written ------------------
#
# This used to live in requirements.txt. It moved here in #235 so that
# `pip install -r requirements.txt` stops demanding a credential that only CI
# has, and so a local `pip install -e ../axis-api-atlas` genuinely satisfies
# the dependency instead of being re-evaluated and overridden.
#
# It is an EXTRA, not an install_requires entry, so `pip install -e .` succeeds
# credential-free. ADMZ does not run without atlas — it will fail at import,
# loudly — but that is a better failure than a clean checkout that cannot
# install at all.
#
# Pinned to a SHA (#232) so `pip freeze` can tell two builds apart and
# `git bisect` can tell an ADMZ regression from an atlas one. The mutable
# `@main` meant CI cloned whatever HEAD was at that moment and the version
# string read `0.1.0` forever.
#
# ATLAS_SHA is parsed out of this file by:
#   .github/scripts/assert_atlas_provenance.py   (asserts the installed commit)
#   .github/workflows/atlas-pin-drift.yml        (weekly: is the pin behind?)
# Same trick as _read_version() below. Keep the literal on one line, in this
# exact `ATLAS_SHA = "<40 hex>"` shape, or both of those stop finding it.
#
# To bump: change ATLAS_SHA, run the suite, and say in the PR why atlas moved.
ATLAS_SHA = "af92f832f042e09e29d4c4bc9c5dc11b27ab0b21"
ATLAS_REPO = "mrdnlabs/axis-api-atlas"
ATLAS_REQUIREMENT = (
    f"axis-api-atlas @ git+ssh://git@github.com/{ATLAS_REPO}.git@{ATLAS_SHA}"
)


def _read(filename: str) -> str:
    return (HERE / filename).read_text(encoding="utf-8")


def _read_version() -> str:
    """Pull __version__ out of admz/__init__.py without importing the package
    (avoids ImportError chains during setup when deps aren't installed yet)."""
    src = (HERE / "admz" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', src, re.MULTILINE)
    if not match:
        raise RuntimeError("Could not find __version__ in admz/__init__.py")
    return match.group(1)


def _read_requirements(filename: str) -> list:
    """Parse a pip requirements file, ignoring comments, blank lines, and
    -r recursive includes.

    Inline comments are stripped on " #" (space-hash), never on a bare "#".
    Almost every line in requirements.txt carries a trailing `# installed X;
    latest Y` note from the bounds work in #231, and setuptools happens to
    strip those itself — checked, and `pip install -e . --dry-run --no-deps`
    exits 0 with 26 correctly-parsed Requires-Dist entries. This is not a bug
    fix; it is hardening, so the metadata stops depending on another library's
    leniency. `packaging.requirements.Requirement` is stricter than the real
    build path and rejects those same lines.

    The space-hash rule matters: a bare "#" split would eat a URL fragment,
    and direct references legitimately carry `#egg=` / `#subdirectory=`. No
    line here uses one today — the `atlas` extra below pins with `@<sha>`, not
    a fragment — but a future one would be silently truncated into a different
    requirement, which is the kind of breakage that does not announce itself.
    """
    lines = (HERE / filename).read_text(encoding="utf-8").splitlines()
    out = []
    for raw in lines:
        line = raw.split(" #", 1)[0].strip()
        if not line or line.startswith("#") or line.startswith("-r"):
            continue
        out.append(line)
    return out


setup(
    name="admz",
    version=_read_version(),
    author="David Nicholl",
    author_email="anthropic@davidnicholl.com",
    description=(
        "Configuration-as-code for fleets of Axis network devices — credential "
        "management, YAML-driven operation catalog, MCP server for LLM "
        "integration, and git-backed snapshot/restore."
    ),
    long_description=_read("README.md"),
    long_description_content_type="text/markdown",
    url="https://github.com/dnobj/admz",
    packages=find_packages(exclude=["tests", "tests.*", "examples", "docs"]),
    include_package_data=True,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Networking :: Monitoring",
        "Topic :: Security",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    # mcp 2.0 declares Requires-Python >=3.10, so 3.8 and 3.9 became
    # uninstallable the moment the bound below was raised. The metadata said
    # >=3.8 with 3.8/3.9 classifiers, which on those interpreters produces a
    # dependency-resolution failure rather than the clean "requires a different
    # Python" message pip gives when the floor is declared honestly.
    python_requires=">=3.10",
    install_requires=_read_requirements("requirements.txt"),
    extras_require={
        # The catalog dependency. Needs the read-only deploy key (CI has it);
        # a local `pip install -e ../axis-api-atlas` is the credential-free
        # equivalent and satisfies the same import.
        "atlas": [ATLAS_REQUIREMENT],
        "dev": [
            line
            for line in _read_requirements("requirements-dev.txt")
            if not line.startswith("hvac")
            and not line.startswith("cryptography")
            and not line.startswith("fastapi")
            and not line.startswith("uvicorn")
            and not line.startswith("jinja2")
            and not line.startswith("python-multipart")
            and not line.startswith("mcp")
            and not line.startswith("pyyaml")
            and not line.startswith("zeroconf")
            and not line.startswith("WSDiscovery")
            and not line.startswith("httpx")
            and not line.startswith("scapy")
            and not line.startswith("pysnmp")
        ],
    },
    entry_points={
        "console_scripts": [
            "admz=admz.__main__:main",
        ],
    },
)
