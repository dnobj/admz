# Requirements: credential storage

Where device credentials live, how they're encrypted, how they get
in, how they get out, and what's NEVER stored.

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-CRED-001 — SQLite + Fernet (default backend) ✅
Account passwords stored encrypted with `cryptography.fernet.Fernet`
(AES-128-CBC + HMAC-SHA256). Key auto-generated on first run, stored
at `~/.admz/admz.key` with chmod 0o600 (Unix; best-effort on
Windows). Override via `ADMZ_KEY_PATH`. See
[ADR-0010](../decisions/0010-fernet-encryption.md).

### FR-CRED-002 — HashiCorp Vault (enterprise backend) ✅
Selected via `DEVICE_REGISTRY_BACKEND=vault`. Reads/writes to KV-v2
under `secret/data/devices/<device_id>/{device_info,accounts/<account_id>}`.
AppRole (`VAULT_ROLE_ID` + `VAULT_SECRET_ID`) or token
(`VAULT_TOKEN`) auth. Vault's own audit log + access policies apply.
See [ADR-0011](../decisions/0011-pluggable-backends.md).

### FR-CRED-003 — Out-of-band credential capture ✅
`capture_credentials(device_id, ...)` returns a one-time URL the user
opens in a browser to submit the password. The form submits directly
to the registry; the password **never enters the LLM's context, chat
transcript, or server logs**. See
[ADR-0009](../decisions/0009-oob-credential-capture.md).

Implementation: `admz/api/capture.py::CaptureStore` (SQLite, WAL,
per-call connections), `admz/api/routes/capture.py` (browser form +
JSON polling endpoints).

### FR-CRED-004 — Batch capture for fleet provisioning ✅
A single capture session can carry multiple `device_ids` so an
operator entering credentials once stores them across N devices.

### FR-CRED-005 — Active credential probing ✅
`test_device_credentials(host, username?, password?, passwords?)`
sends candidate creds to a device (no-auth → legacy `root/pass` → up
to 5 user-supplied passwords). Returns success/failure WITHOUT
echoing the working password. `store=true` saves to the registry on
success.

### FR-CRED-006 — Per-protocol auth method storage ✅
Detected auth methods (digest/basic/bearer) are stored in
`device_info["auth"] = {"http": ..., "https": ..., "scheme": ...}`
during `provision_device` / `test_device_credentials`. The executor
uses the right scheme per request. See
[ADR-0007](../decisions/0007-per-protocol-auth.md).

### FR-CRED-007 — Auto-provisioning ✅
`provision_device(host_or_device_id, password=...)`:
- Detects factory-default state → calls `pwdgrp.cgi:add-user` to
  create admin user, stores creds.
- Detects legacy default `root/pass` → stores creds (or rotates
  if `force_change=true`).
- Returns structured outcome; generated passwords are never echoed
  in the response.

Password source: explicit arg > fleet `default_password` > 24-char
generated.

### FR-CRED-008 — Temporary device-side users ✅
`create_temp_credentials(device_id, permissions, ttl_seconds)`
creates an `at_<8 hex>` user on the device, returns the plaintext
(this is the one place plaintext **is** intentional — the whole point
is that the LLM uses these creds directly for a brief window).

Max 3 temp creds per device. TTL 60–3600s. Background loop cleans
expired ones via `pwdgrp.cgi:remove-user`.

### FR-CRED-009 — Plaintext retrieval is opt-in ✅
`get_credentials` (MCP) and `GET /api/devices/{id}/credentials` (REST)
both return the plaintext password — but only when
`tool_get_credentials_enabled == "true"` in fleet settings. Default:
disabled. The flag is in `PROTECTED_SETTING_KEYS` and can only be
flipped via the web UI at `/confirm-settings`. See
[ADR-0020](../decisions/0020-protected-fleet-settings.md).

### FR-CRED-010 — Per-protocol detection on every probe ✅
`_detect_auth_schemes()` parses `WWW-Authenticate` from 401 responses
on both HTTP and HTTPS. Result stored as a dict per FR-CRED-006.

## Non-functional requirements

### NFR-CRED-001 — Plaintext never in raw DB bytes ✅
Tested in `tests/test_sqlite_backend.py::test_password_is_encrypted_at_rest`
— the SQLite file is inspected for the plaintext password string,
which must not appear.

### NFR-CRED-002 — Audit log records every credential retrieval ✅
`GET /api/devices/{id}/credentials` writes an `audit_log` row with
the authenticated principal as requester, the device_id + account_id
as resource, success/failure, error message.

### NFR-CRED-003 — Capture tokens are 256-bit single-use ✅
`secrets.token_urlsafe(32)`. SQLite `UPDATE … WHERE status='pending'`
prevents double-consumption.

### NFR-CRED-004 — Capture / confirm endpoints rate-limited ✅ (Phase 4 stretch)
10-burst + 10/minute sustained per-IP, configurable.
[reliability.md](reliability.md), [security.md](security.md) KG-SEC-005.

## Known limitations

### KL-CRED-001 — Fernet key has no rotation path ⚠️
Lose `~/.admz/admz.key` → lose all credentials. Documented in README;
no master-key wrap (see [ADR-0010](../decisions/0010-fernet-encryption.md)
"Negative consequences").

### KL-CRED-002 — No automatic credential rotation ⚠️
Manual rotation works via three paths:
- `provision_device(..., force_change=true)` (LLM/MCP/CLI)
- **Web UI "Change password" button** on the account detail
  page — creates a one-time capture session bound to the
  existing device + account_id and redirects the operator to
  the standard `/capture/{token}` OOB form (per ADR-0009).
  Reuses the established capture machinery; the new password
  enters ADMZ only via the browser form, never via chat or
  arbitrary HTML submissions.
- `DeviceRegistry.update_account(device_id, account_id, updates)`
  (programmatic; atomic — replaces the legacy
  `remove_account` + `add_account` pattern that briefly left
  the account observably missing).

Scheduled / policy-driven rotation isn't implemented.

### KL-CRED-003 — No CSRF on capture form POSTs ⚠️
Tokens are single-use and high-entropy, but a CSRF token in the form
would be defense-in-depth. Tracked as KG-SEC-002.

### KL-CRED-004 — Vault mount-point / path-prefix not in env ⚠️
The factory docstring lists `VAULT_MOUNT_POINT` and `VAULT_PATH_PREFIX`
as recognized env vars but the Vault backend doesn't actually read
them. Operators with non-default Vault setups pass them
programmatically.

## References

- ADRs: [0007](../decisions/0007-per-protocol-auth.md), [0009](../decisions/0009-oob-credential-capture.md), [0010](../decisions/0010-fernet-encryption.md), [0011](../decisions/0011-pluggable-backends.md), [0014](../decisions/0014-config-in-git-creds-in-db.md), [0020](../decisions/0020-protected-fleet-settings.md)
- Cross-cutting: [security.md](security.md), [authentication.md](authentication.md)
- Code: `admz/backends/`, `admz/api/capture.py`, `admz/mcp/temp_credentials.py`, `admz/discovery/credential_probe.py`
