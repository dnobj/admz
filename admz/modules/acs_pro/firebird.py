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
    """True when direct Firebird reads are permitted on this installation.

    Delegates to the advanced-capability registry (GH #132) so the switch is
    declared, audited and visible alongside the other privileged ones. Same
    env var (``ADMZ_ACS_FIREBIRD``), same ``acs_firebird_enabled`` setting,
    same precedence — only the parse is now shared.
    """
    from admz import capabilities

    return capabilities.is_active("acs.firebird_read")


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
def _connect_copy(db_name: str) -> Tuple[Any, str]:
    """Copy ``db_name`` to a temp file and open a read-only connection to the
    **copy**. Returns ``(connection, tmp_path)``; the caller closes the
    connection and removes the file. The live DB is never opened (ACS holds an
    exclusive engine lock) — a raw file copy is the only permitted read.

    This is the single seam every read goes through, so a test can count copies.
    """
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
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return con, tmp


def _read_many(db_name: str, queries: List[Any]) -> List[List[Dict[str, Any]]]:
    """Run **N read-only SELECTs against ONE copy** of ``db_name``.

    ``queries`` is a list of ``sql`` strings or ``(sql, params)`` pairs; the
    result is a list of row-lists in the same order. The 22 MB ``.FDB`` is
    copied *once* — a multi-query reader (``rule_anatomy``) that used ``_read``
    per SELECT would copy it once per query.
    """
    con, tmp = _connect_copy(db_name)
    try:
        cur = con.cursor()
        out: List[List[Dict[str, Any]]] = []
        for item in queries:
            if isinstance(item, str):
                sql, params = item, None
            else:
                sql = item[0]
                params = item[1] if len(item) > 1 else None
            cur.execute(sql, params or [])
            cols = [d[0].lower() for d in cur.description]
            out.append([dict(zip(cols, r)) for r in cur.fetchall()])
        return out
    finally:
        try:
            con.close()
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass


def _read(db_name: str, sql: str, params: Optional[list] = None) -> List[Dict[str, Any]]:
    """Copy ``db_name`` to a temp file and run one read-only SELECT against the
    copy. Returns rows as dicts (lowercased column names). Raises on failure."""
    return _read_many(db_name, [(sql, params)])[0]


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
# Rule anatomy (ACS.FDB) — what each rule actually listens to and does
# ---------------------------------------------------------------------------
# ``list_rules`` answers "which rules exist and what action types do they run".
# ``rule_anatomy`` answers "what does this rule listen to, on which device, and
# what does it do, to which device" — the join the demo-inference evidence graph
# needs (#124). Every device reference is resolved to a **canonical MAC**, never
# a raw ACS id, because the MAC is the only key ADMZ and ACS share.
#
# Credential safety: the ``DEVICE`` and ``ACTION`` tables both carry
# ``USERNAME``/``PASSWORD`` columns (device admin creds; HTTP-notify creds).
# Every SELECT below names its columns explicitly and those two are **never**
# among them — redaction by construction rather than by filtering afterwards.
# ``ACTION.URL`` can still carry a secret in userinfo or a query parameter (the
# ADMZ webhook accepts ``?token=``), so URLs are masked on the way out.

_SECRET_QUERY_KEYS = ("token", "password", "passwd", "pwd", "secret", "key",
                      "apikey", "api_key", "auth", "access_token")

# Reserved words in Firebird: "TRIGGER", "TIMESTAMP", "VALUE" must be quoted.
_Q_RULES = (
    "SELECT ID, NAME, IS_ENABLED, REQUIRE_ALL_TRIGGERS, SCHEDULE_ID FROM RULE "
    "WHERE NAME NOT STARTING WITH 'Predefined' ORDER BY NAME, ID"
)
_Q_TRIGGERS = (
    'SELECT ID, RULE_ID, DISCRIMINATOR, TRIGGER_TYPE, CAMERA_ID, DEVICE_ID, PORT_ID, '
    'TOPIC_FILTER, SUBSCRIPTION_FILTER, NICE_NAME, TRIGGER_NAME, TRIGGER_STATE, '
    'IS_STATEFUL, BUTTON_CONFIGURATION_ID FROM "TRIGGER" ORDER BY RULE_ID, ID'
)
_Q_CONTENT_FILTERS = (
    'SELECT ID, DEVICE_EVENT_TRIGGER_ID, NAME, "VALUE", IS_STATE, VALUE_TYPE '
    'FROM CONTENT_FILTER ORDER BY DEVICE_EVENT_TRIGGER_ID, ID'
)
_Q_ACTIONS = (
    "SELECT ID, RULE_ID, DISCRIMINATOR, ACTION_TYPE, DEVICE_ID, CAMERA_ID, PORT_ID, "
    "NEW_STATE, IS_PULSE, IS_TIMED_PULSE, PULSE_LENGTH, TITLE, MESSAGE, SUBJECT, URL, "
    "METHOD, IS_AUTHENTICATION_REQUIRED, CONTENT_TYPE, STREAMING_PROFILE_ID, PRE_BUFFER, "
    "POST_BUFFER, MOBILE_APP_NOTIFICATION_MESSAGE, ASSOCIATED_CAMERA, "
    "DOOR_STATION_CALL_STATE_CHANGE, EVENT_RECIPIENTS, PTZ_PRESET_NAME, PTZ_PRESET_TOKEN, "
    "VIEW_ID, PROFILE_NAME, DELAY_LENGTH FROM ACTION ORDER BY RULE_ID, ID"
)
# NB: DEVICE.USERNAME / DEVICE.PASSWORD deliberately absent.
_Q_DEVICES = (
    "SELECT ID, MAC_ADDRESS, MODEL, MANUFACTURER, IP_ADDRESS, HOSTNAME, PRODUCT_TYPE "
    "FROM DEVICE ORDER BY ID"
)
_Q_CAMERAS = "SELECT ID, NAME, DEVICE_ID, IS_ENABLED FROM CAMERA ORDER BY ID"
_Q_IO_PORTS = ("SELECT ID, DEVICE_ID, NAME, PORT_TYPE, PORT_IDENTIFIER, IS_ENABLED "
               "FROM IO_PORT ORDER BY ID")
_Q_PROFILES = "SELECT ID, CAMERA_ID FROM STREAMING_PROFILE ORDER BY ID"
_Q_SCHEDULES = "SELECT ID, NAME, DISCRIMINATOR FROM SCHEDULE ORDER BY ID"

_ANATOMY_QUERIES = [_Q_RULES, _Q_TRIGGERS, _Q_CONTENT_FILTERS, _Q_ACTIONS,
                    _Q_DEVICES, _Q_CAMERAS, _Q_IO_PORTS, _Q_PROFILES, _Q_SCHEDULES]


def _kind(discriminator: Any, suffix: str) -> str:
    """``"DeviceEventTriggerEntity"`` → ``"DeviceEvent"`` (suffix ``"Trigger"``);
    ``"IOActionEntity"`` → ``"IO"`` (suffix ``"Action"``)."""
    s = str(discriminator or "").strip()
    if s.endswith("Entity"):
        s = s[:-len("Entity")]
    if suffix and s != suffix and s.endswith(suffix):
        s = s[:-len(suffix)]
    return s


def redact_url(url: Any) -> Optional[str]:
    """Mask secrets an ACS HTTP-notify URL may carry: ``user:pass@`` userinfo and
    token-ish query parameters (the ADMZ webhook itself accepts ``?token=``)."""
    if url in (None, ""):
        return None
    text = str(url)
    try:
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
        parts = urlsplit(text)
        netloc = parts.netloc
        if "@" in netloc:
            netloc = "***@" + netloc.rsplit("@", 1)[1]
        query = parts.query
        if query:
            pairs = parse_qsl(query, keep_blank_values=True)
            query = urlencode([
                (k, "***" if k.lower() in _SECRET_QUERY_KEYS else v) for k, v in pairs
            ])
        return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))
    except Exception:  # noqa: BLE001 — never let redaction failure leak the raw URL
        return "***"


def acs_id_int(value: Any) -> Optional[int]:
    """Normalize an ACS device/camera id to its integer key.

    ACS spells the same id three ways: the Firebird primary key ``14070``, the
    live-API composite ``"14070_<server-guid>"``, and the wrapped
    ``{"Id": "14070_<guid>"}``. **Verified live on ACS 6.16.19560**: the integer
    prefix of the API ``DeviceId`` *is* ``DEVICE.ID``, and likewise
    ``CameraId`` ↔ ``CAMERA.ID`` (the whole ACS join rests on this).
    """
    if isinstance(value, dict):
        value = value.get("Id") or value.get("id")
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    head = str(value).strip().split("_", 1)[0]
    try:
        return int(head)
    except ValueError:
        return None


def _device_ref(row: Optional[Dict[str, Any]], join_method: str) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    from admz.device_registry import canonical_mac
    return {
        "acs_device_id": row.get("id"),
        "mac": canonical_mac(row.get("mac_address") or "") or None,
        "ip": (row.get("ip_address") or None),
        "model": (row.get("model") or None),
        "name": (row.get("hostname") or row.get("model") or None),
        "product_type": (row.get("product_type") or None),
        "join_method": join_method,
    }


def build_device_resolver(
    fb_devices: List[Dict[str, Any]],
    acs_api_devices: Optional[List[Dict[str, Any]]] = None,
) -> Callable[[Any], Optional[Dict[str, Any]]]:
    """Return ``resolve(device_id) -> device-ref | None`` over the three paths.

    Tried in order, each recording how it matched so the evidence line can say so:

    1. ``api_device_id`` — the live ``DeviceListFacade``/``CameraListFacade`` row
       whose ``DeviceId`` shares this integer key, taking its ``MacAddress``;
    2. ``firebird_device_mac`` — the ``DEVICE`` table's own ``MAC_ADDRESS``;
    3. ``device_serial_number`` — the API row's ``DeviceSerialNumber`` (on Axis
       devices the serial *is* the MAC), for API rows carrying no ``MacAddress``.

    Returns ``None`` for an id present in no source — the caller reports that
    reference as unresolved rather than dropping it.
    """
    from admz.device_registry import canonical_mac

    by_id: Dict[int, Dict[str, Any]] = {}
    for row in fb_devices or []:
        key = acs_id_int(row.get("id"))
        if key is not None:
            by_id[key] = row

    api_by_id: Dict[int, Dict[str, Any]] = {}
    for row in acs_api_devices or []:
        key = acs_id_int(row.get("DeviceId") if "DeviceId" in row else row.get("Id"))
        if key is not None:
            api_by_id.setdefault(key, row)

    def resolve(device_id: Any) -> Optional[Dict[str, Any]]:
        key = acs_id_int(device_id)
        if key is None:
            return None
        fb_row = by_id.get(key)
        api_row = api_by_id.get(key)

        # 1. supported path: the live API's MacAddress for this DeviceId.
        if api_row and canonical_mac(api_row.get("MacAddress") or ""):
            merged = dict(fb_row or {"id": key})
            merged["mac_address"] = api_row.get("MacAddress")
            merged.setdefault("model", api_row.get("Model"))
            return _device_ref(merged, "api_device_id")

        # 2. the Firebird DEVICE row's own MAC.
        if fb_row and canonical_mac(fb_row.get("mac_address") or ""):
            return _device_ref(fb_row, "firebird_device_mac")

        # 3. the API row's serial number (Axis serial == MAC).
        if api_row and canonical_mac(api_row.get("DeviceSerialNumber")
                                     or api_row.get("SerialNumber") or ""):
            merged = dict(fb_row or {"id": key})
            merged["mac_address"] = (api_row.get("DeviceSerialNumber")
                                     or api_row.get("SerialNumber"))
            merged.setdefault("model", api_row.get("Model"))
            return _device_ref(merged, "device_serial_number")

        if fb_row:
            return _device_ref(fb_row, "acs_device_id_only")
        return None

    return resolve


def rule_anatomy(
    reader: Optional[Reader] = None,
    acs_api_devices: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Per rule: what it listens to, on which device, and what it does to which
    device — with every device reference resolved to a canonical MAC.

    ``[{id, name, enabled, require_all_triggers, schedule:{id,name,kind},
       triggers:[{id, kind, topic, filters[], device|None, join_method, …}],
       actions:[{id, kind, target_device|None, join_method, params{}}],
       unresolved[]}]``

    Hides the auto-generated ``Predefined*`` per-camera rules, exactly as
    ``list_rules`` does. With the default reader the whole thing costs **one**
    copy of the 22 MB ``.FDB`` (``_read_many``); passing ``reader`` (the test
    seam) runs the same SQL query-by-query.
    """
    if reader is None:
        results = _read_many(CONFIG_DB, _ANATOMY_QUERIES)
    else:
        results = [reader(CONFIG_DB, sql) for sql in _ANATOMY_QUERIES]
    (rules, triggers, content_filters, actions,
     devices, cameras, io_ports, profiles, schedules) = results

    resolve = build_device_resolver(devices, acs_api_devices)
    cameras_by_id = {acs_id_int(c.get("id")): c for c in cameras or []}
    ports_by_id = {acs_id_int(p.get("id")): p for p in io_ports or []}
    profiles_by_id = {acs_id_int(p.get("id")): p for p in profiles or []}
    schedules_by_id = {acs_id_int(s.get("id")): s for s in schedules or []}

    filters_by_trigger: Dict[Any, List[Dict[str, Any]]] = {}
    for cf in content_filters or []:
        filters_by_trigger.setdefault(acs_id_int(cf.get("device_event_trigger_id")), []).append({
            "name": cf.get("name"),
            "value": cf.get("value"),
            "is_state": bool(cf.get("is_state")),
        })

    def _via_camera(camera_id: Any) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        cam = cameras_by_id.get(acs_id_int(camera_id))
        return cam, (resolve(cam.get("device_id")) if cam else None)

    def _device_for(row: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any], bool]:
        """``(device-ref, extra params, carried_a_device_reference)``.

        The third value separates *"this row names no device at all"* (an ACS
        server-side alarm action, an HTTPS or manual trigger — correct, not a
        failure) from *"this row named one and the join missed"*, which is what
        the caller reports as ``unresolved``.
        """
        extra: Dict[str, Any] = {}
        if row.get("device_id") not in (None, ""):
            return resolve(row.get("device_id")), extra, True
        if row.get("port_id") not in (None, ""):
            port = ports_by_id.get(acs_id_int(row.get("port_id")))
            if port:
                extra["port"] = {"id": port.get("id"), "name": port.get("name"),
                                 "identifier": port.get("port_identifier"),
                                 "type": port.get("port_type")}
                return resolve(port.get("device_id")), extra, True
            return None, extra, True
        if row.get("streaming_profile_id") not in (None, ""):
            prof = profiles_by_id.get(acs_id_int(row.get("streaming_profile_id")))
            if prof:
                cam, dev = _via_camera(prof.get("camera_id"))
                if cam:
                    extra["camera"] = {"id": cam.get("id"), "name": cam.get("name")}
                return dev, extra, True
            return None, extra, True
        for col in ("camera_id", "associated_camera"):
            if row.get(col) not in (None, ""):
                cam, dev = _via_camera(row.get(col))
                if cam:
                    extra["camera"] = {"id": cam.get("id"), "name": cam.get("name")}
                return dev, extra, True
        return None, extra, False

    triggers_by_rule: Dict[Any, List[Dict[str, Any]]] = {}
    for t in triggers or []:
        device, extra, had_ref = _device_for(t)
        entry = {
            "device_ref_unresolved": bool(had_ref and device is None),
            "id": t.get("id"),
            "kind": _kind(t.get("discriminator"), "Trigger"),
            "trigger_type": t.get("trigger_type"),
            "topic": t.get("topic_filter") or None,
            "subscription_filter": t.get("subscription_filter") or None,
            "nice_name": t.get("nice_name") or None,
            "trigger_name": t.get("trigger_name") or None,
            "stateful": bool(t.get("is_stateful")),
            "button_configuration_id": t.get("button_configuration_id"),
            "filters": filters_by_trigger.get(acs_id_int(t.get("id")), []),
            "device": device,
            "join_method": (device or {}).get("join_method"),
        }
        entry.update(extra)
        triggers_by_rule.setdefault(acs_id_int(t.get("rule_id")), []).append(entry)

    _ACTION_PARAM_COLS = (
        "new_state", "is_pulse", "is_timed_pulse", "pulse_length", "title", "message",
        "subject", "method", "is_authentication_required", "content_type",
        "streaming_profile_id", "pre_buffer", "post_buffer",
        "mobile_app_notification_message", "door_station_call_state_change",
        "event_recipients", "ptz_preset_name", "ptz_preset_token", "view_id",
        "profile_name", "delay_length",
    )
    actions_by_rule: Dict[Any, List[Dict[str, Any]]] = {}
    for a in actions or []:
        device, extra, had_ref = _device_for(a)
        params = {k: a.get(k) for k in _ACTION_PARAM_COLS if a.get(k) not in (None, "")}
        params.update(extra)
        if a.get("url") not in (None, ""):
            params["url"] = redact_url(a.get("url"))
        actions_by_rule.setdefault(acs_id_int(a.get("rule_id")), []).append({
            "device_ref_unresolved": bool(had_ref and device is None),
            "id": a.get("id"),
            "kind": _kind(a.get("discriminator"), "Action"),
            "action_type": a.get("action_type"),
            "target_device": device,
            "join_method": (device or {}).get("join_method"),
            "params": params,
        })

    out: List[Dict[str, Any]] = []
    for rule in rules or []:
        rid = acs_id_int(rule.get("id"))
        sched = schedules_by_id.get(acs_id_int(rule.get("schedule_id")))
        rule_triggers = triggers_by_rule.get(rid, [])
        rule_actions = actions_by_rule.get(rid, [])
        # Only genuine join failures — a rule whose alarm action or HTTPS trigger
        # names no device is correct, not unresolved.
        unresolved = ([f"trigger:{t['id']}" for t in rule_triggers
                       if t["device_ref_unresolved"]]
                      + [f"action:{a['id']}" for a in rule_actions
                         if a["device_ref_unresolved"]])
        out.append({
            "id": rule.get("id"),
            "name": (rule.get("name") or "").strip(),
            "enabled": bool(rule.get("is_enabled")),
            "require_all_triggers": bool(rule.get("require_all_triggers")),
            "schedule": ({"id": sched.get("id"), "name": (sched.get("name") or "").strip(),
                          "kind": _kind(sched.get("discriminator"), "Schedule")}
                         if sched else None),
            "triggers": rule_triggers,
            "actions": rule_actions,
            "unresolved": unresolved,
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
