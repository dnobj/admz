"""The conftest's fleet-settings holder list names every module that needs it.

``tests/conftest.py`` imports each holder before the first test runs, and
checks after every test that none still points at a store the test patched
in. Both cover only the modules the list names. A new module that binds the
singleton at import and is left off the list could be first imported inside a
test and keep that test's store, silently, until a later test in the same run
read the wrong one.

A holder is a module whose import-time code runs
``from admz.fleet_settings import fleet_settings``. An import inside a function
rebinds on every call, and ``import admz.fleet_settings as x`` reads the
attribute at call time, so neither can leak.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from tests.conftest import _FLEET_SETTINGS_HOLDERS

ADMZ = Path(__file__).resolve().parents[1] / "admz"

_CALL_TIME = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _binds_at_import(tree: ast.Module) -> bool:
    """True when code that runs at import binds ``fleet_settings`` by name.

    Walks everything but function bodies: a class body, an ``if`` or a
    ``try`` at module level all run at import.
    """
    stack = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, _CALL_TIME):
            continue
        if (isinstance(node, ast.ImportFrom)
                and (node.module or "").split(".")[-1] == "fleet_settings"
                and any(alias.name == "fleet_settings" for alias in node.names)):
            return True
        stack.extend(ast.iter_child_nodes(node))
    return False


def _module_name(path: Path) -> str:
    parts = path.relative_to(ADMZ.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def test_the_list_names_every_module_that_binds_the_store_at_import():
    found = {
        _module_name(path) for path in ADMZ.rglob("*.py")
        if _binds_at_import(ast.parse(path.read_text(encoding="utf-8")))
    }
    assert found == set(_FLEET_SETTINGS_HOLDERS), (
        "tests/conftest.py _FLEET_SETTINGS_HOLDERS is out of date — "
        f"missing {sorted(found - set(_FLEET_SETTINGS_HOLDERS))}, "
        f"stale {sorted(set(_FLEET_SETTINGS_HOLDERS) - found)}")


def test_every_holder_is_imported_before_any_test_runs():
    """Meaningful when this file runs alone: nothing it imports pulls in a
    holder, so only the conftest's session fixture can have."""
    assert [name for name in _FLEET_SETTINGS_HOLDERS if name not in sys.modules] == []


def test_the_scan_tells_a_binding_from_a_call_time_read():
    def binds(source: str) -> bool:
        return _binds_at_import(ast.parse(source))

    assert binds("from admz.fleet_settings import fleet_settings\n")
    assert binds("from admz.fleet_settings import (\n    fleet_settings,\n    X,\n)\n")
    assert binds("try:\n    from admz.fleet_settings import fleet_settings as fs\n"
                 "except ImportError:\n    fs = None\n")
    assert binds("class C:\n    from admz.fleet_settings import fleet_settings\n")
    assert not binds("def f():\n    from admz.fleet_settings import fleet_settings\n")
    assert not binds("import admz.fleet_settings as _fs\n")
    assert not binds("from admz.fleet_settings import FleetSettings\n")
