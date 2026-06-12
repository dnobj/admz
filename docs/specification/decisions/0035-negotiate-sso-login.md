# ADR-0035: "Continue as the signed-in Windows user" — in-process Negotiate SSO at the login page

**Status:** Accepted (2026-06-11).
**Date:** 2026-06-11.
**Relates to:** ADR-0033 (windows-local backend — this closes its stated
"No SSO" negative), ADR-0021 (IWA via reverse proxy — partially
supersedes its in-process-SPNEGO rejection).

## Context

ADR-0033's login form authenticates real Windows accounts, but the user
types a password every session. Axis Camera Station Pro — on the same
box — signs in as the **current Windows user** with zero typing
("Current user", with "Other user" as the fallback). The operator asked
for the same option in ADMZ.

For a *browser* to authenticate as the current Windows session without a
password, the standard mechanism is HTTP `Negotiate` (SPNEGO): the
browser and the server complete a Kerberos/NTLM handshake. ADR-0021
rejected doing this in-process, citing new Windows-specific dependencies
(`pyspnego`) and a complex protocol state machine — and chose IIS as the
front. Both objections were really about *implementing SPNEGO in
Python*. They don't apply to the approach taken here:

- **Windows owns the state machine.** SSPI's `AcceptSecurityContext`
  (secur32.dll) *is* the Negotiate implementation — the same one IIS
  calls. ADMZ shuttles opaque base64 blobs between the browser and the
  OS; there is no SPNEGO parsing in Python and **no new dependency**
  (plain ctypes with explicit prototypes, the `win_auth.py` pattern).
- **This deployment has no IIS path.** The reference box is Windows 11
  Home, workgroup — exactly the case ADR-0033 exists for.

## Decision

A **single SSO endpoint, `GET /login/sso`**, plus a "Continue as the
signed-in Windows user" button on the login page above the existing
credential form (ACS Pro parity: current user *or* a different user).

- `admz/win_sspi.py` (new): `NegotiateHandshake` wraps
  `AcquireCredentialsHandleW("Negotiate", INBOUND)` +
  `AcceptSecurityContext`; on completion, `QuerySecurityContextToken`
  yields a real access token, read with the **same helpers the form
  login uses** (`win_auth._groups_from_token`, SID lookup) — so group
  gates behave identically for both sign-in methods. A local account's
  machine-name "domain" is normalized away so SSO and form sign-ins of
  the same account produce the same principal name.
- NTLM is multi-leg on one TCP connection: partial contexts park in
  `PendingHandshakes`, keyed by client (host, port), TTL 30 s, capped.
  Kerberos (when domain-joined) usually completes in one leg — the same
  code path handles both; Negotiate picks the protocol.
- **Only `/login/sso` ever issues a `Negotiate` challenge** — no other
  page can trigger a browser auth prompt, and the rest of the auth chain
  (sessions, API keys, middleware, WebSockets, MCP forwarding) is
  untouched: SSO success runs the same `_establish_session` tail as the
  form (same cookie, same audit row — distinguished by a
  `method: negotiate` detail).
- Failure of any kind (unsupporting browser, handshake error,
  `ADMZ_SSO_NEGOTIATE=0`, non-Windows server) lands on
  `/login?sso=failed` — the form with a gentle notice. SSO is an
  *accelerator*, never a wall.
- Rate-limited under its own roomier policy (`login-sso`: 15 instant,
  1/4 s — a legitimate sign-in makes 2–3 handshake legs).

## Consequences

**Positive:**
- ACS-parity sign-in: one click, no password, real Windows identity —
  while "sign in as a different user" stays one form away.
- Zero new dependencies; ~300 lines of ctypes in one module; the
  protocol correctness burden sits with Windows, not ADMZ.
- Works on the workgroup box today (NTLM) and gets Kerberos for free if
  the host ever joins a domain.
- The full SSPI path is testable without a browser: the test suite runs
  a real loopback handshake (client `InitializeSecurityContextW` against
  the production acceptor) and asserts the resulting identity is the
  test-running user.

**Negative / caveats (KL-AUTH-008/009):**
- Browser zone policy governs whether SSO engages: Edge/Chrome treat
  `localhost` as intranet (works out of the box); LAN-hostname access
  needs an intranet-zone entry; Firefox needs `about:config` trust.
- NTLM connection affinity: a proxy that doesn't preserve connections
  would break the multi-leg exchange (no proxy in the reference
  deployment; direct uvicorn).
- UAC token filtering strips `Administrators` from network-type logons
  of local accounts — **observed on the first live SSO sign-in** (the
  token carried Users/docker-users but Administrators rode deny-only).
  Mitigated the same day: both sign-in paths union token groups with the
  account's directory memberships (`NetUserGetLocalGroups`,
  best-effort) — ADMZ authorizes on group *membership*, ACS Pro's
  semantics, not the token's elevation state (KL-AUTH-009).
- Login CSRF surface of a GET sign-in endpoint is acceptable: it can
  only sign the browser's *own* user in, and `_safe_next` blocks
  redirect abuse.

**Alternatives considered:**
- **pyspnego/sspilib** — solid libraries, but the OS API is directly
  reachable with the codebase's established ctypes pattern, and ctypes
  exposes `QuerySecurityContextToken` for group extraction directly.
  Zero-new-deps was an explicit ADR-0033 virtue worth keeping.
- **IIS in front (ADR-0021)** — remains the right answer for
  domain/enterprise deployments; already rejected for this box.
- **Loopback peer-process identification** (TCP table → browser PID →
  process token) — password-less and config-less, but a non-standard
  trust model that silently breaks the moment the bind widens beyond
  localhost.

## References

- Requirements: [authentication.md](../requirements/authentication.md)
  FR-AUTH-016, KL-AUTH-008/009
- Code: `admz/win_sspi.py`, `admz/api/routes/auth_web.py`
  (`login_sso`, `_establish_session`), `admz/api/templates/login.html`,
  `admz/rate_limit.py` (`login-sso`)
- Tests: `tests/test_win_sspi.py` (incl. the real loopback handshake),
  `tests/test_windows_local_backend.py::TestSsoLogin`
