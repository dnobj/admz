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

# Closed vocabulary of confirmation levels an operator may select. An override
# outside this set is ignored by ``get_confirmation_level``, which falls back
# to the table above — this rejects typos, not downgrades.
VALID_CONFIRMATION_LEVELS = {"url_and_password", "url_only", "llm_confirm", "none"}

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

    A risk class absent from the table already resolves to ``none``, so it
    cannot be relaxed further; the namespace rule earns its keep by protecting
    a *future* table entry from the moment it is added rather than from the
    moment someone remembers to update a second list. This is also what the
    glossary, the llm-agent persona and the security-operator persona have
    always promised (``confirm_level_*``). GH #152.
    """
    return key.startswith(CONFIRM_LEVEL_KEY_PREFIX)
