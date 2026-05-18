"""Setup script for ADMZ — Axis Device Management Zone.

Most metadata is duplicated in the README and the package's ``__init__.py``.
The single source of truth for the version is ``admz/__init__.py:__version__``;
this file imports that value rather than hard-coding it.
"""

import re
from pathlib import Path

from setuptools import setup, find_packages


HERE = Path(__file__).parent


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
    -r recursive includes."""
    lines = (HERE / filename).read_text(encoding="utf-8").splitlines()
    return [
        line.strip()
        for line in lines
        if line.strip()
        and not line.strip().startswith("#")
        and not line.strip().startswith("-r")
    ]


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
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=_read_requirements("requirements.txt"),
    extras_require={
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
