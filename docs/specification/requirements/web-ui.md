# Requirements: web UI

The Jinja2-rendered browser-facing pages — humans clicking around to
manage devices, settings, captures, and confirmations. Distinct from
the [web chatbot](web-chatbot.md), which is planned but not yet built.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-UI-001 — Device browsing pages ✅
- `/` — landing page with searchable device list
- `/device/{device_id}` — per-device detail (model, host, location,
  tags, account list, recent snapshots)
- `/search` — full-text search across devices

### FR-UI-002 — Device + account CRUD forms ✅
- `/add-device` — create a device with initial metadata
- `/device/{id}/edit` — update device metadata
- `/device/{id}/add-account` — add an account
- `/device/{id}/account/{account_id}` — view account (no password
  display); revoke or rotate

### FR-UI-003 — Out-of-band credential capture forms ✅
- `/capture/{token}` — single-device or batch credential entry form.
  Renders device metadata (no creds), accepts username + password,
  submits direct to registry. Token is single-use.
- `/capture/fleet/{token}` — fleet-setting password capture; also
  collects `default_username`.

The forms reuse the same `CaptureStore` SQLite machinery the MCP
tool produces tokens against. Cross-surface tokens — a token issued
by MCP can be consumed by the web form.

### FR-UI-004 — Dangerous-operation confirmation forms ✅
- `/confirm/{token}` — renders an approval form. Shows the
  operation/plan, the affected device(s), the catalog-declared
  `danger_description`. For `url_and_password`-level confirms, also
  shows a password field.
- `POST /confirm/{token}` — validates (password if required), marks
  the session complete, the LLM polls and proceeds.

### FR-UI-005 — Fleet settings management ✅
- `/fleet-settings` — read-only display of all fleet settings.
  Password-shaped values are masked.

### FR-UI-006 — Confirm-settings (protected keys) ✅
- `/confirm-settings` — the **only** UI for the protected keys:
  - Per-risk confirmation levels (dropdowns)
  - Confirmation password (set / clear; PBKDF2-hashed)
  - `tool_get_credentials_enabled` toggle

MCP cannot write these (ADR-0020); this page is the privileged entry.

### FR-UI-007 — Error pages ✅
`error.html`, `capture_expired.html` for 4xx/5xx + expired-token
cases. Friendly messaging, no stack traces.

## Non-functional requirements

### NFR-UI-001 — Jinja2 autoescape on, no XSS ✅
FastAPI's `Jinja2Templates` autoescapes by default. All
device-attribute rendering goes through `{{ … }}` and is escaped.
No `{{ … | safe }}` filter on any user-provided value.

### NFR-UI-002 — CSRF protection ⚠️
**Currently absent on capture/confirm form POSTs.** Tokens are
single-use and 256-bit, so a CSRF defense isn't load-bearing for
those routes — but a CSRF token in the form would still be
appropriate. KG-SEC-002 in [security.md](security.md) — the capture POSTs now
enforce same-origin (#3); the confirm POST is still outstanding.

### NFR-UI-003 — No client-side framework dependency ✅
Server-rendered HTML + small amounts of inline JS. No npm toolchain,
no SPA bundler. Operators can deploy ADMZ as a single Python
process without a Node build step.

### NFR-UI-004 — Mobile-readable layout ✅
The CSS is straightforward; templates use semantic HTML. Renders
acceptably on phones (operators sometimes check a device from
their phone while on the floor).

## Known limitations

### KL-UI-001 — Limited interactivity ⚠️
No live updates, no progress streaming, no inline approval cards.
The bundled chatbot (deferred — [ADR-0024](../decisions/0024-bundled-web-chatbot.md))
is the planned home for those richer interactions.

### KL-UI-002 — No login-switching UX ⚠️
Browsers cache Negotiate state, so "sign in as a different user"
isn't reliably achievable from the web UI. Documented in
[authentication.md](authentication.md) KL-AUTH-002.

### KL-UI-003 — No drift visualization 📋
`check_drift` results aren't rendered as a UI page yet. Operators
either use the MCP tool's JSON output or scripts. A "drift dashboard"
page would be a small follow-up.

### KL-UI-004 — No batch device-edit UI 📋
"Add 50 cameras with sequential nicknames" requires either the
discovery flow or per-device clicks. A bulk-edit page would be
useful for Experience Centers.

## References

- ADRs: [0008](../decisions/0008-mcp-and-rest-surfaces.md), [0009](../decisions/0009-oob-credential-capture.md), [0020](../decisions/0020-protected-fleet-settings.md)
- Sibling: [web-chatbot.md](web-chatbot.md) (planned, distinct page set)
- Code: `admz/api/templates/`, `admz/api/routes/web.py`, `admz/api/routes/capture.py`, `admz/api/routes/confirm.py`
