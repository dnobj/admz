# ADR-0033: Sign in with the box's Windows credentials (windows-local backend)

**Status:** Accepted, in production (2026-06-11).
**Date:** 2026-06-11.
**Relates to:** ADR-0021 (Windows IWA via reverse proxy), ADR-0022 (API keys),
ADR-0023 (LDAP group enrichment).

## Context

Phase 4 shipped real authentication (IWA-via-IIS for browsers, Bearer API
keys for agents) but the zero-config default remained
`ADMZ_AUTH_BACKEND=none` — everyone anonymous. On the reference deployment
(a single-operator homelab, Windows 11 Home, workgroup, no IIS) that meant:

- The web UI/chat user was always `anonymous`, so the CR-4 destructive-tool
  gate flat-refused `restore_device`/`accept_baseline` from chat — surfaced
  live when a P3288 baseline restore failed with PermissionDenied.
- The documented browser path (ADR-0021) is heavyweight here: IIS + ARR on
  Home, NTLM-only without a domain, no LDAP groups (KL-AUTH-004).
- API keys couldn't help browsers: there was **no login page or session
  machinery at all** — keys live in an Authorization header.

The operator's requirement: **sign in with the Windows credentials of the
box** — local accounts on a workgroup machine, domain accounts automatically
if the host is domain-joined — i.e. the same account model Axis Camera
Station Pro uses (ACS grants access to Windows users/groups, local or AD).

## Decision

A new **`windows-local`** backend: a `/login` form whose credentials are
validated **by Windows itself, in process**, plus server-side sessions.

- **Validation** (`admz/win_auth.py`): ctypes `advapi32.LogonUserW`
  (`LOGON32_LOGON_NETWORK`, falling back to `INTERACTIVE` under restrictive
  policy). No new dependencies, no IIS, no LDAP. Bare usernames mean the
  local SAM (domain `"."`); `DOMAIN\user` / `user@domain` work when joined.
  The submitted password exists only for the duration of the call — never
  stored, logged, or echoed (the device-password invariant).
- **Groups from the logon token**: `GetTokenInformation(TokenGroups)` +
  `LookupAccountSidW`, authority prefixes stripped — so a member of the
  local **Administrators** group satisfies the existing
  `ADMZ_REVEAL_GROUPS` gate with zero extra configuration. (Note: ctypes
  prototypes are declared explicitly — default int marshaling truncates
  64-bit HANDLEs.)
- **Sessions** (`admz/session_store.py`): `web_sessions` table in `admz.db`;
  the `admz_session` cookie carries a 256-bit random bearer token stored as
  a SHA-256 hash (high-entropy random needs no slow KDF); server-side TTL
  (`ADMZ_SESSION_TTL_SECONDS`, default 12 h) with sliding expiry; revoked on
  logout. The row snapshots the Principal (groups frozen at login, like
  API-key group snapshots).
- **Backend shape**: `windows-local` = composite `[ApiKeyAuth, SessionAuth]`
  — agents keep Bearer keys; browsers carry the cookie (which also rides
  WebSocket upgrades, so voice authenticates). The generic `composite`
  backend gained SessionAuth in its chain, so IWA deployments get sessions
  too. No trusted-header backend in `windows-local` → no reverse-proxy bind
  restriction.
- **UX**: unauthenticated *page* loads 303-redirect to `/login?next=…`
  (API calls keep JSON 401); the login page is standalone (no sidebar —
  no fleet info leaked pre-auth); logins are rate-limited (5/min/IP via the
  shared limiter) and audited (`auth.login`); the navbar shows the signed-in
  principal + sign-out.
- **Default posture**: the shipped code default remains `none`
  (zero-config dev + test suite); the reference deployment launches with
  `ADMZ_AUTH_BACKEND=windows-local`.

## Consequences

**Positive:**
- Real identity on every surface — web, chat, voice — with the accounts the
  operator already manages (ACS parity). Audit rows name a person; the
  destructive-tool gate stops blocking the legitimate operator.
- Workgroup-compatible; zero new dependencies; IWA can still layer on later
  (the Principal shape is identical, `composite` already chains all three).
- Local `Administrators` membership drives RBAC out of the box.

**Negative:**
- The session cookie travels in plaintext if ADMZ is served over plain HTTP
  beyond localhost (KL-AUTH-006; default bind stays 127.0.0.1; a TLS front
  sets `ADMZ_SESSION_COOKIE_SECURE=1`).
- CSRF surface: cookie auth is ambient. Baseline mitigation is
  `SameSite=Lax` + HttpOnly; per-form CSRF tokens remain the documented gap
  (extends the existing known-gap note).
- No SSO: the user types a password once per session (Negotiate SSO is
  exactly what ADR-0021's IIS path adds later).
- `LogonUserW` requires the account to have logon rights on the box; deny
  policies (e.g. "deny network logon") can block otherwise-valid accounts.

**Alternatives considered:**
- **IIS + IWA now** (ADR-0021): correct for domain deployments; rejected
  here — IIS-on-Home setup, NTLM-only, no groups without AD.
- **In-process SPNEGO**: rejected in ADR-0021 already (complex handshake
  state machine); revisiting it for a workgroup gains little (NTLM).
- **Local ADMZ-specific passwords**: a second credential system to manage;
  rejected in favor of the accounts Windows already has.

## References

- Requirements: [authentication.md](../requirements/authentication.md)
  FR-AUTH-013…015, KL-AUTH-006/007
- Code: `admz/win_auth.py`, `admz/session_store.py`,
  `admz/auth.py::SessionAuth`, `admz/api/routes/auth_web.py`,
  `admz/api/templates/login.html`
- Tests: `tests/test_win_auth.py`, `tests/test_session_store.py`,
  `tests/test_windows_local_backend.py`
