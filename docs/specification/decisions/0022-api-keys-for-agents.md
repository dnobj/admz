# ADR-0022: API keys for programmatic clients

**Status:** Accepted, implemented (Phase 4B′).
**Date:** 2026-05-18.

## Context

LLM agents and automation drive ADMZ via the REST API. Unlike browser
users (covered by ADR-0021's Windows IWA flow), agents don't have a
Windows session — they're typically running in the cloud, on a
different host, or unattended on a schedule.

We needed an auth method that:
- Doesn't require the caller to be on a Windows machine or in AD.
- Is operationally simple (no IdP setup).
- Provides per-agent attribution (so the audit log can say "nightly-bot
  did X" instead of just "someone did X").
- Is revocable.
- Is auditable.

Options considered:

1. **No auth on REST API.** Rejected. Anyone on the network can mint
   confirm tokens to spam the user, or call destructive endpoints —
   the two-gate model is the user's last line of defense, not the
   only one.
2. **Static shared secret (single token in env var).** Simple, but
   non-revocable without a service restart, and gives every consumer
   the same identity — no audit trail per agent.
3. **OAuth client-credentials grant.** Standard, well-known, but
   requires an IdP. Most ADMZ deployments don't have an OAuth provider
   stood up. Disproportionate for the threat model.
4. **mTLS with per-agent client certs.** Strong, but operationally
   expensive — every agent host needs a cert, a CA, a rotation plan.
   Worth revisiting for high-security deployments later.
5. **API keys.** Familiar pattern from cloud APIs, stripe, GitHub,
   etc. Lightweight, revocable, per-agent.

## Decision

Use **API keys** with a Bearer-token header.

Format: `admz_<43 url-safe random chars>` (~256 bits entropy), with
the `admz_` prefix for log-greppability and quick rejection of
non-ADMZ tokens.

Storage: PBKDF2-SHA256 (600,000 iterations, 16-byte salt) hashed at
rest in the shared ADMZ SQLite database. The plaintext is returned by
`create()` exactly once and never recoverable thereafter.

Per-key metadata: display_name (e.g. `"nightly-snapshot-bot"`),
created_by (the Windows principal who minted it), created_at,
expires_at (optional), last_used_at, revoked flag, scopes (reserved,
`"*"` in v1), groups snapshot (inherits from creator for future RBAC).

## Consequences

**Positive:**
- Each agent has its own identity — `Principal.source = "api-key"`,
  `Principal.display_name = "nightly-snapshot-bot"`. Audit log
  distinguishes agents from each other and from human users.
- Revocation is immediate — set `revoked=1`, next auth call returns
  401.
- Operators with shell access can bootstrap via
  `python -m admz api-key create`; routine management via web UI
  (login as Windows user → `/api/api-keys` REST surface).
- Bearer token in `Authorization` header is the universally-recognized
  pattern.

**Negative:**
- Keys are bearer tokens — anyone who reads them in transit or at rest
  can use them. Mitigated by HTTPS at the IIS layer (ADR-0021) and
  PBKDF2 at rest, but not by anything intrinsic to the bearer-token
  scheme.
- Linear-scan authentication: every incoming request compares the
  presented token against every active key's hash via PBKDF2. At
  600k iterations that's ~100ms per key on modern hardware. Fine for
  the expected fleet size (handful to tens of keys per install);
  problematic at hundreds. A future O(1) lookup column (HMAC of the
  key under a server-side secret) is a known optimization path.
- No expiry rotation policy in v1 — keys live forever unless explicitly
  expired or revoked.

**Mitigated risks:**
- Key theft → mitigated by revocation, audit log, optional expiry.
- Shared key between agents → discouraged by the per-agent
  `display_name` model and the audit trail it produces.

## Composition with Windows IWA

The default production setup uses `ADMZ_AUTH_BACKEND=composite` which
tries API key first, then Windows IWA. This handles:

- **Agent calls** that send `Authorization: Bearer admz_...` →
  API-key path succeeds.
- **Browser AJAX from a Windows-authenticated session** — no Bearer
  header → API-key returns 401 → falls through to Windows IWA →
  succeeds via `REMOTE_USER`.
- **Neither** → both return 401, final response is 401 with
  `WWW-Authenticate: Negotiate` (the last backend's headers).

## Implementation

- `admz/api_keys.py` — `ApiKey` dataclass, `ApiKeyStore` (SQLite + WAL,
  short-lived connections, parent-dir bootstrap), hash helpers.
- `admz/auth.py::ApiKeyAuth` — backend reading `Authorization: Bearer`
  header.
- `admz/api/routes/api_keys.py` — `GET /api/api-keys`,
  `POST /api/api-keys`, `DELETE /api/api-keys/{id}`. Plaintext returned
  exactly once on `POST`.
- `admz/__main__.py::run_api_key` — CLI `python -m admz api-key
  {create,list,revoke}` for bootstrap when no web UI is available yet.
- Tests: `tests/test_web_auth_backends.py::TestApiKeyAuth`,
  `tests/test_web_auth_backends.py::TestApiKeyHashing`,
  `tests/test_web_auth_backends.py::TestApiKeyStore`,
  `tests/test_auth_integration.py::TestApiKeyAuthIntegration`,
  `tests/test_auth_integration.py::TestApiKeyCrudEndpoints`,
  `tests/test_cli_auth.py::TestApiKeyCli`.

## References

- [requirements/authentication.md](../requirements/authentication.md)
- [ADR-0021](0021-windows-iwa-via-reverse-proxy.md) — Windows IWA companion
- [ADR-0023](0023-ldap-group-enrichment.md) — groups snapshot at mint time
- `docs/DEPLOYMENT_WINDOWS.md` § "Mint an API key for an agent"
