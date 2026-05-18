# ADR-0021: Windows IWA via reverse proxy

**Status:** Accepted, implemented (Phase 4B).
**Date:** 2026-05-18.
**Supersedes:** none. Closes KG-SEC-001.

## Context

The production review (2026-05-17) flagged the absence of authentication
on the ADMZ web UI and REST API as the single largest production-readiness
gap. Mitigations in place (default `--host 127.0.0.1`, CORS allowlist,
`get_credentials` opt-in flag) reduce blast radius but don't address the
core problem: any caller who reaches the bind address can hit every
endpoint, including ones that return credentials, execute operations,
and change settings.

For the Axis-ecosystem product line ADMZ targets, the operations team
already manages Windows AD. Most access-control software in the Axis
ecosystem authenticates via Windows. Matching that convention gives:
- SSO via the user's existing Windows session — no separate login.
- A clean path to AD-group-based RBAC in a future phase.
- Familiarity for operators.

We considered three deployment patterns for Windows auth:

1. **In-process SSPI/Negotiate via `pyspnego`.** Python implements the
   Negotiate handshake directly. No reverse proxy. One process to manage.
   But: pulls Windows-specific Python deps into ADMZ; the SPNEGO state
   machine is complex; not all browsers play nicely with non-IIS
   implementations; debugging Kerberos issues requires deep Python-side
   instrumentation.
2. **OIDC / OAuth bridge.** Use Azure AD or AD FS to issue OIDC tokens
   that ADMZ verifies. More flexible, cleaner cross-platform. But:
   requires an IdP to be configured, extra infrastructure for many of
   our smaller-fleet operators, and OIDC is overkill when the only
   identity provider in play is the local AD.
3. **Reverse proxy (IIS in front of uvicorn).** IIS handles
   authentication; ADMZ reads the authenticated username from a
   forwarded header. Mature pattern, well-documented in IIS docs,
   keeps Python-side Windows dependencies at zero.

## Decision

**Reverse proxy.** IIS sits in front of uvicorn, performs Windows
Authentication (Kerberos preferred, NTLM fallback), and forwards the
authenticated username to uvicorn via the `REMOTE_USER` header. ADMZ's
`ReverseProxyAuth` backend reads the header and produces a Principal.

Trust model:
- ADMZ trusts `REMOTE_USER` only from a configured list of source IPs
  (default: `127.0.0.1`, `::1`). Anything else → 401.
- uvicorn binds `127.0.0.1` only by default. `_check_bind_safety` in
  `admz/__main__.py` refuses to start if `--host` is anything else
  while `ADMZ_AUTH_BACKEND` is `windows` or `composite`, unless an
  explicit override (`ADMZ_AUTH_INSECURE_BIND_OK=true`) is set.

## Consequences

**Positive:**
- Browser SSO works on-domain — no login screen, no friction.
- Zero Windows-specific Python dependencies (the `pywin32`/`pyspnego`
  routes were rejected partly for this).
- IIS is well-known infrastructure for the target customer; ops
  teams already operate it.
- TLS termination at IIS uses IIS's mature cert handling.
- Easy upgrade path to AD-group RBAC via the LDAP enrichment in
  ADR-0023.

**Negative:**
- Couples production deployment to Windows + IIS. Cross-platform was a
  prior project goal — this is the explicit divergence the user
  acknowledged on 2026-05-18.
- Off-domain / workgroup deployments fall back to NTLM (weaker).
  Workable but worth flagging to operators.
- Requires the reverse-proxy admin (IIS) to be configured correctly —
  in particular `<allowedServerVariables>` must permit the
  `HTTP_REMOTE_USER` forwarding, which is non-default.
- Two processes to operate per host (IIS + uvicorn-as-service via
  NSSM). The `HttpPlatformHandler` alternative collapses this back to
  one process but couples ADMZ lifecycle to IIS recycles — documented
  as an alternative, not the default.

**Mitigated risks:**
- Header spoofing — controlled by the trusted-proxies check and
  enforced-localhost-bind startup safety.
- Misconfigured proxy not forwarding the header — manifests as
  401 (missing header) at uvicorn, with a clear error message.

## Implementation

- `admz/auth.py::ReverseProxyAuth` — reads `REMOTE_USER`, validates
  source IP, parses `DOMAIN\\user`/`user@domain`/bare-username,
  returns `Principal(source="windows", ...)`.
- `admz/auth.py::auth_middleware` — runs on every non-exempt request
  via FastAPI's `@app.middleware("http")`; populates
  `request.state.principal` so route handlers grab it via
  `Depends(get_current_principal)` without re-running auth.
- `admz/__main__.py::_check_bind_safety` — startup refusal for unsafe
  bind addresses under IWA-trusting backends.
- Tests: `tests/test_web_auth_backends.py::TestReverseProxyAuth`,
  `tests/test_auth_integration.py::TestReverseProxyAuthIntegration`,
  `tests/test_cli_auth.py::TestBindSafety`.

## References

- [requirements/authentication.md](../requirements/authentication.md) — full FR/NFR list
- [requirements/security.md](../requirements/security.md) — KG-SEC-001 marked closed
- [DEPLOYMENT_WINDOWS.md](../../DEPLOYMENT_WINDOWS.md) — operator setup guide
- [ADR-0022](0022-api-keys-for-agents.md) — sibling for programmatic clients
- [ADR-0023](0023-ldap-group-enrichment.md) — populating Principal.groups
