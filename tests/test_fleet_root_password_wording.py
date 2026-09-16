"""Operators read "fleet root password", never "break-glass".

#499 renamed the Settings row "Fleet root password", and the success flash
under it kept saying "Break-glass root password" — as did the device page's
notes, the approval cards, a log line and the assistant's tool text. The owner
found it on the live page on 2026-09-16.

"Break-glass" stays the design's name for the idea, in ADR-0068 and in code
comments. What can reach an operator says "fleet root password", and this file
checks what can reach one rather than a list of known sentences, since a list
is exactly what missed these:

* every string literal under ``admz/`` that is not a docstring — page copy,
  flashes, approval-card reasons, log lines, tool descriptions and results;
* every template and static script, outside its comments.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ADMZ = Path(__file__).resolve().parents[1] / "admz"

TERM = re.compile(r"break[\s-]*glass", re.IGNORECASE)

#: Jinja, HTML and block comments are never shown; nor are `//` line comments
#: in inline scripts. Only whole-line ones, so a URL's `//` is left alone.
_COMMENTS = re.compile(r"\{#.*?#\}|<!--.*?-->|/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")


def _strings(source: str):
    """(line, text) for each string literal that is not a bare statement.

    A bare string statement is a docstring or an inert note; neither is ever
    shown. Implicitly concatenated literals arrive as one constant, so a
    phrase split across source lines is still seen whole.
    """
    tree = ast.parse(source)
    bare = {id(node.value) for node in ast.walk(tree)
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in bare):
            yield node.lineno, node.value


def _shown(text: str) -> str:
    return _LINE_COMMENT.sub(" ", _COMMENTS.sub(" ", text))


def _python_files():
    return sorted(ADMZ.rglob("*.py"))


def _page_files():
    return sorted([*ADMZ.glob("api/templates/**/*.html"),
                   *ADMZ.glob("api/static/**/*.js")])


def test_no_string_an_operator_can_read_says_break_glass():
    hits = [
        f"{path.relative_to(ADMZ.parent)}:{line}: {text[:70]!r}"
        for path in _python_files()
        for line, text in _strings(path.read_text(encoding="utf-8"))
        if TERM.search(text)
    ]
    assert not hits, (
        "say 'fleet root password' — the name the Settings row uses:\n"
        + "\n".join(hits))


def test_no_page_says_break_glass():
    hits = [
        f"{path.relative_to(ADMZ.parent)}: {match.group(0)!r}"
        for path in _page_files()
        for match in TERM.finditer(_shown(path.read_text(encoding="utf-8")))
    ]
    assert not hits, (
        "say 'fleet root password' — the name the Settings row uses:\n"
        + "\n".join(hits))


# --- the scan can fail --------------------------------------------------------


def test_the_scan_covers_the_code_and_the_pages():
    """A glob that matched nothing would pass both tests above."""
    names = {p.name for p in _python_files()}
    assert {"onboarding.py", "entry_credentials.py", "server.py", "web.py"} <= names
    pages = {p.name for p in _page_files()}
    assert {"settings.html", "device_detail.html"} <= pages


def test_the_scan_finds_the_term_in_every_shape_it_took():
    source = (
        'MESSAGE = ("Break-glass root password " + "set")\n'
        'SPLIT = ("the fleet break-"\n'
        '         "glass password")\n'
        'def f():\n'
        '    """The break-glass value, in a docstring: never shown."""\n'
        '    log("resetting to the fleet break glass password failed")\n'
    )
    found = sorted(line for line, text in _strings(source) if TERM.search(text))
    assert found == [1, 2, 6]


def test_page_comments_are_skipped_and_page_text_is_not():
    page = (
        "{# a break-glass credential, in a Jinja comment #}\n"
        "<!-- break-glass, in an HTML comment -->\n"
        "  // break-glass, in a script comment\n"
        "<a href=\"https://example.test/x\">Set the break-glass password</a>\n"
        "note: ['error', 'root is set to the fleet break-glass password'],\n"
    )
    assert len(TERM.findall(_shown(page))) == 2
