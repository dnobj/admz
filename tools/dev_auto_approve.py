"""Dev-only auto-approver for ADMZ confirmation gates (NOT for production).

ADMZ's `url_only` / `url_and_password` gates are deliberately *human-only*:
the in-process LLM/MCP path cannot self-approve (ADR-0005/0006). That makes
full-stack end-to-end testing of approval-requiring flows impossible for an
unattended agent.

This script closes that gap **without weakening any production code**. It is
an automated stand-in for the human: it watches the shared confirm store for
pending sessions and drives the *real* approval endpoint
(`POST /api/chat/confirm/{token}`) — the same route the in-chat approval
widget uses. The gate logic, password verification, execution, and audit
rows all run exactly as in production. Nothing in the `admz/` package changes
behaviour because of this file; it lives in `tools/` and is never imported by
the app, so production wheels don't even contain it.

Safety (every layer must hold; otherwise it refuses to act):
  1. `ADMZ_DEV_AUTO_APPROVE=1` must be set in the environment.
  2. Scope: by default only sessions whose device(s) carry a `lab`/`test`
     tag are approved. A plan is in scope only if ALL its devices are tagged.
     `--all` disables the tag scope but additionally requires
     `--i-understand-this-is-not-production`.
  3. Every approval writes a loud `dev.auto_approve` audit row stamped
     `confirmed_by="dev-auto-approver"`, plus a stderr line, so a dev
     approval can never be mistaken for a real human one.
  4. Fails closed: if the guard env var is unset, it exits without acting.

Password: if the dev environment has no `confirm_password_hash` fleet
setting, ADMZ already downgrades `url_and_password` -> `url_only`, so no
password is needed. To exercise the password path, set a known dev password
as the fleet setting and pass it here via `ADMZ_DEV_CONFIRM_PASSWORD`.

Usage (run from C:\\admz\\admz with the API server up on :4242):

    # one-shot: approve everything currently pending and in-scope
    ADMZ_DEV_AUTO_APPROVE=1 .venv/Scripts/python.exe tools/dev_auto_approve.py

    # watch mode ("step away and let it run")
    ADMZ_DEV_AUTO_APPROVE=1 .venv/Scripts/python.exe tools/dev_auto_approve.py --watch

    # approve specific tokens only
    ADMZ_DEV_AUTO_APPROVE=1 .venv/Scripts/python.exe tools/dev_auto_approve.py <token> [<token> ...]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence, Set

# Force UTF-8 stdout on Windows so banners/box chars don't blow up cp1252.
if sys.platform == "win32":  # pragma: no cover
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass


GUARD_ENV = "ADMZ_DEV_AUTO_APPROVE"
PASSWORD_ENV = "ADMZ_DEV_CONFIRM_PASSWORD"
DEFAULT_ALLOW_TAGS = {"lab", "test"}
DEV_CONFIRMED_BY = "dev-auto-approver"


# --------------------------------------------------------------------------
# Guards
# --------------------------------------------------------------------------


def guard_enabled(env: Optional[dict] = None) -> bool:
    """True only when the explicit dev guard env var is truthy."""
    env = env if env is not None else os.environ
    return (env.get(GUARD_ENV) or "").strip().lower() in ("1", "true", "yes", "on")


def load_allow_tags(raw: Optional[str]) -> Set[str]:
    if not raw:
        return set(DEFAULT_ALLOW_TAGS)
    return {t.strip().lower() for t in raw.split(",") if t.strip()}


# --------------------------------------------------------------------------
# Scope: which sessions may be auto-approved
# --------------------------------------------------------------------------


def device_ids_for_session(session: Any) -> List[str]:
    """The device(s) a confirm session affects.

    Single-op sessions carry one device_id. Plan sessions store
    ``device_id="multiple"`` but serialize the real per-step device_ids in
    ``plan_steps_json`` (the C-1 cross-process field) — use those.
    """
    if getattr(session, "is_plan", False):
        try:
            steps = json.loads(getattr(session, "plan_steps_json", "") or "[]")
        except (json.JSONDecodeError, TypeError):
            steps = []
        return sorted({s.get("device_id", "") for s in steps if s.get("device_id")})
    did = getattr(session, "device_id", "")
    return [did] if did and did != "multiple" else []


def session_in_scope(registry: Any, session: Any, allow_tags: Set[str]) -> bool:
    """A session is in scope iff every affected device exists and carries at
    least one allowed tag. Empty / unknown device set is out of scope."""
    device_ids = device_ids_for_session(session)
    if not device_ids:
        return False
    for did in device_ids:
        try:
            if not registry.device_exists(did):
                return False
            info = registry.get_device_info(did) or {}
        except Exception:
            return False
        tags = {str(t).lower() for t in (info.get("tags") or [])}
        if not (tags & allow_tags):
            return False
    return True


# --------------------------------------------------------------------------
# Confirm-store reads (read-only; no changes to the shipped package)
# --------------------------------------------------------------------------


def find_pending_tokens(db_path: str) -> List[str]:
    """Read-only SELECT of currently-pending confirm tokens.

    Direct SQL so this dev tool needs no new method on the production
    ConfirmStore. Expiry is enforced later by ConfirmStore.get_session.
    """
    if not Path(db_path).exists():
        return []
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        rows = conn.execute(
            "SELECT token FROM confirm_sessions WHERE status='pending' "
            "ORDER BY created_at"
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    return [r[0] for r in rows]


# --------------------------------------------------------------------------
# Approval — drive the real endpoint, then write a distinct dev audit row
# --------------------------------------------------------------------------


class _DevPrincipal:
    name = DEV_CONFIRMED_BY
    source = "dev"


def _audit_dev_approval(session: Any, *, success: bool, detail: str) -> None:
    """Write an unmistakable dev-approval row to the audit log (best effort)."""
    try:
        from admz.audit import record_event

        if getattr(session, "is_plan", False):
            resource = f"plan:{session.plan_id}"
        else:
            resource = f"device:{session.device_id}/op:{session.operation_id}"
        record_event(
            _DevPrincipal(),
            "dev.auto_approve",
            resource=resource,
            success=success,
            error_message="" if success else detail,
            details={
                "confirmed_by": DEV_CONFIRMED_BY,
                "confirmation_level": getattr(session, "confirmation_level", ""),
                "is_plan": getattr(session, "is_plan", False),
                "note": "DEV auto-approval — not a human approval",
            },
        )
    except Exception as exc:  # pragma: no cover — audit must never block
        print(f"  (warning: dev audit row failed: {exc})", file=sys.stderr)


def _default_post(url: str, data: dict) -> Any:
    import httpx

    # Under an enforcing auth backend (ADR-0033 windows-local etc.) the
    # confirm endpoint requires an authenticated caller. Mint a lab API
    # key (`python -m admz api-key create --name dev-auto-approver`) and
    # export it as ADMZ_DEV_API_KEY; with no key set, requests go out
    # unauthenticated (fine for ADMZ_AUTH_BACKEND=none).
    headers = {}
    dev_key = os.getenv("ADMZ_DEV_API_KEY")
    if dev_key:
        headers["Authorization"] = f"Bearer {dev_key}"
    return httpx.post(url, data=data, timeout=30.0, headers=headers)


def approve_token(
    token: str,
    *,
    base_url: str,
    password: Optional[str],
    registry: Any,
    allow_tags: Set[str],
    scope_all: bool,
    store: Any,
    http_post: Callable[[str, dict], Any] = _default_post,
) -> str:
    """Approve one token via the real JSON confirm endpoint.

    Returns a short status string: ``approved`` | ``out-of-scope`` |
    ``expired`` | ``error:<msg>``.
    """
    session = store.get_session(token)
    if session is None:
        return "expired"

    if not scope_all and not session_in_scope(registry, session, allow_tags):
        device_ids = device_ids_for_session(session) or ["<none>"]
        print(
            f"  ↷ skip {token[:10]}… — device(s) {device_ids} not tagged "
            f"{sorted(allow_tags)}",
            file=sys.stderr,
        )
        return "out-of-scope"

    data = {}
    if password:
        data["confirm_password"] = password

    try:
        resp = http_post(f"{base_url.rstrip('/')}/api/chat/confirm/{token}", data)
    except Exception as exc:
        _audit_dev_approval(session, success=False, detail=f"post failed: {exc}")
        return f"error:{exc}"

    status_code = getattr(resp, "status_code", 0)
    try:
        body = resp.json()
    except Exception:
        body = {}

    if status_code == 200 and body.get("status") == "completed":
        outcome = body.get("outcome", {})
        ok = bool(outcome.get("success")) if isinstance(outcome, dict) else False
        _audit_dev_approval(session, success=True, detail="")
        target = device_ids_for_session(session) or [getattr(session, "device_id", "?")]
        print(
            f"  ✔ APPROVED (dev) {token[:10]}… → {getattr(session, 'operation_id', 'plan')} "
            f"on {target} — execution success={ok}",
            file=sys.stderr,
        )
        return "approved"

    detail = body.get("error") or body.get("status") or f"HTTP {status_code}"
    _audit_dev_approval(session, success=False, detail=str(detail))
    print(f"  ✘ NOT approved {token[:10]}… — {detail}", file=sys.stderr)
    return f"error:{detail}"


# --------------------------------------------------------------------------
# Runners
# --------------------------------------------------------------------------


def run_once(
    *,
    base_url: str,
    password: Optional[str],
    registry: Any,
    allow_tags: Set[str],
    scope_all: bool,
    store: Any,
    db_path: str,
    tokens: Optional[Sequence[str]] = None,
) -> dict:
    toks = list(tokens) if tokens else find_pending_tokens(db_path)
    counts = {"approved": 0, "out-of-scope": 0, "expired": 0, "error": 0}
    for tok in toks:
        result = approve_token(
            tok, base_url=base_url, password=password, registry=registry,
            allow_tags=allow_tags, scope_all=scope_all, store=store,
        )
        key = "error" if result.startswith("error") else result
        counts[key] = counts.get(key, 0) + 1
    return counts


def _banner(base_url: str, allow_tags: Set[str], scope_all: bool, watch: bool) -> None:
    scope = "ALL DEVICES (scope guard OFF)" if scope_all else f"devices tagged {sorted(allow_tags)}"
    print(
        "\n".join([
            "┌────────────────────────────────────────────────────────────┐",
            "│  ADMZ DEV AUTO-APPROVER — NOT FOR PRODUCTION                │",
            "│  Auto-approves confirmation gates as a stand-in for a human │",
            "└────────────────────────────────────────────────────────────┘",
            f"  endpoint : {base_url}",
            f"  scope    : {scope}",
            f"  mode     : {'watch' if watch else 'one-shot'}",
            "",
        ]),
        file=sys.stderr,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Dev-only ADMZ confirmation auto-approver.")
    parser.add_argument("tokens", nargs="*", help="Specific tokens to approve (default: all pending).")
    parser.add_argument("--base-url", default=os.getenv("ADMZ_BASE_URL", "http://localhost:4242"))
    parser.add_argument("--allow-tags", default=None, help="Comma list of device tags in scope (default: lab,test).")
    parser.add_argument("--all", action="store_true", help="Approve regardless of device tags (requires the next flag).")
    parser.add_argument("--i-understand-this-is-not-production", action="store_true")
    parser.add_argument("--watch", action="store_true", help="Keep polling for new pending sessions.")
    parser.add_argument("--interval", type=float, default=1.0, help="Watch poll interval seconds (default 1.0).")
    args = parser.parse_args(argv)

    if not guard_enabled():
        print(
            f"Refusing to run: set {GUARD_ENV}=1 to enable the dev auto-approver. "
            "This tool is for development only and never runs in production.",
            file=sys.stderr,
        )
        return 2

    scope_all = bool(args.all)
    if scope_all and not args.i_understand_this_is_not_production:
        print(
            "--all disables the device-tag scope guard. Re-run with "
            "--i-understand-this-is-not-production to confirm.",
            file=sys.stderr,
        )
        return 2

    allow_tags = load_allow_tags(args.allow_tags)
    password = os.getenv(PASSWORD_ENV) or None

    from admz.factory import create_device_registry
    from admz.api.confirm_store import ConfirmStore

    registry = create_device_registry()
    store = ConfirmStore()
    db_path = store._db_path  # same DB the server writes to

    _banner(args.base_url, allow_tags, scope_all, args.watch)

    common = dict(
        base_url=args.base_url, password=password, registry=registry,
        allow_tags=allow_tags, scope_all=scope_all, store=store, db_path=db_path,
    )

    if not args.watch:
        counts = run_once(tokens=args.tokens or None, **common)
        print(f"  done: {counts}", file=sys.stderr)
        return 0

    print("  watching for pending confirmations — Ctrl-C to stop.", file=sys.stderr)
    try:
        while True:
            run_once(**common)
            time.sleep(max(0.2, args.interval))
    except KeyboardInterrupt:
        print("\n  stopped.", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
