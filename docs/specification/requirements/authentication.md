# Requirements: authentication

Authentication of the **web/REST client → ADMZ HTTP server** boundary.
Other auth boundaries (device-side digest/basic/bearer, Vault, MCP-over-stdio,
at-rest credential encryption) are covered in [security.md](security.md)
and [credential-storage.md](credential-storage.md).

Phase 4 implementation — closes [security.md](security.md) KG-SEC-001.

## Status legend

✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-AUTH-001 — Pluggable auth backends ✅
ADMZ supports five authentication backends, selectable via the
`ADMZ_AUTH_BACKEND` environment variable:
- `none` (default) — synthetic anonymous principal; preserves the
  pre-Phase-4 zero-config behavior and keeps existing tests green.
- `windows` — Windows IWA via reverse-proxy header.
- `api-key` — `Authorization: Bearer admz_<...>` header.
- `windows-local` — browser sign-in with the box's own Windows
  credentials (`/login` → `LogonUserW` → session cookie) + Bearer keys
  for agents. The recommended posture for single-box / workgroup
  deployments without an IIS front (ADR-0033; FR-AUTH-013).
- `composite` — tries API key, then session cookie, then Windows IWA.
  The recommended production default behind IIS — handles browsers and
  programmatic agents transparently.

**Enforced at:** `admz/auth.py::build_auth_backend`. See ADR-0021,
ADR-0022, ADR-0033.

### FR-AUTH-002 — Every non-exempt request is authenticated ✅
A FastAPI middleware (`admz/auth.py::auth_middleware`) runs on every
HTTP request. Exempt paths (health probes, static assets, OpenAPI docs)
short-circuit; everything else routes through the configured backend
before reaching the route handler.

**Exempt paths:** `/health`, `/api/health`, `/static/`, `/api/docs`,
`/api/redoc`, `/api/openapi.json`, `/login`, `/logout` (the login flow
is where a caller *becomes* authenticated; logout must work for expired
sessions so the cookie can be cleared).

### FR-AUTH-003 — Principal carries display info + groups ✅
The authenticated identity is exposed as a `Principal` dataclass with:
- `name` — raw identity string for audit (`DOMAIN\\user`,
  `api-key:bot-name`, `anonymous`)
- `display_name` — short form for UI (`alice`, `bot-name`)
- `domain` — Windows-only
- `groups` — AD group CNs (populated when LDAP enabled; see FR-AUTH-006)
- `source` — `none` / `windows` / `api-key`
- `is_anonymous` — True only for the `NoAuth` synthetic principal

### FR-AUTH-004 — `/api/whoami` returns the current principal ✅
Surfaces the authenticated identity for the web UI's "Signed in as"
indicator and for agents verifying their API key is recognized.
Returns 200 + JSON (always, regardless of backend) with the full
principal shape.

### FR-AUTH-005 — Windows IWA reverse-proxy backend ✅
- Reads username from `REMOTE_USER` header (override:
  `ADMZ_AUTH_REMOTE_USER_HEADER`).
- Parses `DOMAIN\\user`, `DOMAIN/user`, `user@domain.local`, and bare
  username shapes.
- Trusts the header **only** from configured source IPs (default
  `127.0.0.1`, `::1`; override: `ADMZ_AUTH_TRUSTED_PROXIES`). Anything
  else returns 401 with an explanatory error.
- 401 responses include `WWW-Authenticate: Negotiate` so browsers
  re-prompt.

### FR-AUTH-006 — LDAP group enrichment ✅
When `ADMZ_LDAP_ENABLED=true`, `ReverseProxyAuth` queries the configured
directory after parsing `REMOTE_USER` to populate `Principal.groups`.
- Failures are non-fatal — empty groups + logged warning. Auth still
  succeeds.
- Results cached in-memory per username, TTL `ADMZ_LDAP_GROUP_CACHE_TTL`
  (default 300s).
- Service-account credentials in env: `ADMZ_LDAP_BIND_USER`,
  `ADMZ_LDAP_BIND_PASSWORD`.
- See ADR-0023.

### FR-AUTH-007 — API-key backend ✅
- Reads `Authorization: Bearer admz_<...>` header.
- Format: `admz_` prefix + 32 bytes random → ~256 bits entropy.
- Stored hashed (PBKDF2-SHA256, 600,000 iterations, 16-byte salt) in
  the shared SQLite database (`api_keys` table).
- Plaintext returned exactly once on creation; never recoverable.
- Per-key metadata: display_name, created_by, created_at, expires_at,
  last_used_at, revoked, scopes (reserved), groups (snapshot at mint).
- See ADR-0022.

### FR-AUTH-008 — API-key CRUD via REST ✅
`GET /api/api-keys`, `POST /api/api-keys`, `DELETE /api/api-keys/{id}`.
All require auth. The POST response is the only path that exposes the
plaintext.

### FR-AUTH-009 — API-key CLI for bootstrap ✅
`python -m admz api-key {create,list,revoke}` — operators with shell
access can mint the first key without a web UI session.

### FR-AUTH-010 — Composite backend fall-through ✅
With `ADMZ_AUTH_BACKEND=composite`, the auth middleware tries the
configured backends in order (API key first, then Windows IWA). Each
401 falls through to the next; non-401 errors propagate immediately.
If every backend returns 401, the last one's headers (e.g.
`WWW-Authenticate: Negotiate`) are returned to the client.

### FR-AUTH-011 — Audit log records principal on every gated action ✅
Every credential retrieval, API-key mint/revoke, dangerous-op
confirmation, and similar action is recorded in the `audit_log` table
with `requester = principal.name` and `auth_source = principal.source`.
The `requester` parameter on `DeviceRegistry.get_credentials` now
carries real principal data instead of being silently ignored. Closes
[security.md](security.md) KG-SEC-003.

### FR-AUTH-012 — Audit log read endpoint ✅
`GET /api/audit?limit=&action=&requester=&since=` returns recent entries
newest-first, with filters by action, requester, and since-timestamp.

### FR-AUTH-013 — `windows-local` backend: sign in with the box's Windows credentials ✅
A fifth backend (ADR-0033) for hosts without an IIS front (e.g. a
workgroup Windows 11 machine). `/login` validates the submitted
username + password **against Windows itself** via `LogonUserW`
(`admz/win_auth.py`) — local SAM accounts, or domain accounts when the
host is joined — and reads the logon token's **group memberships**
(`GetTokenInformation(TokenGroups)`), so local `Administrators` drives
the reveal gate with no LDAP. The password exists only for the duration
of the Win32 call — never stored, logged, or echoed.
`ADMZ_AUTH_BACKEND=windows-local` = composite `[api-key, session]`:
agents keep Bearer keys, browsers carry the session cookie.

### FR-AUTH-014 — Server-side web sessions ✅
`admz/session_store.py`: `web_sessions` table in `admz.db`; the
`admz_session` cookie (HttpOnly, SameSite=Lax) holds a 256-bit random
bearer token stored as a SHA-256 hash. TTL `ADMZ_SESSION_TTL_SECONDS`
(default 12 h) with sliding expiry; revoked on logout; the row
snapshots the Principal (groups frozen at login, like API-key
snapshots). The cookie rides WebSocket upgrades, so voice authenticates
with the same session. Unauthenticated *page* loads 303-redirect to
`/login?next=…` (same-site targets only); API calls keep JSON 401.

### FR-AUTH-015 — Login attempts are rate-limited and audited ✅
`POST /login` consumes the shared token-bucket limiter (`login` policy:
5 instant, then 1/12 s sustained per client IP → 429) and writes
`auth.login` audit rows for success, bad-credentials, rate-limited, and
unavailable outcomes (with a `method: form|negotiate` detail since
ADR-0035). Failure responses are deliberately generic. `GET /login/sso`
has its own roomier policy (`login-sso`: 15 instant, 1/4 s — one
sign-in legitimately makes 2–3 handshake legs).

### FR-AUTH-016 — Negotiate SSO: continue as the signed-in Windows user ✅
ACS Pro parity (ADR-0035): the login page offers a **"Continue as the
signed-in Windows user"** button above the credential form. It points at
`GET /login/sso`, the only endpoint that ever issues an HTTP `Negotiate`
challenge; the browser and Windows complete the Kerberos/NTLM handshake
(`admz/win_sspi.py` shuttles the token blobs to `AcceptSecurityContext`
— the OS owns the protocol state machine, zero new dependencies). The
completed context's access token yields the username and group
memberships through the same helpers the form login uses, then the same
session/cookie/audit tail (`_establish_session`). NTLM's multi-leg
exchange parks partial contexts per client connection (TTL 30 s).
Failures — unsupporting browser, disabled via `ADMZ_SSO_NEGOTIATE=0`,
handshake error — fall back to the form with a gentle notice
(`/login?sso=failed`); nothing else in the auth chain changes.

## Non-functional requirements

### NFR-AUTH-001 — Startup refuses unsafe binds ✅
When `ADMZ_AUTH_BACKEND` is `windows` or `composite` and `--host` is
anything other than `127.0.0.1`/`::1`/`localhost`,
`admz/__main__.py::_check_bind_safety` exits with code 2 and a clear
error explaining the header-spoofing risk. Override via
`ADMZ_AUTH_INSECURE_BIND_OK=true` for unusual deployments — this logs
a stderr WARNING.

### NFR-AUTH-002 — API-key hashing uses PBKDF2-SHA256 600k iterations ✅
Matches the algorithm used for the confirm-flow password. Same code
path (`secrets.compare_digest` for the verify step) so any future
upgrade to argon2 or similar touches a single place.

### NFR-AUTH-003 — Audit-write failures don't break operations ✅
`AuditLog.record` wraps the SQLite write in try/except; any failure
logs a warning and silently drops the audit row. The intent: never
let an audit-infrastructure issue cascade into denying a legitimate
operation. Tradeoff: audit completeness is best-effort, not guaranteed.

### NFR-AUTH-004 — LDAP failures don't break auth ✅
`LdapGroupResolver.resolve_groups` catches every exception and returns
`[]` with a logged warning. An unreachable DC produces empty groups,
not a 401. Tradeoff: roles depending on group membership silently
become "no roles" during outage — acceptable for soft-failure
semantics.

### NFR-AUTH-005 — Trusted-proxies check is enforced at every request ✅
The reverse-proxy backend re-validates `request.client.host` on every
authentication call, not just at startup. Prevents misconfigurations
where a network change makes uvicorn temporarily reachable.

### NFR-AUTH-006 — All authenticated endpoints emit principal context to logs 📋
Currently audit log carries this, but request logs do not. A future
enhancement adds the principal to the access log format.

## Known limitations

### KL-AUTH-001 — API-key authentication is O(n) over active keys ⚠️
Every request with a Bearer token PBKDF2-verifies against every active
key until a match is found. At 600k iterations per check, this caps
practical fleet size at ~100 active keys before request latency
becomes noticeable. A future O(1) lookup column (HMAC of the key under
a server-side secret, indexed) is the migration path.

### KL-AUTH-002 — Browser SSO "switch user" is browser-dependent ⚠️
Triggering re-auth from a logged-in browser session requires closing
the browser or using a private window. The web UI's "Sign out" link
returns 401 with `WWW-Authenticate: Negotiate`, but Chrome/Edge cache
the Negotiate state across the response. Documented as a UX caveat;
real fix would need browser cooperation we can't unilaterally arrange.

### KL-AUTH-003 — No per-key rate limiting ⚠️
A misbehaving agent with a valid key can hammer ADMZ. The operator's
remedy is to revoke the key. Future enhancement: per-key request
rate limit configurable per row.

### KL-AUTH-004 — Workgroup deployments fall back to NTLM ⚠️
On non-domain-joined hosts, IIS Windows Authentication falls through
to NTLM. Functional but weaker than Kerberos. LDAP enrichment is
unusable in this mode (no DC to query).

### KL-AUTH-005 — Service-account credentials in env vars ⚠️
LDAP bind credentials live in `ADMZ_LDAP_BIND_PASSWORD` (visible to
anyone with shell access on the ADMZ host). Acceptable for typical
threat models; high-security deployments should consider DPAPI-encrypted
config files or a future Vault-integration path.

### KL-AUTH-006 — Session cookie over plain HTTP ⚠️
ADMZ serves plain HTTP; TLS is the reverse proxy's job (NFR-API-003).
With `windows-local` on the default 127.0.0.1 bind the cookie never
leaves the box; serving the UI over plain HTTP across a LAN would expose
it. A TLS-fronted deployment should set `ADMZ_SESSION_COOKIE_SECURE=1`.

### KL-AUTH-007 — CSRF tokens still deferred ⚠️
Cookie-based sessions make auth ambient; the baseline mitigation is
`SameSite=Lax` + HttpOnly (blocks cross-site POSTs in modern browsers).
Per-form CSRF tokens remain the documented gap (same item the
security-conscious-operator persona already tracks for capture/confirm).

### KL-AUTH-008 — Negotiate SSO depends on browser zone policy ⚠️
Browsers only answer a `Negotiate` challenge automatically for hosts
they trust: Edge/Chrome use the Windows Local-Intranet zone (which
includes `localhost` by default — the reference deployment Just Works);
reaching ADMZ by LAN hostname needs the site added to the intranet zone
(or the `AuthServerAllowlist` policy). Firefox requires
`network.negotiate-auth.trusted-uris` in `about:config`. Unsupporting
browsers land on the fallback link to the credential form. On a
workgroup box Negotiate selects NTLM (KL-AUTH-004's caveat applies);
NTLM's multi-leg handshake also requires connection affinity — direct
connections or an affinity-preserving proxy.

### KL-AUTH-009 — UAC token filtering hides Administrators (mitigated) ✅
Network-type logons of *local* admin accounts (both `LogonUserW NETWORK`
form logins and NTLM SSO) yield a UAC-filtered token carrying
`Administrators` deny-only — **observed live** on the first SSO sign-in.
Mitigation (built the same day): both sign-in paths union the token
groups with the account's directory memberships via
`NetUserGetLocalGroups` (`win_auth.local_group_memberships` /
`enriched_groups`) — ADMZ authorizes on group *membership* (the ACS Pro
semantics), not on the token's elevation state. The lookup is
best-effort: a failure leaves the token groups as-is and never breaks a
login.

## References

- ADRs: [0021](../decisions/0021-windows-iwa-via-reverse-proxy.md),
  [0022](../decisions/0022-api-keys-for-agents.md),
  [0023](../decisions/0023-ldap-group-enrichment.md),
  [0033](../decisions/0033-windows-local-credential-auth.md),
  [0035](../decisions/0035-negotiate-sso-login.md)
- Cross-cutting: [security.md](security.md), [configuration.md](configuration.md)
- Deployment: [`docs/DEPLOYMENT_WINDOWS.md`](../../DEPLOYMENT_WINDOWS.md)
- Code: `admz/auth.py`, `admz/api_keys.py`, `admz/audit.py`,
  `admz/ldap_groups.py`, `admz/win_auth.py`, `admz/win_sspi.py`,
  `admz/session_store.py`, `admz/api/routes/auth_web.py`,
  `admz/api/routes/api_keys.py`, `admz/api/routes/audit.py`
