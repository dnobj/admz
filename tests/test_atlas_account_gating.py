"""Creating an account must not be less gated than deleting one (#165).

ADMZ does not decide how risky an operation is — the catalog does. Each
operation's ``risk_level`` comes out of ``axis-api-atlas`` YAML, and
``confirm_store.get_confirmation_level`` maps it to a confirmation level.
That seam is where #165 lived, and why nobody noticed for so long: both
halves were individually reasonable. Atlas said ``pwdgrp.cgi:add-user`` was
``normal``; ADMZ said ``normal`` means run inline. Neither file is wrong on
its own reading, and neither repository's tests could see the combination.

The result, measured against this exact code path before the fix:

===========================  =====================  ===================
operation                    risk_level             confirmation
===========================  =====================  ===================
``pwdgrp.cgi:remove-user``   ``service-affecting``  ``url_only``
``pwdgrp.cgi:add-user``      ``normal``             ``none``
===========================  =====================  ===================

Deleting a user needed a human. Creating a persistent root-group account did
not. Atlas fixed the YAML in ``mrdnlabs/axis-api-atlas@635c395`` and pins the
three files with its own test; this test pins the *resolved* behaviour, which
is the thing #165 was actually about and which no atlas test can see.

The invariant is relative, not absolute. It does not assert
``service-affecting`` — a future catalog may reasonably decide account
changes are ``dangerous``, and that must not turn this red. It asserts only
that the create side is never *weaker* than the remove side, which is the
asymmetry that existed.

WHY THIS TEST SKIPS ON A DEV BOX
--------------------------------
The assertion is about the catalog ADMZ *pins*. Developers install atlas as a
local editable checkout (``pip install -e ../axis-api-atlas``) which may sit on
any commit — ahead of the pin, behind it, or on a feature branch. Asserting
against whatever happens to be checked out would make this test report on the
developer's working tree rather than on ADMZ, so it runs only when the
installed distribution is the pinned commit. CI installs from git at
``setup.py:ATLAS_SHA`` (``.github/actions/setup-admz``) and separately proves
it with ``assert_atlas_provenance.py``, so CI is where this binds.
"""

from __future__ import annotations

import json
import re
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

import pytest

from admz.api.confirm_store import (
    VALID_CONFIRMATION_LEVELS,
    get_confirmation_level,
)

SETUP_PY = Path(__file__).resolve().parents[1] / "setup.py"

# Ordering of confirmation levels, weakest first. The coverage test below
# pins this against VALID_CONFIRMATION_LEVELS so that adding a level to the
# application without ranking it here fails loudly rather than silently
# comparing as "unknown".
_STRENGTH = {
    "none": 0,
    "llm_confirm": 1,
    "url_only": 2,
    "url_and_password": 3,
}

# (creating operation, its removal/modification counterpart in the same family)
ACCOUNT_PAIRS = [
    ("pwdgrp.cgi:add-user", "pwdgrp.cgi:remove-user"),
    ("ssh:addUser", "ssh:removeUser"),
    ("ssh:modifyUser", "ssh:removeUser"),
]


def _pinned_sha() -> str | None:
    try:
        src = SETUP_PY.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'^ATLAS_SHA\s*=\s*"([0-9a-fA-F]{40})"', src, re.MULTILINE)
    return match.group(1).lower() if match else None


def _installed_atlas_commit() -> str | None:
    """The commit the installed atlas came from, or None if it cannot be known.

    None covers both "installed from a local directory" (the developer case —
    ``direct_url.json`` carries ``dir_info`` and there is no commit to compare)
    and "no metadata at all".
    """
    try:
        raw = distribution("axis-api-atlas").read_text("direct_url.json")
    except PackageNotFoundError:
        return None
    if not raw:
        return None
    try:
        info = json.loads(raw)
    except ValueError:
        return None
    commit = info.get("vcs_info", {}).get("commit_id")
    return commit.lower() if isinstance(commit, str) else None


_PINNED = _pinned_sha()
_INSTALLED = _installed_atlas_commit()

running_the_pinned_catalog = pytest.mark.skipif(
    _INSTALLED is None or _PINNED is None or _INSTALLED != _PINNED,
    reason=(
        "this asserts the behaviour of the PINNED atlas catalog; installed "
        f"commit is {_INSTALLED or 'a local/editable checkout'}, pin is "
        f"{_PINNED or 'unreadable'}"
    ),
)


def test_every_confirmation_level_is_ranked():
    """A new confirmation level must be ranked before it can be compared.

    Without this, adding e.g. ``"biometric"`` to VALID_CONFIRMATION_LEVELS
    would make ``_STRENGTH[level]`` raise inside the comparison below and read
    as an error in an unrelated test, or — worse, if the lookup were ever made
    forgiving — compare as weaker than everything.
    """
    assert set(_STRENGTH) == VALID_CONFIRMATION_LEVELS


@running_the_pinned_catalog
@pytest.mark.parametrize("create_op,remove_op", ACCOUNT_PAIRS)
def test_creating_an_account_is_not_less_gated_than_removing_one(
    create_op, remove_op
):
    import axis_api_atlas
    from axis_api_atlas.catalog.loader import CatalogLoader

    loader = CatalogLoader(axis_api_atlas.default_data_path())

    # get_risk_level() answers "normal" for an operation it cannot find, which
    # is indistinguishable from a genuine "normal" — so resolve the operations
    # first. A renamed op must fail this test, not quietly pass it as ungated.
    for op_id in (create_op, remove_op):
        assert loader.get_operation("vapix", op_id) is not None, (
            f"{op_id} is not in the pinned catalog. If it was renamed, update "
            f"ACCOUNT_PAIRS — do not delete the pair; an unfindable operation "
            f"resolves to risk 'normal' and would silently pass ungated."
        )

    create = get_confirmation_level(loader.get_risk_level("vapix", create_op))
    remove = get_confirmation_level(loader.get_risk_level("vapix", remove_op))

    # No fleet-settings override is in play: conftest redirects ADMZ_HOME to a
    # throwaway, so this is the shipped default posture rather than whatever a
    # particular install has configured.
    assert _STRENGTH[create] >= _STRENGTH[remove], (
        f"{create_op} confirms at {create!r} but {remove_op} confirms at "
        f"{remove!r} — creating an account is easier than deleting one (#165)."
    )
