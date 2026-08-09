"""The declared bounds must admit what is actually installed (GH #362).

`requirements-dev.txt` opens by stating the project's rule: bound at *"the next
boundary above the version currently installed, on the package's own breaking
axis"*. Nothing checked that the comments describing installed versions, the
specifiers, and the interpreter running the suite still agreed.

They didn't. `pytest-asyncio>=1.0.0,<2` let CI resolve **1.4.0** while the dev
venv held **1.3.0**, and 1.4 changed event-loop teardown. `tests/test_auth.py`
failed deterministically on both CI legs and passed every local ordering — the
kind of red build nobody can reproduce, which costs a round-trip each time and
teaches people to re-run rather than investigate.

**What this catches, stated precisely, because the obvious reading is wrong.**
It would **not** have caught #362 as it happened: `1.3.0` satisfies `<2`, so the
old loose bound was met by both environments while they differed from each
other. A range cannot detect disagreement inside itself.

What does the work is the *tight* bound — the rule `requirements-dev.txt`
already states and did not follow here. This test is what makes that rule
load-bearing instead of aspirational: once a ceiling sits at the next boundary
above installed, any drift pushes the environment outside the range and fails
here. CI installs from these files, so CI satisfies them by construction; the
only way this fails is a **local** environment that has drifted. Local ==
declaration and CI == declaration gives local == CI, which is what #362 wants.

So: the pin prevents the skew, and this test prevents the pin from quietly
rotting. Neither alone is sufficient.

It deliberately does **not** assert exact versions. A specifier is a range on
purpose; the point is that the range and the environment agree, not that
everyone runs an identical build.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest
from packaging.requirements import Requirement

REPO = Path(__file__).resolve().parent.parent

#: Runtime bounds are checked too — the same drift class produced #241 and
#: `q_86012504` (production on a starlette major CI has never executed).
REQ_FILES = ("requirements-dev.txt", "requirements.txt")

#: Not installed in every environment and not needed to run the suite. A missing
#: optional package is not drift; a *mismatched* one would be, so these are
#: skipped rather than passed.
OPTIONAL = {"axis-api-atlas", "hvac", "pywin32", "fdb", "firebird-driver"}


def _requirements(path: Path):
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):        # blank, comment, or -r include
            continue
        try:
            yield Requirement(line)
        except Exception:                            # noqa: BLE001 — editable/url pins
            continue


def _cases():
    out = []
    for name in REQ_FILES:
        p = REPO / name
        if p.exists():
            out.extend((name, req) for req in _requirements(p))
    return out


CASES = _cases()


def test_the_scan_found_requirements():
    """Guard the guard: a parser change that yields nothing would make every
    case below vacuously pass."""
    assert len(CASES) >= 10, f"only parsed {len(CASES)} requirements"
    assert any(r.name == "pytest-asyncio" for _, r in CASES)


@pytest.mark.parametrize(
    "source,req", CASES, ids=[f"{s}:{r.name}" for s, r in CASES])
def test_installed_version_satisfies_the_declared_bound(source, req):
    canonical = req.name.lower().replace("_", "-")
    try:
        installed = version(req.name)
    except PackageNotFoundError:
        if canonical in OPTIONAL:
            pytest.skip(f"{req.name} is optional and not installed")
        pytest.skip(f"{req.name} is not installed in this environment")

    if not req.specifier:
        return                                       # unbounded: a different complaint

    assert req.specifier.contains(installed, prereleases=True), (
        f"{req.name} {installed} is installed but {source} declares "
        f"'{req.specifier}'.\n\n"
        f"CI installs from {source}, so CI is running something this "
        f"environment is not. Either update the declaration (if the new version "
        f"is wanted) or run:\n\n"
        f"    python -m pip install -U '{req.name}{req.specifier}'\n"
    )
