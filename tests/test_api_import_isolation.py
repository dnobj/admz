"""H-2: importing ADMZ's leaf modules must not build the FastAPI app.

``admz/api/__init__`` used to ``from admz.api.main import app`` at import time,
so importing the "leaf" ``admz.operations`` (which depends on
``admz.api.confirm_store``) dragged in FastAPI + every router. Each test below
imports a leaf module in a *fresh* interpreter and asserts the heavy web stack
was not pulled in.
"""

import subprocess
import sys


def _heavy_modules_after(import_line: str) -> str:
    code = (
        f"{import_line}\n"
        "import sys\n"
        "heavy = [m for m in ('fastapi', 'admz.api.main', 'uvicorn', "
        "'admz.api.routes') if m in sys.modules]\n"
        "print(','.join(sorted(heavy)))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_importing_operations_does_not_build_app():
    assert _heavy_modules_after("import admz.operations") == ""


def test_importing_confirm_store_does_not_build_app():
    assert _heavy_modules_after("import admz.api.confirm_store") == ""


def test_importing_recovery_does_not_build_app():
    assert _heavy_modules_after("import admz.recovery") == ""


def test_importing_redact_does_not_build_app():
    assert _heavy_modules_after("import admz.redact") == ""


def test_app_still_accessible_lazily():
    """`from admz.api import app` must still work (builds on demand)."""
    proc = subprocess.run(
        [sys.executable, "-c",
         "from admz.api import app; print(type(app).__name__)"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "FastAPI" in proc.stdout
