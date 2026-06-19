"""The module contract + registry must stay leaf-light.

``admz/modules/contract.py`` and ``admz/modules/registry.py`` are imported by
the stdio MCP subprocess and by ``admz.operations`` adjacent code, so — like
``admz.operations`` itself (see ``test_api_import_isolation``) — importing them
must NOT drag in the FastAPI app, the VAPIX executor, or the (heavy) catalog
package. Each import below runs in a *fresh* interpreter and asserts the heavy
stack was not pulled in.

Until PR1-P1 creates ``admz/modules/``, these tests skip cleanly; the moment the
package exists they go live and enforce the isolation property with no edit.
"""

import subprocess
import sys

import pytest

# Skip the whole module until the package exists (created in PR1-P1). Once it
# imports, this becomes a live guardrail automatically.
pytest.importorskip("admz.modules.contract")
pytest.importorskip("admz.modules.registry")


_HEAVY = (
    "fastapi",
    "uvicorn",
    "admz.api.main",
    "admz.api.routes",
    "admz.executor.vapix",
    "axis_api_atlas",
)


def _heavy_modules_after(import_line: str) -> str:
    names = ", ".join(repr(m) for m in _HEAVY)
    code = (
        f"{import_line}\n"
        "import sys\n"
        f"heavy = [m for m in ({names},) if m in sys.modules]\n"
        "print(','.join(sorted(heavy)))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_importing_module_contract_stays_leaf_light():
    assert _heavy_modules_after("import admz.modules.contract") == ""


def test_importing_module_registry_stays_leaf_light():
    assert _heavy_modules_after("import admz.modules.registry") == ""
