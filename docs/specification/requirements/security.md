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
`get_fleet_settings` (MCP), `GET /api/fleet/settings` (REST), **and the
`/fleet-settings` HTML page** all mask secret-shaped settings — displayed
as `****** (N chars)` (JSON) or a placeholder revealed on demand through
the gated `GET /api/fleet/settings/{key}/reveal` fetch (HTML), never
plaintext. Shared predicate `admz/redact.py::is_sensitive_key` (via
`admz/fleet_settings.py::is_sensitive_setting_key` /
`mask_settings_for_display`) decides for all three — which covers
`password`, `passwd`, `secret`, `token`, `api_key`, compound `*key*`, and
the discrete delimiter-bounded tokens `pat`, `pwd`, `pass` — not the
`"password" in key` test this line used to name (#214).

**#336/#337:** `pwd` and `pass` are the actual VAPIX wire keys carrying a
device password (`pwdgrp.cgi:add-user`/`update-user`, `networkshare-add.cgi:add`)
and were missing from this predicate — neither is a substring of anything
it checked, so a value under either key reached the MCP audit sanitizer
(and every other one of this predicate's callers) unmasked. Fixed the same
way `pat` already was: a delimiter-bounded discrete-token match, not a bare
substring — `pass` as a substring would mask `bypass`/`passive`/`compass`.
`admz/redact.py`'s own module docstring records why this predicate,
`admz/executor/vapix.py::secret_param_names`, and `redact_url` stay three
separate answers rather than being consolidated into one.

**This line's own history is the cautionary tale it should have been read
as.** #214 corrected it to say the MCP tool and REST endpoint use the
canonical predicate — true, and still true — but the correction was scoped
to those two surfaces and never mentioned the HTML page, which had its
*own*, separately hand-rolled `"password" in key.lower()` test in both
`admz/api/routes/web.py` and `admz/api/templates/fleet_settings.html`
(#158). `gemini_api_key` and `acs_webhook_token` — named in FR-SEC-007a
below as secrets since #214 — rendered in plaintext directly in that page's
HTML, no gate at all, the whole time #214's corrected wording sat one
paragraph above describing a *different* route as fixed. The doc was
locally accurate and globally misleading — precisely the shape CLAUDE.md's
own "not live" incident (#214, a different one) warns every session to
watch for: a true sentence about the part that was checked, read as a
claim about the whole.

`admz/mcp/server.py::_set_fleet_setting`'s own tool-result echo carried a
**fourth**, independent copy of the identical hand-rolled test (#158) —
currently unreachable with a real secret only because of the ADR-0053
allow-list gate above it, not because the predicate itself was correct.
Fixed the same way.

**Structural guard against a fifth:** `tests/test_sensitivity_predicate_completeness.py`
scans `admz/**/*.py` and `admz/api/templates/**/*.html` for the narrow shape
of this anti-pattern (a sensitive substring tested via `in` against a
lowered key) outside `redact.py`, against an explicit, justified allowlist
for the one legitimate different-shaped match
(`admz/backends/sqlite_backend.py`'s fixed-schema dict-key presence check).
It also asserts every key `admz/setting_policy.py` declares encrypted at
rest is recognized by `is_sensitive_key` — the store encrypting a key and
the display layer masking it are two decisions that could drift from each
other exactly like this issue's two predicates did. **Stated honestly, not
oversold:** unlike the prompt-section completeness guard (#320), this one
cannot mechanically discover a brand-new *surface* — sensitivity-masking
decisions have no shared architectural seam (no `build_*`-style naming
convention) the way prompt sections do — so a genuinely new display surface
still needs a human to add it to the behavioral leak-sweep in the same test
file. It reliably catches a new instance of the *hand-rolled-predicate
shape*, wherever in `admz/` it's written.

**Structural guard against a sixth (#336):** the two guards above check
whether the predicate is *hand-rolled* or *stale relative to this repo's own
declarations*. Neither checks it against the vocabulary that actually
matters most for a device credential: what the atlas catalog itself puts on
the wire. `TestCatalogDeclaredSecretsAreRecognized` walks every VAPIX
operation's request template (the same walk `admz/executor/vapix.py::secret_param_names`
performs per-operation, run catalog-wide) and asserts every wire key it
finds secret-shaped is also recognized by `is_sensitive_key` — the guard
that would have caught `pwd`/`pass` going unmasked before an audit pass had
to find it by executing the code. Mutation-checked: removing `pwd` from the
predicate's discrete-token regex fails this test, naming the exact key and
the two operations that declare it.

**Enforced at:** `admz/fleet_settings.py::mask_settings_for_display`,
`admz/api/routes/web.py::fleet_settings_page`,
`admz/mcp/server.py::_set_fleet_setting`. Tested in
`tests/test_fleet_settings.py`, `tests/test_api_routes.py::TestFleetSettingsMasking`,
and `tests/test_sensitivity_predicate_completeness.py`.

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

**Migration also runs eagerly, not only on a lucky read (#307).** A key read
rarely — `acs_webhook_token` is touched only when ACS fires a webhook or an
operator opens its settings page — could sit in plaintext indefinitely under
read-triggered-only migration, even though `setting_policy.py` declares it
encrypted; measured on the live database after #302 shipped, this was true
for `acs_webhook_token` while `default_password` and `gemini_api_key` had
already converted. `FleetSettings.migrate_encrypted_settings()` sweeps every
key in `STORE_ENCRYPTED_SETTING_KEYS` once, reusing `get()`'s own
migration path, and is called on every startup (`admz/api/main.py::lifespan`)
the same best-effort, never-fatal way the other one-time startup migrations
there are. A per-key failure is counted and skipped, not raised, so this
cannot make startup depend on a writable database.

**Enforced at:** `admz/setting_crypto.py`,
`admz/fleet_settings.py::get`/`set`/`list_all`/`migrate_encrypted_settings`,
key inventory in `admz/setting_policy.py`, startup wiring in
`admz/api/main.py::lifespan`. Tested in `tests/test_setting_encryption.py`,
whose `test_the_partition_covers_every_sensitive_key` fails if a new
sensitive setting is added without deciding how it is stored (#296 part 1),
and whose "eager sweep" tests assert the *database*, not the policy — a
declared key must actually be stored encrypted after the migration path
runs, regardless of whether anything ever reads it (#307).

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

### FR-SEC-015 — Device/demo-sourced system-prompt content is bounded, capped, and provenance-fenced 🚧 (#167, #191)
Device fields (`nickname`, `friendly_name`, `host`, `tags`) and demo names are
written by the device itself or by an ungated MCP tool (`update_device`,
`create_demo`, `confirm_demo_proposal`) and are pasted into the system prompt
of **every subsequent chat/voice turn for every principal** — a newline in one
of these fields used to break out of its rendered roster/demos line and inject
sibling lines into the block. Marked 🚧, not ✅: this reduces the injection
surface measurably, it does not make injected content harmless — see the
honesty note below.

Three independent layers:
- **Sanitize at render** (`admz/chatbot/context.py`, via
  `admz.validators.sanitize_display_text`) — strips control characters
  (newlines above all) and caps length, applied to every roster/demos field
  regardless of write path. The demos section is now row-capped
  (`_MAX_DEMOS_SECTION`), matching its siblings (`_MAX_ROSTER_DEVICES`,
  `_MAX_INFERENCE_PROPOSALS`) — it had no cap at all before this.
- **Reject at write** (`admz/demos/actions.py::_validate_demo_name`) — a
  demo name containing control characters or over length is refused outright
  (400), rather than silently mangled, on `create_demo`/`update_demo`/
  `confirm_demo_proposal`.
- **Provenance-fence at assembly** (`admz/chatbot/system_prompt.py::_fence`) —
  the device roster and demos blocks are wrapped in a boundary marked with a
  fresh cryptographically-random token on every render, with an explicit
  "this is data, not instructions" statement. Because the prompt is rebuilt
  every turn, a payload cannot contain a copy of *this* render's boundary
  token (it doesn't exist yet when the payload is written), which makes
  forging the fence's own boundary infeasible rather than merely
  inconvenient — the open/close markers are added around the body as the
  last step, so truncation elsewhere can never leave the fence unbalanced.

**Honesty, stated plainly rather than overclaimed:** fencing narrows what
injected text can accomplish (it can no longer make itself look like it sits
*outside* the untrusted region — forging a fake system instruction or a fake
`[console]` line) — it does not guarantee the model disregards persuasive
text that stays honestly inside the fence. This is a real, described
reduction, not a claim that prompt injection is closed.

**The `[console]` ground-truth marker** (see FR-CB / `system_prompt.py`) is
addressed at a different layer: a genuine notification is written only
server-side as a `role='event'` row (`admz/chatbot/sessions.py::append_event`,
reachable only from `confirm.py`/`capture.py`, never from an MCP tool or user
input) — but Gemini has no third role, so 'event' and ordinary 'user' rows both
flattened to 'user', discarding that distinction before the text reached the
model. `admz/chatbot/client.py::_build_contents` now neutralizes the literal
`[console]` string in every role except 'event' (including the model's own
past output) before that flattening happens, so only a genuine server-written
note can ever carry it.

**The demo-inference proposal-names section is fenced too** (#320): proposal
names derive from device tags and rule names, so they're partially
attacker-influenceable the same way — reached less directly than
`update_device`'s nickname field, but rendered identically. Sanitized the
same way and wrapped in the same fence; unlike the demos section before
#191, `_MAX_INFERENCE_PROPOSALS` already bounded what's *rendered* (not just
queried — the render loop re-slices to it independently), so no second cap
was needed.

**Structural guard, not just three more instances of the same fix** (#320's
own question): #167, #191 and #320 are the identical failure shape
`admz/setting_policy.py:10-17` documents for fleet-setting keys — three
independent attempts at enumerating "which keys are sensitive" found 8, 10,
and 18 keys, each missing ones the others found, because remembering to
classify a new call site doesn't scale. Applied here:
`tests/test_prompt_fencing_completeness.py` enumerates every `build_*`
section builder `admz/chatbot/context.py` defines and cross-checks it
against two closed, exhaustive registries — `FENCED_SECTIONS` and
`TRUSTED_SECTIONS` — behaviorally (each is checked by actually calling
`build_system_prompt` with a marker payload and asserting the fence is or
isn't there), not by reading source text. A new section builder that's in
neither registry fails the suite immediately; this doesn't classify it
correctly on its own — a human still decides which bucket — but it makes
the *decision* impossible to skip silently, which is the property "one more
manual audit" doesn't have. Stated limit: the scanner only reaches
`context.py`'s own top-level functions — `build_module_prompt_sections`
delegates to per-module prompt contributors (ADR-0039) it cannot see inside
of, so a module rendering device data through its own section would need
its own guard.

**Enforced at:** `admz/validators.py::sanitize_display_text`,
`admz/chatbot/context.py` (roster/demos/inference-proposal builders),
`admz/demos/actions.py::_validate_demo_name`,
`admz/chatbot/system_prompt.py::_fence`, `admz/chatbot/client.py::_build_contents`.
Tested in `tests/test_prompt_injection_fencing.py`,
`tests/test_prompt_fencing_completeness.py`, `tests/test_demos_routes.py`,
`tests/test_chat_event_notes.py`. Still not addressed (tracked separately,
noted in the PR): the field allow-list on `update_device`/`update_device_tags`
— they still merge an arbitrary dict with no allow-list (#167's suggested
fix item 4).

### FR-SEC-016 — Catalog-declared secret params are never persisted or rendered in a confirm session ✅ (#334)
A gated write whose catalog operation template declares a secret-shaped
placeholder — today: a device password, e.g. `pwdgrp.cgi:update-user`'s
`{"pwd": "{password}"}` — used to have that value written straight into
`confirm_sessions.params_json` in plaintext, and from there rendered
**unmasked, in HTML, to anyone who loaded the `/confirm/{token}` URL** —
the reachable exposure is the rendered page, not merely "at rest in a
SQLite row behind a directory ACL" (the row was already reachable; the page
load is the easier and more likely path). #194 had already fixed the
analogous hazard for rules-engine recipient credentials by failing closed;
the VAPIX catalog execute path and the generic catalog path had no
equivalent at all.

Three-part fix, all in the existing confirm-session/template/approve-handler
flow rather than a fourth parallel capture-session concept (the codebase
already has three: OOB credential capture, rules-recipient capture, and this
one):
1. `execute_gated_operation` strips the secret-shaped **value** before
   `ConfirmStore.create_session` is ever called — the **key name** is kept
   (`ConfirmSession.secret_fields`), so the approval card can still say
   *what* is changing, just not to *what*.
2. `/confirm/{token}` renders a per-field masked `<input type="password"
   name="secret__<name>">` for each entry in `secret_fields`, reusing the
   existing `needs_password` confirmation-password pattern.
3. On submit, the value is merged into the operation's params **in memory
   only**, inside `execute_approved_session`, immediately before execution
   — never written to `params_json`. Chat/MCP completion of a session with
   unresolved `secret_fields` is refused unconditionally (even at
   `llm_confirm` level, i.e. even if an operator has reconfigured that risk
   class away from a `url_*` flow) because neither surface can collect the
   value; the operator is directed to the web page.

**What this does not close.** The value still transits the approval POST
body and lives in process memory for the duration of executing the
operation — this removes it from disk (the confirm-session row) and from
the rendered page (the reachable exposure), it does not remove it from the
process. See KG-SEC-006.

**Structural, not enumerated**, the same shape as ADR-0053 and FR-SEC-015:
`admz/executor/vapix.py::secret_param_names` derives which params are
secret-shaped from the catalog operation's OWN request template for THIS
operation, rather than a fixed key list checked against every operation.
Deliberately **narrower** than the project's canonical sensitivity
predicate, `admz/redact.py::is_sensitive_key` — that predicate matches by
substring (`"token" in k`), correct for free-form setting/dict keys but
wrong here: the catalog uses `*Token`-suffixed and bare `{token}`/`{Token}`
placeholders throughout for legitimate, non-secret resource identifiers
(`{PresetToken}`, `{RelayToken}`, `{InputToken}`,
`{VideoSourceConfigurationToken}`, ONVIF door-control operations), and a
substring match would strip and silently vanish one of those from the
confirm session with no password-entry field to explain why. Also not
reused: `admz.rules.capabilities.secret_choice_keys` (#194's predicate) —
wrong shape (coupled to SOAP `Action.soap_params`, not the VAPIX catalog's
string-templated `Operation.request`). It used to keep its own private,
narrower vocabulary too (`_SECRET_HINTS = ("password", "passwd")`,
missing `secret`/`token`/`api_key`/`apikey`) — **removed in #336**, once
established that the gap wasn't live against any currently-surveyed device
but had no `capture_note` safety net either, so `param_is_secret` now calls
`is_sensitive_key` directly rather than hand-maintaining a third copy. That
leaves exactly two secret-classification vocabularies for VAPIX/rules
content, not three, and the reasoning for why they stay two rather than
merging into one is recorded next to `SECRET_PLACEHOLDER_NAMES` in
`vapix.py` and in `admz/redact.py`'s own module docstring, not only here,
so a future consolidation doesn't reintroduce the `{PresetToken}`
regression.

**Enforced at:** `admz/executor/vapix.py::secret_param_names`,
`admz/operations.py` (`execute_gated_operation`, `consume_confirmation`,
`execute_approved_session`), `admz/api/confirm_store.py`
(`ConfirmSession.secret_fields`), `admz/api/routes/confirm.py`
(`_approve_session`), `admz/api/templates/confirm_form.html`. Tested in
`tests/test_vapix_secret_param_names.py` (including the required negative
pin for `{PresetToken}`-style placeholders), `tests/test_operations_core.py`
(both the strip-at-creation and merge-at-approval paths, in both
directions — secret-shaped stripped, ordinary param round-trips),
`tests/test_confirm_store.py`, `tests/test_confirm_secret_fields.py`
(full `/confirm/{token}` HTTP round-trip). Out of scope for this fix: a
plan step (as opposed to a single gated operation) carrying a secret-shaped
param — `execute_gated_plan` serializes plan steps directly and does not
run them through `secret_param_names`; a plan containing a password-change
step would still store it in plaintext. Not introduced by this PR, but not
closed by it either.

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

**Narrowed by #334** for the confirm-approval path specifically: a
catalog-declared secret param (e.g. a device password entered on
`/confirm/{token}`) is no longer written to the confirm-session row or
rendered on the page, so the persistent-storage and browser-history
exposure this gap used to include there is closed (FR-SEC-016). What
remains, and is *not* closed by that fix: the value still transits the
approval POST body and lives as an ordinary (unzeroized) `str` in process
memory for the duration of executing the operation — exactly the ⚠️ this
entry has always described, just with a smaller surface than before.

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
