"""The catalog's risk vocabulary must be one the gate can interpret (#397).

``risk_level`` is written in ``mrdnlabs/axis-api-atlas`` and interpreted by
``admz/confirm_policy.py``. Two repositories, one pinned to the other by SHA,
each locally consistent — which is exactly the seam #165 lived in, and the
reason a word can be added on one side that the other silently cannot read.

Since #397 an unrecognised risk fails CLOSED, so the consequence of divergence
is a confirmation card where none was intended rather than an execution where
one was. That is the safe direction, but it is still a surprise landing on
whoever bumps the pin, and the surprise arrives at runtime.

This test moves it to the moment it is introduced. The vocabulary only changes
when the catalog changes, catalog changes arrive as a pin bump, and pin bumps
go through CI — so a test blocks the divergence where a startup warning would
merely have described it.

Deliberately NOT skipped on a developer's editable atlas checkout, unlike
``test_atlas_account_gating``. That test asserts something about the *pinned*
catalog, so an arbitrary local checkout cannot speak to it. This one asserts
something about the catalog you are *actually running*: if your installed atlas
uses a risk word ADMZ cannot interpret, your ADMZ is misgating right now, and
being told so is the point.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import axis_api_atlas

from admz.confirm_policy import (
    UNKNOWN_RISK_CONFIRMATION,
    VALID_CONFIRMATION_LEVELS,
    unknown_risk_levels,
)


def _catalog_risk_levels() -> dict[str, list[str]]:
    """Every distinct ``risk_level`` in the installed catalog → example files.

    Parsed as YAML rather than grepped. Two ACS operations write
    ``risk_level: action   # transmits audio TO a device``; a line-based reader
    reports the trailing comment as part of the value and invents two risk
    classes that do not exist.
    """
    root = Path(axis_api_atlas.default_data_path())
    found: dict[str, list[str]] = {}
    for path in root.rglob("*.yaml"):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - a malformed file is not this test's subject
            continue
        if not isinstance(data, dict):
            continue
        risk = data.get("risk_level")
        if isinstance(risk, str):
            found.setdefault(risk, []).append(str(path.relative_to(root)))
    return found


def test_the_catalog_uses_no_risk_level_admz_cannot_interpret():
    found = _catalog_risk_levels()
    assert found, (
        "no risk_level found anywhere in the catalog — the catalog path is "
        "probably wrong, and an empty corpus passes every assertion below"
    )

    unknown = unknown_risk_levels(found)
    detail = {r: found[r][:3] for r in sorted(unknown)}
    assert not unknown, (
        f"the catalog uses risk classes admz/confirm_policy.py does not map: "
        f"{detail}. Since #397 these fail closed to "
        f"{UNKNOWN_RISK_CONFIRMATION!r}, so nothing is running ungated — but a "
        f"confirmation card is now appearing for operations nobody classified. "
        f"Add them to _DEFAULT_CONFIRMATION_LEVELS with a deliberate level."
    )


def test_every_mapped_risk_resolves_to_a_real_confirmation_level():
    """The table's own values must be levels the rest of the app accepts.

    Cheap, and it closes the other direction: a typo in the *value* column
    would otherwise produce a confirmation level nothing knows how to render.
    """
    from admz.confirm_policy import _DEFAULT_CONFIRMATION_LEVELS

    bad = {
        risk: level
        for risk, level in _DEFAULT_CONFIRMATION_LEVELS.items()
        if level not in VALID_CONFIRMATION_LEVELS
    }
    assert not bad, f"unrenderable confirmation levels in the table: {bad}"


def test_the_fail_closed_default_is_itself_a_real_level():
    assert UNKNOWN_RISK_CONFIRMATION in VALID_CONFIRMATION_LEVELS


@pytest.mark.parametrize("risk", ["critical", "", "Service-Affecting", "normal "])
def test_an_unrecognised_risk_does_not_resolve_to_none(risk, monkeypatch, tmp_path):
    """The #397 regression itself, at the function that decides.

    The cases are the plausible shapes of the mistake rather than one invented
    word: a severity nobody added (``critical``), an empty value, a
    capitalisation slip, and a trailing space. Each previously resolved to
    ``none`` — run inline, no human.
    """
    from admz.fleet_settings import FleetSettings
    import admz.fleet_settings
    from admz.api.confirm_store import get_confirmation_level

    fs = FleetSettings(db_path=str(tmp_path / "fleet.db"))
    monkeypatch.setattr(admz.fleet_settings, "fleet_settings", fs)

    level = get_confirmation_level(risk)
    assert level != "none", (
        f"risk {risk!r} resolves to 'none' — it would execute with no "
        f"confirmation (#397)"
    )
    assert level == UNKNOWN_RISK_CONFIRMATION
