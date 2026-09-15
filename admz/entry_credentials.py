"""Entry credentials — the list ADMZ tries to get *into* a device (FR-CRED-011).

ADR-0061 splits one credential doing two jobs into two credentials doing one
each. This module owns the first: **getting in** to a device ADMZ does not yet
manage. The second — the per-device ``admz`` account that becomes the ongoing
credential — shipped as #411 slice 2 (``provisioning.adopt_with_admz_account``).

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
rather than migrated away. Since ADR-0064 slice E it is no longer written to a
factory-defaulted device (FR-CRED-007: the generated password wins), so it is
purely an entry credential; retiring it into the list is still a separate
decision with its own blast radius — every install's effective list is its
legacy pair — and this module only stops it being the *whole* answer.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from admz.fleet_settings import fleet_settings

logger = logging.getLogger(__name__)

#: One encrypted fleet setting holding the JSON list.
SETTING_KEY = "entry_credentials"

#: Legacy single pair, still authoritative for provisioning a factory-defaulted
#: device. Read here as the first entry so an existing install keeps working
#: with no migration step and no window where nothing resolves.
LEGACY_USER_KEY = "default_username"
LEGACY_PASS_KEY = "default_password"
#: The label the legacy pair is listed and tried under.
LEGACY_LABEL = "fleet default"

#: Ceiling on how many entry credentials may be STORED through the writer API.
#:
#: The storage cap keeps the settings page honest — what it shows is what
#: exists. It is not the only bound: since ADR-0064 slice C the device-facing
#: loop is bounded separately (``MAX_ATTEMPTS_PER_PASS`` below, the same
#: number) and ``describe()`` reports both what is stored and what is tried,
#: so the page can never claim five are tried when three are.
#:
#: Three rather than an arbitrary larger number because N credentials is N
#: failed authentications, and Axis brute-force behaviour varies by model and
#: firmware. ADR-0061 requires that be MEASURED against a spare device before
#: the trying half ships — until then this number is a conservative guess and
#: should be revisited with the measurement, not defended as if it were one.
MAX_STORED = 3
#: What one onboarding pass may TRY (ADR-0064 slice C). Equal to the storage
#: cap by design, but enforced separately: the storage cap keeps the settings
#: page honest, while this bounds the device-facing loop — the CLI writer
#: (``admz settings set entry_credentials``) bypasses the cap because
#: :func:`_parse` never truncates, so without this one command could make a
#: pass unbounded. Each wrong entry costs two credentialed operations (the
#: primary auth op and its corroborator, GH #149/#150): the loop is at most
#: 3 x 2 = 6 operations, up to 12 sends at the wire when the executor re-sends
#: on a method-relearn. A pass is the loop plus the stored-credential check
#: that precedes it (``onboarding.py`` step 1), and a stale stored credential
#: is corroborated the same way — so one pass is at most 8 operations /
#: 16 sends. A pair the stored-credential check saw REFUSED is skipped when
#: the loop reaches it, so no pair is put to a device to authenticate twice
#: in one pass (#475, ADR-0065).
MAX_ATTEMPTS_PER_PASS = MAX_STORED

#: Posture: this installation stores NO entry credentials and prompts for a
#: device credential every time (FR-CRED-013).
#:
#: Distinct from the list merely being empty. Empty is a state — the next add
#: changes it. This is a decision: adds are refused while it holds, and any
#: value already stored is ignored rather than used.
#:
#: Viable because nothing requires a stored *entry* credential: since ADR-0064
#: slice E ``provision_factory_default`` never writes the fleet
#: ``default_password`` (FR-CRED-007), as the deferred reprovision path has
#: since #185. The only thing this posture costs
#: is that adopting an already-set-up device always asks a human — which is
#: precisely what it is choosing.
#:
#: **It no longer costs nothing, though** (ADR-0068). Provisioning a
#: factory-defaulted device now REQUIRES ``fleet_root_password`` and refuses
#: without it, so an installation running this posture still has to set a root
#: password — a different setting, governed by neither this flag nor the cap —
#: or it cannot provision a factory-default device at all.
PROMPT_ALWAYS_KEY = "entry_credentials_prompt_always"

#: Why a write to the list was refused, as a stable tag for an audit row. The
#: exception's message is operator copy and will be reworded; never match on it.
REFUSED_PROMPT_ALWAYS = "prompt-always"
REFUSED_INCOMPLETE = "incomplete"
REFUSED_CAP = "cap-reached"
REFUSED_UNREADABLE = "unreadable"
REFUSED_STALE = "stale"


class EntryCredentialRefused(ValueError):
    """A write the list's rules refuse, carrying a stable :attr:`code`.

    A ``ValueError``, so every existing ``except ValueError`` caller — the
    capture form's promotion among them — is unchanged.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        #: One of the ``REFUSED_*`` tags above.
        self.code = code


@dataclass(frozen=True)
class EntryCredential:
    """One (username, password) pair ADMZ may try to get into a device."""

    username: str
    #: Never in a repr: a ``%s`` over the list or a traceback must not leak it.
    password: str = field(repr=False)
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


def _unreadable(raw: Optional[str]) -> bool:
    """True when ``raw`` — what ``fleet_settings.get`` returned for the list —
    is ``None`` only because a stored list cannot be decrypted."""
    return raw is None and fleet_settings.is_stored(SETTING_KEY)


def _stored_list() -> List[EntryCredential]:
    """The stored list, read for a WRITE: refused when it cannot be decrypted.

    A reader is right to treat an undecryptable list as empty
    (``setting_crypto.read_stored``). A writer is not, because it rewrites the
    list from what it read: an add would replace the unreadable value with a
    one-entry list, when ``read_stored`` promises that value is left alone so
    that restoring the right key recovers it.
    """
    raw = fleet_settings.get(SETTING_KEY)
    if _unreadable(raw):
        raise EntryCredentialRefused(
            REFUSED_UNREADABLE,
            "the stored entry list cannot be decrypted, so it cannot be changed "
            "without destroying it; restore the key file it was written with first",
        )
    return _parse(raw)


def _write_list(creds: List[EntryCredential]) -> None:
    fleet_settings.set(SETTING_KEY, json.dumps([
        {"username": c.username, "password": c.password, "label": c.label}
        for c in creds
    ]))


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
            label=LEGACY_LABEL,
        ))
    seen = {(c.username, c.password) for c in creds}
    for cred in _parse(fleet_settings.get(SETTING_KEY)):
        if (cred.username, cred.password) in seen:
            continue
        seen.add((cred.username, cred.password))
        creds.append(cred)
    return creds


def _break_glass_attempt(already: List[EntryCredential]) -> List[EntryCredential]:
    """ADMZ's own break-glass root password, as a synthetic attempt (ADR-0068).

    Not an entry credential — nobody stored it here, and it is not in the list.
    It is the value ADMZ itself wrote to ``root`` when it provisioned the
    device, and without it a pass that failed partway is unretryable: root
    holds a password ADMZ *has* and ``attempt_order`` would not offer it.

    Tried **last**, so it never displaces a credential an operator configured,
    and reported by :func:`describe` so the settings page cannot understate
    what ADMZ puts to a device. The extra attempt is affordable on measured
    evidence, not assumption: the lockout measurement (FR-CRED-013, 2026-09-09)
    found no cumulative lockout at all on the device tested, only a 20/s rate
    throttle ADMZ runs some 400x under.

    **Under ``root``, never ``default_username``.** Provisioning writes this
    value to the ``root`` account, while ``default_username`` names an
    unrelated legacy entry credential — ``operator`` on the fleet ADR-0061
    measured. Paired with that username the attempt could never authenticate,
    and the retry it exists for would fail exactly where it is needed.

    **The prompt-always posture does not suppress it.** That posture is about
    *storing entry credentials*; this value is ADMZ's own, and suppressing it
    would lock ADMZ out of a device it had just provisioned itself.
    """
    from admz.provisioning import FLEET_ROOT_PASSWORD_KEY

    break_glass = fleet_settings.get(FLEET_ROOT_PASSWORD_KEY)
    if not break_glass:
        return []
    username = "root"
    if any((c.username, c.password) == (username, break_glass) for c in already):
        return []
    return [EntryCredential(username, break_glass, "ADMZ break-glass root")]


def _attempts(*, warn: bool) -> Tuple[List[EntryCredential], List[EntryCredential]]:
    """One pass's attempts: the bounded entry credentials, then ADMZ's
    break-glass attempt (empty when none is configured).

    The one place a pass is composed. :func:`attempt_order` joins the two and
    :func:`describe` reports them, so what is tried and what the settings page
    says is tried cannot drift; they are returned apart only so the page can
    say "three entry credentials, then the break-glass password" rather than
    "4 (at most 3)".
    """
    creds = list_entry_credentials()
    if len(creds) > MAX_ATTEMPTS_PER_PASS:
        if warn:
            logger.warning(
                "%d entry credentials are stored but a pass tries at most %d — "
                "the rest are never used; trim the list (ADR-0064 slice C)",
                len(creds), MAX_ATTEMPTS_PER_PASS,
            )
        creds = creds[:MAX_ATTEMPTS_PER_PASS]
    # After the slice, deliberately: the break-glass value is ADMZ's own way
    # back into a device it provisioned, and a full entry list must not be able
    # to crowd it out.
    return creds, _break_glass_attempt(creds)


def attempt_order(*, warn: bool = True) -> List[EntryCredential]:
    """What one onboarding pass should try — at most :data:`MAX_ATTEMPTS_PER_PASS`
    entry credentials, **plus** ADMZ's break-glass root password when one is
    configured (ADR-0068; appended last by :func:`_break_glass_attempt`).

    Composed in one place (:func:`_attempts`): the onboarding loop iterates
    this and :func:`describe` reports the same attempts as ``in_use``, so what
    is tried and what the settings page says is tried cannot drift. The order
    is the stored order (the legacy pair first); reordering
    most-recently-successful-first is ADR-0064 slice F and waits for the
    lockout measurement — and it must sort *before* the slice, or success
    history could never pull a tail entry into the tried set.

    ``warn=False`` is for readers (:func:`describe`, the settings page): the
    WARNING about a list stored over the bound belongs to the pass that
    truncates it, not to every page view. The message carries counts only,
    never a credential.
    """
    entries, break_glass = _attempts(warn=warn)
    return entries + break_glass


def add_entry_credential(username: str, password: str, label: str = "") -> bool:
    """Add a credential to the entry list (FR-CRED-012) — promoted from a
    capture, or typed on the Fleet Settings page.

    Returns ``True`` if it was added, ``False`` if an identical pair was already
    present — the caller decides whether that is worth reporting.

    **This widens what ADMZ will try against every device in the fleet.** The
    caller is responsible for the operator having asked for it explicitly and
    for auditing the addition separately from whatever produced the credential;
    ADR-0061 requires both. Nothing here should be called as a side effect of a
    successful capture.

    A refusal raises :class:`EntryCredentialRefused`: the prompt-always
    posture, half a credential, the storage cap, or a stored list that cannot
    be decrypted (:func:`_stored_list`).
    """
    if prompt_always():
        raise EntryCredentialRefused(
            REFUSED_PROMPT_ALWAYS,
            f"this installation stores no entry credentials ({PROMPT_ALWAYS_KEY} "
            f"is on); clear that posture first if you want to store one",
        )
    username, password = (username or "").strip(), password or ""
    if not username or not password:
        raise EntryCredentialRefused(
            REFUSED_INCOMPLETE,
            "an entry credential needs both a username and a password",
        )
    existing = _stored_list()
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
        raise EntryCredentialRefused(
            REFUSED_CAP,
            f"at most {MAX_STORED} entry credentials may be stored (currently "
            f"{total}); remove one before adding another. Each is another failed "
            f"authentication against every device ADMZ adopts.",
        )
    existing.append(EntryCredential(username, password, label))
    _write_list(existing)
    return True


def remove_entry_credential(position: int, *, username: str, label: str) -> Dict[str, object]:
    """Remove one stored entry credential — the one the operator was shown.

    ``position`` is the entry's index in :func:`describe`'s ``stored`` list,
    which is the order the settings page shows (the legacy pair first, when
    set). ``username`` and ``label`` are what the page showed there, and the
    entry is removed only if they still match. The page may be stale — a second
    tab, the CLI writer or a promotion may have changed the list since it was
    rendered — and removing whatever sits at that position *now* would remove a
    credential the operator never saw. A mismatch, or a position that no longer
    exists, raises :class:`EntryCredentialRefused` (``stale``) and changes
    nothing.

    Two entries with the same username and label cannot be told apart this
    way. Nor can the operator tell them apart, since passwords are never shown,
    so the guard is as strong as the page itself — the most it can be without
    putting a password-derived value into the HTML.

    **Removal narrows what ADMZ tries; it never widens it**, so unlike an add
    it is allowed under the prompt-always posture. It cannot be undone from the
    page: ADMZ never shows the password, so only someone who knows it can add
    it back.

    The legacy pair lives in its own two settings rather than in the list, so
    removing it deletes ``default_password`` and then ``default_username`` —
    the password first, so an interrupted removal leaves a username with no
    password, which is read as no legacy entry at all.

    Returns ``{"username", "label", "legacy_pair"}`` for an audit row — never
    the password.
    """
    if fleet_settings.get(LEGACY_PASS_KEY):
        if position == 0:
            shown = fleet_settings.get(LEGACY_USER_KEY) or "root"
            if (shown, LEGACY_LABEL) != (username, label):
                raise _stale()
            fleet_settings.delete(LEGACY_PASS_KEY)
            fleet_settings.delete(LEGACY_USER_KEY)
            return {"username": shown, "label": LEGACY_LABEL, "legacy_pair": True}
        position -= 1
    existing = _stored_list()
    if not 0 <= position < len(existing):
        raise _stale()
    cred = existing[position]
    if (cred.username, cred.label) != (username, label):
        raise _stale()
    del existing[position]
    _write_list(existing)
    return {"username": cred.username, "label": cred.label, "legacy_pair": False}


def _stale() -> EntryCredentialRefused:
    return EntryCredentialRefused(
        REFUSED_STALE,
        "the entry list has changed since it was shown, so nothing was removed",
    )


def describe() -> dict:
    """The redacted state, for a settings page, an API response or a log.

    Reports what is STORED separately from what is in USE, because under
    :func:`prompt_always` those differ and an operator reading "0 credentials"
    would not know whether that is a policy or an empty box.

    ``in_use`` ends with ADMZ's break-glass root password when one is
    configured (ADR-0068), and ``break_glass_last`` says so — letting a page
    count the entry credentials apart from it, rather than report four tried
    "at most three". ``unreadable`` says a list is stored that cannot be
    decrypted: it reads as empty, and without the flag a page would say "none
    stored" about a list that exists.
    """
    raw = fleet_settings.get(SETTING_KEY)
    stored = _parse(raw)
    if fleet_settings.get(LEGACY_PASS_KEY):
        stored.insert(0, EntryCredential(
            fleet_settings.get(LEGACY_USER_KEY) or "root", "", LEGACY_LABEL))
    entries, break_glass = _attempts(warn=False)
    return {
        "prompt_always": prompt_always(),
        "max_stored": MAX_STORED,
        "max_attempts_per_pass": MAX_ATTEMPTS_PER_PASS,
        "stored": [c.redacted() for c in stored],
        "in_use": [c.redacted() for c in entries + break_glass],
        "break_glass_last": bool(break_glass),
        "unreadable": _unreadable(raw),
    }
