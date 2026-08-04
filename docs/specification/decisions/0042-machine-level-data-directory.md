# ADR-0042 — Machine-level data directory (ADMZ_HOME) + Windows-service deployment

**Status:** Accepted (2026-06-22).
**Relates to:** ADR-0033 (windows-local auth), ADR-0035 (Negotiate SSO),
ADR-0039/0040 (ACS Pro module — process-identity Negotiate).

## Context

All ADMZ state — the SQLite DB, the Fernet key, the git config-repo, the
firmware cache, `schedules.json`, the dev API key — lived under `~/.admz`,
resolved by ~15 independently copy-pasted `Path.home() / ".admz"` expressions.
Coupling server state to the launching user's profile broke down twice:

1. **Running ADMZ as a Windows service.** A service is the only way to get a
   durable, boot-time, login-independent server on Windows. But LocalSystem's
   `~` resolves to `System32\config\systemprofile` (a blank ADMZ), and running
   the service as the interactive user is fragile — on consumer installs the
   account is often Microsoft-account-backed, so the service Log On password is
   the MSA password and breaks whenever it changes.
2. **Fleet deployment.** ADMZ will be installed on multiple servers. Server
   state belongs in a machine-level directory — the same convention ACS itself
   uses (`C:\ProgramData\Axis Communications\...`) — not in whichever admin's
   profile first launched the app.

## Decision

1. **One base directory, one resolver module.** `admz/paths.py` owns all data
   paths. The base is **`ADMZ_HOME`** (env var), default `~/.admz` — dev
   installs are unchanged. Every resolver is **call-time**; nothing reads the
   environment at import time (the two prior import-time constants —
   `executor.vapix._UPLOAD_ROOT`, `firmware.downloader._DEFAULT_FIRMWARE_DIR` —
   became functions).
2. **Precedence:** specific override (`ADMZ_DB_PATH`, `ADMZ_KEY_PATH`,
   `ADMZ_CONFIG_REPO_PATH`, `ADMZ_REPO_PATH_ROOT`, `ADMZ_SURVEY_*`) →
   `ADMZ_HOME`-derived → `~/.admz` default. The specific overrides predate
   ADMZ_HOME and remain authoritative, so the ~100 tests isolating via
   `ADMZ_DB_PATH` are untouched even on a machine with a global ADMZ_HOME.
3. **Deployment shape (Windows):** `ADMZ_HOME=C:\ProgramData\admz`; ADMZ runs
   as a Windows service via the **Shawl** wrapper
   (https://github.com/mtkennerly/shawl), run-as **LocalSystem** (no stored
   password, starts headless at boot). `setup-admz-service.ps1` performs the
   one-time migration + service registration.
   **Extended by [ADR-0054](0054-separate-production-tree-and-venv.md)** — this
   decision settles where production's *data* lives and the service identity
   that reads it, both unchanged; 0054 settles where its *code and interpreter*
   live and repoints the service's `--cwd` and interpreter path at a dedicated
   production clone and venv.

## Why LocalSystem works (verified in code + live)

- `LogonUserW` (form login) needs no process privilege; the SSPI Negotiate
  acceptor (SSO) extracts the principal from the *client* token — neither
  depends on the process identity.
- The ACS Pro connection authenticates as the process identity (by design, no
  stored password). SYSTEM's token includes BUILTIN\Administrators, which ACS
  installations typically authorize. If a given ACS server refuses it, set the
  service Log On to a dedicated local account that ACS authorizes (fixed local
  password) — the data dir no longer forces that choice.
- The Firebird reader uses `tempfile.gettempdir()` (`C:\Windows\Temp` under
  SYSTEM) and reads ACS's own ProgramData files.

## Migration notes (per machine)

- File copy `~/.admz` → `C:\ProgramData\admz` (source kept as rollback).
- **Security:** default ProgramData ACLs let all Users read created files. The
  setup script disables inheritance and grants SYSTEM + Administrators only
  (+ the dev account on single-operator dev boxes) — the dir holds the Fernet
  key, the DB, and the dev API key.
- **Git ownership:** a repo created by a user and read by SYSTEM trips Git
  2.36+ "dubious ownership." The script sets the tree's owner to SYSTEM and
  adds `git config --system safe.directory` entries.
- **`organizations.repo_path` is stored absolute** in SQLite and immutable via
  the API; the migration updates it directly.
- Config-repo `git push` from a service has no per-user GitHub credentials;
  pushes are best-effort. If remote push is ever needed from the service, use a
  machine-level credential (deploy key) — deliberately out of scope here.

## Consequences

- Any host can relocate ADMZ state with one env var; services/agents on the
  same box agree by setting it machine-wide (`setx /M`).
- The chatbot's MCP subprocess pool inherits the parent environment, so
  ADMZ_HOME propagates to tool subprocesses automatically.
- `tests/test_paths.py` pins the precedence + call-time contracts;
  `test_api_import_isolation.py` continues to guard import-time binding.
