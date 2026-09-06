"""
Confirmation policy vocabulary: risk level → confirmation level.

This module is deliberately a **leaf**. It imports nothing from :mod:`admz`,
so any module may import it without creating a cycle — in particular
:mod:`admz.fleet_settings`, which derives the protected ``confirm_level_*``
setting keys from :data:`_DEFAULT_CONFIRMATION_LEVELS` below.

Why the vocabulary lives here rather than in :mod:`admz.api.confirm_store`
(its original home) or in :mod:`admz.fleet_settings`:

* ``confirm_store`` already imports ``fleet_settings`` at module scope (the
  CR-3 relocation of ``PROTECTED_SETTING_KEYS``). Deriving the protected key
  names from a table defined in ``confirm_store`` would mean ``fleet_settings``
  importing *up* into ``confirm_store`` while ``confirm_store`` imports *down*
  into ``fleet_settings`` — a cycle that raises ``ImportError`` differently
  depending on which module is imported first. The vocabulary has to move
  down, not reach up.
* ``fleet_settings`` is settings *plumbing*; the risk vocabulary is *policy*,
  and ``admz/api/routes/web.py`` consumes ``VALID_CONFIRMATION_LEVELS``
  independently of the settings store.

``confirm_store`` re-exports both tables under their original names, the same
way it re-exports ``PROTECTED_SETTING_KEYS``. See ADR-0006, ADR-0020, ADR-0034.
"""

from typing import Dict


# Default mapping from risk level → confirmation level.
#
# Single source of truth for the risk vocabulary. Everything that needs to
# enumerate risk classes derives from this table rather than restating it:
#
#   * ``admz.fleet_settings.PROTECTED_SETTING_KEYS`` — the ``confirm_level_*``
#     keys that MCP and anonymous REST callers are refused (GH #152).
#   * ``admz/api/routes/web.py`` — the rows rendered on /confirm-settings and
#     the fields accepted by its POST handler.
#   * ``tests/test_confirm_store.py`` — the coverage guards.
_DEFAULT_CONFIRMATION_LEVELS: Dict[str, str] = {
    "dangerous": "url_and_password",
    "service-affecting": "url_only",
    "normal": "none",
    "read-only": "none",
    # ACS Pro (and other server-target families) use a simpler read|action
    # risk vocabulary. Actions mutate live state → widget-gate them (ADR-0034);
    # reads are unconfirmed. Without these, the .get(risk, "none") fallback
    # would let an unmapped 'action' risk through ungated.
    "action": "url_only",
    "read": "none",
}

# What a risk class ABSENT from the table above resolves to (GH #397).
#
# This used to be ``none`` — run inline, no card, no human — so the gate failed
# OPEN on a vocabulary it did not recognise. An operation carrying a typo'd or
# newly-invented ``risk_level`` passed every existence check downstream and
# executed unconfirmed, and the more severe the author intended the unfamiliar
# word to sound, the more likely it was one nobody had added here.
#
# The risk vocabulary and this table are maintained in DIFFERENT REPOSITORIES —
# the catalog is ``mrdnlabs/axis-api-atlas``, pinned by SHA — so the two can
# diverge with each side locally consistent. That is the same seam #165 lived
# in, and it is why the default has to be safe rather than convenient.
#
# Two neighbouring decisions already went this way and are the precedent:
# ``plans/engine.py``'s raise-only step floor ignores a declared risk it does
# not know and compares EFFECTIVE confirmation levels, so a declared word can
# never soften a catalog word (#456); and ``mcp/server.py`` resolves an
# unreadable catalog to ``service-affecting`` because "an unreadable catalog
# must not open the gate".
#
# Choosing ``url_only`` rather than ``url_and_password``: unknown means unknown,
# not maximally dangerous, and ``url_only`` is a click rather than a password —
# enough to put a human in the loop without implying a severity nobody
# established. ``tests/test_risk_vocabulary.py`` asserts this is unreachable for
# the pinned catalog, so in practice it fires only on a catalog change, which is
# exactly when someone should look.
UNKNOWN_RISK_CONFIRMATION = "url_only"

# Closed vocabulary of confirmation levels an operator may select. An override
# outside this set is ignored by ``get_confirmation_level``, which falls back
# to the table above — this rejects typos, not downgrades.
VALID_CONFIRMATION_LEVELS = {"url_and_password", "url_only", "llm_confirm", "none"}

# Strictness order of the confirmation levels — the ONE severity scale
# (GH #456). ``operations._plan_level_and_risk`` ranks plan steps with it, and
# the plan engine's raise-only risk floor ranks risk WORDS through it via
# :func:`risk_rank`, so there is no second vocabulary table anywhere that can
# quietly disagree with this one. The engine used to keep its own four-word
# ``_RISK_ORDER`` in which every unknown catalog word — ``action``, ``read``,
# or anything new — ranked 0, so a declared ``normal`` overrode it and the
# fail-closed default below never got the chance: the #397 pathology
# reproduced one table over.
LEVEL_STRICTNESS: Dict[str, int] = {
    "none": 0,
    "llm_confirm": 1,
    "url_only": 2,
    "url_and_password": 3,
}


def is_known_risk(risk_level: str) -> bool:
    """Whether ``risk_level`` is a word the policy table interprets."""
    return risk_level in _DEFAULT_CONFIRMATION_LEVELS


def risk_rank(risk_level: str) -> int:
    """Severity rank of a risk word = the strictness of the confirmation it
    earns by default. An UNKNOWN word ranks as :data:`UNKNOWN_RISK_CONFIRMATION`
    — fail closed — so nothing a caller declares short of ``dangerous`` can
    soften a catalog word this table has never seen. (Whether a *declared*
    unknown word may be honoured at all is the caller's decision; see
    :func:`is_known_risk`.)"""
    level = _DEFAULT_CONFIRMATION_LEVELS.get(risk_level, UNKNOWN_RISK_CONFIRMATION)
    return LEVEL_STRICTNESS[level]


def unknown_risk_levels(risk_levels) -> set:
    """Which of ``risk_levels`` this table cannot interpret.

    Exposed so a test can hold the pinned catalog's vocabulary against the
    table without importing the private mapping.
    """
    return {r for r in risk_levels if r not in _DEFAULT_CONFIRMATION_LEVELS}

# Fleet-setting key namespace for per-risk confirmation overrides.
CONFIRM_LEVEL_KEY_PREFIX = "confirm_level_"


def confirm_level_key(risk_level: str) -> str:
    """Return the fleet-setting key holding the override for ``risk_level``."""
    return f"{CONFIRM_LEVEL_KEY_PREFIX}{risk_level}"


def is_confirm_level_key(key: str) -> bool:
    """Return True for any key in the ``confirm_level_*`` namespace.

    Deliberately a namespace test rather than membership of the risk classes
    :data:`_DEFAULT_CONFIRMATION_LEVELS` happens to name today.
    ``get_confirmation_level`` interpolates the risk string it is handed, and
    that string comes from catalog YAML rather than from this table, so the
    invariant that has to hold is "no low-privilege caller writes *anything*
    under ``confirm_level_*``" — not "…writes one of today's six".

    A risk class absent from the table resolves to ``url_only`` (#397), and a
    ``confirm_level_<word>`` override written for it *would* relax that — which
    is exactly why the namespace rule earns its keep: it protects
    a *future* table entry from the moment it is added rather than from the
    moment someone remembers to update a second list. This is also what the
    glossary, the llm-agent persona and the security-operator persona have
    always promised (``confirm_level_*``). GH #152.
    """
    return key.startswith(CONFIRM_LEVEL_KEY_PREFIX)
