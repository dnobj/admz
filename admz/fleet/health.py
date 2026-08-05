"""Background device health monitor.

Polls every registered device on a configurable interval and
maintains a single-row-per-device "current status" table in the
shared ADMZ SQLite DB. This is the answer to the user's "which
devices are online?" question — without operators having to fire
ad-hoc checks.

Design notes:

- **Current-state-only storage.** One row per device. We don't keep
  the full history here; that's what the audit log + future
  time-series store are for. Operators want "right now, which
  devices are reachable?" — that's a single-row read.
- **Single async loop.** No thread-per-device, no operator-defined
  schedules. The HealthMonitor wakes on a fixed interval, iterates
  the registry, and checks each device with bounded concurrency
  (uses the same fleet semaphore as snapshot to avoid hammering).
- **Two-tier probe.** If we have stored credentials for the
  device, call ``systemready.cgi:systemReady`` via the executor —
  that gives us uptime + bootid + auth proof. If not (or auth
  fails), fall back to a raw TCP connect against the device's host
  — at least we learn whether the IP is up.
- **Reachability ≠ API capability** (GH #138). "Is the host up?" and
  "can ADMZ speak its API?" are different questions and never share a
  verdict. ``unreachable`` means a genuine connect failure and nothing
  else; a device that answers but can't be parsed as VAPIX (a T85 PoE
  switch serving its HTML login page) is ``reachable_no_api``. The
  classification is always confirmed with a TCP connect rather than
  inferred from an error string.
- **Status reflects last successful probe, not running counters.**
  A device that was online 30 seconds ago and is online now has
  ``status=online``. ``last_seen_online`` advances each successful
  probe so operators can see "was online 2 minutes ago" for
  flapping devices.
- **Opt-in.** Defaults off via ``health_monitor_enabled`` fleet
  setting. Enabling it doesn't restart the server — the FastAPI
  lifespan checks at startup, and operators can also start/stop
  the monitor from the web UI.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import admz.fleet_settings as _fs_module

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tuning knobs (env + fleet-setting overrides)
# ---------------------------------------------------------------------------


_DEFAULT_INTERVAL_SECONDS = 60.0       # Poll every minute by default
_DEFAULT_TIMEOUT_SECONDS = 5.0         # Per-device check timeout
_DEFAULT_CONCURRENCY = 8               # Concurrent probes in flight

# Reachability vs. authentication: ``systemready`` answers 200 even with
# *invalid* credentials on some Axis firmware, so a 200 there proves the
# device is up but NOT that ADMZ's stored password is correct. To detect a
# wrong/stale password (status auth_failed, not a misleading "online") we
# follow up a successful systemready with one auth-required call.
SYSTEMREADY_OP = "systemready.cgi:systemReady"
AUTH_CHECK_OP = "basicdeviceinfo.cgi:getAllProperties"

# A 401 from ONE op is not proof of bad credentials (GH #149). The AXIS
# P8815-2 3D People Counter (fw 11.11.205) authenticates ``root``/digest
# perfectly on ``param.cgi`` and ``usergroup.cgi`` while ``basicdeviceinfo``'s
# *data* methods 401 — it is not a missing method (an invented method name
# answers 200 with a JSON error) and not the auth method, scheme, or API
# version. That device sat at ``auth_failed`` with 18,004 consecutive failures
# while being fully manageable.
#
# So a 401/403 from the auth-check op is corroborated with a second,
# independent auth-required op before we call the password bad. ``param.cgi``
# is the natural corroborator: already catalogued, cheap, read-only, and the
# exact "tiny authenticated read" that snapshot's ``probe_readable()`` already
# depends on (``admz/snapshot/engine.py``) — which is why drift already
# considered this device readable while health called it ``auth_failed``.
CORROBORATION_OP = "param.cgi:list"
CORROBORATION_PARAMS = {"group": "root.Brand"}

# Device-info key holding what we LEARNED about probing this device, in the
# same spirit as the executor's scheme/auth self-heal (``_persist_learned_auth``
# in ``admz/operations.py``). Deliberately a sibling of ``auth`` rather than a
# field inside it: ``auth`` means *transport auth profile*, this means "which
# auth-required op actually works here".
#
# It selects probe ORDER ONLY — it never skips verification. A marker that
# meant "trust this device without an auth check" would make a stale password
# on a marked device invisible, which is #149's own complaint inverted.
PROBE_MARKER_KEY = "health_probe"
_MARKER_OP_FIELD = "auth_check_op"


def _fs():
    return _fs_module.fleet_settings


def _verify_credentials_enabled() -> bool:
    """Whether the health probe confirms credentials with an auth-required
    call after systemready. Default on; set ``health_verify_credentials`` to
    a falsey value to skip it (e.g. fleets of intentionally low-privilege
    accounts that legitimately can't read basicdeviceinfo)."""
    raw = _fs().get("health_verify_credentials")
    if raw is None:
        return True
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def _resolve_interval_seconds() -> float:
    raw = _fs().get("health_check_interval_seconds")
    if raw is None:
        raw = os.getenv("ADMZ_HEALTH_INTERVAL_SECONDS")
    if not raw:
        return _DEFAULT_INTERVAL_SECONDS
    try:
        v = float(raw)
    except ValueError:
        logger.warning("Invalid health-check interval %r; using %s", raw, _DEFAULT_INTERVAL_SECONDS)
        return _DEFAULT_INTERVAL_SECONDS
    return max(5.0, v)  # Floor at 5s — anything faster is hostile


def _resolve_timeout_seconds() -> float:
    raw = _fs().get("health_check_timeout_seconds")
    if raw is None:
        raw = os.getenv("ADMZ_HEALTH_TIMEOUT_SECONDS")
    if not raw:
        return _DEFAULT_TIMEOUT_SECONDS
    try:
        v = float(raw)
    except ValueError:
        return _DEFAULT_TIMEOUT_SECONDS
    return max(1.0, min(60.0, v))


def _is_enabled() -> bool:
    return _fs().get("health_monitor_enabled") == "true"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class DeviceHealthStatus(str, Enum):
    """Coarse-grained reachability state for a device.

    **Reachability and API capability are separate questions** (GH #138).
    ``unreachable`` answers only the first one and means exactly what it says:
    the host did not answer at all. A device that answers HTTP but doesn't
    speak VAPIX — a T85 PoE switch serving its HTML login page, say — is
    ``reachable_no_api``, not ``unreachable``: it is up, ADMZ just can't
    manage it.
    """

    ONLINE = "online"
    UNREACHABLE = "unreachable"     # no TCP connect
    AUTH_FAILED = "auth_failed"     # TCP up, VAPIX rejected creds
    NEEDS_SETUP = "needs_setup"     # reachable but factory-defaulted (needsetup=yes)
    # TCP up + the host answered, but the answer wasn't usable VAPIX (unparsable
    # body, wrong content type, an unexpected-but-valid HTTP status). "Up, but
    # ADMZ can't manage it" — an attention state, never a network failure.
    REACHABLE_NO_API = "reachable_no_api"
    UNKNOWN = "unknown"             # never checked


# Statuses that are a *settled* answer rather than a failed probe. These reset
# ``consecutive_failures`` instead of incrementing it: a device that simply
# doesn't speak VAPIX is in a stable state, and counting each sweep as a
# failure is what produced the meaningless five-figure counters of GH #138.
_STABLE_STATUSES = frozenset(
    {DeviceHealthStatus.ONLINE, DeviceHealthStatus.REACHABLE_NO_API}
)


@dataclass
class DeviceHealthRecord:
    """Current-state row for one device."""

    device_id: str
    status: DeviceHealthStatus
    last_check: Optional[float] = None        # unix ts
    last_seen_online: Optional[float] = None  # unix ts of last ONLINE result
    latency_ms: Optional[int] = None          # most recent probe round-trip
    consecutive_failures: int = 0
    last_error: str = ""
    # Bonus fields we get from systemReady when authenticated probe works:
    uptime_seconds: Optional[int] = None
    bootid: Optional[str] = None
    # SD-card presence from disks-list.cgi (authenticated probes only):
    # the device's own status word ("disconnected" = empty slot, "OK" =
    # card working, "no_slot" = device has no SD slot) + card size in kB.
    # None = unknown (probe didn't run / failed) — the sweep then keeps
    # the previous value instead of blanking it.
    sd_status: Optional[str] = None
    sd_total_kb: Optional[int] = None
    # Transient: model/serial/firmware lifted from the basicdeviceinfo
    # credential-check response (when it ran). Not persisted to the health
    # store — the sweep flushes it to the device registry instead.
    observed_facts: Optional[Dict[str, str]] = None
    # Transient, same seam as ``observed_facts``: what the credential check
    # learned about *how* to auth-check this device (GH #149) — i.e. which
    # auth-required op actually works. ``probe_device`` has no registry
    # handle, so the sweep is what flushes it to the device record.
    learned_probe: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "status": self.status.value,
            "last_check": self.last_check,
            "last_seen_online": self.last_seen_online,
            "latency_ms": self.latency_ms,
            "consecutive_failures": self.consecutive_failures,
            "last_error": self.last_error,
            "uptime_seconds": self.uptime_seconds,
            "bootid": self.bootid,
            "sd_status": self.sd_status,
            "sd_total_kb": self.sd_total_kb,
        }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


_SCHEMA = """
CREATE TABLE IF NOT EXISTS device_health (
    device_id              TEXT PRIMARY KEY,
    status                 TEXT NOT NULL,
    last_check             REAL,
    last_seen_online       REAL,
    latency_ms             INTEGER,
    consecutive_failures   INTEGER NOT NULL DEFAULT 0,
    last_error             TEXT NOT NULL DEFAULT '',
    uptime_seconds         INTEGER,
    bootid                 TEXT,
    sd_status              TEXT,
    sd_total_kb            INTEGER
);
"""

# Columns added after the table first shipped; applied via ALTER TABLE for
# databases created before them (CREATE TABLE IF NOT EXISTS won't).
_MIGRATION_COLUMNS = (
    ("sd_status", "TEXT"),
    ("sd_total_kb", "INTEGER"),
)


def _default_db_path() -> Path:
    from admz.paths import db_path
    return db_path()


class DeviceHealthStore:
    """SQLite-backed current-state-only store for device health."""

    def __init__(self, db_path: Optional[str] = None):
        """No I/O here -- constructing a store must not touch the filesystem,
        because this class backs a module-level singleton and anything done
        here happens at *import* (#254/#258)."""
        self._explicit_db_path = str(db_path) if db_path else None
        self._ready: set = set()
        self._ready_lock = threading.Lock()

    @property
    def _db_path(self) -> str:
        """Resolved at CALL time, not cached at construction (#258).

        Caching in ``__init__`` is what froze the path: an ``ADMZ_HOME`` or
        ``ADMZ_DB_PATH`` set afterwards was ignored for the life of the
        process. Stays a ``str`` -- tests read this attribute and hand it
        straight to ``sqlite3.connect()``.
        """
        return self._explicit_db_path or str(_default_db_path())

    def _connect(self) -> sqlite3.Connection:
        path = self._db_path
        if path not in self._ready:  # fast path: no lock once warm
            with self._ready_lock:
                if path not in self._ready:  # double-checked
                    from admz.paths import ensure_parent_dir

                    ensure_parent_dir(path)
                    self._create_schema(path)
                    self._ready.add(path)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _create_schema(self, path: str) -> None:
        """Open our own connection -- via ``_connect`` this would recurse.

        ``_ready`` is keyed by path rather than a boolean, so a rebind runs
        the schema and its migrations against the new file instead of
        assuming the previous one's columns exist.

        Migrates the _MIGRATION_COLUMNS list onto device_health, each ALTER
        swallowing OperationalError when the column is already present.
        Swallowed exactly as before.
        """
        try:
            conn = sqlite3.connect(path)
            try:
                conn.executescript(_SCHEMA)
                for col, coltype in _MIGRATION_COLUMNS:
                    try:
                        conn.execute(
                            f"ALTER TABLE device_health ADD COLUMN {col} {coltype}"
                        )
                    except sqlite3.OperationalError:
                        pass  # already there (fresh table or prior migration)
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as exc:  # pragma: no cover - defensive
            logger.warning("DeviceHealthStore table creation failed: %s", exc)

    def _ensure_table(self) -> None:
        """Retained for callers that reach for it by name; ensuring now
        happens inside :meth:`_connect`."""
        self._connect().close()
    def upsert(self, record: DeviceHealthRecord) -> None:
        """Insert or update one device's row."""
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO device_health "
                "(device_id, status, last_check, last_seen_online, latency_ms, "
                " consecutive_failures, last_error, uptime_seconds, bootid, "
                " sd_status, sd_total_kb) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(device_id) DO UPDATE SET "
                "  status               = excluded.status, "
                "  last_check           = excluded.last_check, "
                "  last_seen_online     = excluded.last_seen_online, "
                "  latency_ms           = excluded.latency_ms, "
                "  consecutive_failures = excluded.consecutive_failures, "
                "  last_error           = excluded.last_error, "
                "  uptime_seconds       = excluded.uptime_seconds, "
                "  bootid               = excluded.bootid, "
                "  sd_status            = excluded.sd_status, "
                "  sd_total_kb          = excluded.sd_total_kb",
                (
                    record.device_id,
                    record.status.value,
                    record.last_check,
                    record.last_seen_online,
                    record.latency_ms,
                    record.consecutive_failures,
                    record.last_error,
                    record.uptime_seconds,
                    record.bootid,
                    record.sd_status,
                    record.sd_total_kb,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get(self, device_id: str) -> Optional[DeviceHealthRecord]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT device_id, status, last_check, last_seen_online, "
                "       latency_ms, consecutive_failures, last_error, "
                "       uptime_seconds, bootid, sd_status, sd_total_kb "
                "FROM device_health WHERE device_id=?",
                (device_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return DeviceHealthRecord(
            device_id=row[0],
            status=DeviceHealthStatus(row[1]),
            last_check=row[2],
            last_seen_online=row[3],
            latency_ms=row[4],
            consecutive_failures=row[5],
            last_error=row[6],
            uptime_seconds=row[7],
            bootid=row[8],
            sd_status=row[9],
            sd_total_kb=row[10],
        )

    def list_all(self) -> List[DeviceHealthRecord]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT device_id, status, last_check, last_seen_online, "
                "       latency_ms, consecutive_failures, last_error, "
                "       uptime_seconds, bootid, sd_status, sd_total_kb "
                "FROM device_health ORDER BY device_id"
            ).fetchall()
        finally:
            conn.close()
        return [
            DeviceHealthRecord(
                device_id=r[0],
                status=DeviceHealthStatus(r[1]),
                last_check=r[2],
                last_seen_online=r[3],
                latency_ms=r[4],
                consecutive_failures=r[5],
                last_error=r[6],
                uptime_seconds=r[7],
                bootid=r[8],
                sd_status=r[9],
                sd_total_kb=r[10],
            )
            for r in rows
        ]

    def delete(self, device_id: str) -> bool:
        """Drop a device's health row (e.g. after device removal)."""
        conn = self._connect()
        try:
            cur = conn.execute(
                "DELETE FROM device_health WHERE device_id=?", (device_id,)
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


# Module-level singleton.
device_health_store = DeviceHealthStore()


# ---------------------------------------------------------------------------
# Per-device probe
# ---------------------------------------------------------------------------


def _probe_port(device_info: Dict[str, Any]) -> int:
    """The port the reachability probe should knock on for this device.

    Mirrors how the VAPIX executor picks its port (``admz/executor/vapix.py``):
    an explicit ``port`` wins, otherwise the device's learned scheme decides
    (443 for https, 80 otherwise). Matters because newer Axis firmware is
    HTTPS-only — knocking on 80 there would call a live device unreachable.
    Devices ADMZ has never talked to keep the historical default of 80.
    """
    port = device_info.get("port")
    if port:
        try:
            return int(port)
        except (TypeError, ValueError):
            pass
    auth_info = device_info.get("auth_info")
    scheme = auth_info.get("scheme") if isinstance(auth_info, dict) else None
    return 443 if scheme == "https" else 80


async def _tcp_probe(host: str, port: int, timeout: float) -> Optional[int]:
    """Open a TCP connection to ``host:port`` with ``timeout`` seconds.

    Returns the round-trip latency in ms on success, None on failure.
    Doesn't write anything to the socket — just verifies the device
    accepts the connection. Cheap and reliable as a "the IP is up"
    signal.
    """
    started = time.monotonic()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
    except (asyncio.TimeoutError, OSError):
        return None
    try:
        elapsed_ms = int((time.monotonic() - started) * 1000)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:  # pragma: no cover — defensive
            pass
    return elapsed_ms


# Sentinels for "the op isn't in the catalog" vs "the call blew up". Callers
# must tell these apart: a missing op is a config gap (conclusions unchanged
# from before #149), an errored call is transient (prove nothing, don't flap).
_OP_MISSING = object()
_OP_ERRORED = object()


def _preferred_auth_op(device_info: Dict[str, Any]) -> str:
    """Which auth-required op to try FIRST on this device.

    Defaults to :data:`AUTH_CHECK_OP`. A learned marker (GH #149) can promote
    the corroborator instead, so a device whose ``basicdeviceinfo`` is
    restricted pays two calls per sweep rather than three. Only the two known
    op ids are honoured — a marker holding anything else is ignored rather
    than trusted, so a corrupt device record can't redirect the auth check.
    """
    marker = device_info.get(PROBE_MARKER_KEY)
    if isinstance(marker, dict):
        op_id = marker.get(_MARKER_OP_FIELD)
        if op_id in (AUTH_CHECK_OP, CORROBORATION_OP):
            return str(op_id)
    return AUTH_CHECK_OP


async def _run_auth_op(
    *,
    catalog: Any,
    executor: Any,
    device_info: Dict[str, Any],
    device_id: str,
    credentials: Dict[str, Any],
    timeout_seconds: float,
    op_id: str,
) -> Any:
    """Execute one auth-required op, returning its result or a sentinel."""
    try:
        op = catalog.get_operation("vapix", op_id)
    except Exception:
        op = None
    if op is None:
        return _OP_MISSING
    params = dict(CORROBORATION_PARAMS) if op_id == CORROBORATION_OP else {}
    try:
        return await asyncio.wait_for(
            executor.execute(
                op.to_executor_dict(),
                {**device_info, "device_id": device_id},
                credentials,
                params,
            ),
            timeout=timeout_seconds + 2,
        )
    except Exception:
        return _OP_ERRORED


def _is_authenticated_2xx(result: Any) -> bool:
    sc = getattr(result, "status_code", None)
    return bool(
        getattr(result, "success", False)
        and sc is not None
        and 200 <= int(sc) < 300
    )


def _facts_from(result: Any) -> Dict[str, str]:
    """Identity facts from a basicdeviceinfo body. Empty on anything else."""
    try:
        from admz.device_facts import extract_device_facts
        return extract_device_facts(getattr(result, "parsed_data", None))
    except Exception:
        return {}


async def _corroborate_rejection(
    *,
    catalog: Any,
    executor: Any,
    device_info: Dict[str, Any],
    device_id: str,
    credentials: Dict[str, Any],
    timeout_seconds: float,
    refused_op: str,
) -> "tuple[Optional[bool], Dict[str, str], Optional[Dict[str, str]]]":
    """One auth-required op refused the credentials — ask a second, independent
    one before declaring the password bad (GH #149).

    Returns the same ``(creds_ok, facts, learned)`` triple as
    :func:`_confirm_credentials`.
    """
    other_op = CORROBORATION_OP if refused_op != CORROBORATION_OP else AUTH_CHECK_OP
    result = await _run_auth_op(
        catalog=catalog, executor=executor, device_info=device_info,
        device_id=device_id, credentials=credentials,
        timeout_seconds=timeout_seconds, op_id=other_op,
    )

    if result is _OP_MISSING:
        # Can't corroborate at all. Keep the pre-#149 verdict: a false alarm is
        # safer than a missed one — a genuinely stale password must not read as
        # "online" merely because the corroborator isn't in the catalog.
        logger.warning(
            "health: %s refused credentials for %s and the corroborating op %s "
            "is not in the catalog — falling back to single-op judgement",
            refused_op, device_id, other_op,
        )
        return False, {}, None

    if result is _OP_ERRORED:
        return None, {}, None  # transient — proves nothing, don't flap

    sc = getattr(result, "status_code", None)
    if sc in (401, 403):
        return False, {}, None  # both refused — genuinely bad credentials

    if _is_authenticated_2xx(result):
        # A real authenticated 2xx from an auth-required op. This deliberately
        # satisfies ``strict=True`` (onboarding SAVES a password on it): strict
        # exists because the LENIENT path accepted *non-auth* answers as proof,
        # and this is not that — it is genuine proof, just from the other op.
        facts = _facts_from(result) if other_op == AUTH_CHECK_OP else {}
        return True, facts, {_MARKER_OP_FIELD: other_op}

    # Answered some other way (unparsable body, odd status): proves nothing
    # either direction, so don't move the status.
    return None, {}, None


async def _confirm_credentials(
    *,
    catalog: Any,
    executor: Any,
    device_info: Dict[str, Any],
    device_id: str,
    credentials: Dict[str, Any],
    timeout_seconds: float,
    strict: bool = False,
) -> "tuple[Optional[bool], Dict[str, str], Optional[Dict[str, str]]]":
    """Confirm the stored credentials actually authenticate.

    Calls an auth-required op (``basicdeviceinfo`` by default). Returns a
    ``(creds_ok, facts, learned)`` triple where ``creds_ok`` is:
      - ``False`` when the device explicitly rejects the credentials — which
        since GH #149 means **two independent auth-required ops** refused
        them, not one,
      - ``True`` when they're accepted (2xx) or — in the default lenient
        mode — the device answers some other way (a non-auth error doesn't
        implicate the password; right for health, which must not flap a
        device to auth_failed over a connection hiccup),
      - ``None`` when we can't tell (op missing, transient error) — caller
        should not flip status on ``None``.

    ``strict=True`` inverts the benefit of the doubt: only a genuine
    authenticated 2xx counts as ``True``; any non-auth failure is ``None``
    (unknown). Onboarding uses this — it SAVES credentials on ``True``, and
    a connection-level error must never be mistaken for proof that a
    password works (a fresh device with no learned scheme/auth profile can
    easily produce one on the first touch).

    ``facts`` carries model/serial/firmware lifted from the same response on
    the success path (empty otherwise), so the monitor can self-populate the
    device record without a second probe. It is empty when the corroborating
    ``param.cgi`` read is what proved the credentials — that body is a
    parameter dump, not basicdeviceinfo's shape. Empty facts never *erase* a
    stored value: both flush sites skip falsy entries.

    ``learned`` is a probe marker to persist on the device record (or ``None``)
    — see :data:`PROBE_MARKER_KEY`. Emitted only when the corroborator is what
    proved the credentials, so the common path never writes to the registry.
    """
    primary_op = _preferred_auth_op(device_info)
    result = await _run_auth_op(
        catalog=catalog, executor=executor, device_info=device_info,
        device_id=device_id, credentials=credentials,
        timeout_seconds=timeout_seconds, op_id=primary_op,
    )
    if result is _OP_MISSING or result is _OP_ERRORED:
        return None, {}, None

    sc = getattr(result, "status_code", None)
    if sc in (401, 403):
        # Don't believe a single op (GH #149) — corroborate before condemning.
        return await _corroborate_rejection(
            catalog=catalog, executor=executor, device_info=device_info,
            device_id=device_id, credentials=credentials,
            timeout_seconds=timeout_seconds, refused_op=primary_op,
        )

    if strict and not _is_authenticated_2xx(result):
        return None, {}, None  # didn't prove anything — not good enough to save

    # Accepted (or non-auth answer): mine the body for identity facts.
    facts = _facts_from(result) if primary_op == AUTH_CHECK_OP else {}
    return True, facts, None


def _persist_probe_marker(
    registry: Any,
    device_id: str,
    device_info: Dict[str, Any],
    learned: Dict[str, str],
) -> None:
    """Merge a learned probe marker into the device record (GH #149).

    Best-effort and delta-only, mirroring ``_persist_learned_auth`` in
    ``admz/operations.py``: a backend without ``update_device_info`` just
    keeps re-learning per sweep, which costs one extra CGI and nothing else.
    """
    current = device_info.get(PROBE_MARKER_KEY)
    merged = dict(current) if isinstance(current, dict) else {}
    merged.update(learned)
    if merged == current:
        return
    try:
        registry.update_device_info(device_id, {PROBE_MARKER_KEY: merged})
        logger.info(
            "health: learned auth-check op for %s: %s", device_id, dict(learned)
        )
    except Exception:  # noqa: BLE001 - best effort
        logger.debug(
            "health: could not persist probe marker for %s", device_id,
            exc_info=True,
        )


SD_PROBE_OP = "disks-list.cgi:list-disks"


async def _probe_sd_card(
    *,
    catalog: Any,
    executor: Any,
    device_info: Dict[str, Any],
    device_id: str,
    credentials: Dict[str, Any],
    timeout_seconds: float,
) -> "tuple[Optional[str], Optional[int]]":
    """SD-card presence via ``disks-list.cgi`` (authoritative status attr).

    Returns ``(status, total_kb)``; ``(None, None)`` on any failure — the
    sweep treats that as *unknown* and keeps the previous stored value.
    Cheap read-only CGI, same order of cost as the basicdeviceinfo
    credential check that already runs each sweep.
    """
    try:
        op = catalog.get_operation("vapix", SD_PROBE_OP)
    except Exception:
        op = None
    if op is None:
        return None, None
    try:
        result = await asyncio.wait_for(
            executor.execute(
                op.to_executor_dict(),
                {**device_info, "device_id": device_id},
                credentials,
                {"diskid": "all"},
            ),
            timeout=timeout_seconds + 2,
        )
    except Exception:
        return None, None
    if not getattr(result, "success", False):
        return None, None
    try:
        from admz.device_facts import extract_sd_card
        return extract_sd_card(getattr(result, "parsed_data", None))
    except Exception:
        return None, None


#: The two shapes a VAPIX StepResult uses to report an actual 401, anchored at
#: the start of the message (``executor/vapix.py:1112`` and the generic
#: ``f"HTTP {status_code}: {body[:500]}"`` at ``:1123``).
_REPORTED_401 = re.compile(r"^(?:HTTP 401\b|Authentication failed \(401\))")


def _reports_401(error: Any) -> bool:
    """Does this StepResult error actually say the device answered 401?

    Anchored on purpose. This used to be ``"401" in str(error)``, and `error`
    carries **up to 500 characters of the device's own response body** for any
    status >= 400 (``executor/vapix.py:1123``) — so a 500 whose body happened to
    contain ``401`` anywhere (a request id, a byte count, an error code) was
    reported as AUTH_FAILED. On a factory-defaulted unit that is precisely the
    #149/#154 misclassification this path exists to prevent: *needs setup* read
    as *your credentials are wrong*.

    The loose form also had **no true-positive value here**. Every genuine 401
    from the VAPIX executor sets ``status_code=401`` (``vapix.py:1105-1114``),
    which the caller's first clause already catches; an AST sweep of every
    ``StepResult`` in ``admz/`` whose error mentions 401 found exactly one, and
    it sets ``status_code``. So the substring branch could only ever fire on a
    false positive.

    It was also what made ``test_needsetup_marks_needs_setup_not_auth_failed``
    flaky (#291): the test's mock never set ``error``, so ``str()`` of the
    auto-created child mock embedded ``id='<address>'`` — and ~1 run in 110,
    that address contains ``401``. Anchoring makes the mock's repr unmatchable
    whatever its address, so the flake cannot recur even if a mock is unfaithful
    again.
    """
    return bool(error) and bool(_REPORTED_401.match(str(error)))


async def probe_device(
    *,
    device_id: str,
    device_info: Dict[str, Any],
    credentials: Optional[Dict[str, Any]],
    catalog: Any = None,
    executor: Any = None,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> DeviceHealthRecord:
    """Check one device and return a fresh health record.

    Two-tier probe:
      1. If we have credentials AND the catalog + executor are
         available, call ``systemready.cgi:systemReady`` via the
         executor. Success → ONLINE with uptime/bootid populated.
         Auth failure (401) → AUTH_FAILED. Connect failure →
         UNREACHABLE. Any *other* failure (unparsable body, wrong
         content type, unexpected status) is a statement about the
         device's API, not its reachability — so it falls through to
         a TCP connect and becomes REACHABLE_NO_API if the host
         answers, UNREACHABLE only if it doesn't.
      2. Otherwise (or as a fallback if the catalog isn't loaded),
         just do a TCP connect probe against the device's host on its
         effective port (see :func:`_probe_port`). Connect OK →
         ONLINE (without uptime info). Connect fail → UNREACHABLE.
    """
    host = device_info.get("host")
    now = time.time()

    if not host:
        return DeviceHealthRecord(
            device_id=device_id,
            status=DeviceHealthStatus.UNREACHABLE,
            last_check=now,
            last_error="no host configured",
            consecutive_failures=1,
        )

    # ---- Tier 1: authenticated VAPIX systemReady ----
    if (
        credentials
        and credentials.get("password")
        and catalog is not None
        and executor is not None
    ):
        try:
            op = catalog.get_operation("vapix", "systemready.cgi:systemReady")
        except Exception:
            op = None
        if op is not None:
            started = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    executor.execute(
                        op.to_executor_dict(),
                        {**device_info, "device_id": device_id},
                        credentials,
                        {"timeout": "10"},  # device-side wait in seconds
                    ),
                    timeout=timeout_seconds + 2,  # +2 for the executor wrapper
                )
            except asyncio.TimeoutError:
                return DeviceHealthRecord(
                    device_id=device_id,
                    status=DeviceHealthStatus.UNREACHABLE,
                    last_check=now,
                    last_error=f"systemReady timed out after {timeout_seconds}s",
                    consecutive_failures=1,
                )
            except Exception as exc:
                return DeviceHealthRecord(
                    device_id=device_id,
                    status=DeviceHealthStatus.UNREACHABLE,
                    last_check=now,
                    last_error=f"executor error: {exc}",
                    consecutive_failures=1,
                )
            elapsed_ms = int((time.monotonic() - started) * 1000)

            status_code = getattr(result, "status_code", None)
            if status_code == 401 or _reports_401(getattr(result, "error", None)):
                return DeviceHealthRecord(
                    device_id=device_id,
                    status=DeviceHealthStatus.AUTH_FAILED,
                    last_check=now,
                    latency_ms=elapsed_ms,
                    last_error="HTTP 401 from device",
                    consecutive_failures=1,
                )

            if not getattr(result, "success", False):
                err = getattr(result, "error", "") or "unknown error"
                # Distinguish connect failure (UNREACHABLE) from other
                # failure modes. httpx connect errors typically have
                # "connect" or "timeout" in the message.
                lower = err.lower()
                if (
                    "timeout" in lower
                    or "connect" in lower
                    or "refused" in lower
                    or "unreachable" in lower
                ):
                    return DeviceHealthRecord(
                        device_id=device_id,
                        status=DeviceHealthStatus.UNREACHABLE,
                        last_check=now,
                        last_error=err[:200],
                        consecutive_failures=1,
                    )
                # Anything else — an unparsable body, an unexpected content
                # type, an unexpected-but-valid HTTP status — says nothing
                # about reachability, only about ADMZ's ability to speak this
                # device's API. Don't infer a verdict from the error string:
                # confirm with a TCP connect and classify on that evidence.
                tcp_ms = await _tcp_probe(
                    host, _probe_port(device_info), timeout_seconds
                )
                if tcp_ms is None:
                    return DeviceHealthRecord(
                        device_id=device_id,
                        status=DeviceHealthStatus.UNREACHABLE,
                        last_check=now,
                        last_error=err[:200],
                        consecutive_failures=1,
                    )
                return DeviceHealthRecord(
                    device_id=device_id,
                    status=DeviceHealthStatus.REACHABLE_NO_API,
                    last_check=now,
                    # The host answered, so the reachability clock advances —
                    # this asserts nothing about the device beyond "it is up".
                    last_seen_online=now,
                    latency_ms=elapsed_ms,
                    consecutive_failures=0,
                    last_error=err[:200],
                )

            # Success — pull uptime/bootid/needsetup from the parsed result.
            data = getattr(result, "parsed_data", None) or {}
            needsetup = False
            if isinstance(data, dict):
                inner = data.get("data") if "data" in data else data
                if isinstance(inner, dict):
                    uptime_seconds = inner.get("uptime")
                    bootid = inner.get("bootid")
                    needsetup = str(inner.get("needsetup", "")).lower() == "yes"
                else:
                    uptime_seconds = None
                    bootid = None
            else:
                uptime_seconds = None
                bootid = None

            uptime_int = int(uptime_seconds) if uptime_seconds is not None else None
            bootid_str = str(bootid) if bootid is not None else None

            # A factory-defaulted device answers systemready (reachable) but has
            # no account yet — needsetup=yes is a definitive, auth-free signal,
            # so it's "needs setup", NOT "auth failed" (a recoverable state).
            if needsetup:
                return DeviceHealthRecord(
                    device_id=device_id,
                    status=DeviceHealthStatus.NEEDS_SETUP,
                    last_check=now,
                    last_seen_online=now,  # reachable, just not provisioned yet
                    latency_ms=elapsed_ms,
                    consecutive_failures=0,
                    last_error="factory-defaulted (needsetup=yes) — not provisioned",
                    uptime_seconds=uptime_int,
                    bootid=bootid_str,
                )

            # systemready 200 proves reachability but NOT valid credentials on
            # some firmware. Confirm with an auth-required call so a wrong/stale
            # password surfaces as auth_failed instead of a misleading "online".
            observed: Dict[str, str] = {}
            learned_probe: Optional[Dict[str, str]] = None
            if _verify_credentials_enabled():
                creds_ok, observed, learned_probe = await _confirm_credentials(
                    catalog=catalog, executor=executor, device_info=device_info,
                    device_id=device_id, credentials=credentials,
                    timeout_seconds=timeout_seconds,
                )
                if creds_ok is False:
                    return DeviceHealthRecord(
                        device_id=device_id,
                        status=DeviceHealthStatus.AUTH_FAILED,
                        last_check=now,
                        last_seen_online=now,  # it IS reachable, just not authable
                        latency_ms=elapsed_ms,
                        consecutive_failures=1,
                        # Two independent auth-required ops refused these
                        # credentials (GH #149) — say so, because "401 on
                        # basicdeviceinfo" alone was never the proof it claimed.
                        last_error=(
                            "credentials rejected — both "
                            f"{AUTH_CHECK_OP} and {CORROBORATION_OP} refused them"
                        ),
                        uptime_seconds=uptime_int,
                        bootid=bootid_str,
                    )

            # Same opportunistic pattern as the facts refresh: while we're
            # authenticated anyway, note whether an SD card is actually
            # inserted (disks-list status — root.Storage params can't tell).
            sd_status, sd_total_kb = await _probe_sd_card(
                catalog=catalog, executor=executor, device_info=device_info,
                device_id=device_id, credentials=credentials,
                timeout_seconds=timeout_seconds,
            )

            return DeviceHealthRecord(
                device_id=device_id,
                status=DeviceHealthStatus.ONLINE,
                last_check=now,
                last_seen_online=now,
                latency_ms=elapsed_ms,
                consecutive_failures=0,
                uptime_seconds=uptime_int,
                bootid=bootid_str,
                sd_status=sd_status,
                sd_total_kb=sd_total_kb,
                observed_facts=observed or None,
                learned_probe=learned_probe or None,
            )

    # ---- Tier 2: TCP connect probe ----
    port = _probe_port(device_info)
    elapsed_ms = await _tcp_probe(host, port, timeout_seconds)
    if elapsed_ms is not None:
        return DeviceHealthRecord(
            device_id=device_id,
            status=DeviceHealthStatus.ONLINE,
            last_check=now,
            last_seen_online=now,
            latency_ms=elapsed_ms,
            consecutive_failures=0,
            last_error="",
        )

    return DeviceHealthRecord(
        device_id=device_id,
        status=DeviceHealthStatus.UNREACHABLE,
        last_check=now,
        last_error=f"TCP connect to {host}:{port} failed within {timeout_seconds}s",
        consecutive_failures=1,
    )


# ---------------------------------------------------------------------------
# Background monitor
# ---------------------------------------------------------------------------


class HealthMonitor:
    """Async background loop that polls every device on an interval.

    Started on FastAPI/MCP startup (when the
    ``health_monitor_enabled`` fleet flag is true), stopped on
    shutdown. One instance per process — shared between the MCP
    and REST surfaces just like SnapshotScheduler.

    Bounded concurrency via an asyncio.Semaphore (capacity matches
    SnapshotEngine.fleet_concurrency so we don't pick a number that
    fights with snapshot sweeps).
    """

    def __init__(
        self,
        *,
        registry,
        catalog=None,
        executors: Optional[Dict[str, Any]] = None,
        store: Optional[DeviceHealthStore] = None,
        concurrency: int = _DEFAULT_CONCURRENCY,
    ):
        self.registry = registry
        self.catalog = catalog
        self.executors = executors or {}
        self.store = store or device_health_store
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._concurrency = concurrency

    # ----- Lifecycle -----

    async def start(self) -> None:
        """Spin up the background loop if the fleet flag is enabled.

        No-op when disabled — operators have to flip
        ``health_monitor_enabled=true`` to start it. Restart-safe:
        calling start() twice doesn't spawn two tasks.
        """
        if self._running:
            return
        if not _is_enabled():
            logger.info(
                "Device health monitor disabled (health_monitor_enabled fleet flag)."
            )
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        interval = _resolve_interval_seconds()
        logger.info(
            "Device health monitor started (interval=%.0fs, concurrency=%d)",
            interval,
            self._concurrency,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    # ----- Loop -----

    async def _loop(self) -> None:
        """Poll, sleep, repeat. Re-reads the interval each cycle so
        operators can change it without restarting."""
        try:
            # Run one sweep immediately on start so the first read
            # of the table isn't full of "unknown" rows.
            await self.sweep_once()
            while self._running:
                interval = _resolve_interval_seconds()
                await asyncio.sleep(interval)
                if not self._running:
                    break
                await self.sweep_once()
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception("Health monitor loop crashed: %s", exc)

    async def sweep_once(self) -> int:
        """Probe every device once. Returns the number of devices checked.

        Public so operators (or tests) can trigger a sweep
        on-demand without waiting for the next interval.
        """
        # The sweep is also when one-shot detection tasks get evaluated —
        # expire stale ones up front so they can't fire late.
        try:
            from admz.tasks.store import tasks_store
            tasks_store.expire_stale()
        except Exception:  # noqa: BLE001
            pass

        try:
            devices = self.registry.list_devices()
        except Exception as exc:
            logger.warning("Health sweep: list_devices failed: %s", exc)
            return 0

        if not devices:
            return 0

        timeout = _resolve_timeout_seconds()
        sem = asyncio.Semaphore(self._concurrency)

        async def _check(device: Dict[str, Any]) -> None:
            device_id = device.get("device_id")
            if not device_id:
                return
            async with sem:
                # Try to fetch credentials; missing creds is fine —
                # we fall back to TCP probe.
                creds: Optional[Dict[str, Any]] = None
                try:
                    creds = self.registry.get_credentials(device_id)
                except Exception:
                    creds = None

                executor = self.executors.get("vapix") if self.executors else None
                try:
                    record = await probe_device(
                        device_id=device_id,
                        device_info=device,
                        credentials=creds,
                        catalog=self.catalog,
                        executor=executor,
                        timeout_seconds=timeout,
                    )
                except Exception as exc:
                    record = DeviceHealthRecord(
                        device_id=device_id,
                        status=DeviceHealthStatus.UNREACHABLE,
                        last_check=time.time(),
                        last_error=f"probe crashed: {exc}",
                        consecutive_failures=1,
                    )

                # Preserve last_seen_online and bump failure counter
                # if this probe failed.
                prev = self.store.get(device_id)
                if prev is not None:
                    if record.status not in _STABLE_STATUSES:
                        record.consecutive_failures = prev.consecutive_failures + 1
                    # ``last_seen_online`` is the REACHABILITY clock: every
                    # probe that proved the host answered stamps it (online,
                    # auth_failed, needs_setup, reachable_no_api). Only carry
                    # the previous value forward when this probe proved
                    # nothing — never overwrite a fresh stamp with a stale one.
                    if record.last_seen_online is None:
                        record.last_seen_online = prev.last_seen_online
                    if record.sd_status is None:
                        # SD probe didn't run or failed this sweep — keep the
                        # last known value rather than flapping to unknown.
                        record.sd_status = prev.sd_status
                        record.sd_total_kb = prev.sd_total_kb

                self.store.upsert(record)

                # Opportunistic fact refresh: the credential check already
                # fetched basicdeviceinfo, so flush any model/serial/firmware
                # that changed (or was missing) to the device registry — no
                # extra probe. Only writes on an actual delta to avoid churn.
                if record.observed_facts:
                    changed = {
                        k: v for k, v in record.observed_facts.items()
                        if v and str(device.get(k) or "") != str(v)
                    }
                    if changed:
                        try:
                            self.registry.update_device_info(device_id, changed)
                        except Exception:
                            logger.debug(
                                "health: fact refresh skipped for %s",
                                device_id, exc_info=True,
                            )

                # Same seam, one level up (GH #149): persist what the credential
                # check learned about *how* to auth-check this device, so a
                # model whose basicdeviceinfo is restricted stops paying for a
                # corroborating call every sweep. probe_device has no registry
                # handle; the sweep does.
                if record.learned_probe:
                    _persist_probe_marker(
                        self.registry, device_id, device, record.learned_probe
                    )

                # Fire any pre-authorized deferred actions whose trigger this
                # device's new state now satisfies (e.g. came back needsetup ->
                # re-provision). Launched async so a slow recovery action can't
                # stall the sweep; a no-op unless something is pending.
                await self._fire_pending(device_id, record.status.value)

        await asyncio.gather(*(_check(d) for d in devices))
        return len(devices)

    async def _fire_pending(self, device_id: str, status_value: str) -> None:
        """Evaluate + launch any pre-authorized detection tasks for this device
        whose event its new state now satisfies. Atomic claim → fire-once;
        launched async so it can't stall the sweep."""
        try:
            from admz.tasks.store import event_for_status, tasks_store
            ev = event_for_status(status_value)
            if ev is None:
                return
            for task in tasks_store.claim_for_event(device_id, ev):
                asyncio.create_task(self._run_pending(task))
        except Exception:  # noqa: BLE001
            logger.debug(
                "detection-task evaluation failed for %s", device_id, exc_info=True
            )

    async def _run_pending(self, task) -> None:
        """Execute one claimed (pre-authorized) detection task + audit it."""
        from types import SimpleNamespace

        from admz.audit import record_event
        from admz.tasks.handlers import execute_task_action
        from admz.tasks.store import tasks_store

        pid = task.id
        did = task.device_id
        principal = SimpleNamespace(
            name=task.approved_by or "deferred",
            source="deferred-trigger",
        )
        try:
            await execute_task_action(task)
            tasks_store.mark(pid, "done")
            record_event(
                principal, "deferred_action_fired", resource=f"device:{did}",
                details={"id": pid, "action": task.action_type, "trigger": task.event},
            )
        except Exception as exc:  # noqa: BLE001
            tasks_store.mark(pid, "failed", str(exc)[:300])
            logger.warning("detection task %s for %s failed: %s", pid, did, exc)
            try:
                record_event(
                    principal, "deferred_action_failed", resource=f"device:{did}",
                    success=False, error_message=str(exc)[:300],
                    details={"id": pid, "action": task.action_type},
                )
            except Exception:  # noqa: BLE001
                pass
