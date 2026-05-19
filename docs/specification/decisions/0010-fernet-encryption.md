# ADR-0010: Fernet at-rest encryption with auto-generated keys

**Status:** Accepted, in production.
**Date:** Original design 2026-02; recorded as ADR 2026-05-18.

## Context

The default SQLite backend stores device credentials. A stolen laptop,
unencrypted backup, or compromised host gives an attacker the database
file. We needed at-rest encryption that:

1. Works zero-config on first install (no asking the operator to
   provide a master key).
2. Doesn't require an external service (so workgroup hosts work).
3. Has a sensible primitive — symmetric AES with integrity, not raw
   AES or some bespoke construction.
4. Doesn't leak across instances (two registries on the same machine
   pointing at different DBs must have independent keys).

## Decision

Use the `cryptography` library's **Fernet** recipe (AES-128-CBC +
HMAC-SHA256). The key is auto-generated on first run and stored
beside the database:

```
~/.admz/admz.db     # encrypted at the field level
~/.admz/admz.key    # 32-byte Fernet key, chmod 0o600
```

Override via `ADMZ_DB_PATH` / `ADMZ_KEY_PATH` env vars. The key file
is created with `chmod 0o600` on Unix (best-effort on Windows; ACLs
work differently and we don't try to replicate Unix mode semantics).

Each `SQLiteDeviceRegistry` instance loads its own key from
`self._key_path` — there's no module-global Fernet object, so two
registries pointing at different key files don't share state. This
was an explicit fix: the original implementation had a global
`_FERNET` that meant the second-built registry silently reused the
first's key.

What gets encrypted: just the `password` field in `accounts.data_json`.
Everything else (device IDs, hostnames, models, usernames) is plain
JSON. The threshold: we encrypt secrets, not metadata.

## Consequences

**Positive:**
- Zero-config — installations work on first run, key creation is
  automatic.
- Standard primitive — Fernet is a well-vetted recipe, no rolling
  our own crypto.
- Per-installation key — a leaked DB without the key file is useless.
- Cheap — encrypt/decrypt is in-memory, no I/O per operation.

**Negative:**
- **Losing the key file = losing all credentials.** No master-key
  wrap, no envelope encryption, no key rotation. Backup discipline
  is documented in README (admz.db + admz.key must be backed up
  together) but not enforceable.
- Metadata (device IDs, hostnames, account labels) is plaintext. An
  attacker with the DB file learns *what* you have, even if they
  can't get *what's in* the credentials.
- No HSM integration. Enterprise deployments with that requirement
  use Vault instead (ADR-0011).

**Alternatives considered:**
- **Whole-DB encryption (SQLCipher).** Rejected for v1 — adds a
  build-time dependency on a non-standard SQLite, complicates
  deployment.
- **Master key derived from a passphrase.** Rejected — operators
  would have to type a passphrase on every ADMZ startup. Doesn't
  match the "zero-config local installs" persona.
- **OS keychain integration.** Considered for v2 — most platforms
  have one (Windows DPAPI, macOS Keychain, Linux libsecret). Cross-
  platform abstraction is non-trivial; deferred.

## References

- ADR-0011 — Vault as an enterprise alternative
- ADR-0014 — config in git, creds in DB (this ADR is for the DB side)
- Requirements: [credential-storage.md](../requirements/credential-storage.md)
- Code: `admz/backends/sqlite_backend.py::_build_fernet`, `_encrypt`, `_decrypt`
