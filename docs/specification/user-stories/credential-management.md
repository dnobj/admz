# User stories: credential management

How device credentials are captured, stored, retrieved, and rotated — with special care to keep plaintext out of the LLM context.

## US-CR-001 — At-rest encryption (default)

**As an** operator running ADMZ on a laptop, **I want** stored credentials encrypted at rest **so that** a stolen laptop or backup doesn't expose them.

**Acceptance criteria:**
1. On first run, `SQLiteDeviceRegistry` generates a Fernet key and writes it to `~/.admz/admz.key` with mode `0o600` (Unix; best-effort on Windows).
2. Account passwords are encrypted with the Fernet key before being written to the `accounts.data_json` column.
3. Raw SQLite-file bytes never contain plaintext passwords (verified by `test_password_is_encrypted_at_rest`).
4. Two registries with different key files have independent ciphertexts (no module-global Fernet).
5. The `~/.admz/` parent directory is chmod'd to `0o700` on Unix.

**Related requirements:** [credential-storage](../requirements/credential-storage.md), [security](../requirements/security.md).

**Related decisions:** [0010 — Fernet encryption](../decisions/0010-fernet-encryption.md).

## US-CR-002 — Vault backend for enterprise

**As an** enterprise fleet operator with existing Vault secret-management discipline, **I want** ADMZ to read and write credentials in Vault **instead of** its own SQLite database.

**Acceptance criteria:**
1. Setting `DEVICE_REGISTRY_BACKEND=vault` (or passing `"vault"` to `create_device_registry`) selects the Vault backend.
2. The Vault client uses `VAULT_ADDR`, `VAULT_TOKEN`, or `VAULT_ROLE_ID`+`VAULT_SECRET_ID` (AppRole) for auth.
3. Device metadata lives under `secret/data/devices/<device_id>/device_info`; accounts under `secret/data/devices/<device_id>/accounts/<account_id>`.
4. The Vault backend implements the same `DeviceRegistry` ABC contract — every MCP tool and REST endpoint works identically.
5. The `~/.admz/admz.db` and `admz.key` files are not used when Vault is the backend.

**Related requirements:** [credential-storage](../requirements/credential-storage.md), [configuration](../requirements/configuration.md).

**Related decisions:** [0011 — pluggable backends](../decisions/0011-pluggable-backends.md).

## US-CR-003 — Out-of-band capture (no LLM exposure)

**As an** operator who's chatting with an LLM, **I want to** enter a device password in a browser form **so that** the password never appears in chat history, model context, or server logs.

**Acceptance criteria:**
1. The LLM calls `capture_credentials(device_id, …)` and receives a `/capture/{token}` URL.
2. The user opens the URL, enters the password in a form, submits.
3. The credential is stored directly into the registry by the form handler.
4. The LLM polls `check_capture_status(token)` and sees only `{status: pending|completed|expired_or_not_found}` — never the password.
5. Tokens are stored in the SQLite `CaptureStore` (shared across MCP and REST processes), single-use, 256 bits of entropy, TTL 10 minutes by default.
6. Batch capture (single token for `device_ids: [...]`) is supported.

**Related requirements:** [credential-storage](../requirements/credential-storage.md), [security](../requirements/security.md).

**Related decisions:** [0009 — OOB capture](../decisions/0009-oob-credential-capture.md).

## US-CR-004 — `get_credentials` is opt-in

**As a** security-conscious operator, **I want** device passwords to be **un-viewable through the web/REST UI** and LLM retrieval **disabled by default** **so that** neither a casual UI visitor nor a hostile LLM prompt can exfiltrate device passwords.

**Acceptance criteria:**
1. Device-account passwords are never displayed in the web UI (the account page shows a "stored · never displayed" lock) and there is no device-credential reveal endpoint — `GET /api/devices/{id}/credentials` returns 404 (route removed).
2. The MCP `get_credentials` tool is filtered out of `list_tools()` unless `fleet_settings["tool_get_credentials_enabled"] == "true"`; with the flag off, calling it returns `{success: false, error: "ToolDisabled", ...}`.
3. The flag itself is **protected**: `set_fleet_setting("tool_get_credentials_enabled", …)` from MCP is rejected. Only the web UI at `/confirm-settings` can change it.

**Related requirements:** [security](../requirements/security.md), [mcp-server](../requirements/mcp-server.md), [web-api](../requirements/web-api.md).

**Related decisions:** [0020 — protected fleet settings](../decisions/0020-protected-fleet-settings.md).

## US-CR-005 — Auto-provision a factory-default device with a generated password

**As an** operator unboxing a fresh camera, **I want** ADMZ to generate a strong password and create the admin user **without** me having to choose or type it.

**Acceptance criteria:**
1. `provision_device(host=…)` probes the device and detects factory-default state.
2. ADMZ calls `pwdgrp.cgi:add-user` to create the admin user with a 24-char generated password (mixed case + digit).
3. The credential is stored in the registry under account `default`.
4. The generated password is **never returned** in the response.
5. To retrieve it later, the operator enables `tool_get_credentials_enabled` and calls `get_credentials(device_id)`.

**Related requirements:** [mcp-server](../requirements/mcp-server.md), [credential-storage](../requirements/credential-storage.md).

## US-CR-006 — Fleet-wide default password set via OOB

**As an** enterprise operator deploying 200 cameras, **I want** to set the fleet's default provisioning password once **so that** every provision call uses the same value, **and so that** the password is captured via OOB rather than typed in chat.

**Acceptance criteria:**
1. The LLM calls `set_fleet_setting(key="default_password")` (with `value` omitted).
2. The MCP returns `{success, action: "capture", capture_url: "/capture/fleet/{token}", token}`.
3. The user opens the URL, enters the password (and optionally a username) in the form.
4. On submit, both `default_password` and `default_username` are written to `fleet_settings`.
5. Subsequent `provision_device(...)` calls use these defaults when no explicit `password` argument is given.
6. `get_fleet_settings` returns the password as a masked placeholder (e.g. `****** (12 chars)`) — both via MCP and via `GET /api/fleet/settings`.

**Related requirements:** [credential-storage](../requirements/credential-storage.md), [mcp-server](../requirements/mcp-server.md), [web-api](../requirements/web-api.md).

## US-CR-007 — Per-protocol auth detection

**As an** operator with cameras that enforce digest auth on HTTP but basic auth on HTTPS, **I want** ADMZ to use the right auth scheme per protocol **so that** I don't see spurious 401s.

**Acceptance criteria:**
1. `provision_device` / `test_device_credentials` send a probe request to each scheme and parse the `WWW-Authenticate` header.
2. The detected auth methods are stored in `device_info["auth"] = {"http": "digest", "https": "basic", "scheme": "http"}`.
3. The VAPIX executor uses the scheme-appropriate auth at request time.
4. Backward-compat: a legacy `device_info["auth_method"]` value (a single string) is honored as a fallback when the structured `auth` dict isn't present.

**Related requirements:** [executor](../requirements/executor.md), [discovery](../requirements/discovery.md).

**Related decisions:** [0007 — per-protocol auth](../decisions/0007-per-protocol-auth.md).

## US-CR-008 — Manual credential rotation

**As an** operator following a security incident, **I want to** rotate the admin password on a device **so that** the old credential becomes invalid.

**Acceptance criteria:**
1. `provision_device(device_id, force_change=true, password="<new>")` calls `pwdgrp.cgi:update-user` on the device.
2. On success, the new password replaces the stored one in the registry.
3. On failure, the old credential remains stored (the rotation is atomic-from-ADMZ's-perspective).
4. The web UI offers a "Rotate" action on the device's account page (which submits an `update_user` operation under the hood).

**Related requirements:** [credential-storage](../requirements/credential-storage.md), [web-ui](../requirements/web-ui.md).

## Known limitations (as of 2026-05)

- 📋 **No automatic rotation policy.** Scheduled rotation (e.g. "every 90 days") is not implemented — operators rotate manually.
- ⚠️ **Fernet key has no rotation path.** Losing `~/.admz/admz.key` means losing all encrypted credentials. There is no master-key wrap or envelope encryption.
- ⚠️ **No audit log of credential access.** The registry ABC's `requester` parameter is documented but ignored by the SQLite backend.
- ⚠️ **No CSRF protection** on the `/capture/{token}` POST handler. Tokens are high-entropy and single-use, but a CSRF defense would still be appropriate.
- 📋 **No rate limiting** on capture attempts. The unguessable token is the only barrier.
