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

## ADMZ_HOME hardening is setup's job, not the code's (added 2026-08-04, #250)

The code deliberately does **not** set an ACL on `ADMZ_HOME` on Windows.
`admz/backends/sqlite_backend.py` now guards its `chmod 0o700` on
`sys.platform` and does nothing on Windows. That absence is a decision, not
an omission awaiting cleanup — record it here so the next reader does not
"finish the job."

Background: `os.chmod` on Windows is a complete no-op for access control
(#207 / ADR-0010). The obvious follow-up was to point #252's ctypes DACL
mechanism at the directory as well. That is wrong, for three measured
reasons:

1. **A file-shaped DACL collapses the contents.** `win_acl`'s
   `build_secret_file_sddl` emits ACEs with no inheritance flags — correct
   for a file, wrong for a container. `SetNamedSecurityInfo` re-propagates
   inheritance to existing children, so a parent left with no inheritable
   ACEs strips theirs. Measured: `admz.db` went from 4 ACEs to **0** — an
   empty DACL, which denies *everyone*, including SYSTEM. A directory-shaped
   `(A;OICI;...)` SDDL does work, but it is a different mechanism, not a
   reuse.
2. **The code cannot know the right principals.** The service runs as
   LocalSystem, so a service-created directory is owned by `S-1-5-18`.
   Granting SYSTEM + Administrators is *not* sufficient for the operator: a
   non-elevated administrator's UAC-filtered token does not carry
   `S-1-5-32-544` at all, and such a file is measured unreadable. This is
   why `setup-admz-service.ps1` grants `${env:USERDOMAIN}\${env:USERNAME}`
   explicitly — an account the running code has no way to identify. The
   production directory's ACL shows the same thing: `DNLT\dnich` appears
   separately from `BUILTIN\Administrators` because it has to.
3. **This is not the creation path.** Twelve sites create `ADMZ_HOME`. In
   the web/service process `admz/events/store.py` creates it at *import*,
   long before the registry is constructed in the FastAPI lifespan — so a
   DACL applied from the registry would land on a directory another module
   already made, potentially with files in it. Worse, because inheritance
   re-propagates, it would rewrite the ACL of the existing `admz.key`, and
   tightening *that* file is #183 — an open operator decision.

So: **`setup-admz-service.ps1` owns Windows ADMZ_HOME permissions**, as this
ADR already said. [ADR-0054](0054-separate-production-tree-and-venv.md) plans
to bring that script into `scripts/`; the SID-vs-name issue below should be
fixed when it lands.

Two defects in the current script, noted for that move:

- It grants `SYSTEM` and the operator **by name**, not by SID
  (`*S-1-5-32-544` is used for Administrators but not the other two). Account
  names are localized; SIDs are not. `admz/win_acl.py` compares only SIDs for
  exactly this reason.
- `robocopy /COPY:DAT` does not copy ACLs (no `S`), so migrated files land
  inheriting `C:\ProgramData` and are rescued only by the subsequent
  directory-level `/inheritance:r` propagating down. That works, but by side
  effect rather than by intent.

The `~/.admz` rollback copy this ADR keeps (see Migration notes) is a second
copy of the Fernet key and DB outside `ADMZ_HOME`. It is absent on the
current deployment, so this is script hygiene rather than a live exposure —
but it belongs in the same cleanup.

## Consequences

- Any host can relocate ADMZ state with one env var; services/agents on the
  same box agree by setting it machine-wide (`setx /M`).
- The chatbot's MCP subprocess pool inherits the parent environment, so
  ADMZ_HOME propagates to tool subprocesses automatically.
- `tests/test_paths.py` pins the precedence + call-time contracts;
  `test_api_import_isolation.py` continues to guard import-time binding.
