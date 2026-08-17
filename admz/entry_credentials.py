"""Entry credentials — the list ADMZ tries to get *into* a device (FR-CRED-011).

ADR-0061 splits one credential doing two jobs into two credentials doing one
each. This module owns the first: **getting in** to a device ADMZ does not yet
manage. The second — the per-device ``admz`` account that becomes the ongoing
credential — is the next slice of #411 and is not here.

WHY A LIST
----------
``fleet_settings`` holds one ``default_username`` and one ``default_password``,
so ADMZ can express exactly one setup era. A fleet acquired over time has
several: different batches, different usernames, different passwords. Measured
on the live fleet when ADR-0061 was written — ``default_username`` was
``operator`` and **none of the nine stored device accounts used it**. Eight were
``root``, one ``admz``. The configured pair could not resolve anything, and the
capture form had been doing all the work.

STORAGE
-------
The list lives in one encrypted fleet setting, ``entry_credentials``, as JSON.
It is declared in ``setting_policy.STORE_ENCRYPTED_SETTING_KEYS`` alongside
``default_password`` — ADR-0061 makes these credentials the only route back into
a fleet after a database loss, so they are recovery material, not merely
sensitive.

The legacy ``default_username``/``default_password`` pair is **read as entry #1**
rather than migrated away. It is still what ``provision_factory_default`` writes
to a factory-defaulted device, so removing it is a separate decision with its own
blast radius; this module only stops it being the *whole* answer.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import List, Optional

from admz.fleet_settings import fleet_settings

logger = logging.getLogger(__name__)

#: One encrypted fleet setting holding the JSON list.
SETTING_KEY = "entry_credentials"

#: Legacy single pair, still authoritative for provisioning a factory-defaulted
#: device. Read here as the first entry so an existing install keeps working
#: with no migration step and no window where nothing resolves.
LEGACY_USER_KEY = "default_username"
LEGACY_PASS_KEY = "default_password"

#: Ceiling on how many credentials a single device adoption may try.
#:
#: Not arbitrary caution: N credentials is N failed authentications, and Axis
#: brute-force behaviour varies by model and firmware. ADR-0061 requires this be
#: measured against a spare device before the trying half ships; until then the
#: cap is the guard. Adding a fourth credential must not be the thing that locks
#: ADMZ out of the fleet.
MAX_ATTEMPTS = 4


@dataclass(frozen=True)
class EntryCredential:
    """One (username, password) pair ADMZ may try to get into a device."""

    username: str
    password: str
    #: Free-text note — which batch or era this came from. Never a secret.
    label: str = ""

    def redacted(self) -> dict:
        """Safe for a log, an API response or an LLM context."""
        return {"username": self.username, "label": self.label}


def _parse(raw: Optional[str]) -> List[EntryCredential]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("%s is not valid JSON; treating as empty", SETTING_KEY)
        return []
    if not isinstance(data, list):
        logger.warning("%s is not a JSON list; treating as empty", SETTING_KEY)
        return []
    out: List[EntryCredential] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        user, password = item.get("username"), item.get("password")
        if not user or not password:
            # A half-written entry cannot authenticate anything, and keeping it
            # would burn one of MAX_ATTEMPTS on a guaranteed failure.
            continue
        out.append(EntryCredential(str(user), str(password), str(item.get("label") or "")))
    return out


def list_entry_credentials() -> List[EntryCredential]:
    """Every credential ADMZ may try, in the order it should try them.

    The legacy pair comes first when set. It is the one an operator has most
    recently confirmed by hand, and trying it first means an install that has
    never touched this feature behaves exactly as it did before.
    """
    creds: List[EntryCredential] = []
    legacy_pass = fleet_settings.get(LEGACY_PASS_KEY)
    if legacy_pass:
        creds.append(EntryCredential(
            username=fleet_settings.get(LEGACY_USER_KEY) or "root",
            password=legacy_pass,
            label="fleet default",
        ))
    seen = {(c.username, c.password) for c in creds}
    for cred in _parse(fleet_settings.get(SETTING_KEY)):
        if (cred.username, cred.password) in seen:
            continue
        seen.add((cred.username, cred.password))
        creds.append(cred)
    return creds


def attempt_order() -> List[EntryCredential]:
    """What an adoption should actually try — the list, capped.

    Separate from :func:`list_entry_credentials` so the settings surface can
    show every configured credential while the device-facing path stays bounded.
    A list that grows past the cap is a configuration problem to surface, not a
    reason to hammer a camera.
    """
    creds = list_entry_credentials()
    if len(creds) > MAX_ATTEMPTS:
        logger.warning(
            "%d entry credentials configured; only the first %d will be tried "
            "(see entry_credentials.MAX_ATTEMPTS)", len(creds), MAX_ATTEMPTS,
        )
    return creds[:MAX_ATTEMPTS]


def add_entry_credential(username: str, password: str, label: str = "") -> bool:
    """Promote a credential to the entry list (FR-CRED-012).

    Returns ``True`` if it was added, ``False`` if an identical pair was already
    present — the caller decides whether that is worth reporting.

    **This widens what ADMZ will try against every device in the fleet.** The
    caller is responsible for the operator having asked for it explicitly and
    for auditing the promotion separately from whatever produced the credential;
    ADR-0061 requires both. Nothing here should be called as a side effect of a
    successful capture.
    """
    username, password = (username or "").strip(), password or ""
    if not username or not password:
        raise ValueError("an entry credential needs both a username and a password")
    existing = _parse(fleet_settings.get(SETTING_KEY))
    for cred in existing:
        if cred.username == username and cred.password == password:
            return False
    # The legacy pair is not in `existing`, so check it too — promoting a
    # duplicate of it would spend an attempt slot on the credential already
    # being tried first.
    if (fleet_settings.get(LEGACY_PASS_KEY) == password
            and (fleet_settings.get(LEGACY_USER_KEY) or "root") == username):
        return False
    existing.append(EntryCredential(username, password, label))
    fleet_settings.set(SETTING_KEY, json.dumps([
        {"username": c.username, "password": c.password, "label": c.label}
        for c in existing
    ]))
    return True


def describe() -> List[dict]:
    """The list, redacted — for a settings page, an API response or a log."""
    return [c.redacted() for c in list_entry_credentials()]
