# ADR-0014: Configurations in git, credentials never in git

**Status:** Accepted, in production.
**Date:** Original design 2026-04 (`EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md`).

## Context

The snapshot/restore system commits device configurations to git. Git
history is forever — every commit is a permanent record that
propagates wherever the repo is cloned, pushed, mirrored, or backed
up. That property makes git great for configuration tracking and
terrible for secrets.

A naive design might dump everything-the-device-knows into git: param
trees, user accounts, stream profiles, certificates, AND the
passwords. That would make a single repo leak compromise every
credential ever stored for every device.

## Decision

Strict separation:

**Goes in git** (`fleet/<device>/config/`, `fleet/<device>/raw/`):
- Device metadata (model, host, tags, location)
- All operational configuration (param trees minus the sensitive
  prefixes, stream profiles, view areas, privacy masks, NTP, time,
  events, action rules, ACAP names + versions + config)
- User account *lists* — usernames and roles only
- Public certificates and trust anchors
- Per-device notes and documentation (markdown)

**Stays in the credential store** (SQLite + Fernet, or Vault):
- Passwords for any device account
- API tokens, bearer tokens, OAuth refresh tokens
- Private keys (matching certs)
- Encryption key references (e.g. the KMS ARN that wraps the Fernet
  key, when we get there)
- Audit logs (operational events; not config)
- In-flight capture / confirm session state

The snapshot engine enforces this with explicit allow/deny lists:

```python
# admz/snapshot/engine.py
SENSITIVE_PREFIXES = [
    "root.HTTPS.PrivateKey",
    "root.Network.Wireless.WPA.",
    "root.RemoteService.",
]

def _is_sensitive(key: str) -> bool:
    return any(key.startswith(p) for p in SENSITIVE_PREFIXES)
```

Sensitive keys are filtered out *before* they reach the YAML or
the raw dump that goes into the commit.

## Consequences

**Positive:**
- The snapshot repo is **safe to share** — clone it onto a backup
  server, mirror it offsite, hand it to a customer auditor. None of
  it leaks credentials.
- Restore plans never include the password — they rebuild user
  accounts by name, then the operator (or an automated provisioning
  step) populates the password fresh.
- The two stores have distinct backup strategies: git has natural
  versioning; the credential store needs the joint `admz.db + admz.key`
  discipline (documented in README).

**Negative:**
- Restore isn't fully autonomous — recreating a user requires both
  the snapshot (username, role) AND a fresh password from somewhere
  (capture flow, generated, or fleet default).
- The sensitive-prefix list is a denylist — new firmware versions
  could expose secrets in new prefixes we haven't yet listed. Worth
  reviewing the list each AXIS OS major release.

**Alternative considered:**
- **Encrypted secrets in git** (sealed-secrets, age, sops). Rejected:
  - Decryption keys would still need a separate secure store.
  - Operationally complex compared to just keeping the secret in the
    credential store from the start.
  - Git history of *encrypted* values is still a leak if the encryption
    is ever broken or the key compromised — once you commit, you can't
    "un-commit" the historical ciphertext.

## References

- [EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md](../../EXPERIENCE_CENTER_CONFIG_MANAGEMENT.md) §3 "What stays in the DB regardless"
- ADR-0010 — Fernet (the DB side)
- ADR-0011 — Vault (the enterprise DB alternative)
- ADR-0013 — hybrid YAML + raw artifact format
- Requirements: [credential-storage.md](../requirements/credential-storage.md), [snapshot-restore.md](../requirements/snapshot-restore.md)
- Code: `admz/snapshot/engine.py::SENSITIVE_PREFIXES`, `_is_sensitive`
