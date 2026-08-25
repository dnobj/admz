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
        # Serialized surfaces carry the TRI-STATE, not the raw storage bool:
        # an ``absent_unconfirmed`` row stores ``supported=0`` (it must not be
        # trusted as present) but MEANS "could not verify" — rendering it as
        # ``false`` says "the device lacks it", which is the conflation the
        # #454/#457 reviews both flagged. Selection code keeps reading the
        # dataclass attribute; only serialization softens.
        if self.classification == ABSENT_UNCONFIRMED:
            d["supported"] = None
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


# ---------------------------------------------------------------------------
# S2 (#452): the full enumeration, the firmware event, and the cadence
# ---------------------------------------------------------------------------

#: The one op the survey runs. Through the EXECUTOR — not atlas
#: ``build_snapshot``, which raise_for_status()es on basicdeviceinfo and
#: forces https, so it cannot reach a ``limited_api`` device (the T8516).
SURVEY_OPERATION_ID = "apidiscovery.cgi:getApiList"

#: Fleet setting: seconds between scheduled capability surveys. The default
#: is 30 days — the survey is a safety net; the audit's own reads (S1) and
#: the firmware-change trigger do the day-to-day learning.
SURVEY_INTERVAL_KEY = "capability_survey_interval_seconds"
SURVEY_INTERVAL_DEFAULT = 30 * 86400

#: The singleton schedule task id (mirrors the survey/drift_audit shape).
SURVEY_SCHEDULE_ID = "capability-survey"

#: Detection-task action type (registered in admz/tasks/handlers.py).
SURVEY_ACTION_TYPE = "capability_survey"


def _id_mapper() -> Any:
    """The atlas CapabilitiesLoader, built once per process (its YAML map is
    static data; #455 review measured ~1 ms per fresh construction, which a
    95-API survey would pay 95 times). ``None`` when unavailable."""
    global _ID_MAPPER
    if _ID_MAPPER is _UNSET:
        try:
            import axis_api_atlas
            from axis_api_atlas.capabilities.loader import CapabilitiesLoader

            loader = CapabilitiesLoader(axis_api_atlas.default_data_path())
            loader.get_api_id_map()  # parse now — fail here, loudly, not per id
            _ID_MAPPER = loader
        except Exception:  # noqa: BLE001
            # Identity mapping still yields truthful rows under the device's
            # own names, but every MAPPED id (fwmgr→firmware-manager) stops
            # lining up with audit-written rows — "a positive clears an
            # absent row" quietly breaks for those. Say so once, loudly.
            logger.error(
                "atlas api-id map unavailable — device-reported ids will be "
                "recorded unmapped; mapped ids (e.g. fwmgr) will not clear "
                "their absent rows", exc_info=True,
            )
            _ID_MAPPER = None
    return _ID_MAPPER


_UNSET = object()
_ID_MAPPER: Any = _UNSET


def _device_id_to_catalog(device_reported_id: str) -> str:
    """Map a device-reported API id to the catalog's api_id (the probe key).
    Identity when the atlas (or its map) is unavailable."""
    mapper = _id_mapper()
    if mapper is None:
        return str(device_reported_id)
    try:
        return mapper.device_id_to_catalog_api_id(str(device_reported_id))
    except Exception:  # noqa: BLE001
        return str(device_reported_id)


async def run_capability_survey(
    *,
    device_id: str,
    registry: Any,
    catalog: Any,
    executors: Any,
    store: Optional[DeviceCapabilityStore] = None,
    source: str = SOURCE_DISCOVERY,
) -> Dict[str, Any]:
    """Enumerate one device's APIs via its own ``getApiList`` and record the
    result as PRESENT rows — **positives only, never negatives** (FR-KNW-012):
    getApiList is legacy-only, so an API missing from its answer proves
    nothing — recording absence from it would recreate the partial-snapshot
    problem locally. A positive overwrites (clears) an ``absent`` row.
    """
    from admz import operations

    store = store if store is not None else capability_store
    try:
        result = await operations.run_execution_tail(
            device_id=device_id,
            operation_id=SURVEY_OPERATION_ID,
            family="vapix",
            params={},
            catalog=catalog,
            registry=registry,
            executors=executors,
        )
    except Exception as exc:  # noqa: BLE001 — op missing / no executor / no device
        return {"device_id": device_id, "success": False, "error": str(exc)}
    if not getattr(result, "success", False):
        return {
            "device_id": device_id, "success": False,
            "error": str(getattr(result, "error", "") or "getApiList failed"),
        }

    entries = result.parsed_data
    if isinstance(entries, dict):  # tolerate an unstripped envelope
        if isinstance(entries.get("data"), dict) and "apiList" in entries["data"]:
            entries = entries["data"]["apiList"]
        else:
            entries = entries.get("apiList")
    if not isinstance(entries, list):
        return {
            "device_id": device_id, "success": False,
            "error": f"unexpected getApiList payload: {type(entries).__name__}",
        }

    firmware = device_firmware(registry.get_device_info(device_id))
    recorded: List[str] = []
    for entry in entries:
        reported = (entry or {}).get("id") if isinstance(entry, dict) else None
        if not reported:
            continue
        key = _device_id_to_catalog(reported)
        try:
            store.record(
                device_id, key, PRESENT,
                firmware=firmware, source=source,
                reason=f"getApiList reported {reported!r}",
            )
            recorded.append(key)
        except Exception:  # noqa: BLE001
            logger.warning(
                "capability positive not recorded for %s/%s", device_id, key,
                exc_info=True,
            )
    return {
        "device_id": device_id, "success": True,
        "apis": sorted(recorded), "recorded": len(recorded),
    }


def enqueue_capability_survey(
    device_id: str, *, reason: str, approved_by: str = "system"
) -> Optional[str]:
    """Queue a one-shot capability survey for ``device_id`` as an
    ``on_online`` detection task — it fires from the health sweep the next
    time the device is confirmed reachable+authenticated, which is exactly
    when a survey can succeed. Deduped: a device with a pending survey task
    is not queued twice. Never raises."""
    try:
        from admz.tasks.store import EVENT_ONLINE, tasks_store

        pending = [
            t for t in tasks_store.list_active_for(device_id)
            if t.action_type == SURVEY_ACTION_TYPE
        ]
        if pending:
            return pending[0].id
        return tasks_store.create_detection(
            device_id=device_id,
            event=EVENT_ONLINE,
            action_type=SURVEY_ACTION_TYPE,
            approved_by=approved_by,
            description=f"Capability survey — {reason}",
        )
    except Exception:  # noqa: BLE001 — queueing is bookkeeping, never fatal
        logger.warning(
            "capability survey not enqueued for %s", device_id, exc_info=True
        )
        return None


def note_firmware(device_id: str, prev: str, new: str) -> Optional[str]:
    """The firmware delta both observers (health sweep, engine dump-lift)
    already compute and used to discard (FR-KNW-013). ``prev`` non-empty and
    different → ``device.firmware_changed`` audit row + a capability survey
    enqueued (the API surface may have changed with it). First sight
    (``prev`` empty) → ``device.firmware_observed`` only: a new device's
    None→X is not a change, and onboarding owns its first survey. Returns
    the audit action recorded, or None. Never raises."""
    prev = (prev or "").strip()
    new = (new or "").strip()
    if not new or prev == new:
        return None
    action = "device.firmware_changed" if prev else "device.firmware_observed"
    try:
        from types import SimpleNamespace

        from admz.audit import record_event

        record_event(
            SimpleNamespace(name="system", source="firmware-observer"),
            action,
            resource=f"device:{device_id}",
            details={"previous": prev, "current": new},
        )
    except Exception:  # noqa: BLE001 — the audit row must not break a sweep
        logger.warning("firmware event not audited for %s", device_id, exc_info=True)
    if action == "device.firmware_changed":
        enqueue_capability_survey(
            device_id,
            reason=f"firmware changed {prev} → {new}",
            approved_by="system:firmware-change",
        )
    return action


def ensure_capability_survey_schedule(tasks_store: Any, fleet_settings: Any) -> None:
    """Seed/sync the recurring fleet-wide survey from the
    ``capability_survey_interval_seconds`` fleet setting (default 30 days).

    Runs at every app build, so the setting is live-on-restart (#455 review,
    MINOR-1 — "consulted exactly once, ever" was a trap: a registered setting
    that silently does nothing). Semantics:

    * task absent  → created at the setting's interval (``0`` = opted out,
      nothing created). Note a DELETED task therefore comes back on restart —
      the setting, not deletion, is the opt-out authority; pause sticks.
    * task present → the interval follows the setting when they differ;
      ``0`` force-disables. The ``enabled`` flag is otherwise untouched —
      an operator's pause is theirs and survives restarts and setting edits.
    """
    try:
        raw = fleet_settings.get(SURVEY_INTERVAL_KEY)
        try:
            interval = int(raw) if raw not in (None, "") else SURVEY_INTERVAL_DEFAULT
        except (TypeError, ValueError):
            interval = SURVEY_INTERVAL_DEFAULT
        task = tasks_store.get(SURVEY_SCHEDULE_ID)
        if task is None:
            if interval <= 0:
                return  # opted out of the cadence
            tasks_store.create_schedule(
                task_id=SURVEY_SCHEDULE_ID,
                description="Capability survey (fleet-wide API enumeration)",
                interval_seconds=interval,
                action_type=SURVEY_ACTION_TYPE,
            )
            return
        if interval <= 0:
            if task.enabled:
                tasks_store.update(SURVEY_SCHEDULE_ID, enabled=False)
            return
        if task.interval_seconds != interval:
            tasks_store.update(SURVEY_SCHEDULE_ID, interval_seconds=interval)
    except Exception:  # noqa: BLE001 — startup seeding must never block boot
        logger.warning("capability survey schedule not synced", exc_info=True)


# Module-level singleton — same shape as drift_alerts.drift_alerts.
capability_store = DeviceCapabilityStore()
