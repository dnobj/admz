# ADR-0023: LDAP / AD group enrichment for principals

**Status:** Accepted, implemented (Phase 4E).
**Date:** 2026-05-18.

## Context

Windows IWA via reverse proxy (ADR-0021) gives ADMZ the authenticated
username, but **not** the user's group membership. IIS doesn't forward
`memberOf` by default; the only thing in `REMOTE_USER` is the username.

Group membership matters because ADMZ's future role-based access
control will map AD groups to ADMZ roles. Without groups available at
auth time, every authenticated user looks identical — fine for "anyone
in the org can use ADMZ" but inadequate for "only the access-control
team can revoke API keys" (which is the operator's eventual goal).

Options for enriching the principal with groups:

1. **Custom IIS module that adds an `X-User-Groups` header.** Ships the
   work to IIS. But: requires a custom module (C# / native code) we'd
   have to write and distribute. Operators install it once per IIS host.
   Too high-friction for the target customer.
2. **ASP.NET intermediary that reads `WindowsIdentity.Groups`.** Same
   shape as option 1, less code, but adds ASP.NET to the deployment
   stack. Operators have to manage another runtime.
3. **LDAP / AD query at auth time from ADMZ.** ADMZ holds a service
   account, binds to the DC, queries `(&(objectClass=user)(sAMAccount
   Name=<user>))` for `memberOf`. Cached briefly to avoid hammering
   the DC. Pure-Python (`ldap3`), no Windows-only deps. Mature pattern.
4. **Skip groups entirely; use API-key-based scopes only.** Workable
   but loses the AD-as-source-of-truth story that motivates ADR-0021.

## Decision

**LDAP query at auth time** with a thread-safe TTL cache.

Configuration is fully opt-in via env vars (`ADMZ_LDAP_ENABLED=true`).
Workgroup deployments and small fleets that don't yet need RBAC leave
it disabled; `Principal.groups` is just empty.

Failures are **non-fatal**: an unreachable LDAP server, malformed
config, or slow query results in empty groups + a logged warning, not
a 401. Authentication and authorization are decoupled — auth doesn't
break when the DC is down.

Cache: in-memory, keyed by normalized username (`DOMAIN\\user`,
`user@domain`, bare `user` all collapse to the bare form), TTL default
300s, thread-safe. Cache invalidation API is exposed for ops use.

Library choice: `ldap3` (pure-Python, MIT-licensed). Adds zero native
dependencies, works on Windows / Linux / macOS, has reasonable docs
and active maintenance.

## Consequences

**Positive:**
- AD becomes the source of truth for group membership, matching
  operator expectations on Windows.
- Cache keeps the average request cost ~zero (one query per
  username per 5 minutes by default).
- Failure mode is graceful — LDAP outage doesn't lock anyone out.
- Workgroup hosts and dev installs cost nothing (config disabled).

**Negative:**
- Service account credentials (`ADMZ_LDAP_BIND_USER`,
  `ADMZ_LDAP_BIND_PASSWORD`) live in env vars on the ADMZ host.
  Anyone with shell access on that host can read them. Acceptable
  for the target threat model but worth documenting.
- LDAP queries can be slow on first hit (~100ms over a fast LAN, more
  over a WAN). Cache amortizes but the first request after a deploy
  can feel sluggish.
- Adds a Python dependency (`ldap3`). Pure-Python so no install
  pain, but it's another moving part.
- Groups are inherited at API-key mint time (ADR-0022), not re-queried
  per request. If you revoke an AD group from a user, their existing
  API keys retain the snapshot until you revoke + reissue. This is
  intentional (keeps key auth fast and cache-free) but worth knowing.

## Implementation

- `admz/ldap_groups.py` — `LdapConfig`, `LdapGroupResolver`, module-level
  lazy singleton via `get_resolver()`.
- Wired into `admz/auth.py::ReverseProxyAuth.authenticate` after
  parsing `REMOTE_USER`. Wrapped in broad try/except so any LDAP
  failure produces empty groups, not a 401.
- API keys snapshot `principal.groups` at mint time
  (`admz/api/routes/api_keys.py::create_api_key`); the resolver is NOT
  invoked when an API key authenticates (the key has cached groups
  already).
- Tests: `tests/test_ldap_groups.py` — full coverage with mocked
  `ldap3` connection objects (real LDAP server not required for CI).

## When NOT to enable

- Workgroup-only deployments (no DC reachable).
- Dev / single-user installs.
- Deployments that prefer simpler explicit role assignment over
  AD-derived grouping.

In those cases leave `ADMZ_LDAP_ENABLED` unset/false. `Principal.groups`
will be empty; the future RBAC layer can fall back to explicit
allowlists.

## References

- [requirements/authentication.md](../requirements/authentication.md)
- [ADR-0021](0021-windows-iwa-via-reverse-proxy.md) — produces the
  Principal that this ADR enriches.
- [ADR-0022](0022-api-keys-for-agents.md) — describes the
  groups-snapshot-at-mint behavior.
- `docs/DEPLOYMENT_WINDOWS.md` § "Step 1 — Install ADMZ as a Windows
  service" for the LDAP env-var examples.
