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

#: Ceiling on how many entry credentials may be STORED — not merely tried.
#:
#: Capping attempts while letting the list grow would be worse than no cap: the
#: settings page would show six credentials, ADMZ would try three, and the other
#: three would be a lie the operator had no way to see. A limit enforced where
#: the decision is made is visible; one enforced at try-time is not.
#:
#: Three rather than an arbitrary larger number because N credentials is N
#: failed authentications, and Axis brute-force behaviour varies by model and
#: firmware. ADR-0061 requires that be MEASURED against a spare device before
#: the trying half ships — until then this number is a conservative guess and
#: should be revisited with the measurement, not defended as if it were one.
MAX_STORED = 3

#: Posture: this installation stores NO entry credentials and prompts for a
#: device credential every time (FR-CRED-013).
#:
#: Distinct from the list merely being empty. Empty is a state — the next add
#: changes it. This is a decision: adds are refused while it holds, and any
#: value already stored is ignored rather than used.
#:
#: Viable because nothing requires a stored fleet password.
#: ``provision_factory_default`` prefers it but falls back to
#: ``generate_device_password()``, and #185 already made the deferred/scheduled
#: reprovision path generate unconditionally. The only thing this posture costs
#: is that adopting an already-set-up device always asks a human — which is
#: precisely what it is choosing.
PROMPT_ALWAYS_KEY = "entry_credentials_prompt_always"


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
            # would occupy one of the MAX_STORED slots on a guaranteed failure.
            continue
        out.append(EntryCredential(str(user), str(password), str(item.get("label") or "")))
    return out


def prompt_always() -> bool:
    """True when this installation stores no entry credentials by policy."""
    raw = fleet_settings.get(PROMPT_ALWAYS_KEY)
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def list_entry_credentials() -> List[EntryCredential]:
    """Every credential ADMZ may try, in the order it should try them.

    Empty under :func:`prompt_always`, whatever is stored. Turning the posture
    on therefore stops ADMZ using a credential immediately, without requiring
    the operator to delete anything first — and turning it off restores what
    was there, which is why nothing is deleted on their behalf.

    Otherwise the legacy pair comes first when set: it is the one an operator
    has most recently confirmed by hand, and trying it first means an install
    that has never touched this feature behaves exactly as it did before.
    """
    if prompt_always():
        return []
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
    """What an adoption should try. Identical to the stored list, by design.

    The cap is enforced on storage, so there is nothing to trim here. This
    function exists as the device-facing name for the same thing: a later slice
    may reorder it (ADR-0061 suggests most-recently-successful first) without
    changing what the settings page shows.
    """
    return list_entry_credentials()


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
    if prompt_always():
        raise ValueError(
            f"this installation stores no entry credentials ({PROMPT_ALWAYS_KEY} "
            f"is on); clear that posture first if you want to store one"
        )
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
    # Counted against the legacy pair too: it occupies one of the slots,
    # because it is one of the credentials that gets tried.
    total = len(existing) + (1 if fleet_settings.get(LEGACY_PASS_KEY) else 0)
    if total >= MAX_STORED:
        raise ValueError(
            f"at most {MAX_STORED} entry credentials may be stored (currently "
            f"{total}); remove one before adding another. Each is another failed "
            f"authentication against every device ADMZ adopts."
        )
    existing.append(EntryCredential(username, password, label))
    fleet_settings.set(SETTING_KEY, json.dumps([
        {"username": c.username, "password": c.password, "label": c.label}
        for c in existing
    ]))
    return True


def describe() -> dict:
    """The redacted state, for a settings page, an API response or a log.

    Reports what is STORED separately from what is in USE, because under
    :func:`prompt_always` those differ and an operator reading "0 credentials"
    would not know whether that is a policy or an empty box.
    """
    stored = _parse(fleet_settings.get(SETTING_KEY))
    if fleet_settings.get(LEGACY_PASS_KEY):
        stored.insert(0, EntryCredential(
            fleet_settings.get(LEGACY_USER_KEY) or "root", "", "fleet default"))
    return {
        "prompt_always": prompt_always(),
        "max_stored": MAX_STORED,
        "stored": [c.redacted() for c in stored],
        "in_use": [c.redacted() for c in list_entry_credentials()],
    }
