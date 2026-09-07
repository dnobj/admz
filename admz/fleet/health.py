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
from dataclasses import dataclass, field, replace as _dc_replace
from enum import Enum
from pathlib import Path
from typing import NamedTuple, Any, Dict, List, Optional

import admz.fleet_settings as _fs_module
from admz.exceptions import AccountNotFoundError, DeviceNotFoundError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tuning knobs (env + fleet-setting overrides)
# ---------------------------------------------------------------------------


_DEFAULT_INTERVAL_SECONDS = 60.0       # Poll every minute by default
_DEFAULT_TIMEOUT_SECONDS = 5.0         # Per-device check timeout
_DEFAULT_CONCURRENCY = 8               # Concurrent probes in flight
# Ceiling on the #469 escalating hold (ADR-0065). A CHOSEN number, not a
# measured one: the lockout behaviour ADR-0061 asked about has never been
# measured, and ADR-0064 decision 7 still owns that. 30 min settles a
# condemned device at roughly 120 failed authentications a day instead of
# 4,300. 0 disables the hold.
_DEFAULT_AUTH_HOLD_MAX_SECONDS = 1800.0

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

#: The executor's own reachability verdicts (``executor/vapix.py``): a
#: connect failure or a timeout is already a statement about the host, so the
#: health probe may take it at face value. Anchored on PREFIXES (GH #461): the
#: substring rule this replaces matched ``"connect"`` inside ``"disconnected"``
#: — so a ``RemoteProtocolError`` from a device that drops unknown JSON-RPC
#: posts was filed UNREACHABLE before the legacy read could prove it readable,
#: and the #458 capability record could never be taught. Anything that is not
#: one of these takes the evidence path (TCP probe → legacy read), which
#: reaches the same UNREACHABLE verdict for a genuinely dead host anyway.
_UNREACHABLE_PREFIXES = ("Connection failed:", "Request timed out")
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


def _resolve_auth_hold_max_seconds() -> float:
    """Ceiling on the #469 hold. 0 disables it; 24 h is the upper clamp."""
    raw = _fs().get("health_auth_hold_max_seconds")
    if raw is None:
        raw = os.getenv("ADMZ_HEALTH_AUTH_HOLD_MAX_SECONDS")
    if raw is None or raw == "":
        return _DEFAULT_AUTH_HOLD_MAX_SECONDS
    try:
        v = float(raw)
    except ValueError:
        logger.warning(
            "Invalid auth-hold ceiling %r; using %s", raw, _DEFAULT_AUTH_HOLD_MAX_SECONDS
        )
        return _DEFAULT_AUTH_HOLD_MAX_SECONDS
    return max(0.0, min(24 * 3600.0, v))


def _is_enabled() -> bool:
    return _fs().get("health_monitor_enabled") == "true"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class DeviceHealthStatus(str, Enum):
    """Coarse-grained reachability state for a device.

    **Reachability and API capability are separate questions** (GH #138).
    ``unreachable`` answers only the first one and means exactly what it says:
    the host did not answer at all.

    **API capability is not binary either** (GH #357). The original wording
    here used a T85 PoE switch as the example of ``reachable_no_api`` — and
    was wrong about that exact device. A T8516 does not serve the JSON-RPC
    surface the health probe uses, but it answers ``param.cgi`` perfectly:
    ADMZ reads its configuration into four facets and tracks drift against a
    baseline on every audit cycle. Calling that "ADMZ can't manage it" while
    committing its config is not defensible, and it parked the device in the
    attention bucket permanently — a status that by design never escalates
    (see ``_STABLE_STATUSES``) and never clears is a device that can no longer
    signal anything. So the three states are:

    * ``online`` — the full API answers.
    * ``limited_api`` — up, and a **managed read succeeds**, but the JSON-RPC
      surface does not answer. ADMZ can read and track this device; an
      operator asking "can I push arbitrary config to it?" still deserves the
      honest no, which is why this is not folded into ``online``.
    * ``reachable_no_api`` — up, and **no** managed read succeeds. The genuine
      "cannot manage it" case, and the only one of the three that wants
      attention.
    """

    ONLINE = "online"
    UNREACHABLE = "unreachable"     # no TCP connect
    AUTH_FAILED = "auth_failed"     # TCP up, VAPIX rejected creds
    NEEDS_SETUP = "needs_setup"     # reachable but factory-defaulted (needsetup=yes)
    # TCP up, the device is provisioned (not needsetup), and ADMZ holds no
    # usable stored credential for it. Nothing was refused — ADMZ never had a
    # way in. Settled, and an attention state (ADR-0064 / FR-HLT-011): until
    # it existed this device read `online` on every surface, for hours.
    NO_CREDENTIALS = "no_credentials"
    # TCP up, the JSON-RPC probe didn't answer usefully, but an authenticated
    # legacy-CGI read DID. Manageable, just not over the surface we probed.
    LIMITED_API = "limited_api"
    # TCP up + the host answered, but nothing ADMZ can read did — not the
    # JSON-RPC probe and not the legacy-CGI fallback. "Up, but ADMZ can't
    # manage it" — an attention state, never a network failure.
    REACHABLE_NO_API = "reachable_no_api"
    UNKNOWN = "unknown"             # never checked


# Statuses that are a *settled* answer rather than a failed probe. These reset
# ``consecutive_failures`` instead of incrementing it: a device that simply
# doesn't speak VAPIX is in a stable state, and counting each sweep as a
# failure is what produced the meaningless five-figure counters of GH #138.
#
# NOTE (GH #357): "settled" and "needs attention" are two DIFFERENT questions
# asked of this enum, and both answers were right in isolation — which is how
# the T8516 ended up parked. This set answers "settled?"; the UI's ``bucket``
# answers "needs attention?". Do not make one match the other; give a status
# the right answer to each.
_STABLE_STATUSES = frozenset(
    {
        DeviceHealthStatus.ONLINE,
        DeviceHealthStatus.LIMITED_API,
        DeviceHealthStatus.REACHABLE_NO_API,
        # Settled AND needs attention (ADR-0064) — the two questions answered
        # separately, as the note above asks.
        DeviceHealthStatus.NO_CREDENTIALS,
    }
)


#: Statuses that ANSWER the credential question, so the #469 hold is
#: forgotten: two prove an authentication succeeded, and two say the
#: question no longer applies. Deliberately excludes ``unreachable`` and
#: ``reachable_no_api`` — they answer nothing, and letting a flapping device
#: reset the escalation is how the burn comes back.
_AUTH_HOLD_CLEARING_STATUSES = frozenset(
    {
        DeviceHealthStatus.ONLINE,
        DeviceHealthStatus.LIMITED_API,
        DeviceHealthStatus.NEEDS_SETUP,
        DeviceHealthStatus.NO_CREDENTIALS,
    }
)


class AuthHold(NamedTuple):
    """Why this sweep sends nothing credentialed to one device (#469).

    ``reason`` is the condemnation to carry forward — the text that routes an
    operator to capture — and ``retry_after`` the absolute deadline, so the
    hold survives a restart and can be shown on the device page.
    """

    active: bool
    reason: str = ""
    retry_after: float = 0.0


def _next_auth_retry_after(streak: int, now: float) -> float:
    """``min(interval * 2**(streak-1), MAX)`` — ADR-0063's lease shape.

    Returns an absolute unix timestamp, or 0.0 when the hold is disabled.
    """
    ceiling = _resolve_auth_hold_max_seconds()
    if ceiling <= 0:
        return 0.0
    exponent = max(int(streak) - 1, 0)
    wait = min(_resolve_interval_seconds() * float(2 ** min(exponent, 32)), ceiling)
    return now + wait


def _auth_hold_for(
    prev: "Optional[DeviceHealthRecord]", now: float
) -> "AuthHold":
    """Is this device inside its #469 hold right now?"""
    if prev is None or not prev.auth_retry_after:
        return AuthHold(False)
    ceiling = _resolve_auth_hold_max_seconds()
    if ceiling <= 0:
        return AuthHold(False)
    # A clock step backwards (NTP, a resumed VM) must not park the deadline
    # in the far future: anything beyond one whole ceiling is treated as due.
    if prev.auth_retry_after > now + ceiling:
        return AuthHold(False)
    if prev.auth_retry_after <= now:
        return AuthHold(False)
    return AuthHold(True, prev.last_error or "", prev.auth_retry_after)


def _auth_hold_note(reason: str, wait_seconds: float) -> str:
    """The condemnation, plus why this sweep asked nothing.

    Suffixed, never replaced: ``reason`` is what tells the operator the
    password is wrong and sends them to capture. Re-suffixing is idempotent
    so the note cannot grow one sweep at a time.
    """
    base = (reason or "credentials rejected").split(" \u2014 credential check held")[0]
    minutes = max(1, int((max(wait_seconds, 0) + 59) // 60))
    return (base + f" \u2014 credential check held ~{minutes} min (#469)")[:200]


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
    # #469 / ADR-0065: how many times in a row this device's stored
    # credential has been refused, and the absolute time the sweep may send
    # it again. A held sweep spends no authentication (FR-HLT-012).
    auth_fail_streak: int = 0
    auth_retry_after: Optional[float] = None
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
            "auth_fail_streak": self.auth_fail_streak,
            "auth_retry_after": self.auth_retry_after,
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
    sd_total_kb            INTEGER,
    auth_fail_streak       INTEGER NOT NULL DEFAULT 0,
    auth_retry_after       REAL
);
"""

# Columns added after the table first shipped; applied via ALTER TABLE for
# databases created before them (CREATE TABLE IF NOT EXISTS won't).
_MIGRATION_COLUMNS = (
    ("sd_status", "TEXT"),
    ("sd_total_kb", "INTEGER"),
    ("auth_fail_streak", "INTEGER NOT NULL DEFAULT 0"),
    ("auth_retry_after", "REAL"),
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
                    # Only mark the path ready when the schema really landed.
                    # Marking it regardless is how a migration that failed
                    # once stays "done" for the life of the process, and every
                    # later statement fails on a column that never arrived.
                    if self._create_schema(path):
                        self._ready.add(path)
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _create_schema(self, path: str) -> bool:
        """Open our own connection -- via ``_connect`` this would recurse.

        ``_ready`` is keyed by path rather than a boolean, so a rebind runs
        the schema and its migrations against the new file instead of
        assuming the previous one's columns exist.

        Migrates the _MIGRATION_COLUMNS list onto device_health. Only the
        "already there" answer is benign: a locked or unwritable database
        must not be mistaken for a completed migration, so anything else
        propagates to the caller below, which then leaves the path unmarked
        and retries on the next connection. Returns True when the schema and
        its migrations are in place.
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
                    except sqlite3.OperationalError as exc:
                        if "duplicate column" not in str(exc).lower():
                            raise
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as exc:  # pragma: no cover - defensive
            logger.warning("DeviceHealthStore table creation failed: %s", exc)
            return False
        return True

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
                " sd_status, sd_total_kb, auth_fail_streak, auth_retry_after) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
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
                "  sd_total_kb          = excluded.sd_total_kb, "
                "  auth_fail_streak     = excluded.auth_fail_streak, "
                "  auth_retry_after     = excluded.auth_retry_after",
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
                    record.auth_fail_streak,
                    record.auth_retry_after,
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
                "       uptime_seconds, bootid, sd_status, sd_total_kb, "
                "       auth_fail_streak, auth_retry_after "
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
            auth_fail_streak=row[11] or 0,
            auth_retry_after=row[12],
        )

    def list_all(self) -> List[DeviceHealthRecord]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT device_id, status, last_check, last_seen_online, "
                "       latency_ms, consecutive_failures, last_error, "
                "       uptime_seconds, bootid, sd_status, sd_total_kb, "
                "       auth_fail_streak, auth_retry_after "
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
                auth_fail_streak=r[11] or 0,
                auth_retry_after=r[12],
            )
            for r in rows
        ]

    def clear_auth_hold(self, device_id: str) -> bool:
        """Forget one device's #469 hold, so the next sweep asks again.

        An UPDATE, never an upsert: #428 purges health rows inside the
        device-delete transaction, and a device that has never been swept
        has no row that should be conjured here. A miss is success.
        """
        conn = self._connect()
        try:
            cur = conn.execute(
                "UPDATE device_health SET auth_fail_streak=0, auth_retry_after=NULL "
                "WHERE device_id=?",
                (device_id,),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

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


def clear_auth_hold(device_id: str) -> None:
    """Forget the #469 hold for one device (ADR-0065).

    Called by the registry backends when a stored `default` credential
    changes: the sweep must ask again rather than make the operator wait out
    the ceiling. Best-effort and never raises — a credential write must not
    fail because the health store is unavailable. The MCP server is a
    separate process, so this is a row write rather than a signal.
    """
    try:
        device_health_store.clear_auth_hold(device_id)
    except Exception:  # noqa: BLE001 - never break a credential write
        logger.debug("could not clear the auth hold for %s", device_id, exc_info=True)


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

# Verdict words shared by the three corroboration helpers. A condemnation
# must be able to say what it asked (GH #464): "both refused" is only true
# when the second op was sent and refused.
_REFUSAL_BOTH = "both_refused"           # the corroborator refused them too
_REFUSAL_UNCORROBORABLE = "uncorroborable"  # this device has no JSON surface to ask
_REFUSAL_UNCATALOGUED = "uncatalogued"   # the corroborator is not in the catalog
_REFUSAL_CLEARED = "cleared"             # the corroborator authenticated
_REFUSAL_TRANSIENT = "transient"         # the corroborator errored; proves nothing
_REFUSAL_INCONCLUSIVE = "inconclusive"   # the corroborator answered oddly; proves nothing
_VERDICT_ACCEPTED = "accepted"           # the primary op authenticated (or, lenient, answered)
_VERDICT_UNKNOWN = "unknown"             # the primary op was missing/errored/unproven
#: The verdicts that condemn the stored credentials on the failure branch.
#: The middle two are single-op judgements, deliberately — see
#: :func:`_corroborate_legacy_refusal`.
_LEGACY_REFUSAL_CONDEMNS = frozenset(
    {_REFUSAL_BOTH, _REFUSAL_UNCORROBORABLE, _REFUSAL_UNCATALOGUED}
)


class _Corroboration(NamedTuple):
    """What a credential check concluded, and on what.

    ``creds_ok`` is the tri-state every caller has always read (``False`` =
    condemned, ``True`` = proven, ``None`` = don't move the status);
    ``verdict`` is one of the words above; ``rejection`` is the
    ``last_error`` text to file when ``creds_ok`` is ``False`` — it names
    exactly what was asked, so a corroborator that was never sent is never
    said to have refused (GH #464). :meth:`triple` is the shape external
    callers (onboarding, reconcile) unpack.
    """

    creds_ok: Optional[bool]
    facts: Dict[str, str]
    learned: Optional[Dict[str, str]]
    verdict: str
    rejection: str = ""

    def triple(self) -> "tuple[Optional[bool], Dict[str, str], Optional[Dict[str, str]]]":
        return self.creds_ok, self.facts, self.learned


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


def _looks_like_param_data(result: Any) -> bool:
    """True if a ``param.cgi`` result actually carries parameter data.

    **A 2xx is not enough here, and assuming otherwise would repeat the very
    bug #357 fixes.** For text-format operations the executor sets
    ``success=True`` on any non-error 2xx and hands the raw body through as
    ``parsed_data`` (``executor/vapix.py``, the ``else`` branch of
    ``_parse_response``) — it only fails on a declared ``error_prefix``. So a
    device serving an HTML login page from ``param.cgi`` with HTTP 200 yields
    a "successful" result containing no parameters at all. Classifying that as
    ``limited_api`` would be the same mistake as classifying the T8516 as
    ``reachable_no_api``: trusting one signal's shape instead of reading what
    came back.

    A genuine ``param.cgi:list`` response is ``key=value`` lines. Accept a
    non-empty mapping, or text with at least one ``<dotted.key>=`` line; reject
    anything that opens like markup.
    """
    data = getattr(result, "parsed_data", None)
    if isinstance(data, dict):
        return bool(data)
    if not isinstance(data, str):
        return False
    body = data.strip()
    if not body or body.startswith("<"):
        return False
    return any(
        re.match(r"^[A-Za-z][\w.]*=", line.strip())
        for line in body.splitlines()
    )


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
) -> _Corroboration:
    """One auth-required op refused the credentials — ask a second, independent
    one before declaring the password bad (GH #149).

    Returns a :class:`_Corroboration`; ``creds_ok`` is the tri-state
    :func:`_confirm_credentials` documents, and ``rejection`` is the text to
    file when it is ``False`` — worded by what actually happened (GH #464).
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
        # "online" merely because the corroborator isn't in the catalog. But
        # say so: this is single-op judgement, not two refusals.
        logger.warning(
            "health: %s refused credentials for %s and the corroborating op %s "
            "is not in the catalog — falling back to single-op judgement",
            refused_op, device_id, other_op,
        )
        return _Corroboration(
            False, {}, None, _REFUSAL_UNCATALOGUED,
            f"credentials rejected — {refused_op} refused them; the "
            f"corroborating op {other_op} is not in the catalog, so this is "
            "single-op judgement",
        )

    if result is _OP_ERRORED:
        return _Corroboration(None, {}, None, _REFUSAL_TRANSIENT)  # transient — proves nothing, don't flap

    sc = getattr(result, "status_code", None)
    if sc in (401, 403):
        return _Corroboration(
            False, {}, None, _REFUSAL_BOTH,
            f"credentials rejected — both {refused_op} and {other_op} refused them",
        )

    if _is_authenticated_2xx(result):
        # A real authenticated 2xx from an auth-required op. This deliberately
        # satisfies ``strict=True`` (onboarding SAVES a password on it): strict
        # exists because the LENIENT path accepted *non-auth* answers as proof,
        # and this is not that — it is genuine proof, just from the other op.
        facts = _facts_from(result) if other_op == AUTH_CHECK_OP else {}
        return _Corroboration(True, facts, {_MARKER_OP_FIELD: other_op}, _REFUSAL_CLEARED)

    # Answered some other way (unparsable body, odd status): proves nothing
    # either direction, so don't move the status.
    return _Corroboration(None, {}, None, _REFUSAL_INCONCLUSIVE)


async def _confirm_credentials_verdict(
    *,
    catalog: Any,
    executor: Any,
    device_info: Dict[str, Any],
    device_id: str,
    credentials: Dict[str, Any],
    timeout_seconds: float,
    strict: bool = False,
) -> _Corroboration:
    """Confirm the stored credentials actually authenticate.

    Calls an auth-required op (``basicdeviceinfo`` by default). Returns a
    :class:`_Corroboration` (``creds_ok``, ``facts``, ``learned``, plus the
    verdict word and, on a condemnation, the ``rejection`` text — GH #464);
    :func:`_confirm_credentials` is the same call returning only the triple,
    for callers that unpack it. ``creds_ok`` is:
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
        return _Corroboration(None, {}, None, _VERDICT_UNKNOWN)

    sc = getattr(result, "status_code", None)
    if sc in (401, 403):
        # Don't believe a single op (GH #149) — corroborate before condemning.
        return await _corroborate_rejection(
            catalog=catalog, executor=executor, device_info=device_info,
            device_id=device_id, credentials=credentials,
            timeout_seconds=timeout_seconds, refused_op=primary_op,
        )

    if strict and not _is_authenticated_2xx(result):
        return _Corroboration(None, {}, None, _VERDICT_UNKNOWN)  # didn't prove anything — not good enough to save

    # Accepted (or non-auth answer): mine the body for identity facts.
    facts = _facts_from(result) if primary_op == AUTH_CHECK_OP else {}
    return _Corroboration(True, facts, None, _VERDICT_ACCEPTED)


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
    """:func:`_confirm_credentials_verdict` for callers that unpack the
    ``(creds_ok, facts, learned)`` triple — onboarding, reconcile."""
    corroboration = await _confirm_credentials_verdict(
        catalog=catalog, executor=executor, device_info=device_info,
        device_id=device_id, credentials=credentials,
        timeout_seconds=timeout_seconds, strict=strict,
    )
    return corroboration.triple()


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


# How a JSON-RPC op's failed answer reads for this sweep's status.
_JSON_ABSENT = "absent"        # the device cannot serve this op
_JSON_TRANSIENT = "transient"  # the surface exists; this answer proves nothing
# The executor's two message shapes (``executor/vapix.py``) for a JSON op the
# device cannot serve AT ALL: a dropped/refused connection after TCP accepted,
# and a 2xx whose body is not JSON (HTML where JSON was expected). Both are
# device-wide — every JSON POST to a legacy-only device fails one of these
# ways — unlike a 404, which is about one endpoint.
_TRANSPORT_PREFIX = "Transport error:"
_PARSE_FAILURE_PREFIX = "Failed to parse JSON response"


def _json_surface_gone(result: Any) -> bool:
    """Does this failed JSON-RPC answer say the device has no JSON surface
    at all? Only the two device-wide shapes (the T8516's): a transport drop
    after TCP accepted, or a 2xx body that is not JSON. A 404 is not that —
    it says one endpoint is missing (``systemready.cgi`` needs firmware 9.50;
    ``basicdeviceinfo.cgi`` exists from 6.50) — and a JSON-RPC error object
    at 2xx is a JSON surface answering.
    """
    status = getattr(result, "status_code", None)
    error = str(getattr(result, "error", "") or "")
    if status is None:
        return error.startswith(_TRANSPORT_PREFIX)
    try:
        code = int(status)
    except (TypeError, ValueError):
        return False
    return 200 <= code < 300 and error.startswith(_PARSE_FAILURE_PREFIX)


def _json_answer_kind(result: Any) -> str:
    """How the *corroborator's* failed answer reads: can this device serve
    the op at all?

    ABSENT when the JSON surface is gone (:func:`_json_surface_gone`) or the
    endpoint is not there — ADR-0063's absent status codes (400/404/405/410/
    501, reused from ``device_capabilities``): a corroborator the device does
    not have is the catalog-missing case in another form. TRANSIENT for
    everything else: a 5xx, a 4xx the ADR does not call absent (408, 429), a
    connect or timeout verdict (about the host, not the surface), and any
    JSON-RPC error object at 2xx — ``1100: Internal error`` and
    ``2004: Method not supported`` alike — because that is a JSON surface
    answering in JSON over an HTTP layer that just accepted the credentials;
    whatever it says about the method, it cannot mean "no surface to ask".
    ADR-0063 files the surface-gone shapes as *unconfirmed* absence with a
    short lease rather than a 7-day row; the health status is re-evaluated
    every sweep, so acting on the same evidence one sweep at a time is
    cheaper than a lease — and, like the ADR, a live surface's bad moment
    never reads as a missing one.
    """
    from admz.device_capabilities import ABSENT_STATUS_CODES

    if _json_surface_gone(result):
        return _JSON_ABSENT
    status = getattr(result, "status_code", None)
    try:
        code = int(status) if status is not None else None
    except (TypeError, ValueError):
        code = None
    if code in ABSENT_STATUS_CODES:
        return _JSON_ABSENT
    return _JSON_TRANSIENT


def _reason_of(result: Any, limit: int = 50) -> str:
    error = str(getattr(result, "error", "") or "")
    if not error:
        sc = getattr(result, "status_code", None)
        error = f"HTTP {sc}" if sc is not None else "no answer"
    return error[:limit]


async def _corroborate_legacy_refusal(
    *,
    catalog: Any,
    executor: Any,
    device_info: Dict[str, Any],
    device_id: str,
    credentials: Dict[str, Any],
    timeout_seconds: float,
    json_probe: Any,
) -> "tuple[str, Dict[str, str], str]":
    """The legacy read (:data:`CORROBORATION_OP`) refused the credentials on a
    sweep whose JSON probe already failed. Decide whether the password is
    condemned, and say exactly on what evidence (GH #462).

    Not :func:`_corroborate_rejection`. That helper folds "the corroborator
    could not answer" into the same *don't condemn* verdict as "it answered
    oddly", which is right on the ONLINE path: there the JSON surface has
    just proven itself, so a corroborator that fails is a transient. Here the
    sweep is in the failure branch *because* the JSON surface did not answer
    (or the capability record says it is absent), and the corroborator is a
    JSON-RPC op too. On a legacy-only device — the T8516, the device #462 is
    about — it can never answer, and reading that as "not proven" would leave
    a rotated password filed ``reachable_no_api`` forever, which is the
    defect. So a JSON surface that is demonstrably not there to ask is the
    same case as a corroborator that is not in the catalog, and gets the
    verdict the existing helper already gives that case: the legacy read's
    refusal is the only evidence this device can give, and a false alarm is
    safer than a missed one. Which failures mean "not there to ask" is
    :func:`_json_answer_kind`'s question, drawn on ADR-0063's line — a bad
    moment on a live surface never condemns.

    ``json_probe`` is this sweep's own :data:`SYSTEMREADY_OP` result (``None``
    when the probe was skipped on the record). When it already failed in a
    *device-wide* missing-surface shape (:func:`_json_surface_gone`), that IS
    the corroboration: the JSON surface was asked this sweep and was not
    there, so a second JSON op is not sent — no dead request, and one
    transport WARNING per sweep rather than two. A 404-class answer from
    ``systemready`` is not that: it says one endpoint is missing (firmware
    6.50–9.49 has ``basicdeviceinfo`` and not ``systemready``), so the
    corroborator is asked. On a skip sweep there is no fresh evidence, so
    the corroborator is asked.

    Returns ``(verdict, facts, message)``: one of the ``_REFUSAL_*`` words,
    identity facts when the corroborator authenticated, and the
    ``last_error`` text naming what was asked and what it said.
    """
    if json_probe is not None and _json_surface_gone(json_probe):
        return (
            _REFUSAL_UNCORROBORABLE, {},
            f"credentials rejected — {CORROBORATION_OP} refused them; no JSON "
            f"surface to corroborate ({SYSTEMREADY_OP} this sweep: "
            f"{_reason_of(json_probe)})",
        )
    other = await _run_auth_op(
        catalog=catalog, executor=executor, device_info=device_info,
        device_id=device_id, credentials=credentials,
        timeout_seconds=timeout_seconds, op_id=AUTH_CHECK_OP,
    )
    if other is _OP_MISSING:
        logger.warning(
            "health: %s refused credentials for %s and the corroborating op %s "
            "is not in the catalog — falling back to single-op judgement",
            CORROBORATION_OP, device_id, AUTH_CHECK_OP,
        )
        return (
            _REFUSAL_UNCATALOGUED, {},
            f"credentials rejected — {CORROBORATION_OP} refused them; the "
            f"corroborating op {AUTH_CHECK_OP} is not in the catalog, so this "
            "is single-op judgement",
        )
    if other is _OP_ERRORED:
        return (
            _REFUSAL_TRANSIENT, {},
            f"{CORROBORATION_OP} refused the credentials and {AUTH_CHECK_OP} "
            "errored — credentials NOT condemned on one op's evidence",
        )
    sc = getattr(other, "status_code", None)
    if sc in (401, 403) or _reports_401(getattr(other, "error", None)):
        return (
            _REFUSAL_BOTH, {},
            f"credentials rejected — {CORROBORATION_OP} and {AUTH_CHECK_OP} "
            "both refused them",
        )
    if _is_authenticated_2xx(other):
        return (
            _REFUSAL_CLEARED, _facts_from(other),
            f"{CORROBORATION_OP} refused the credentials but {AUTH_CHECK_OP} "
            "authenticated — credentials look valid; ADMZ cannot read this "
            "device's config",
        )
    if _json_answer_kind(other) == _JSON_ABSENT:
        return (
            _REFUSAL_UNCORROBORABLE, {},
            f"credentials rejected — {CORROBORATION_OP} refused them; no JSON "
            f"surface to corroborate ({AUTH_CHECK_OP}: {_reason_of(other)})",
        )
    return (
        _REFUSAL_TRANSIENT, {},
        f"{CORROBORATION_OP} refused the credentials and {AUTH_CHECK_OP} could "
        f"not corroborate it ({_reason_of(other, 30)}) — credentials NOT "
        "condemned on one op's evidence",
    )


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


#: Rows the health monitor writes say so. ``learn`` defaults to ``audit``,
#: which would make a row the drift audit never wrote claim it had.
_HEALTH_SOURCE = "health"


def _systemready_record(device_id: str, device_info: Dict[str, Any]):
    """``(row, stale, skip)`` for ``systemready``: the device's row in ANY
    state, whether it is stale for the device's current firmware, and whether
    the JSON probe should be skipped — only on a NON-stale row that says
    unsupported. Best-effort: a store problem means "probe as before", never
    a failed sweep."""
    try:
        from admz.device_capabilities import capability_store, device_firmware

        row = capability_store.get(device_id, "systemready")
        if row is None:
            return None, False, False
        stale = row.is_stale(device_firmware(device_info), time.time())
        return row, stale, (not stale and not row.supported)
    except Exception:  # noqa: BLE001
        logger.debug("capability record unavailable for %s", device_id, exc_info=True)
        return None, False, False


def _teach_systemready(device_id: str, device_info: Dict[str, Any], result: Any) -> None:
    """Record what ``systemready`` answered, on a sweep where the device was
    demonstrably readable. Best-effort; never fails the sweep."""
    try:
        from admz.device_capabilities import capability_store, device_firmware, learn

        learn(
            capability_store,
            device_id=device_id,
            firmware=device_firmware(device_info),
            outcomes=[("systemready", result)],
            device_readable=True,
            source=_HEALTH_SOURCE,
        )
    except Exception:  # noqa: BLE001
        logger.debug("systemready outcome not recorded for %s", device_id, exc_info=True)


async def _unauth_systemready(
    catalog: Any,
    executor: Any,
    device_id: str,
    device_info: Dict[str, Any],
    timeout_seconds: float,
) -> Optional[Dict[str, Any]]:
    """Read ``systemready`` with NO credentials at all. Returns None if it
    could not be asked or did not answer.

    The three courtesies this request is owed: consult the ADR-0063 record so
    a device known to refuse systemready is not asked every sweep (#458);
    bound it by the sweep's budget rather than the executor's 15 s; and send
    it with auth switched off — the op is auth-free by design, and a `basic`
    profile would otherwise put an empty Basic header on the wire every 60 s,
    which is a credentialed request from a sweep (NFR-HLT-002).
    """
    if catalog is None or executor is None:
        return None
    from admz.fleet.systemready import read_systemready

    _row, _stale, skip_read = _systemready_record(device_id, device_info)
    if skip_read:
        return None
    unauth_info = {
        **device_info,
        "device_id": device_id,
        "auth": {**(device_info.get("auth") or {}),
                 "http": "none", "https": "none"},
        "auth_method": "none",
    }
    try:
        return await asyncio.wait_for(
            read_systemready(
                catalog, executor, unauth_info,
                {"username": "", "password": ""},
            ),
            timeout=timeout_seconds + 2,
        )
    except asyncio.TimeoutError:
        return None


async def probe_device(
    *,
    device_id: str,
    device_info: Dict[str, Any],
    credentials: Optional[Dict[str, Any]],
    catalog: Any = None,
    executor: Any = None,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    auth_hold: Optional[AuthHold] = None,
) -> DeviceHealthRecord:
    """Check one device and return a fresh health record.

    Two-tier probe:
      1. If we have credentials AND the catalog + executor are
         available, call ``systemready.cgi:systemReady`` via the
         executor. Success → ONLINE with uptime/bootid populated.
         Auth failure (401) → AUTH_FAILED **only once a second,
         independent auth-required op has also refused** (GH #150;
         see the ordering note below). Connect failure →
         UNREACHABLE. Any *other* failure (unparsable body, wrong
         content type, unexpected status) is a statement about the
         device's API, not its reachability — so it falls through to
         a TCP connect and becomes REACHABLE_NO_API if the host
         answers, UNREACHABLE only if it doesn't.
      2. Otherwise, a TCP connect probe against the device's host on its
         effective port (see :func:`_probe_port`). Connect fail →
         UNREACHABLE. Connect OK with a usable credential (the catalog or
         executor was simply unavailable) → ONLINE without uptime info.
         Connect OK with **no** usable credential (ADR-0064 / FR-HLT-011):
         ask ``systemready`` *unauthenticated* — it is auth-free by design,
         and onboarding reads it the same way — so a factory-default unit
         is NEEDS_SETUP; anything else is NO_CREDENTIALS: the host
         answered, it is provisioned, and ADMZ has no way in. It used to
         be ONLINE, which an A1210 read for seven hours (#443).

    **Ordering: why a systemready 401 still cannot reach ``needs_setup``,
    and why moving the branch would not change that (GH #150).**

    #150 observed that the 401 branch returns before the needsetup check, so a
    factory-defaulted device that 401s on systemready cannot be classified
    ``NEEDS_SETUP`` — which matters because the deferred-recovery triggers of
    #70/#71 key off exactly that state.

    The observation is correct; the obvious remedy does not work. ``needsetup``
    is read out of **systemready's own parsed body** (see below, and
    ``admz/fleet/systemready.py::read_systemready``, which likewise returns
    ``None`` unless ``result.success``). A 401 has no such body. Reordering the
    branches would therefore evaluate ``needsetup = False`` against an empty
    ``parsed_data`` and fall straight through — the same outcome, reached less
    obviously. **When systemready 401s there is no needsetup signal available
    anywhere in ADMZ**, because systemready *is* the auth-free signal.

    So this fix does not reorder. It removes the wrong verdict rather than
    relocating it: a 401 that is not corroborated yields ``REACHABLE_NO_API``
    (the host answered, ADMZ cannot read its readiness) instead of the
    unsupported ``AUTH_FAILED``. A device in that state is no longer condemned,
    and an operator sees an attention state naming the actual ambiguity.

    Recovering ``NEEDS_SETUP`` from this state would need a *new* signal — the
    obvious candidate being an unauthenticated systemready retry, since the CGI
    is specified as auth-free. That is deliberately **not** built here: the
    scenario has never been observed on a real device, and adding a speculative
    extra request to every 401 sweep is the kind of assumption this issue was
    split out of #149 to avoid making in the other direction.
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

    # A "usable" credential is one with a non-empty password — the only kind
    # this registry stores (the executor's bearer method falls back to the
    # password field; nothing writes a token). ADR-0064.
    has_usable_credential = bool(credentials and credentials.get("password"))

    # ---- Tier 0: the #469 hold (ADR-0065 / FR-HLT-012) ----
    #
    # This device's stored credential was refused and the hold has not
    # expired. Send nothing that costs an authentication; send the two things
    # that cost none, so reachability stays fresh and a factory reset stays
    # visible while the hold is in force.
    #
    # The previous verdict is carried forward rather than re-derived. Deriving
    # one here would read `online` off the TCP probe below (a device in this
    # branch has a credential by definition) and fire `on_online` at a device
    # ADMZ cannot authenticate to — the failure FR-HLT-011 exists to prevent.
    #
    # Above the Tier-1 gate on purpose: inside it, a monitor built without a
    # catalog or executor would skip the hold and fall through to exactly
    # that mistake.
    if auth_hold is not None and auth_hold.active and has_usable_credential:
        port = _probe_port(device_info)
        elapsed_ms = await _tcp_probe(host, port, timeout_seconds)
        if elapsed_ms is None:
            return DeviceHealthRecord(
                device_id=device_id,
                status=DeviceHealthStatus.UNREACHABLE,
                last_check=now,
                last_error=(
                    f"TCP connect to {host}:{port} failed within {timeout_seconds}s"
                ),
                consecutive_failures=1,
            )
        ready = await _unauth_systemready(
            catalog, executor, device_id, device_info, timeout_seconds
        )
        if ready and ready.get("needsetup"):
            return DeviceHealthRecord(
                device_id=device_id,
                status=DeviceHealthStatus.NEEDS_SETUP,
                last_check=now,
                last_seen_online=now,
                latency_ms=elapsed_ms,
                consecutive_failures=0,
                last_error="factory-defaulted (needsetup=yes) — not provisioned",
                uptime_seconds=ready.get("uptime"),
                bootid=ready.get("bootid"),
            )
        return DeviceHealthRecord(
            device_id=device_id,
            status=DeviceHealthStatus.AUTH_FAILED,
            last_check=now,
            last_seen_online=now,
            latency_ms=elapsed_ms,
            # The sweep carries the previous count: this sweep asked the
            # device nothing about its credential.
            consecutive_failures=0,
            last_error=_auth_hold_note(auth_hold.reason, auth_hold.retry_after - now),
        )

    # ---- Tier 1: authenticated VAPIX systemReady ----
    if has_usable_credential and catalog is not None and executor is not None:
        try:
            op = catalog.get_operation("vapix", "systemready.cgi:systemReady")
        except Exception:
            op = None
        if op is not None:
            # ADR-0063 / GH #458: consult the capability record before the
            # JSON probe. A device that has demonstrably refused systemready
            # (a limited_api switch) used to be asked again every sweep — one
            # dead request and one WARNING per sweep to learn what the record
            # already said. Only the JSON probe is skipped: the legacy read
            # below still runs, so reachability and credentials are judged
            # fresh each sweep; only the request known to fail is not sent.
            _cap_row, _cap_stale, skip_json_probe = _systemready_record(
                device_id, device_info
            )
            result = None
            elapsed_ms = 0
            started = time.monotonic()
            try:
                if not skip_json_probe:
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
                # GH #150. One op's 401 is not proof the password is wrong.
                # #149 disproved exactly this inference for basicdeviceinfo on a
                # real AXIS P8815-2 — per-op authorization differences are real
                # on Axis firmware — so ask a second, independent auth-required
                # op before condemning the stored credentials.
                #
                # Whether systemready specifically CAN 401 while other ops
                # authenticate has never been observed. This does not assume it
                # happens; it stops assuming it cannot, which is a different and
                # much cheaper claim: the corroborating call only ever runs on a
                # path that already failed.
                corroboration = await _corroborate_rejection(
                    catalog=catalog, executor=executor, device_info=device_info,
                    device_id=device_id, credentials=credentials,
                    timeout_seconds=timeout_seconds, refused_op=SYSTEMREADY_OP,
                )
                creds_ok = corroboration.creds_ok
                if creds_ok is False:
                    return DeviceHealthRecord(
                        device_id=device_id,
                        status=DeviceHealthStatus.AUTH_FAILED,
                        last_check=now,
                        latency_ms=elapsed_ms,
                        # Worded by the verdict (GH #464): "both refused" only
                        # when the corroborator was sent and refused; a
                        # corroborator missing from the catalog says so.
                        last_error=corroboration.rejection,
                        consecutive_failures=1,
                    )

                # Not condemned. systemready still failed, so there is no
                # parsed body — and therefore no uptime, no bootid, and NO
                # (Deliberately no capability teaching here: a 401 row would
                # flip the verdict between REACHABLE_NO_API on probe sweeps
                # and LIMITED_API on skip sweeps — the ADR-0063 amendment-2
                # flap. Absence is taught only where the legacy read proved
                # the device readable.)
                # needsetup signal (see the ordering note in this function's
                # docstring). Classify on reachability evidence, exactly as the
                # generic failure path below does, via the same helper.
                logger.info(
                    "health: %s returned 401 for %s but %s did not corroborate "
                    "(verdict=%s) — not condemning the stored credentials",
                    SYSTEMREADY_OP, device_id, CORROBORATION_OP,
                    corroboration.verdict,
                )
                tcp_ms = await _tcp_probe(
                    host, _probe_port(device_info), timeout_seconds
                )
                if tcp_ms is None:
                    return DeviceHealthRecord(
                        device_id=device_id,
                        status=DeviceHealthStatus.UNREACHABLE,
                        last_check=now,
                        last_error=f"{SYSTEMREADY_OP} returned 401; host then "
                                   "failed to accept a TCP connection",
                        consecutive_failures=1,
                    )
                return DeviceHealthRecord(
                    device_id=device_id,
                    status=DeviceHealthStatus.REACHABLE_NO_API,
                    last_check=now,
                    last_seen_online=now,  # it answered HTTP — it is up
                    latency_ms=elapsed_ms,
                    consecutive_failures=0,
                    last_error=(
                        f"{SYSTEMREADY_OP} returned 401 but {CORROBORATION_OP} "
                        "authenticated — credentials look valid; ADMZ cannot "
                        "read this device's readiness"
                        if creds_ok
                        else f"{SYSTEMREADY_OP} returned 401 and "
                             f"{CORROBORATION_OP} could not corroborate it — "
                             "credentials NOT condemned on one op's evidence"
                    ),
                )

            if result is None or not getattr(result, "success", False):
                if skip_json_probe:
                    # Skipped on the record: say so. The text starts with the
                    # op id, so it can never match the executor's reachability
                    # prefixes below — no guard is needed for this path.
                    err = (
                        f"{SYSTEMREADY_OP} not sent — capability record says "
                        f"{_cap_row.classification} ({_cap_row.source})"
                    )
                else:
                    # ``str()`` on purpose: a non-string ``error`` (a result
                    # object of another shape, a mock without one) must not
                    # take the fast path by answering ``startswith`` truthily.
                    err = str(getattr(result, "error", "") or "unknown error")
                # A connect failure or timeout is a reachability verdict the
                # executor already made — take it at face value. Only those
                # two shapes, by prefix (GH #461); every other error text is
                # a statement about ADMZ's ability to speak this device's API,
                # not about the host, and is settled on evidence below.
                if err.startswith(_UNREACHABLE_PREFIXES):
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
                        # On a skip sweep the verdict is the TCP probe's, not
                        # the record's — say which (#460 review).
                        last_error=(
                            f"host did not accept a TCP connection ({err})"
                            if skip_json_probe else err
                        )[:200],
                        consecutive_failures=1,
                    )
                # GH #357: the host is up and one probe failed — that is not
                # yet enough to say ADMZ cannot manage it. This exact path is
                # where the T8516 landed: `systemready` is JSON-RPC, the switch
                # serves HTML, the parse fails, and the device was filed as
                # unmanageable *while ADMZ was committing its config every
                # cycle over `param.cgi`*. So ask the legacy-CGI surface before
                # concluding anything. Same op the 401 branch already uses, on
                # a path that has by definition already failed — no extra
                # request on any healthy sweep.
                # ONE call, direct. Not `_corroborate_rejection`: that helper
                # answers "are the credentials bad?" for the 401 path and folds
                # several outcomes into one tri-state, whereas the question
                # here is narrower — did a managed read actually return data?
                # Reusing it would also cost a second request to say so.
                legacy = await _run_auth_op(
                    catalog=catalog, executor=executor, device_info=device_info,
                    device_id=device_id, credentials=credentials,
                    timeout_seconds=timeout_seconds, op_id=CORROBORATION_OP,
                )
                # GH #462: the managed read REFUSED the stored credentials.
                # That is a credential question, not an API one — a
                # limited_api device with a rotated password used to read as
                # "lost its API surface" (reachable_no_api) on every sweep,
                # never "lost its password", and nothing routed the operator
                # to capture. One op's 401 is not proof (GH #149), so a second
                # auth-required op decides — by a helper that knows this
                # branch is only ever entered because the JSON surface did not
                # answer: when this sweep's own JSON probe already failed in a
                # missing-surface shape that IS the corroboration, and a JSON
                # corroborator that cannot answer either is the shape of a
                # legacy-only device, not a reason to withhold the verdict.
                # See _corroborate_legacy_refusal.
                legacy_refused = (
                    legacy is not _OP_MISSING
                    and legacy is not _OP_ERRORED
                    and (
                        getattr(legacy, "status_code", None) in (401, 403)
                        or _reports_401(getattr(legacy, "error", None))
                    )
                )
                if legacy_refused:
                    verdict, facts, why = await _corroborate_legacy_refusal(
                        catalog=catalog, executor=executor, device_info=device_info,
                        device_id=device_id, credentials=credentials,
                        timeout_seconds=timeout_seconds, json_probe=result,
                    )
                    latency = elapsed_ms if not skip_json_probe else (tcp_ms or 0)
                    if verdict in _LEGACY_REFUSAL_CONDEMNS:
                        return DeviceHealthRecord(
                            device_id=device_id,
                            status=DeviceHealthStatus.AUTH_FAILED,
                            last_check=now,
                            last_seen_online=now,  # it IS reachable, just not authable
                            latency_ms=latency,
                            consecutive_failures=1,
                            last_error=why[:200],
                        )
                    return DeviceHealthRecord(
                        device_id=device_id,
                        status=DeviceHealthStatus.REACHABLE_NO_API,
                        last_check=now,
                        last_seen_online=now,
                        latency_ms=latency,
                        consecutive_failures=0,
                        last_error=why[:200],
                        # Identity facts from the corroborator when it
                        # authenticated — free, and the sweep flushes them.
                        observed_facts=facts or None,
                    )
                # Authenticated AND carrying real parameter data. The second
                # half is not belt-and-braces: a text-format 2xx counts as
                # "successful" even when the body is an HTML login page, so
                # without it a switch that serves HTML from param.cgi too would
                # be promoted to limited_api on no evidence — the same
                # trust-the-shape error this issue is about.
                if (
                    legacy is not _OP_MISSING
                    and legacy is not _OP_ERRORED
                    and _is_authenticated_2xx(legacy)
                    and _looks_like_param_data(legacy)
                ):
                    logger.info(
                        "health: %s did not answer usefully for %s (%s), but %s "
                        "did — classifying limited_api, not reachable_no_api",
                        SYSTEMREADY_OP, device_id, err[:80], CORROBORATION_OP,
                    )
                    if result is not None:
                        # The legacy read answering with real data is the
                        # ADR-0063 readability control: the device is readable
                        # NOW, so systemready failing is evidence about
                        # systemready. Transport/parse -> unconfirmed (24h->7d
                        # backoff); a clean 404-class -> absent (7d).
                        _teach_systemready(device_id, device_info, result)
                    return DeviceHealthRecord(
                        device_id=device_id,
                        status=DeviceHealthStatus.LIMITED_API,
                        last_check=now,
                        last_seen_online=now,
                        latency_ms=elapsed_ms if not skip_json_probe else (tcp_ms or 0),
                        consecutive_failures=0,
                        last_error=(
                            f"{SYSTEMREADY_OP} unusable ({err[:120]}); "
                            f"{CORROBORATION_OP} answers — managed reads work, "
                            "no JSON-RPC surface"
                        ),
                    )
                return DeviceHealthRecord(
                    device_id=device_id,
                    status=DeviceHealthStatus.REACHABLE_NO_API,
                    last_check=now,
                    # The host answered, so the reachability clock advances —
                    # this asserts nothing about the device beyond "it is up".
                    last_seen_online=now,
                    latency_ms=elapsed_ms if not skip_json_probe else (tcp_ms or 0),
                    consecutive_failures=0,
                    last_error=(
                        f"{CORROBORATION_OP} did not return parameter data "
                        f"({err})" if skip_json_probe else err
                    )[:200],
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
                corroboration = await _confirm_credentials_verdict(
                    catalog=catalog, executor=executor, device_info=device_info,
                    device_id=device_id, credentials=credentials,
                    timeout_seconds=timeout_seconds,
                )
                creds_ok, observed, learned_probe = corroboration.triple()
                if creds_ok is False:
                    return DeviceHealthRecord(
                        device_id=device_id,
                        status=DeviceHealthStatus.AUTH_FAILED,
                        last_check=now,
                        last_seen_online=now,  # it IS reachable, just not authable
                        latency_ms=elapsed_ms,
                        consecutive_failures=1,
                        # Since GH #149 a condemnation means two independent
                        # auth-required ops refused — and since GH #464 the
                        # text says exactly that, or says the corroborator was
                        # not in the catalog and this is single-op judgement.
                        last_error=corroboration.rejection,
                        uptime_seconds=uptime_int,
                        bootid=bootid_str,
                    )

            # A device that now answers systemready overwrites a lingering
            # absent/unconfirmed (or stale) row so the record says what is
            # true. NOT when the row is already a trustworthy PRESENT: the S2
            # survey records `systemready` PRESENT for every camera, so
            # "teach whenever a row exists" would have been one UPSERT per
            # camera per sweep — and would have overwritten the survey's
            # provenance (#460 review, MAJOR-1). A healthy fleet pays no
            # write per device per sweep.
            if _cap_row is not None and (not _cap_row.supported or _cap_stale):
                _teach_systemready(device_id, device_info, result)

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
        if has_usable_credential:
            # Credentials exist; only the catalog/executor/op was missing.
            return DeviceHealthRecord(
                device_id=device_id,
                status=DeviceHealthStatus.ONLINE,
                last_check=now,
                last_seen_online=now,
                latency_ms=elapsed_ms,
                consecutive_failures=0,
                last_error="",
            )
        # No usable stored credential (ADR-0064 / FR-HLT-011). The host
        # answered, so the reachability clock advances — but "online" is the
        # one thing this device is not. A factory-default unit is the case
        # where "no credentials" would be the wrong word: systemready needs no
        # credential by design and onboarding reads it that way, so ask it
        # the same way and let needsetup=yes win — its CTA and deferred
        # recovery trigger already exist.
        if catalog is not None and executor is not None:
            ready = await _unauth_systemready(
                catalog, executor, device_id, device_info, timeout_seconds
            )
            if ready and ready.get("needsetup"):
                return DeviceHealthRecord(
                    device_id=device_id,
                    status=DeviceHealthStatus.NEEDS_SETUP,
                    last_check=now,
                    last_seen_online=now,
                    latency_ms=elapsed_ms,
                    consecutive_failures=0,
                    last_error="factory-defaulted (needsetup=yes) — not provisioned",
                    uptime_seconds=ready.get("uptime"),
                    bootid=ready.get("bootid"),
                )
        return DeviceHealthRecord(
            device_id=device_id,
            status=DeviceHealthStatus.NO_CREDENTIALS,
            last_check=now,
            last_seen_online=now,
            latency_ms=elapsed_ms,
            consecutive_failures=0,
            last_error=(
                "no usable stored credential — ADMZ has no way into this "
                "device; enter credentials or run onboarding"
            ),
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


#: Keys a task handler may surface into the `deferred_action_fired` audit row.
#: An allow-list, not a filter: a handler that starts returning something
#: sensitive must not have it copied into an audit row by default (GH #326).
_AUDITABLE_OUTCOME_KEYS = ("password_source",)


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

    async def sweep_once(self, force: bool = False) -> int:
        """Probe every device once. Returns the number of devices checked.

        Public so operators (or tests) can trigger a sweep
        on-demand without waiting for the next interval.

        ``force`` ignores the #469 hold (ADR-0065): an operator who asks for
        a check must get one, which is also the recovery path if a device is
        ever wedged. The interval loop never forces.
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
                # Fetch credentials. Absence is something the registry SAYS
                # (no account row): the probe files it as no_credentials or
                # needs_setup. A lookup that FAILED to say — a locked database,
                # a decrypt error, Vault down — is not "no credentials"; the
                # previous record is kept with the failure named, rather than
                # raising a false amber across the fleet (ADR-0064).
                creds: Optional[Dict[str, Any]] = None
                lookup_error: Optional[BaseException] = None
                try:
                    creds = self.registry.get_credentials(device_id)
                except DeviceNotFoundError:
                    # Removed between list_devices() and now. #428 purges its
                    # health row in the same transaction — do not re-create it.
                    return
                except AccountNotFoundError:
                    creds = None
                except Exception as exc:  # noqa: BLE001
                    lookup_error = exc
                if lookup_error is not None:
                    # Fernet's InvalidToken stringifies to nothing — name the type.
                    note = (
                        "credential lookup failed: "
                        f"{type(lookup_error).__name__}: {lookup_error}"
                    )[:200]
                    logger.warning(
                        "health: %s for %s — keeping the previous record",
                        note, device_id,
                    )
                    # The registry and the health store share one SQLite file:
                    # the failure that brought us here (a locked database) is
                    # the one these two calls are likeliest to raise too, and
                    # an exception escaping _check ends the monitor loop.
                    try:
                        prev = self.store.get(device_id)
                        kept = (
                            _dc_replace(prev, last_check=time.time(), last_error=note)
                            if prev is not None
                            else DeviceHealthRecord(
                                device_id=device_id,
                                status=DeviceHealthStatus.UNKNOWN,
                                last_check=time.time(),
                                last_error=note,
                            )
                        )
                        self.store.upsert(kept)
                    except Exception:  # noqa: BLE001 — the store is failing too
                        logger.warning(
                            "health: could not record the lookup failure for %s "
                            "(health store unavailable); the row is untouched",
                            device_id, exc_info=True,
                        )
                    return

                # Read the previous row BEFORE probing: the #469 hold is
                # decided from it, and `last_seen_online` / the SD fields are
                # carried from it below. Wrapped for the same reason the
                # lookup-failure path above is — the registry and the health
                # store share one SQLite file, and an exception escaping
                # _check ends the monitor loop.
                prev: Optional[DeviceHealthRecord] = None
                try:
                    prev = self.store.get(device_id)
                except Exception:  # noqa: BLE001 - the store is failing
                    logger.warning(
                        "health: could not read the previous record for %s; "
                        "probing as if new", device_id, exc_info=True,
                    )
                hold = AuthHold(False) if force else _auth_hold_for(prev, time.time())

                executor = self.executors.get("vapix") if self.executors else None
                try:
                    record = await probe_device(
                        device_id=device_id,
                        device_info=device,
                        credentials=creds,
                        catalog=self.catalog,
                        executor=executor,
                        timeout_seconds=timeout,
                        auth_hold=hold,
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
                held = (
                    hold.active
                    and record.status is DeviceHealthStatus.AUTH_FAILED
                )
                if prev is not None:
                    if held:
                        # A held sweep asked the device nothing about its
                        # credential, so it did not observe a failure. Counting
                        # it would rebuild GH #138's five-figure counters out
                        # of sweeps that made no request.
                        record.consecutive_failures = prev.consecutive_failures
                    elif record.status not in _STABLE_STATUSES:
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

                # #469 / ADR-0065: the hold's own bookkeeping.
                #
                # First, the race the whole-row upsert below would otherwise
                # lose: a credential write clears the hold by UPDATEing this
                # row, and it can land while the probe is in flight. Writing
                # the in-flight record back would resurrect a deadline the
                # operator just cancelled and leave them waiting it out. Only
                # re-read for a device that actually had a deadline, so the
                # ordinary fleet pays nothing.
                cleared_mid_probe = False
                if prev is not None and prev.auth_retry_after:
                    try:
                        latest = self.store.get(device_id)
                        cleared_mid_probe = (
                            latest is None or not latest.auth_retry_after
                        )
                    except Exception:  # noqa: BLE001 - the store is failing
                        cleared_mid_probe = False

                prev_streak = 0 if cleared_mid_probe else (
                    prev.auth_fail_streak if prev is not None else 0
                )
                if cleared_mid_probe:
                    # The credential changed under us. Whatever this probe
                    # concluded was about the old one; let the next sweep ask.
                    record.auth_fail_streak = 0
                    record.auth_retry_after = None
                elif record.status is DeviceHealthStatus.AUTH_FAILED:
                    if held:
                        record.auth_fail_streak = prev_streak
                        record.auth_retry_after = hold.retry_after
                    else:
                        record.auth_fail_streak = prev_streak + 1
                        record.auth_retry_after = _next_auth_retry_after(
                            record.auth_fail_streak, time.time()
                        )
                elif record.status in _AUTH_HOLD_CLEARING_STATUSES:
                    # The credential question was answered, or no longer
                    # applies. Forget the escalation.
                    record.auth_fail_streak = 0
                    record.auth_retry_after = None
                elif prev is not None:
                    # unreachable / reachable_no_api / unknown: nothing was
                    # learned about the credential, so the hold stands rather
                    # than restarting at the base interval on every flap.
                    record.auth_fail_streak = prev_streak
                    record.auth_retry_after = prev.auth_retry_after

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
                        else:
                            # FR-KNW-013: the firmware delta this sweep has
                            # always computed (and discarded) becomes an
                            # event — audit row + a capability survey when
                            # it's a real A→B change.
                            if "firmware_version" in changed:
                                from admz.device_capabilities import note_firmware
                                note_firmware(
                                    device_id,
                                    prev=str(device.get("firmware_version") or ""),
                                    new=str(changed["firmware_version"]),
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
            outcome = await execute_task_action(task)
            # #455 review (MAJOR-1): a handler that RETURNS success=False —
            # rather than raising — used to be marked "done" and audited as
            # fired, so a one-shot trigger (a capability survey queued on a
            # firmware change, against a device mid-reboot) was consumed
            # silently. Honor the result: a failed outcome is a failed task,
            # with the error on the row where an operator can see it.
            failed_outcome = isinstance(outcome, dict) and not outcome.get(
                "success", True
            )
            if failed_outcome:
                err = str(outcome.get("error") or outcome.get("summary")
                          or "handler reported failure")[:300]
                tasks_store.mark(pid, "failed", err)
                record_event(
                    principal, "deferred_action_failed",
                    resource=f"device:{did}", success=False, error_message=err,
                    details={"id": pid, "action": task.action_type,
                             "trigger": task.event},
                )
                return
            tasks_store.mark(pid, "done")
            # GH #326: handlers return a result dict and this discarded it, so
            # the row could never carry anything action-specific. Only a small
            # allow-list of NON-SECRET keys is copied through — `password_source`
            # is a mode name (provided / fleet_default / generated), never the
            # password, and an audit row records attribution rather than a
            # second copy of a secret.
            details = {"id": pid, "action": task.action_type, "trigger": task.event}
            if isinstance(outcome, dict):
                for key in _AUDITABLE_OUTCOME_KEYS:
                    if outcome.get(key) is not None:
                        details[key] = outcome[key]
            record_event(
                principal, "deferred_action_fired", resource=f"device:{did}",
                details=details,
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
