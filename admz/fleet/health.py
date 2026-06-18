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
  fails), fall back to a raw TCP connect against ``device.host:80``
  — at least we learn whether the IP is up.
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
import sqlite3
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
    """Coarse-grained reachability state for a device."""

    ONLINE = "online"
    UNREACHABLE = "unreachable"     # no TCP connect
    AUTH_FAILED = "auth_failed"     # TCP up, VAPIX rejected creds
    NEEDS_SETUP = "needs_setup"     # reachable but factory-defaulted (needsetup=yes)
    UNKNOWN = "unknown"             # never checked


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
    # Transient: model/serial/firmware lifted from the basicdeviceinfo
    # credential-check response (when it ran). Not persisted to the health
    # store — the sweep flushes it to the device registry instead.
    observed_facts: Optional[Dict[str, str]] = None

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
    bootid                 TEXT
);
"""


def _default_db_path() -> Path:
    return Path(
        os.getenv("ADMZ_DB_PATH", str(Path.home() / ".admz" / "admz.db"))
    )


class DeviceHealthStore:
    """SQLite-backed current-state-only store for device health."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = str(db_path or _default_db_path())
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self) -> None:
        try:
            with self._connect() as conn:
                conn.executescript(_SCHEMA)
                conn.commit()
        except sqlite3.Error as exc:  # pragma: no cover — defensive
            logger.warning("DeviceHealthStore table creation failed: %s", exc)

    def upsert(self, record: DeviceHealthRecord) -> None:
        """Insert or update one device's row."""
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO device_health "
                "(device_id, status, last_check, last_seen_online, latency_ms, "
                " consecutive_failures, last_error, uptime_seconds, bootid) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(device_id) DO UPDATE SET "
                "  status               = excluded.status, "
                "  last_check           = excluded.last_check, "
                "  last_seen_online     = excluded.last_seen_online, "
                "  latency_ms           = excluded.latency_ms, "
                "  consecutive_failures = excluded.consecutive_failures, "
                "  last_error           = excluded.last_error, "
                "  uptime_seconds       = excluded.uptime_seconds, "
                "  bootid               = excluded.bootid",
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
                "       uptime_seconds, bootid "
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
        )

    def list_all(self) -> List[DeviceHealthRecord]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT device_id, status, last_check, last_seen_online, "
                "       latency_ms, consecutive_failures, last_error, "
                "       uptime_seconds, bootid "
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


async def _confirm_credentials(
    *,
    catalog: Any,
    executor: Any,
    device_info: Dict[str, Any],
    device_id: str,
    credentials: Dict[str, Any],
    timeout_seconds: float,
) -> "tuple[Optional[bool], Dict[str, str]]":
    """Confirm the stored credentials actually authenticate.

    Calls an auth-required op (``basicdeviceinfo``). Returns a
    ``(creds_ok, facts)`` pair where ``creds_ok`` is:
      - ``False`` when the device explicitly rejects the credentials (401/403),
      - ``True`` when they're accepted (2xx) or the device answers some other
        way (a non-auth error doesn't implicate the password),
      - ``None`` when we can't tell (op missing, transient error) — caller
        should not flip status on ``None``.
    ``facts`` carries model/serial/firmware lifted from the same response on
    the success path (empty otherwise), so the monitor can self-populate the
    device record without a second probe.
    """
    op = None
    try:
        op = catalog.get_operation("vapix", AUTH_CHECK_OP)
    except Exception:
        op = None
    if op is None:
        return None, {}
    try:
        result = await asyncio.wait_for(
            executor.execute(
                op.to_executor_dict(),
                {**device_info, "device_id": device_id},
                credentials,
                {},
            ),
            timeout=timeout_seconds + 2,
        )
    except Exception:
        return None, {}  # transient — don't flap the status on a second-call hiccup
    sc = getattr(result, "status_code", None)
    if sc in (401, 403):
        return False, {}
    # Accepted (or non-auth answer): mine the body for identity facts.
    facts: Dict[str, str] = {}
    try:
        from admz.device_facts import extract_device_facts
        facts = extract_device_facts(getattr(result, "parsed_data", None))
    except Exception:
        facts = {}
    return True, facts


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
         UNREACHABLE.
      2. Otherwise (or as a fallback if the catalog isn't loaded),
         just do a TCP connect probe against the device's host
         on port 80. Connect OK → ONLINE (without uptime info).
         Connect fail → UNREACHABLE.
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
            if status_code == 401 or "401" in str(getattr(result, "error", "")):
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
                # Other errors — treat as unreachable but record the message.
                return DeviceHealthRecord(
                    device_id=device_id,
                    status=DeviceHealthStatus.UNREACHABLE,
                    last_check=now,
                    latency_ms=elapsed_ms,
                    last_error=err[:200],
                    consecutive_failures=1,
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
            if _verify_credentials_enabled():
                creds_ok, observed = await _confirm_credentials(
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
                        last_error="credentials rejected (HTTP 401 on basicdeviceinfo)",
                        uptime_seconds=uptime_int,
                        bootid=bootid_str,
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
                observed_facts=observed or None,
            )

    # ---- Tier 2: TCP connect probe ----
    elapsed_ms = await _tcp_probe(host, 80, timeout_seconds)
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
        last_error=f"TCP connect to {host}:80 failed within {timeout_seconds}s",
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
        # The sweep is also when one-shot deferred actions get evaluated —
        # expire stale ones up front so they can't fire late.
        try:
            from admz.fleet.pending_actions import pending_actions
            pending_actions.expire_stale()
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
                    if record.status != DeviceHealthStatus.ONLINE:
                        record.consecutive_failures = prev.consecutive_failures + 1
                        record.last_seen_online = prev.last_seen_online
                    # Else (ONLINE): consecutive_failures already 0 and
                    # last_seen_online already set to now.

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

                # Fire any pre-authorized deferred actions whose trigger this
                # device's new state now satisfies (e.g. came back needsetup ->
                # re-provision). Launched async so a slow recovery action can't
                # stall the sweep; a no-op unless something is pending.
                await self._fire_pending(device_id, record.status.value)

        await asyncio.gather(*(_check(d) for d in devices))
        return len(devices)

    async def _fire_pending(self, device_id: str, status_value: str) -> None:
        """Evaluate + launch any pre-authorized deferred actions for this
        device whose trigger its new state now satisfies. Atomic claim →
        fire-once; launched async so it can't stall the sweep."""
        try:
            from admz.fleet.pending_actions import (
                pending_actions, trigger_for_status,
            )
            trig = trigger_for_status(status_value)
            if trig is None:
                return
            for action_row in pending_actions.claim_for_trigger(device_id, trig):
                asyncio.create_task(self._run_pending(action_row))
        except Exception:  # noqa: BLE001
            logger.debug(
                "pending-action evaluation failed for %s", device_id, exc_info=True
            )

    async def _run_pending(self, action_row: Dict[str, Any]) -> None:
        """Execute one claimed (pre-authorized) deferred action + audit it."""
        from types import SimpleNamespace

        from admz.audit import record_event
        from admz.fleet.pending_actions import (
            execute_pending_action, pending_actions,
        )

        pid = action_row.get("id")
        did = action_row.get("device_id")
        action = action_row.get("action") or {}
        principal = SimpleNamespace(
            name=action_row.get("approved_by") or "deferred",
            source="deferred-trigger",
        )
        try:
            await execute_pending_action(action, did)
            pending_actions.mark(pid, "done")
            record_event(
                principal, "deferred_action_fired", resource=f"device:{did}",
                details={"id": pid, "action": action.get("action"),
                         "trigger": action_row.get("trigger")},
            )
        except Exception as exc:  # noqa: BLE001
            pending_actions.mark(pid, "failed", str(exc)[:300])
            logger.warning("deferred action %s for %s failed: %s", pid, did, exc)
            try:
                record_event(
                    principal, "deferred_action_failed", resource=f"device:{did}",
                    success=False, error_message=str(exc)[:300],
                    details={"id": pid, "action": action.get("action")},
                )
            except Exception:  # noqa: BLE001
                pass
