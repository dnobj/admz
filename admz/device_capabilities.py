"""Local device-capability knowledge — probe once, record, revalidate on change
(ADR-0063, #451).

One store of *device-truth*, written by ADMZ's own reads and consulted before
every probe. Unknown means probe. The atlas advises; it never suppresses a
probe (its negatives are demonstrably partial — the ADR carries the evidence).

    device_capabilities(device_id, probe_key, supported, firmware, source,
                        reason, fail_streak, observed_at, expires_at)
                        PRIMARY KEY (device_id, probe_key)

``probe_key`` is derived from the operation a facet reads — the catalog
``api_id`` for that operation's API where one exists, else the API name — so
no facet declares anything, and operations whose API has no ``api_id``
(``applications-list.cgi``, ``param.cgi``) are learnable too
(:func:`probe_key_for`).

A row is **stale** when its firmware differs from the device's current
firmware or it has expired. Keyed by firmware, a firmware upgrade makes every
row stale with no invalidation code; the next audit re-probes. Rows are
forgotten on a hardware rebind (ADR-0036: the row describes the *unit*, the
key is the *slot*) and purged with the device (#428 cascade).

The learner (:func:`learn`) classifies each extra-read outcome with the
**same-cycle readability control**: if the shared ``param.cgi`` dump succeeded
this cycle the device is readable now, and a specific operation failing is
evidence about that operation, not about the network.

    2xx                                          → present      (until fw change)
    404 / 405 / 501 / 400 / 410, or a 2xx error
        that literally says "no such method"     → absent       (7 days)
    401 / 403 / 5xx / parse / transport / timeout
        / any other 2xx application error,
        on a READABLE device                     → absent_unconfirmed
                                                   (24h · 2^(streak-1), cap 7d)
    anything, device NOT readable this cycle     → indeterminate (no row)

The third row is the one that matters: the T8516's failure is an
``httpx.ReadError`` — a transport error. "Transport → no record" would never
have learned the one device this was written for.

Same store discipline as every other per-device table (#254/#258): no I/O in
``__init__``, the path resolved at call time, schema ensured inside
``_connect``.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Classifications and their lifetimes
# ---------------------------------------------------------------------------

PRESENT = "present"
ABSENT = "absent"
ABSENT_UNCONFIRMED = "absent_unconfirmed"

ABSENT_TTL_SECONDS = 7 * 86400
UNCONFIRMED_BASE_TTL_SECONDS = 24 * 3600
UNCONFIRMED_MAX_TTL_SECONDS = 7 * 86400

#: Who wrote the row. ``audit`` = the drift audit / snapshot engine's own
#: reads (S1); ``discovery`` = the getApiList enumeration (S2).
SOURCE_AUDIT = "audit"
SOURCE_DISCOVERY = "discovery"

# HTTP statuses that say "this endpoint / method is not here" rather than
# "something went wrong reaching it". Every other 4xx and all 5xx are
# unconfirmed: the device answered, but we cannot say the API is absent.
_ABSENT_STATUS_CODES = frozenset({400, 404, 405, 410, 501})

# 2xx application-level error shapes that actually SAY the method/API is not
# there. Everything else a live endpoint returns as an error object — Axis
# "1100: Internal error" is the canonical transient — is a device having a
# bad moment, not proof of absence, and must take the short unconfirmed
# lease rather than a 7-day absent one (review of #454, MINOR-5).
_METHOD_ABSENT_MARKS = (
    "method not found",       # JSON-RPC -32601 text
    "-32601",
    "unknown method",
    "no such method",
    "not supported",          # "API version not supported" — can't serve it
    "unsupported method",
)

# Evidence strength when two operations on the same API disagree in one
# cycle: a 2xx proves the API exists; a 404 outranks a dropped connection.
_RANK = {PRESENT: 3, ABSENT: 2, ABSENT_UNCONFIRMED: 1}

_REASON_MAX = 200


def device_firmware(device_info: Optional[Dict[str, Any]]) -> str:
    """The firmware the device is believed to run, ``""`` when unknown.

    The registry stores the *observed* firmware as ``firmware_version``
    (health refresh, basicdeviceinfo); ``firmware`` is the manual / legacy
    field from the add-device form. Observed first — it is the one that
    tracks an upgrade. ``""`` is a real value: rows recorded under it go
    stale the moment the firmware becomes known.
    """
    if not device_info:
        return ""
    return str(
        device_info.get("firmware_version") or device_info.get("firmware") or ""
    ).strip()


def probe_key_for(catalog: Any, family: str, operation_id: str) -> str:
    """The key a capability row is stored under, derived from the operation.

    The catalog ``api_id`` of the operation's API when it declares one
    (``sip:getSIPAccounts`` → ``sip``, ``ntp.cgi:getNTPInfo`` → ``ntp``),
    else the API name — the part before the colon (``applications-list.cgi``,
    ``param.cgi``). Guarded: a test's ``FakeCatalog`` may lack
    ``get_api_metadata`` entirely.
    """
    api_name = operation_id.split(":", 1)[0]
    getter = getattr(catalog, "get_api_metadata", None)
    if getter is None:
        return api_name
    try:
        meta = getter(family, api_name)
    except Exception:  # noqa: BLE001 — the key must always resolve
        meta = None
    api_id = getattr(meta, "api_id", None) if meta is not None else None
    return str(api_id) if api_id else api_name


def classify(result: Any, *, device_readable: bool) -> Optional[str]:
    """Classify one extra-read outcome per the ADR-0063 table.

    ``result`` is an executor ``StepResult`` (``success``, ``status_code``,
    ``error``). Returns :data:`PRESENT`, :data:`ABSENT`,
    :data:`ABSENT_UNCONFIRMED`, or ``None`` — indeterminate, record nothing —
    when the device was not readable this cycle.
    """
    if getattr(result, "success", False):
        return PRESENT
    if not device_readable:
        return None
    status = getattr(result, "status_code", None)
    error = str(getattr(result, "error", "") or "")
    if status in _ABSENT_STATUS_CODES:
        return ABSENT
    if status is None:
        # No HTTP response at all: connect refused, timeout, dropped
        # connection, TLS failure. On a readable device this is evidence
        # about the operation — but unconfirmed, with a short lease.
        return ABSENT_UNCONFIRMED
    if status >= 400:
        # 401/403, 5xx, and every 4xx the absent set does not name.
        return ABSENT_UNCONFIRMED
    # 2xx with success=False: the endpoint answered and refused the call at
    # the application level — a JSON-RPC error object or a text error prefix.
    # Only shapes that literally say "no such method" are proof of absence;
    # a transient device-side error (Axis 1100 "Internal error") from an
    # endpoint the device HAS must not earn a 7-day absent lease.
    low = error.lower()
    if any(mark in low for mark in _METHOD_ABSENT_MARKS):
        return ABSENT
    return ABSENT_UNCONFIRMED


def expiry_for(classification: str, *, streak: int, now: float) -> Optional[float]:
    """When a row of ``classification`` stops being trusted (``None`` = until
    the firmware changes)."""
    if classification == PRESENT:
        return None
    if classification == ABSENT:
        return now + ABSENT_TTL_SECONDS
    ttl = min(
        UNCONFIRMED_BASE_TTL_SECONDS * (2 ** max(streak - 1, 0)),
        UNCONFIRMED_MAX_TTL_SECONDS,
    )
    return now + ttl


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS device_capabilities (
    device_id    TEXT    NOT NULL,
    probe_key    TEXT    NOT NULL,
    supported    INTEGER NOT NULL,
    firmware     TEXT    NOT NULL DEFAULT '',
    source       TEXT    NOT NULL DEFAULT 'audit',
    reason       TEXT    NOT NULL DEFAULT '',
    fail_streak  INTEGER NOT NULL DEFAULT 0,
    observed_at  REAL    NOT NULL,
    expires_at   REAL,
    PRIMARY KEY (device_id, probe_key)
);
"""


def _default_db_path():
    from admz.paths import db_path
    return db_path()


@dataclass
class CapabilityRow:
    device_id: str
    probe_key: str
    supported: bool
    firmware: str
    source: str
    reason: str
    fail_streak: int
    observed_at: float
    expires_at: Optional[float]

    @property
    def classification(self) -> str:
        if self.supported:
            return PRESENT
        return ABSENT_UNCONFIRMED if self.fail_streak > 0 else ABSENT

    def is_stale(self, firmware: str, now: float) -> bool:
        """Stale ⇔ recorded for a different firmware, or expired."""
        if self.firmware != (firmware or ""):
            return True
        return self.expires_at is not None and self.expires_at <= now

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["classification"] = self.classification
        return d


class DeviceCapabilityStore:
    """SQLite-backed per-device capability rows. Same file as every other
    per-device store; same call-time path discipline (#258)."""

    def __init__(self, db_path: Optional[str] = None):
        """No I/O here — this class backs a module-level singleton and anything
        done here happens at *import* (#254/#258)."""
        self._explicit_db_path = str(db_path) if db_path else None
        self._ready: set = set()
        self._ready_lock = threading.Lock()

    @property
    def _db_path(self) -> str:
        """Resolved at CALL time, never cached at construction (#258)."""
        return self._explicit_db_path or str(_default_db_path())

    def _connect(self) -> sqlite3.Connection:
        path = self._db_path
        if path not in self._ready:
            with self._ready_lock:
                if path not in self._ready:
                    from admz.paths import ensure_parent_dir

                    ensure_parent_dir(path)
                    self._create_schema(path)
                    self._ready.add(path)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _create_schema(self, path: str) -> None:
        try:
            conn = sqlite3.connect(path)
            try:
                conn.executescript(_SCHEMA)
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as exc:  # pragma: no cover - defensive
            logger.warning("DeviceCapabilityStore table creation failed: %s", exc)

    @staticmethod
    def _row(r: Tuple) -> CapabilityRow:
        return CapabilityRow(
            device_id=r[0], probe_key=r[1], supported=bool(r[2]),
            firmware=r[3] or "", source=r[4] or "", reason=r[5] or "",
            fail_streak=int(r[6] or 0), observed_at=float(r[7]),
            expires_at=float(r[8]) if r[8] is not None else None,
        )

    _SELECT = (
        "SELECT device_id, probe_key, supported, firmware, source, reason, "
        "fail_streak, observed_at, expires_at FROM device_capabilities "
    )

    def list(self, device_id: str) -> List[CapabilityRow]:
        """Every row for ``device_id``, stale or not (for inspection)."""
        conn = self._connect()
        try:
            rows = conn.execute(
                self._SELECT + "WHERE device_id=? ORDER BY probe_key",
                (device_id,),
            ).fetchall()
        finally:
            conn.close()
        return [self._row(r) for r in rows]

    def get(self, device_id: str, probe_key: str) -> Optional[CapabilityRow]:
        conn = self._connect()
        try:
            r = conn.execute(
                self._SELECT + "WHERE device_id=? AND probe_key=?",
                (device_id, probe_key),
            ).fetchone()
        finally:
            conn.close()
        return self._row(r) if r else None

    def view(
        self, device_id: str, firmware: str, now: Optional[float] = None
    ) -> Dict[str, CapabilityRow]:
        """The rows that may be *trusted* for a device running ``firmware``
        right now — non-stale only. Selection asks this; anything not in it
        is unknown, and unknown means probe."""
        now = time.time() if now is None else now
        return {
            row.probe_key: row
            for row in self.list(device_id)
            if not row.is_stale(firmware, now)
        }

    def record(
        self,
        device_id: str,
        probe_key: str,
        classification: str,
        *,
        firmware: str,
        source: str = SOURCE_AUDIT,
        reason: str = "",
        now: Optional[float] = None,
    ) -> CapabilityRow:
        """Upsert one row. The unconfirmed backoff streak continues only across
        consecutive unconfirmed observations *at the same firmware*; anything
        else resets it."""
        if classification not in _RANK:
            raise ValueError(f"unknown classification {classification!r}")
        now = time.time() if now is None else now
        firmware = firmware or ""
        previous = self.get(device_id, probe_key)
        streak = 0
        if classification == ABSENT_UNCONFIRMED:
            if (
                previous is not None
                and previous.fail_streak > 0
                and previous.firmware == firmware
            ):
                streak = previous.fail_streak + 1
            else:
                streak = 1
        row = CapabilityRow(
            device_id=device_id,
            probe_key=probe_key,
            supported=classification == PRESENT,
            firmware=firmware,
            source=source,
            reason=(reason or "")[:_REASON_MAX],
            fail_streak=streak,
            observed_at=now,
            expires_at=expiry_for(classification, streak=streak, now=now),
        )
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO device_capabilities "
                "(device_id, probe_key, supported, firmware, source, reason, "
                " fail_streak, observed_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(device_id, probe_key) DO UPDATE SET "
                "  supported   = excluded.supported, "
                "  firmware    = excluded.firmware, "
                "  source      = excluded.source, "
                "  reason      = excluded.reason, "
                "  fail_streak = excluded.fail_streak, "
                "  observed_at = excluded.observed_at, "
                "  expires_at  = excluded.expires_at",
                (
                    row.device_id, row.probe_key, int(row.supported),
                    row.firmware, row.source, row.reason, row.fail_streak,
                    row.observed_at, row.expires_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return row

    def forget(self, device_id: str) -> int:
        """Drop every row for ``device_id`` — a hardware rebind (ADR-0036): the
        rows described the old unit. Returns the number removed."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "DELETE FROM device_capabilities WHERE device_id=?", (device_id,)
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# The learner — a cycle's outcomes → rows
# ---------------------------------------------------------------------------

def learn(
    store: DeviceCapabilityStore,
    *,
    device_id: str,
    firmware: str,
    outcomes: Iterable[Tuple[str, Any]],
    device_readable: bool,
    source: str = SOURCE_AUDIT,
    now: Optional[float] = None,
) -> Dict[str, str]:
    """Classify one cycle's extra-read outcomes and record them.

    ``outcomes`` is ``(probe_key, StepResult)`` pairs — several operations may
    share a key (both SIP reads → ``sip``); they are merged per key before
    recording, strongest evidence winning (present > absent > unconfirmed).
    Returns ``{probe_key: classification}`` for what was recorded. Never
    raises: a learner failure must not fail the audit.
    """
    merged: Dict[str, Tuple[str, str]] = {}
    for probe_key, result in outcomes:
        cls = classify(result, device_readable=device_readable)
        if cls is None:
            continue
        reason = str(getattr(result, "error", "") or "") if cls != PRESENT else ""
        current = merged.get(probe_key)
        if current is None or _RANK[cls] > _RANK[current[0]]:
            merged[probe_key] = (cls, reason)
    recorded: Dict[str, str] = {}
    for probe_key, (cls, reason) in merged.items():
        try:
            store.record(
                device_id, probe_key, cls,
                firmware=firmware, source=source, reason=reason, now=now,
            )
            recorded[probe_key] = cls
        except Exception:  # noqa: BLE001 — must never break the audit
            logger.warning(
                "capability row not recorded for %s/%s", device_id, probe_key,
                exc_info=True,
            )
    return recorded


# Module-level singleton — same shape as drift_alerts.drift_alerts.
capability_store = DeviceCapabilityStore()
