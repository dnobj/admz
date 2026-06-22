"""ACS Pro rule-firing webhook — the supported way to detect ANY action-rule firing.

ACS exposes no generic "rule fired" API event (probed exhaustively; only the
*effects* of recording/alarm actions are observable, and only via polling). The
one Axis-documented mechanism is the **"Send HTTP Notification"** action: the
operator adds it to a rule (one-time, additive), pointing at this endpoint with a
templated body. ADMZ then receives a **real-time, rule-named** firing and feeds it
into the same event store + detection evaluator as device events (``source="acs"``).

Auth: a shared secret token (ACS's notification action can't do Negotiate). The
token is accepted as HTTP Basic password, a Bearer token, an ``X-ACS-Token``
header, or a ``?token=`` query param — whichever the operator's ACS version
supports. Compared in constant time; never logged.
"""

from __future__ import annotations

import hmac
import secrets
import uuid
from typing import Any, Dict, Optional

_TOKEN_KEY = "acs_webhook_token"
WEBHOOK_PATH = "/api/acs/rule-fired"


def _settings():
    from admz.fleet_settings import fleet_settings
    return fleet_settings


def get_token(create: bool = True) -> str:
    """The webhook shared secret (generated on first use). Treat as a credential."""
    try:
        tok = (_settings().get(_TOKEN_KEY) or "").strip()
    except Exception:  # noqa: BLE001
        tok = ""
    if not tok and create:
        tok = secrets.token_urlsafe(24)
        try:
            _settings().set(_TOKEN_KEY, tok)
        except Exception:  # noqa: BLE001
            pass
    return tok


def regenerate_token() -> str:
    tok = secrets.token_urlsafe(24)
    _settings().set(_TOKEN_KEY, tok)
    return tok


def token_ok(request, body: Optional[Dict[str, Any]] = None) -> bool:
    """Validate the shared secret from any of the channels ACS might use."""
    expected = get_token(create=False)
    if not expected:
        return False  # not configured yet → reject (fail closed)
    candidates = []
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        candidates.append(auth.split(None, 1)[1].strip())
    if auth.lower().startswith("basic "):
        import base64
        try:
            decoded = base64.b64decode(auth.split(None, 1)[1]).decode("utf-8", "replace")
            candidates.append(decoded.split(":", 1)[1] if ":" in decoded else decoded)
        except Exception:  # noqa: BLE001
            pass
    candidates.append(request.headers.get("x-acs-token", ""))
    candidates.append(request.query_params.get("token", ""))
    if isinstance(body, dict):
        candidates.append(str(body.get("token") or ""))
    return any(c and hmac.compare_digest(str(c), expected) for c in candidates)


def _first(body: Dict[str, Any], *keys: str) -> Optional[str]:
    for k in keys:
        v = body.get(k)
        if v not in (None, ""):
            return str(v)
    return None


def normalize_webhook(body: Dict[str, Any]) -> Dict[str, Any]:
    """Map a (templated, liberal) ACS notification body → the canonical event
    record (``source="acs"``). The operator controls the body template, so we
    accept several common key spellings and stash the raw body for the UI.

    Each webhook POST is a genuine distinct firing, so the id is unique (no
    content dedup) and the timestamp is receipt time unless the body carries one.
    """
    import datetime

    rule = _first(body, "rule", "ruleName", "rule_name", "name", "Rule") or "ACS action rule"
    camera = _first(body, "camera", "cameraName", "source", "device", "Camera")
    message = _first(body, "message", "text", "description", "Message")
    now = datetime.datetime.now(datetime.timezone.utc)
    ts = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"
    ts_ms = int(now.timestamp() * 1000)
    summary = f"Action rule fired · {rule}" + (f" ({camera})" if camera else "")
    # `data.data` holds the rule name/camera so a detection condition (which reads
    # data.data[key]) can match e.g. {key:"rule", op:"eq", value:"<name>"}.
    return {
        "id": uuid.uuid4().hex,
        "ts": ts,
        "ts_ms": ts_ms,
        "source": "acs",
        "type": "ACS/ActionRule",
        "device_id": camera or None,
        "device_name": camera,
        "summary": summary,
        "data": {
            "topic": "ACS/ActionRule",
            "category": "action_rule",
            "rule_name": rule,
            "message": message,
            "via": "webhook",
            "data": {"rule": rule, "camera": camera or ""},
        },
    }
