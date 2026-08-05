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
~/.admz/admz.key    # 32-byte Fernet key; chmod 0o600 on POSIX,
                    # protected owner-only DACL on Windows (see below)
```

Override via `ADMZ_DB_PATH` / `ADMZ_KEY_PATH` env vars.

### Key-file permissions at creation (amended 2026-08-04, issue #207)

This ADR previously said the key was created with `chmod 0o600` on Unix,
"best-effort on Windows; ACLs work differently and we don't try to
replicate Unix mode semantics." **That is reversed.** "Best-effort" was
not a weaker protection on Windows — it was *no* protection, and ADMZ
ships on Windows only.

`os.chmod(key_path, 0o600)` on Windows never touches the DACL. The only
thing it can affect is `FILE_ATTRIBUTE_READONLY`, and because `0o600`
carries the owner-write bit it *clears* that attribute rather than
setting it. Measured: the DACL is byte-identical before and after,
`os.stat().st_mode & 0o777` reads back `0o666`, and `os.access(W_OK)`
stays `True`. It is a complete no-op.

The key therefore inherited its parent directory's ACL. `C:\ProgramData`
grants `BUILTIN\Users:(OI)(CI)(RX)`, so a freshly-created `ADMZ_HOME`
inherits it and every local user can read the master key that encrypts
the whole fleet's device credentials. ADR-0042 hardens `ADMZ_HOME` via a
*setup script*; that leaves any deployment which never ran the script
silently unprotected.

**The key file is now created with an explicit, protected (non-inheriting)
DACL on Windows** — `admz/win_acl.py`, applied from `_build_fernet`'s
creation branch:

```
D:P(A;;FA;;;S-1-5-18)(A;;FA;;;S-1-5-32-544)(A;;FRFW;;;<owner SID>)
```

`D:P` is the load-bearing part: **P** = `SE_DACL_PROTECTED`, i.e. the
DACL does not inherit. Without it the permissive parent ACEs are merged
straight back in.

Mechanism is ctypes (`advapi32`), not `pywin32`, following ADR-0033's
"no new dependencies". `pywin32` is present in the dev venv only as
`mcp`'s transitive dependency and is declared nowhere; depending on it
would let an `mcp` minor release turn this guard into a silent
`ImportError` on `windows-latest`.

`chmod 0o600` remains the POSIX path, unchanged and still correct.
`os.chmod` is deliberately *not* called on Windows — calling it would
only imply a protection that does not exist. A failure to apply either
is now logged (`admz.backends.sqlite_backend`) instead of being swallowed
by a bare `except OSError: pass`; it is not fatal, because a service that
refuses to boot on an exotic filesystem is worse than one that boots and
says so.

**Consequence, stated plainly for anyone deploying differently:** the
`admz` service runs as **LocalSystem** (ADR-0042), so a key created by
the service is owned by `SYSTEM` and is readable by **SYSTEM and
Administrators only**. A non-elevated user process cannot read it. That
is the intended posture — it is what #183 asks for — but it means a
deployment that runs ADMZ as a non-admin service account, or that expects
a non-admin operator to read the key directly, must grant that principal
explicitly rather than relying on the inherited ACL that used to be
there.

Only the **creation** path is affected. `_build_fernet` short-circuits on
`if key_path.exists()`, so an already-deployed key is never re-ACLed by
this change; tightening those is issue #183, an operator decision.

Each `SQLiteDeviceRegistry` instance loads its own key from
`self._key_path` — there's no module-global Fernet object, so two
registries pointing at different key files don't share state. This
was an explicit fix: the original implementation had a global
`_FERNET` that meant the second-built registry silently reused the
first's key.

What gets encrypted: the `password` field in `accounts.data_json`.
Everything else (device IDs, hostnames, models, usernames) is plain
JSON. The threshold: we encrypt secrets, not metadata.

### Amendment 2026-08-04 — the same key also covers fleet-setting secrets (#296 part 1)

The threshold above was applied only to credentials ADMZ stores **about** a
device. `fleet_settings.default_password` — the credential ADMZ **writes to**
devices — sat in the settings table as a plain value, protected only by the
directory ACL added in #252. So did `gemini_api_key` and `acs_webhook_token`.
That was an inconsistency, not an exploit, and it is now closed: the same
Fernet key encrypts them.

Three things worth recording, because each was a decision:

- **Recoverable, not hashed.** ADMZ has to send these values somewhere, so they
  are encrypted and decrypted. `confirm_password_hash` is the opposite — only
  ever compared — and is deliberately left alone. Copying the hash pattern here
  would break provisioning.
- **The store encrypts, not the callers.** `default_password` alone has three
  readers with no accessor between them; they already shared exactly one path,
  `fleet_settings.get`, so that is where it goes. Patching each call site would
  have been the divergence of #255. One consequence worth knowing: the value a
  caller sees is unchanged, so nothing downstream needed editing.
- **The scope is a checked partition, not a list someone maintains.** Every
  sensitive key must be declared store-encrypted, module-encrypted, or
  deliberately plaintext-with-a-reason (`admz/setting_policy.py`), and a test
  fails if one is not. Encrypting a single key and calling it done is the shape
  that left three of four subresources unpinned in #200.

Migration is read-old-write-new on first `get`, and the trap is that a value
which will not decrypt is **not** necessarily legacy plaintext — it is also what
a rotated or missing key looks like. Migrating that would hand a caller
ciphertext as a password and re-encrypt it, destroying the secret. The two are
told apart structurally (`setting_crypto.looks_encrypted`) before anything is
written; an unreadable value is reported as unset and left untouched, so
restoring the correct key recovers it.

`survey/secrets.py` and `github_app/secrets.py` had each grown an identical
private `encrypt`/`decrypt` pair. They now delegate to `admz/setting_crypto.py`,
so one Fernet path serves every fleet-setting secret rather than a third copy
appearing. Their stored ciphertext is unaffected — same key, same tokens.

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
