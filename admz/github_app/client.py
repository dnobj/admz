"""GitHub App API client: sign the App JWT, mint installation tokens, exchange a
manifest-conversion code, list installation repos.

RS256 JWTs are signed with the already-present ``cryptography`` package (no PyJWT
dependency). httpx style mirrors ``admz/survey/github.py`` (sync
``httpx.Client(timeout=30)``, ``Accept: application/vnd.github+json``); the http
session is injectable for tests. Tokens/keys are never logged.
"""

from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

GITHUB_API = "https://api.github.com"
_API_VERSION = "2022-11-28"

# installation_id -> (token, expires_epoch). Installation tokens live 1h; we
# refresh a few minutes early. Module-level so the singleton GitRepo reuses it.
_token_cache: Dict[str, "tuple[str, float]"] = {}


class GitHubAppError(Exception):
    """Any failure talking to the GitHub App API (surfaces a short message)."""


def _b64url(raw: bytes) -> bytes:
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


def app_jwt(app_id, private_key_pem: str, *, now: Optional[float] = None) -> str:
    """Sign a short-lived (10 min) RS256 App JWT used to authenticate *as the
    App* (to mint installation tokens). GitHub requires ``exp`` <= 10 min out and
    tolerates a little clock skew, so we backdate ``iat`` 60s."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    pem_bytes = private_key_pem.encode() if isinstance(private_key_pem, str) else private_key_pem
    key = serialization.load_pem_private_key(pem_bytes, password=None)

    iat = int(now if now is not None else time.time())
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"},
                                separators=(",", ":")).encode())
    payload = _b64url(json.dumps({"iat": iat - 60, "exp": iat + 9 * 60, "iss": str(app_id)},
                                 separators=(",", ":")).encode())
    signing_input = header + b"." + payload
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return (signing_input + b"." + _b64url(signature)).decode("ascii")


# ---------------------------------------------------------------------------
# http plumbing
# ---------------------------------------------------------------------------


def _client(session=None):
    if session is not None:
        return session, False
    import httpx
    return httpx.Client(timeout=30), True


def _headers(bearer: Optional[str] = None) -> Dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": _API_VERSION,
    }
    if bearer:
        h["Authorization"] = f"Bearer {bearer}"
    return h


def _request(method: str, url: str, *, session=None, bearer=None,
             json_body=None) -> Any:
    client, owned = _client(session)
    try:
        resp = client.request(method, url, headers=_headers(bearer), json=json_body)
    except Exception as exc:  # noqa: BLE001 - network/transport
        raise GitHubAppError(f"GitHub request failed: {exc}") from exc
    finally:
        if owned:
            try:
                client.close()
            except Exception:
                pass
    if resp.status_code // 100 != 2:
        body = (resp.text or "")[:300]
        raise GitHubAppError(f"GitHub {method} {url} -> {resp.status_code}: {body}")
    if not resp.content:
        return None
    return resp.json()


# ---------------------------------------------------------------------------
# App operations
# ---------------------------------------------------------------------------


def exchange_manifest_code(code: str, *, session=None) -> Dict[str, Any]:
    """Convert a one-time manifest ``code`` (from GitHub's create redirect) into
    the new App's credentials: {id, slug, pem, client_id, client_secret, ...}.
    The ``code`` is itself the authorization (no bearer)."""
    data = _request("POST", f"{GITHUB_API}/app-manifests/{code}/conversions",
                    session=session)
    if not data or "id" not in data or "pem" not in data:
        raise GitHubAppError("manifest conversion returned no App credentials")
    return data


def get_installation_token(app_id, private_key_pem: str, installation_id, *,
                           session=None, use_cache: bool = True,
                           now: Optional[float] = None) -> str:
    """Return a valid installation access token, minting a fresh one if the
    cached token is missing or within 5 min of expiry."""
    key = str(installation_id)
    t = time.time() if now is None else now
    if use_cache:
        cached = _token_cache.get(key)
        if cached and cached[1] - 300 > t:
            return cached[0]

    jwt = app_jwt(app_id, private_key_pem, now=now)
    data = _request(
        "POST",
        f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
        session=session, bearer=jwt,
    )
    token = (data or {}).get("token")
    if not token:
        raise GitHubAppError("installation token response had no token")
    expires_epoch = _parse_expiry((data or {}).get("expires_at"), fallback=t + 3600)
    _token_cache[key] = (token, expires_epoch)
    return token


def list_installation_repositories(installation_token: str, *,
                                   session=None) -> List[Dict[str, Any]]:
    """Repos the installation can access — used to confirm/resolve the config
    repo. Returns a list of {full_name, owner, name}."""
    data = _request("GET", f"{GITHUB_API}/installation/repositories",
                    session=session, bearer=installation_token)
    out = []
    for r in (data or {}).get("repositories", []):
        out.append({
            "full_name": r.get("full_name"),
            "owner": (r.get("owner") or {}).get("login"),
            "name": r.get("name"),
        })
    return out


def clear_token_cache(installation_id=None) -> None:
    if installation_id is None:
        _token_cache.clear()
    else:
        _token_cache.pop(str(installation_id), None)


def _parse_expiry(expires_at: Optional[str], *, fallback: float) -> float:
    if not expires_at:
        return fallback
    try:
        dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:  # noqa: BLE001
        return fallback
