# Persona: Security-Conscious Operator

## Profile

**Who:** The human at the keyboard — possibly a security engineer, a CISO's designee, or just an operator who's been bitten once and is suspicious by default. Sets the safety policy for everyone else (Experience Center operators, enterprise fleet operators, LLM agents).

**Technical level:** Understands authentication, authorization, encryption, attack surfaces. Reads CVEs. Has opinions about TLS, CSRF, secret-rotation cadence.

**Scale:** Whatever the deployment is. This persona's concerns scale with blast radius, not device count.

**Frequency of use:** Configures policy once, audits periodically. Doesn't drive day-to-day operations — but every other persona must operate within the bounds this one sets.

## Goals

- **Constrain what LLMs can do unilaterally.** Dangerous operations must require a human approval that the LLM cannot fake.
- **Keep credentials out of LLM context.** Never let a plaintext password flow into a model.
- **Encrypt credentials at rest.** Default storage encryption with documented key handling.
- **Audit access to credentials and execution of operations.** Who got what credential when, what plan ran when, what changed when.
- **Audit device configuration on a schedule.** Detect unauthorized or out-of-band config changes (someone logged into a device's own web UI, an integration partner pushed a config) without relying on anyone remembering to look — a recurring, unattended configuration audit that runs with no LLM in the loop.
- **Block writes to security-critical fleet settings from anywhere but the web UI.** The LLM cannot loosen its own guardrails.
- **Verify device identity** before trusting it — confirm certificates, MAC OUI, serial.
- **Defend against typical web vulnerabilities** — CSRF, XSS, open CORS, weak TLS.
- **Rotate credentials and keys** on a schedule or after an event.
- **Restrict device-side users to least privilege** — temp creds with `viewer` permissions where `admin` isn't needed.

## Pains today (without ADMZ or with naive deployment)

- "Bot got the password" — the LLM saw a credential and now the credential is in the model's context window forever.
- "Bot rebooted production" — the LLM unilaterally invoked a service-affecting operation it shouldn't have.
- "Bot turned off the safety gate" — the LLM was allowed to modify confirmation policy.
- "Anyone on the network can change device passwords" — the management surface had no authentication.
- "We lost the key file" — at-rest encryption with no recovery path.
- "We can't tell who restarted that device" — no audit log.

## Use cases (links to user stories)

- [LLM-driven configuration](../user-stories/llm-driven-configuration.md) — the gating points.
- [Credential management](../user-stories/credential-management.md) — OOB capture, temp creds, rotation.
- [Drift and monitoring](../user-stories/drift-and-monitoring.md) — configuration audits (just-in-time + scheduled) as a detective control.
- [Scheduled operations](../user-stories/scheduled-operations.md) — the unattended-job framework scheduled audits run on (no LLM in the loop).
- This persona is also the *author* of the security and reliability requirements files.

## What ADMZ owes this persona

- **Two-gate safety.** Independent semantic (LLM/user) and mechanical (catalog risk-level) approval for every write.
- **Multi-level confirmation by risk.** `dangerous` → `url_and_password` by default; `service-affecting` → `llm_confirm`; configurable per fleet.
- **OOB credential capture.** Passwords enter via a one-time browser URL, not via chat.
- **Fernet at-rest encryption** for SQLite-backed credentials, with a per-installation key file.
- **Vault as a first-class alternative** for enterprise deployments.
- **Protected fleet-setting keys.** `confirm_level_*`, `confirm_password_hash`, `tool_get_credentials_enabled` are settable only via the web UI.
- **`get_credentials` MCP tool disabled by default.** Must be explicitly enabled per fleet via the protected setting.
- **Per-protocol auth.** ADMZ tracks `{"http": "digest", "https": "basic"}` per device so it uses the auth the device actually expects.
- **Risk classification in the catalog.** Every operation declares its level; the system doesn't reason about it.
- **Single-use confirm tokens** with TTL (5 minutes).

## What ADMZ does *not* yet provide (known gaps this persona should call out)

- ⚠️ **No authentication to ADMZ itself.** Web UI and REST API have no auth — security depends entirely on network controls (private subnet, VPN). Adding auth is a top priority.
- ⚠️ **`verify_ssl=False` by default.** The VAPIX executor and discovery probes do not verify device TLS certificates by default. Reasoning: most Axis devices ship with self-signed certs; verifying would require pre-installing trust anchors. Documented but worth changing for environments that have done the cert work.
- ⚠️ **CORS allow-all** on FastAPI app. Acceptable for localhost-only use; risky for any other deployment.
- ⚠️ **No CSRF protection** on capture and confirm forms. Tokens have high entropy (32 bytes) and are single-use, but a CSRF defense would still be appropriate.
- ⚠️ **No audit log** of credential access or operation execution. Git history of snapshots is the closest equivalent for configuration changes.
- ⚠️ **No master-key wrap for Fernet.** Lose the key file, lose all credentials. No envelope encryption, no support for key rotation.
- ⚠️ **Plan engine can bypass dangerous-op gate** when steps are run via the engine directly rather than via `execute_operation` — a known structural gap.
- ⚠️ **Two confirmation systems coexist** (in-memory tokens + SQLite ConfirmStore) and are not yet unified.

## Constraints (for ADMZ developers)

- **Don't accept a feature request that loosens a safety gate** without explicit decision-record discussion. (See [decisions/0005](../decisions/0005-two-gate-plan-approval.md), [0006](../decisions/0006-multi-level-confirmation.md), [0020](../decisions/0020-protected-fleet-settings.md).)
- **Don't add MCP tools that return credentials, even "just this once."**
- **Don't expose settings management to MCP** that affects the LLM's own guardrails.
- **Don't default `verify_ssl=True` without giving operators a migration path** for self-signed certs.

## Anti-personas

- Not the day-to-day operator — though the day-to-day operator depends on this one's choices being sane defaults.
- Not the LLM agent — this persona's job is *constraining* the LLM agent.
