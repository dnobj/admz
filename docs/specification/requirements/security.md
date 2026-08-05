# Requirements: security (cross-cutting)

Security posture for ADMZ. Spans every subsystem because most attacks are systemic. Each requirement is tagged with status (✅ implemented, 🚧 partial, ⚠️ known gap, 📋 planned) and a short note on enforcement.

## Functional requirements

### FR-SEC-001 — Two-gate write safety ✅
Every write operation against a device passes through two independent gates:
1. **Semantic gate** — the LLM (or REST caller) presents the proposed change to a human in natural language; the human approves or rejects.
2. **Mechanical gate** — the catalog's per-operation `risk_level` field. `dangerous`-risk operations are blocked at execute time and return a `confirm_token`. A reasoning bug in the LLM cannot bypass the mechanical check; a misconfigured catalog cannot bypass the user review.

**Enforced at:** the shared gate in `operations.py` (`execute_gated_operation` / `execute_gated_plan`), which the MCP server (`mcp/server.py`), REST (`api/routes/catalog.py`, `api/routes/plans.py`), and the plan engine all delegate to — one risk→level policy, one execution tail. See [0005](../decisions/0005-two-gate-plan-approval.md).

### FR-SEC-002 — Gated-risk plans require explicit confirmation ✅
A plan's required confirmation level is the strictest across its steps (per the configurable per-risk policy). `operations.execute_gated_plan` runs it immediately only when that level is `none`; an `llm_confirm`-level plan needs `confirm_dangerous=True` (else a `{blocked: true, retry_with: {confirm_dangerous: true}}` envelope); a `url_*`-level plan returns a blocked envelope whose `/confirm/{token}` page approves and runs it. `plans/engine.py::run_plan` itself is un-gated and only reached after approval.

**Enforced at:** `operations.py::execute_gated_plan` (the shared plan gate). Tested in `tests/test_plan_engine.py::TestPlanGate` and `tests/test_operations_core.py`.

### FR-SEC-003 — Confirmation tokens are single-use, time-limited, cross-surface ✅
`confirm_token`s issued by either MCP `execute_operation` or REST `POST /api/catalog/execute` are stored in a shared SQLite `ConfirmStore`:
- 32-byte URL-safe random (≈256 bits entropy)
- 5-minute TTL (`CONFIRM_TOKEN_TTL_SECONDS = 300`)
- Single-use via `UPDATE … WHERE status='pending'` (atomic — a concurrent second consumer gets HTTP 409)
- Tokens issued by MCP can be consumed via REST and vice versa

**Enforced at:** `api/confirm_store.py` (Phase 2E). Tested in `tests/test_api_routes.py::TestConfirmTokenUnification`.

### FR-SEC-004 — Out-of-band credential capture ✅
Tools that need a device password (`capture_credentials`, `set_fleet_setting` for password keys) return a one-time URL (`/capture/{token}`, `/capture/fleet/{token}`) that opens a browser form. The password is submitted directly to the registry; it never enters the LLM context or the chat transcript.

**Enforced at:** `api/capture.py` + `api/routes/capture.py`. See [0009](../decisions/0009-oob-credential-capture.md).

### FR-SEC-005 — At-rest credential encryption ✅
The SQLite backend encrypts the `password` field of each account with Fernet (AES-128-CBC + HMAC-SHA256). The key lives in `~/.admz/admz.key` (overridable with `ADMZ_KEY_PATH`), chmod'd to `0o600` on Unix. The `~/.admz/` parent directory is chmod'd to `0o700`.

**Enforced at:** `backends/sqlite_backend.py::_store_account_data` and `_encrypt`/`_decrypt`. Tested in `tests/test_sqlite_backend.py::TestEncryption`.

### FR-SEC-006 — device passwords never displayed; LLM access is opt-in ✅
Device-account passwords are never returned over web/REST — the
device-credential reveal endpoint and its `web_reveal_credentials_enabled`
flag were removed. ADMZ reads the plaintext from the secrets backend only
at execution time. The MCP `get_credentials` tool (which would place the
password in LLM context) is gated by `tool_get_credentials_enabled`
(default: disabled), which is in `PROTECTED_SETTING_KEYS` — MCP cannot
write it; only the `/confirm-settings` web UI can.

**Enforced at:** `mcp/server.py::_register_handlers` (filters tool out of `list_tools()`); the device-credential REST endpoint no longer exists. See [0020](../decisions/0020-protected-fleet-settings.md).

### FR-SEC-007 — Password values masked when listing fleet settings ✅
`get_fleet_settings` (MCP) and `GET /api/fleet/settings` (REST) both mask secret-shaped settings — displayed as `****** (N chars)`, never plaintext. Shared helper `mask_settings_for_display` in `admz/fleet_settings.py` enforces a single rule across both surfaces; **which keys count is `admz/redact.py::is_sensitive_key`**, which covers `password`, `passwd`, `secret`, `token`, `api_key`, compound `*key*` and a discrete `pat` — not the `"password" in key` test this line used to name (#214). FR-SEC-007a below names `gemini_api_key` and `acs_webhook_token` as secrets, which the old wording would not have covered.

**Enforced at:** `admz/fleet_settings.py::mask_settings_for_display`. Tested in `tests/test_fleet_settings.py` and `tests/test_api_routes.py::TestFleetSettingsMasking`.

### FR-SEC-007a — Fleet-setting secrets encrypted at rest ✅
Masking (FR-SEC-007) governs what a *caller* is shown; this governs what is in
the *file*. `default_password`, `gemini_api_key` and `acs_webhook_token` are
encrypted with the registry's Fernet key (ADR-0010), joining
`survey_github_pat` and the two `github_app_*` secrets which already were. The
value is **recoverable, not hashed** — ADMZ has to send it to a device — which
is the opposite of `confirm_password_hash`, deliberately left as a hash.

Encryption lives in the store (`fleet_settings.get`/`set`), not at the call
sites: `default_password` has three readers with no accessor between them, and
they already shared that one path. Callers see plaintext and are unchanged.

A legacy plaintext value is migrated in place on first read, and the plaintext
is *gone* from the database file afterwards rather than superseded — asserted
against the raw file bytes, with a control proving it was findable beforehand.
A value that will not decrypt is reported unset and **left untouched**, so a
rotated key cannot destroy the secret.

**Enforced at:** `admz/setting_crypto.py`, `admz/fleet_settings.py::get`/`set`/`list_all`,
key inventory in `admz/setting_policy.py`. Tested in
`tests/test_setting_encryption.py`, whose
`test_the_partition_covers_every_sensitive_key` fails if a new sensitive
setting is added without deciding how it is stored (#296 part 1).

### FR-SEC-008 — Per-protocol device authentication ✅
ADMZ probes each device's `WWW-Authenticate` header on HTTP and HTTPS, persists the detected scheme per-protocol in `device_info["auth"]`, and uses the scheme-appropriate auth handler at request time. Supported schemes: `digest`, `basic`, `bearer`, `none`.

**Enforced at:** `discovery/credential_probe.py::_detect_auth_schemes`, `executor/vapix.py::_resolve_auth`. See [0007](../decisions/0007-per-protocol-auth.md).

### FR-SEC-009 — TLS verification is operator-selectable ✅
The `ADMZ_VERIFY_SSL` env var controls TLS verification across the VAPIX executor and all four discovery probes (`http_probe`, `ssdp_discovery`, `credential_probe` ×2). Default is `false` (backward-compatible — most Axis devices ship with self-signed certs). Accepts `true`/`false`/`1`/`0`/`yes`/`no` (case-insensitive). Unknown values fall back to `false` with a warning.

**Enforced at:** `admz/ssl_config.py::verify_ssl_default`. Tested in `tests/test_ssl_config.py`.

### FR-SEC-010 — Default bind to localhost ✅
`python -m admz api` defaults to `--host 127.0.0.1`. Binding to `0.0.0.0` requires the operator to pass it explicitly. The help text and README both call out the no-auth caveat (FR-SEC-013).

**Enforced at:** `admz/__main__.py::api_parser`.

### FR-SEC-011 — CORS allowlist, not wildcard ✅
The FastAPI app's CORS policy is driven by `ADMZ_ALLOWED_ORIGINS` (comma-separated). Default is the 4 localhost variants (ports 4242 and 8000 × `localhost`/`127.0.0.1`). Wildcard `*` is opt-in and forces `allow_credentials=False` per CORS spec.

**Enforced at:** `api/main.py` (CORS middleware config).

### FR-SEC-011b — No external subresources; CSP enforces it ✅ (#200)
ADMZ loads **no** script, stylesheet, font or image from another origin. `lucide`
is vendored under `admz/api/static/vendor/` with provenance in `manifest.json`
(version, source URL, sha256, SRI hash, licence); the Google Fonts `@import` in
`admz.css` was dropped, since `--sans`/`--mono` already carry full fallback
stacks so the UI degrades to the platform font.

Two measurements drove the shape of the fix, and are worth keeping because they
rule out the obvious alternatives:

- `lucide@latest` resolved with `Cache-Control: max-age=60` — re-resolved about
  once a minute, so a newly published version reached the operator's browser
  within roughly a minute. "Unpinned" understated it.
- The Google Fonts `css2` endpoint serves **UA-dependent** content (24,770 bytes
  for a Chrome UA vs 470 for a legacy IE UA, different SHA-384), so a single
  `integrity` attribute cannot cover both browsers. "Pin + SRI" was
  *structurally incapable* of closing that subresource.

A `Content-Security-Policy` is now emitted on every response
(`admz/security_headers.py`), together with `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY` and `Referrer-Policy: same-origin` (chosen so capture
and confirm tokens in the URL path are never sent off-origin).

**The policy is complete against external subresource loads and weak against
XSS**, deliberately: `script-src` retains `'unsafe-inline'` because the
templates hold 16 inline `<script>` blocks, 32 inline `on*=` handlers, 11
`<style>` blocks and 640 inline `style="…"` attributes. `'unsafe-inline'` does
not weaken the *source* allow-list, so `https://unpkg.com` is still refused —
which is the threat #200 was about. Tightening to nonces or hashes is tracked
separately.

**Enforced at:** `admz/security_headers.py`; guarded by
`tests/test_no_external_subresources.py`, which fails on any new external
subresource, on a vendored file whose bytes stop matching its recorded hash,
and on a vendored file with no manifest entry.

### FR-SEC-012 — Fleet settings are deny-by-default for the LLM ✅
The MCP `set_fleet_setting` tool may write **only** the keys declared in
`admz/setting_policy.py::LLM_WRITABLE_SETTING_KEYS`. Every other fleet setting
is refused — including one added tomorrow and never mentioned anywhere.

The allow-set is the fleet credential pair, and nothing else:
- `default_username`
- `default_password`, and only via the out-of-band capture URL — a supplied
  value is refused (FR-MCP-008)

The rationale is unchanged from ADR-0020: an LLM that can change its own
guardrails has no guardrails. What changed is the **failure direction**. This
requirement used to enumerate the protected keys, and that enumeration was
wrong in two ways at once — it listed three keys while the code protected
thirty, and the code protected thirty while eighteen more were writable. An
opt-in deny-list failed four times (#152, #168, #195, #203); three independent
attempts to enumerate what it missed returned 8, 10 and 18 keys, each missing
keys the others found. A sentence that says "only the allow-set" cannot drift
the way a list can.

Two rules overlap deliberately. The `confirm_level_*` **namespace** rule is
kept even though it is now redundant: it can only ever refuse more, and it
covers risk names built at runtime from catalog YAML, which the static guard in
`tests/test_setting_policy.py` cannot see.

Operators are unaffected: every protected key is writable from the web UI where
one exists, and from `python -m admz settings set` for the nine that have no
web route.

**Enforced at:** `setting_policy.py::is_llm_writable`,
`fleet_settings.py::is_protected_setting` (allow-set + namespace rule),
`mcp/server.py::_set_fleet_setting` (the one production call site),
`api/routes/capture.py` (the out-of-band write path). Callers must use the
`is_protected_setting` predicate rather than testing membership of
`PROTECTED_SETTING_KEYS`, which since ADR-0053 is derived documentation and
decides nothing. Guarded by `tests/test_setting_policy.py`, which walks `admz/`
with `ast` — resolving module-level constants, because every previous
enumeration matched on names and inherited its author's blind spot. See
[0020](../decisions/0020-protected-fleet-settings.md), [0053](../decisions/0053-llm-writable-fleet-settings.md).

### FR-SEC-014 — Sibling-declared secrets are masked in audit rows and chat cards ✅
Redaction masks by field *name*, which is structurally blind to the
`{key: <name>, value: <secret>}` argument shape — the sensitivity of `value` is
declared by its sibling, and neither field's own name looks sensitive (`key` is
deliberately exempt because it carries a setting name, not a secret). `set_fleet_setting`
is exactly that shape, so its value reached the audit log in cleartext (#217).

Within a single mapping, a name-carrying field (`key`, `name`, `setting`, …)
holding a sensitive-looking string now masks its sibling value field (`value`,
`new_value`, …). The setting *name* is deliberately preserved — an auditor must
still be able to answer "which setting was written?". The rule is fail-safe: it
fires only when both a name field and a value field are present, and in that
narrow case prefers over-masking to a leak.

This is not specific to one tool. `call_tool` has **three** audit sites (invalid
input, anonymous-destructive, and the `finally`), all recording the same
pre-dispatch sanitized arguments, and the chat args card ran a display-side twin
of the same loop. One rule, consulted by all of them.

**Enforced at:** `admz/redact.py::sibling_masked_fields`, consulted by
`redact_structure` and `chatbot/client.py::_redact_for_display`. Tested in
`tests/test_redact.py` — including end-to-end coverage driving the real
dispatcher for each of the three audit sites, since a test against the redactor
alone would stay green if the wiring changed. Related: `rules/runner.py::redact_soap_body`
solves the same shape for SOAP `<Parameter Name=… Value=…>` rows.

## Non-functional requirements

### NFR-SEC-001 — Confirmation password is PBKDF2-hashed ✅
The `confirm_password_hash` fleet setting stores a PBKDF2-SHA256 hash with 600,000 iterations and a 16-byte salt. Stored format: `salt_hex:hash_hex`.

**Enforced at:** `api/confirm_store.py::hash_confirm_password` / `verify_confirm_password`.

### NFR-SEC-002 — No plaintext in logs ⚠️
The standard logger never emits passwords. `StepResult.error` messages may contain HTTP response bodies that *could* include sensitive data (e.g. a misformatted SOAP response echoing credentials) — this is a non-mitigated risk and is called out for review. Audit log (NFR-OBS-001 in `observability.md`) is a known gap.

### NFR-SEC-003 — Confirm tokens are not predictable ✅
All confirmation tokens use `secrets.token_urlsafe(32)` → 256 bits of entropy. Brute force is computationally infeasible. Single-use enforcement (FR-SEC-003) prevents replay.

## Known gaps (Phase 4 work, tracked in [review-followup.md](../review-followup.md))

### KG-SEC-001 — No authentication on ADMZ itself ✅ CLOSED (Phase 4)
Two-method authentication added: Windows IWA via reverse proxy
(ADR-0021) and API keys for programmatic clients (ADR-0022). The
default production setup uses the `composite` backend that accepts
either. Phase 4 ships with end-to-end tests for all four backends
(`none`/`windows`/`api-key`/`composite`), CLI for bootstrap, and a
deployment guide ([DEPLOYMENT_WINDOWS.md](../../DEPLOYMENT_WINDOWS.md)).
See [requirements/authentication.md](authentication.md) for the full
FR/NFR list.

### KG-SEC-002 — No CSRF protection on capture / confirm forms ⚠️ PARTIALLY CLOSED (#3)
**Capture forms: closed.** `admz/csrf.py` enforces same-origin on the three
browser-only capture POSTs — `/capture/{token}`, `/capture/fleet/{token}` and
`/capture/rule/{token}`. `Origin` is checked, `Referer` is the fallback, and a
request carrying **neither is refused** (fail closed: these endpoints serve an
HTML form a human types credentials into, and no non-browser client exists for
them).

**Confirm forms: still open.** `POST /confirm/{token}` has the same shape and
the same need; it was left out of #3 only because `admz/api/routes/confirm.py`
was being edited concurrently (#178). The guard is a one-line call —
`check_same_origin(request)` — so closing it is small.

Worth recording *why* this matters, because the original entry and #3 both got
the threat model slightly wrong. CSRF needs **ambient authority**, and ADMZ's
backends differ:

| backend | browser credential | CSRF-able |
|---|---|---|
| `windows-local` | `admz_session` cookie, `SameSite=Lax` | no |
| `api-key` | `Authorization: Bearer` (never ambient) | no |
| `none` | nothing to borrow | n/a |
| `windows`, `composite` | proxy does Negotiate, injects a trusted header — **no cookie** | **yes** |

`SameSite=Lax` already blocks a cross-site POST from carrying the session
cookie, and Negotiate SSO (ADR-0035) ends in that same cookie. The real gap is
`ReverseProxyAuth` (ADR-0021), where the browser re-authenticates
*automatically* on every request with no cookie involved, so `SameSite` cannot
help. `ADMZ_AUTH_BACKEND=composite` includes it and is what
[DEPLOYMENT_WINDOWS.md](../../DEPLOYMENT_WINDOWS.md) documents.

Also note the token argument cuts the other way: an attacker who *knows* the
token does not need CSRF — they can POST it directly. What CSRF buys is the
victim's ambient credentials on an endpoint the attacker cannot otherwise
reach.

Comparison is on host+port, not scheme: behind a TLS-terminating proxy the
browser sends `https://` while ADMZ sees plain HTTP with no
`X-Forwarded-Proto`. `ADMZ_TRUSTED_ORIGINS` (comma-separated) covers a proxy
whose public hostname differs from the `Host` ADMZ receives.

### KG-SEC-003 — No audit log ✅ CLOSED (Phase 4D)
New `audit_log` SQLite table populated on every gated action (credential
retrieval, API-key mint/revoke, dangerous-op confirms, etc.). The
`requester` parameter on `DeviceRegistry.get_credentials` now carries
the authenticated principal's identity instead of being ignored.
Readable via `GET /api/audit` with filters by action/requester/since.
See `admz/audit.py` and [authentication.md](authentication.md) FR-AUTH-011.

### KG-SEC-004 — Fernet key has no rotation path ⚠️
Losing `~/.admz/admz.key` means losing all encrypted credentials. There is no master-key wrap or envelope encryption. Joint backup of `admz.db` + `admz.key` is documented in `README.md::Backup`.

### KG-SEC-005 — Rate limiting on `/capture` and `/confirm` POSTs ✅ (closed)
Both halves of this gap shipped. The POST handlers rate-limit per client
(`admz/api/routes/confirm.py:200`, `:687`; `admz/api/routes/capture.py:200`),
and a wrong confirmation password locks the token for 300 s
(`admz/api/routes/confirm.py:41`, `_PW_LOCKOUT_SECONDS`).

> **Corrected 2026-08-04 (#214).** Kept as ⚠️ after both were implemented. A
> known-gap list is read to decide what to build next, so a ⚠️ on closed work
> invites someone to build it twice — the same cost as a 📋 on shipped code.

### KG-SEC-006 — No secret zeroization in memory ⚠️
Python `str` is immutable and lives in the arena until GC. Memory dumps would expose credentials. Acceptable for the target threat model; switching to `bytearray` everywhere is out of proportion.

## Conventions for new code

- **Don't add MCP tools that return credentials.** The OOB capture pattern is the right answer. Exception: `create_temp_credentials` returns plaintext intentionally because the whole point is the LLM uses the short-lived cred directly.
- **Don't add MCP tools that change confirmation policy.** Protected keys (FR-SEC-012) are the right surface for that.
- **Don't add executor families that hard-code `verify=False`.** Use `verify_ssl_default()` from `admz/ssl_config.py`.
- **Don't add REST endpoints that return passwords without the same fleet-flag gating** as the MCP equivalents (FR-SEC-006).
- **Always mask password-shaped fleet settings** in any list/get response (FR-SEC-007).

## References

- Decisions: [0005](../decisions/0005-two-gate-plan-approval.md), [0006](../decisions/0006-multi-level-confirmation.md), [0007](../decisions/0007-per-protocol-auth.md), [0009](../decisions/0009-oob-credential-capture.md), [0010](../decisions/0010-fernet-encryption.md), [0020](../decisions/0020-protected-fleet-settings.md).
- Cross-cutting reqs: [reliability.md](reliability.md), [observability.md](observability.md), [configuration.md](configuration.md).
- Personas: [security-conscious-operator.md](../personas/security-conscious-operator.md), [llm-agent.md](../personas/llm-agent.md).
