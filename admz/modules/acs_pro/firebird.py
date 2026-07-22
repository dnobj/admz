"""Read-only reader for ACS Pro's embedded Firebird databases (ADR-0041).

ACS Pro v6 keeps the classic Firebird 3 `.FDB` databases alongside its newer
PostgreSQL store. Two of them are gold:

* ``ACS.FDB``      — config: the ``RULE`` / ``ACTION`` / ``TRIGGER`` tables (the
  **named action-rule inventory** — names, enabled flags, what each rule does).
* ``ACS_LOGS.FDB`` — logs: the ``LOG`` table, where ``DISCRIMINATOR='AlarmEntity'``
  rows are **named rule firings** (``RULE_NAME`` + timestamp + camera) — including
  firings the ACS *API* can't see. This is the only signal that detects an
  action-rule firing **without modifying the rule** (validated live 2026-06-22).

ACS holds the embedded DBs with an exclusive engine lock, so a live second
attachment is impossible — but a raw file **copy** is permitted (shared read). So
every read works against a short-lived copy, opened read-only with GC disabled;
the live DB is never touched. The whole thing is gated off (``acs_firebird_enabled``)
and degrades cleanly when the driver/files aren't present (non-ACS hosts).

Schema notes (live): ``"TIMESTAMP"`` and ``"TRIGGER"`` are Firebird reserved words
(quote them); creds are SYSDBA / masterkey; the `firebird-driver` package + the
ACS-shipped ``fbclient.dll`` do the work.
"""

from __future__ import annotations

import glob
import logging
import os
import shutil
import tempfile
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Defaults for the standard Windows install (overridable via fleet settings).
_DEFAULT_INSTALL = r"C:\Program Files\Axis Communications\AXIS Camera Station"
_DEFAULT_DATA = r"C:\ProgramData\Axis Communications\AXIS Camera Station Server"
_FB_USER, _FB_PASSWORD = "SYSDBA", "masterkey"

CONFIG_DB = "ACS.FDB"
LOGS_DB = "ACS_LOGS.FDB"


def _settings():
    from admz.fleet_settings import fleet_settings
    return fleet_settings


def _setting(key: str) -> str:
    try:
        return (_settings().get(key) or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def firebird_enabled() -> bool:
    if os.getenv("ADMZ_ACS_FIREBIRD") == "1":
        return True
    return _setting("acs_firebird_enabled").lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Path discovery
# ---------------------------------------------------------------------------
def fbclient_path() -> Optional[str]:
    """Locate the ACS-shipped Firebird 3 client DLL (fleet-overridable)."""
    override = _setting("acs_fb_fbclient")
    if override and os.path.isfile(override):
        return override
    install = _setting("acs_fb_install") or _DEFAULT_INSTALL
    hits = glob.glob(os.path.join(install, "**", "Firebird3_x64", "fbclient.dll"), recursive=True)
    # prefer the running server's copy
    hits.sort(key=lambda p: ("Core\\Server" not in p, len(p)))
    return hits[0] if hits else None


def data_dir() -> str:
    return _setting("acs_fb_data_dir") or _DEFAULT_DATA


def db_path(name: str) -> str:
    return os.path.join(data_dir(), name)


def firebird_available() -> Tuple[bool, str]:
    """(usable, reason). Cheap checks only — no DB open."""
    try:
        import firebird.driver  # noqa: F401
    except Exception:  # noqa: BLE001
        return False, "firebird-driver not installed"
    fb = fbclient_path()
    if not fb:
        return False, "fbclient.dll not found (ACS not installed here?)"
    if not os.path.isfile(db_path(CONFIG_DB)):
        return False, f"{CONFIG_DB} not found in {data_dir()}"
    return True, "ok"


# ---------------------------------------------------------------------------
# Copy-then-read core (the live DB is never opened — ACS locks it exclusively)
# ---------------------------------------------------------------------------
def _read(db_name: str, sql: str, params: Optional[list] = None) -> List[Dict[str, Any]]:
    """Copy ``db_name`` to a temp file and run one read-only SELECT against the
    copy. Returns rows as dicts (lowercased column names). Raises on failure."""
    fb = fbclient_path()
    if not fb:
        raise RuntimeError("fbclient.dll not found")
    fbdir = os.path.dirname(fb)
    os.environ.setdefault("FIREBIRD", fbdir)
    from firebird.driver import connect, driver_config
    if not driver_config.fb_client_library.value:
        driver_config.fb_client_library.value = fb

    src = db_path(db_name)
    tmp = os.path.join(tempfile.gettempdir(), f"admz_acsfb_{uuid.uuid4().hex[:8]}_{db_name}")
    shutil.copy2(src, tmp)   # shared-read copy; ACS keeps the original
    try:
        con = connect(tmp, user=_FB_USER, password=_FB_PASSWORD, no_gc=True, no_db_triggers=True)
        try:
            cur = con.cursor()
            cur.execute(sql, params or [])
            cols = [d[0].lower() for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            con.close()
        return rows
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


# A ``Reader`` is the injectable seam: (db_name, sql, params) -> list[dict].
Reader = Callable[..., List[Dict[str, Any]]]


# ---------------------------------------------------------------------------
# Rule inventory (ACS.FDB)
# ---------------------------------------------------------------------------
def list_rules(reader: Optional[Reader] = None) -> List[Dict[str, Any]]:
    """The named action-rule inventory: id, name, enabled, + the action types
    each rule runs. Hides the auto-generated ``Predefined*`` per-camera rules."""
    r = reader or _read
    rules = r(CONFIG_DB,
              "SELECT ID, NAME, IS_ENABLED FROM RULE "
              "WHERE NAME NOT STARTING WITH 'Predefined' ORDER BY NAME")
    actions = r(CONFIG_DB, "SELECT RULE_ID, ACTION_TYPE, DISCRIMINATOR FROM ACTION")
    by_rule: Dict[Any, List[str]] = {}
    for a in actions:
        label = (a.get("discriminator") or "").replace("Entity", "").replace("Action", "") \
            or str(a.get("action_type"))
        by_rule.setdefault(a.get("rule_id"), []).append(label)
    out = []
    for rule in rules:
        rid = rule.get("id")
        out.append({
            "id": rid,
            "name": (rule.get("name") or "").strip(),
            "enabled": bool(rule.get("is_enabled")),
            "actions": sorted(set(by_rule.get(rid, []))),
        })
    return out


# ---------------------------------------------------------------------------
# Firing log (ACS_LOGS.FDB) — AlarmEntity rows are named rule firings
# ---------------------------------------------------------------------------
def max_firing_id(reader: Optional[Reader] = None) -> int:
    r = reader or _read
    rows = r(LOGS_DB, "SELECT MAX(ID) AS MAX_ID FROM LOG WHERE DISCRIMINATOR='AlarmEntity'")
    return int((rows[0].get("max_id") if rows else 0) or 0)


def read_new_firings(since_id: int, reader: Optional[Reader] = None) -> List[Dict[str, Any]]:
    """``AlarmEntity`` LOG rows with ID > ``since_id`` (oldest-first).

    ``RULE_ID <> 0`` excludes ACS *system* alarms (e.g. unexpected-server-shutdown
    notices, LOG_CATEGORY=3/LOG_SUB_TYPE=4) — they are also ``AlarmEntity`` rows
    but carry ``RULE_ID=0`` / ``RULE_NAME=NULL`` and are not rule firings (#125).
    """
    r = reader or _read
    # NB: "TRIGGER", "TIMESTAMP" and "VALUE" are Firebird reserved words — quote
    # them (as "TIMESTAMP" is here) in any future query, e.g. against CONTENT_FILTER.
    return r(LOGS_DB,
             "SELECT ID, \"TIMESTAMP\", RULE_ID, RULE_NAME, TITLE, CAMERA_IDS, TRIGGER_TYPE "
             "FROM LOG WHERE DISCRIMINATOR='AlarmEntity' AND RULE_ID <> 0 AND ID > ? ORDER BY ID",
             [int(since_id)])


def normalize_firing(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map a LOG AlarmEntity row → the canonical ``source="acs"`` event record
    (mirrors the webhook shape; the rule name comes straight from the log)."""
    rule = (row.get("rule_name") or "ACS action rule")
    if isinstance(rule, str):
        rule = rule.strip()
    title = row.get("title")
    cams = row.get("camera_ids")
    ts = row.get("timestamp")
    ts_str = str(ts).replace(" ", "T") if ts else ""
    ts_ms = 0
    try:
        import datetime
        if isinstance(ts, datetime.datetime):
            d = ts if ts.tzinfo else ts.replace(tzinfo=datetime.timezone.utc)
            ts_ms = int(d.timestamp() * 1000)
    except Exception:  # noqa: BLE001
        ts_ms = 0
    summary = f"Action rule fired · {rule}" + (f" ({title})" if title else "")
    return {
        "id": f"acsfb-{row.get('id')}",     # stable per LOG row → store dedups on re-read
        "ts": ts_str,
        "ts_ms": ts_ms,
        "source": "acs",
        "type": "ACS/ActionRule",
        "device_id": cams or None,
        "device_name": cams,
        "summary": summary,
        "data": {
            "topic": "ACS/ActionRule",
            "category": "action_rule",
            "rule_name": rule,
            "rule_id": row.get("rule_id"),
            "title": title,
            "via": "firebird",
            "data": {"rule": rule, "camera": cams or ""},
        },
    }
