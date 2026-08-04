# ADR-0009: Out-of-band credential capture via one-time URL

**Status:** Accepted, implemented.
**Date:** Original design 2026-02; SQLite-backed store landed Phase 0.

## Context

ADMZ is designed to be driven by LLM agents. A naive design has the user type a device password into the chat:

> User: "The lobby camera password is `correcthorsebatterystaple`."
> LLM: *calls `add_account(device_id, …, password="correcthorsebatterystaple")`*

This is bad for several reasons:
1. The password lives in the chat transcript forever (often on third-party infrastructure: Anthropic, OpenAI, etc.).
2. The password is in the LLM's context window, where any prompt-injection in subsequent tool returns could exfiltrate it.
3. Audit logs of "what the LLM said and did" include plaintext credentials.
4. Multi-tenant LLM platforms might cache, fine-tune on, or otherwise persist the chat content.

We needed a way for the LLM to *initiate* credential capture without ever *seeing* the credential.

## Decision

When the LLM (or REST caller) needs to capture a password, it calls `capture_credentials(device_id, account_id, purpose, …)`. ADMZ:

1. Generates a 32-byte URL-safe random token (~256 bits entropy).
2. Stores a `CaptureSession` in SQLite (`api/capture.py::CaptureStore`) bound to the device(s) and account(s), with TTL 10 minutes by default.
3. Returns `{success, url: "http://<host>/capture/{token}", token, expires_in_seconds}` to the LLM.

The user opens the URL in their browser. The form at `GET /capture/{token}` displays device metadata and a password field. On `POST`:

1. The credential is stored directly into the registry by the form handler — the LLM never sees it.
2. The session is marked `completed` (single-use).
3. The form returns a confirmation page.

The LLM polls `check_capture_status(token)` to know when to proceed. The poll returns only `{status, device_id, account_id, message}` — never the credential.

The same pattern handles **batch capture** (one form, many devices: `device_ids: [...]`) and **fleet-setting capture** (`/capture/fleet/{token}` for fleet-wide passwords like `default_password`).

## Consequences

**Positive:**
- The credential never enters the LLM's context. Chat transcripts can be shared, cached, even leaked, without exposing device passwords.
- The credential's journey is the user's browser → the ADMZ server → the registry. No intermediate hop through a third party.
- Single-use tokens mean a leaked URL is neutralized after first submission.
- The session metadata makes the purpose visible to the user before they type ("This form is for `camera-lobby-01`, account `default`, purpose: `Manual configuration`").

**Negative:**
- Two extra round-trips: LLM → token → URL → human → submit → poll. Slower than just typing the password in chat.
- Requires the ADMZ server to be reachable from the user's browser. For localhost dev that's free; for fleet deployments it requires either co-location or a tunnel.
- ✅ The form enforces **same-origin** on POST (#3, `admz/csrf.py`): `Origin` checked, `Referer` as fallback, neither present → refused. Applies to `/capture/{token}`, `/capture/fleet/{token}` and `/capture/rule/{token}`.
  The gap this closes is narrower than it was first written: an attacker who knows the token does not need CSRF at all — they can POST directly. CSRF buys the *victim's ambient credentials*, which only exist under `ADMZ_AUTH_BACKEND=windows`/`composite` (proxy-injected Negotiate header, no cookie, so `SameSite=Lax` cannot help). `POST /confirm/{token}` still needs the same call — see KG-SEC-002 in `security.md`.
- ⚠️ No rate limiting on the POST handler. Tokens are single-use so this is mostly moot, but a determined attacker who races the legitimate user could overwrite the captured password.

**Alternatives considered:**
- **Type password in chat.** Rejected — see Context above.
- **Encrypt password in chat, decrypt server-side.** Considered — but the encryption key would have to live somewhere, and any place the LLM can see is a place an attacker who controls the LLM can exfiltrate from.
- **Use OS keychain integration.** Rejected for v1 — adds platform-specific code paths; not all deployments have a usable keychain (servers, containers).

## Implementation

- Store: `admz/api/capture.py::CaptureStore` (SQLite-backed, shared with MCP and REST via `~/.admz/admz.db`)
- MCP tools: `capture_credentials`, `check_capture_status` (`mcp/server.py`)
- REST endpoints: `POST /api/capture`, `GET /api/capture/{token}/status`
- Web form: `GET /capture/{token}`, `POST /capture/{token}` (`api/routes/capture.py`)
- Templates: `capture_form.html`, `capture_done.html`, `capture_expired.html`, `capture_fleet_form.html`, `capture_fleet_done.html`

## References

- [Personas: llm-agent, security-conscious-operator](../personas/)
- [Requirements: security FR-SEC-004](../requirements/security.md)
- [User stories: US-DO-003, US-CR-003, US-CR-006](../user-stories/)
- [ADR-0006 — multi-level confirmation](0006-multi-level-confirmation.md) uses the same OOB pattern for the `url_only` and `url_and_password` confirm levels
