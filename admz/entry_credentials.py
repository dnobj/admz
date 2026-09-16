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
factory-defaulted device (FR-CRED-007; under ADR-0068 ``root`` gets the fleet
root password instead), so it is purely an entry credential; retiring it
into the list is still a separate decision with its own blast radius — every
install's effective list is its legacy pair — and this module only stops it
being the *whole* answer.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from admz.fleet_settings import fleet_settings

logger = logging.getLogger(__name__)

#: One encrypted fleet setting holding the JSON list.
SETTING_KEY = "entry_credentials"

#: Legacy single pair — an entry credential only: nothing writes it to a device
#: (FR-CRED-007). Read here as the first entry so an existing install keeps
#: working with no migration step and no window where nothing resolves.
LEGACY_USER_KEY = "default_username"
LEGACY_PASS_KEY = "default_password"
#: The label the legacy pair is listed and tried under.
LEGACY_LABEL = "fleet default"
#: The label ADMZ's own attempt with the fleet root password is listed under —
#: the name an operator sets it by on the Settings page (FR-CRED-014).
FLEET_ROOT_LABEL = "fleet root password"

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
#: pass unbounded. Each wrong attempt costs two credentialed operations (the
#: primary auth op and its corroborator, GH #149/#150). The fleet root
#: password is one more attempt, beside the bound rather than inside it
#: (ADR-0068, :func:`_attempts`): the loop is at most (1 + 3) x 2 = 8
#: operations, up to 16 sends at the wire when the executor re-sends on a
#: method-relearn. A pass is the loop plus the stored-credential check that
#: precedes it (``onboarding.py`` step 1), and a stale stored credential is
#: corroborated the same way — so one pass is at most 10 operations /
#: 20 sends. A pair the stored-credential check saw REFUSED is skipped when
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

#: The settings the page's view of the list is built from: a write to any of
#: them can move a row to a different position.
_REVISION_KEYS = (SETTING_KEY, LEGACY_PASS_KEY, LEGACY_USER_KEY)

#: The MAC key for :func:`list_revision` — random per process, never stored.
#: ADMZ serves its web UI from one process, so the only cost is that a page
#: rendered before a restart has its Remove refused as stale; a reload fixes it.
_REVISION_MAC_KEY = secrets.token_bytes(32)


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
    #: True only on ADMZ's own attempt with the fleet root password
    #: (:func:`_fleet_root_attempt`). A stored entry never carries it, whatever
    #: its label says, so a caller tells the two apart without reading text an
    #: operator can type.
    fleet_root: bool = False

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
    """True when a stored list exists that cannot be read in full.

    ``raw`` is what ``fleet_settings.get`` returned for the list. The list is
    unreadable when ``raw`` is ``None`` only because the stored value cannot be
    decrypted, or when it decrypts to something other than a JSON list of
    complete username/password pairs. A reader is right to treat both as
    (partly) empty; :func:`_stored_list` says why a writer must not.
    """
    if raw is None:
        return fleet_settings.is_stored(SETTING_KEY)
    if not raw.strip():
        return False
    try:
        data = json.loads(raw)
    except ValueError:
        return True
    return not isinstance(data, list) or len(_parse(raw)) != len(data)


def _stored_list() -> List[EntryCredential]:
    """The stored list, read for a WRITE: refused unless it can be read in full.

    Every write rewrites the whole list from what it read. An undecryptable list
    would therefore be replaced by the one new entry — when
    ``setting_crypto.read_stored`` promises an unreadable value is left alone so
    that restoring the right key recovers it — and a list holding anything
    :func:`_parse` skips (not JSON, not a list, a half-written pair) would lose
    it silently.
    """
    raw = fleet_settings.get(SETTING_KEY)
    if _unreadable(raw):
        raise EntryCredentialRefused(
            REFUSED_UNREADABLE,
            "the stored entry list cannot be read in full (it cannot be decrypted, "
            "or it is not a list of complete username/password pairs), so it cannot "
            "be changed without losing part of it; restore the key file it was "
            f"written with, or correct it with `python -m admz settings set {SETTING_KEY}`",
        )
    return _parse(raw)


def _write_list(creds: List[EntryCredential]) -> None:
    fleet_settings.set(SETTING_KEY, json.dumps([
        {"username": c.username, "password": c.password, "label": c.label}
        for c in creds
    ]))


def list_revision() -> str:
    """A token that changes whenever the list, or the legacy pair, is written.

    Each Remove button on the settings page carries the token the page was
    rendered with, and :func:`remove_entry_credential` acts only while it still
    matches — so a removal applies to exactly the list the operator saw. A
    position alone cannot promise that. Rows often look identical (the username
    defaults to ``root`` and the label is optional), so a form resubmitted by a
    browser reload, a second tab or another writer would otherwise remove a
    different credential that happens to sit where the shown one was.

    It is an HMAC of the three settings' values *as stored*: a secret contributes
    its ciphertext, whose random IV changes the token on every write, even of an
    identical list. Keyed, because a secret can still be at legacy plaintext, and
    an unkeyed digest in a page would let anyone who can view the page test
    guesses against it.
    """
    digest = fleet_settings.stored_digest(*_REVISION_KEYS)
    return hmac.new(_REVISION_MAC_KEY, digest, hashlib.sha256).hexdigest()[:32]


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


def _fleet_root_attempt() -> List[EntryCredential]:
    """ADMZ's own attempt with the fleet root password (ADR-0068), or nothing
    when none is configured.

    Not an entry credential — nobody stored it in the list. It is the value
    ADMZ itself writes to ``root`` on every device it provisions, and without
    it a pass that failed partway would be unretryable: root would hold a
    password ADMZ *has* and :func:`attempt_order` would not offer it.

    **Tried first** — the owner's call on 2026-09-16; ADR-0068 had put it last.
    It is the one password ADMZ knows is on every device it provisioned, and
    the one an operator is most likely to have set by hand as well, so the
    commonest re-onboard gets in on the first attempt rather than after every
    entry credential has failed. It takes no entry credential's place: the
    list is bounded separately (:func:`_attempts`). Nor does the order widen
    what a hostile device can collect — one that refuses everything is sent
    every attempt either way. What it changes is that a device an entry
    credential would have opened first refuses one root attempt, which the
    lockout measurement (FR-CRED-013, 2026-09-09) makes affordable: no
    cumulative lockout on the device tested, only a 20/s rate throttle ADMZ
    runs some 400x under.

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

    password = fleet_settings.get(FLEET_ROOT_PASSWORD_KEY)
    if not password:
        return []
    return [EntryCredential("root", password, FLEET_ROOT_LABEL, fleet_root=True)]


def _attempts(*, warn: bool) -> Tuple[List[EntryCredential], List[EntryCredential]]:
    """One pass's parts: ADMZ's fleet root attempt (empty when none is
    configured), and the bounded entry credentials.

    The one place a pass is composed. :func:`attempt_order` joins the two with
    :func:`_in_order` and :func:`describe` reports them, so what is tried and
    what the settings page says is tried cannot drift; they are returned apart
    so the page can say "after the fleet root password, top to bottom" rather
    than "4 (at most 3)".
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
    # Beside the slice, not inside it: the fleet root password is ADMZ's own
    # way back into a device it provisioned, so a full entry list must not be
    # able to crowd it out — and it takes no entry's place either.
    return _fleet_root_attempt(), creds


def _in_order(fleet_root: List[EntryCredential],
              entries: List[EntryCredential]) -> List[EntryCredential]:
    """The pass as it is asked: the fleet root attempt, then each entry.

    An entry holding the fleet root pair is left out — the first attempt has
    already put that exact question to the device. The slice happened before
    this, so leaving one out only shortens a pass; it never pulls an entry
    stored past the bound into it.
    """
    if not fleet_root:
        return list(entries)
    same = (fleet_root[0].username, fleet_root[0].password)
    return fleet_root + [c for c in entries if (c.username, c.password) != same]


def attempt_order(*, warn: bool = True) -> List[EntryCredential]:
    """What one onboarding pass should try: ADMZ's fleet root password first,
    when one is configured (ADR-0068, :func:`_fleet_root_attempt`), then at
    most :data:`MAX_ATTEMPTS_PER_PASS` entry credentials.

    Composed in one place (:func:`_attempts`): the onboarding loop iterates
    this and :func:`describe` reports the same attempts as ``in_use``, so what
    is tried and what the settings page says is tried cannot drift. The entry
    credentials keep their stored order (the legacy pair first). Reordering
    them most-recently-successful-first is ADR-0064 slice F — not yet built;
    the lockout measurement that gated it was made on 2026-09-09 — and it must
    sort *before* the slice, or success history could never pull a tail entry
    into the tried set.

    ``warn=False`` is for readers (:func:`describe`, the settings page): the
    WARNING about a list stored over the bound belongs to the pass that
    truncates it, not to every page view. The message carries counts only,
    never a credential.
    """
    return _in_order(*_attempts(warn=warn))


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
    be read in full (:func:`_stored_list`).
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


def remove_entry_credential(position: int, *, revision: str) -> Dict[str, object]:
    """Remove one stored entry credential — from exactly the list the page showed.

    ``position`` is the entry's index in :func:`describe`'s ``stored`` list, the
    order the settings page shows (the legacy pair first, when set).
    ``revision`` is the :func:`list_revision` the page was rendered with. If
    anything has written the list or the legacy pair since — a second tab, the
    CLI writer, a promotion, or this same form resubmitted by a browser reload —
    the token no longer matches, nothing is removed, and
    :class:`EntryCredentialRefused` (``stale``) is raised. A position that does
    not exist is refused the same way; only a hand-made request sends one.

    **Removal narrows what ADMZ tries; it never widens it**, so unlike an add it
    is allowed under the prompt-always posture. It cannot be undone from the
    page: ADMZ never shows the password, so only someone who knows it can add
    it back.

    The legacy pair lives in its own two settings rather than in the list, so
    removing it deletes ``default_password`` and then ``default_username`` —
    the password first, so an interrupted removal leaves a username with no
    password, which is read as no legacy entry at all.

    Returns the removed row's ``{"username", "label", "legacy_pair"}``, as read
    from storage, for an audit row — never the password.
    """
    if not hmac.compare_digest(str(revision).encode("utf-8"),
                               list_revision().encode("ascii")):
        raise _stale()
    if fleet_settings.get(LEGACY_PASS_KEY):
        if position == 0:
            username = fleet_settings.get(LEGACY_USER_KEY) or "root"
            fleet_settings.delete(LEGACY_PASS_KEY)
            fleet_settings.delete(LEGACY_USER_KEY)
            return {"username": username, "label": LEGACY_LABEL, "legacy_pair": True}
        position -= 1
    existing = _stored_list()
    if not 0 <= position < len(existing):
        raise _stale()
    removed = existing.pop(position)
    _write_list(existing)
    return {"username": removed.username, "label": removed.label, "legacy_pair": False}


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

    ``stored_tried`` runs alongside ``stored``: whether each stored entry is one
    a pass actually tries. It is worked out from the credentials, not their
    redacted names, because an exact duplicate is tried only once — of two
    identical-looking rows only the first is live, and matching on username and
    label would mark the wrong one tried and invite removing the live one.

    ``stored_tried`` is about the entries within the bound: an entry holding
    the fleet root pair counts as tried, because that pair is put to the device
    (first), and under :func:`prompt_always` nothing stored counts, even then.

    ``in_use`` starts with ADMZ's fleet root password when one is configured
    (ADR-0068), and ``fleet_root_first`` says so — letting a page count the
    entry credentials apart from it, rather than report four tried "at most
    three". ``unreadable`` says a stored list exists that cannot be
    read in full; it reads as (partly) empty, and without the flag a page would
    say "none stored" about a list that exists. ``revision`` is
    :func:`list_revision`, for a page's Remove buttons.
    """
    raw = fleet_settings.get(SETTING_KEY)
    stored = _parse(raw)
    legacy_pass = fleet_settings.get(LEGACY_PASS_KEY)
    if legacy_pass:
        stored.insert(0, EntryCredential(
            fleet_settings.get(LEGACY_USER_KEY) or "root", legacy_pass, LEGACY_LABEL))
    fleet_root, entries = _attempts(warn=False)
    tried = {(c.username, c.password) for c in entries}
    seen = set()
    stored_tried = []
    for cred in stored:
        pair = (cred.username, cred.password)
        stored_tried.append(pair in tried and pair not in seen)
        seen.add(pair)
    return {
        "prompt_always": prompt_always(),
        "max_stored": MAX_STORED,
        "max_attempts_per_pass": MAX_ATTEMPTS_PER_PASS,
        "stored": [c.redacted() for c in stored],
        "stored_tried": stored_tried,
        "in_use": [c.redacted() for c in _in_order(fleet_root, entries)],
        "fleet_root_first": bool(fleet_root),
        "unreadable": _unreadable(raw),
        # Last, after every read above: a read can migrate a legacy plaintext
        # secret to ciphertext, and the token has to describe the state a
        # Remove will find when it comes back.
        "revision": list_revision(),
    }
