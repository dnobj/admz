# ADR-0045 — GitHub App "Connect GitHub" flow for config-repo backup

**Status:** Accepted (2026-07-11).
**Relates to:** ADR-0042 (ADMZ_HOME / LocalSystem service), PR #103 (repo-local git
identity), PR #105 (non-blocking push / tree-kill), [[project-admz-home-service]].

## Context

The config-repo (device-config history) mirrors to a private GitHub repo, but under
the LocalSystem service there are no push credentials, so the mirror was disabled
(PR #105 made a missing/hung push harmless). Restoring it needed a credential
mechanism that works headlessly under SYSTEM. The operator's requirement: setup
should be a **streamlined "approve this app" step**, not a manual PAT/SSH-key paste.

Options weighed:
- **SSH deploy key** — needs a public key hand-copied into repo settings; no
  approve-and-redirect UX.
- **Fine-grained PAT** — needs the operator to create + paste a long-lived token;
  sits on disk.
- **GitHub App** — the operator clicks "Connect", GitHub shows an install/authorize
  page, and ADMZ mints **short-lived (1h), auto-rotated, repo-scoped installation
  tokens**. This is the requested UX *and* the most secure option.

## Decision

Ship a **GitHub App** connect flow using GitHub's **App Manifest** (so even the App
*registration* is redirect-and-approve — GitHub creates the App from ADMZ's manifest
and returns its credentials). ADMZ runs on localhost and GitHub permits `127.0.0.1`
callback URLs, so the OAuth redirects work for the local deployment.

New subsystem `admz/github_app/` + routes + a Settings card:

1. **Secrets** (`github_app/secrets.py`) — the App **private key** + **client
   secret** are Fernet-encrypted in `fleet_settings` (reusing the one registry key,
   mirroring `survey/secrets.py`); id/slug/installation/repo are plaintext. Keys with
   `key`/`secret` in the name auto-mask via `redact.py`; all are in
   `PROTECTED_SETTING_KEYS` (no MCP/anonymous writes).

2. **Client** (`github_app/client.py`) — signs the App JWT (RS256) with the
   already-present `cryptography` (no PyJWT added), mints installation tokens
   (in-memory cache, ~5 min early refresh), exchanges the manifest code, lists
   installation repos. httpx sync style from `survey/github.py`.

3. **Routes** (`api/routes/github_app.py`):
   - `GET /api/github/connect` — auto-submit the manifest to GitHub (auth required).
   - `GET /api/github/setup/callback` — exchange the code → store the App → redirect
     to install.
   - `GET /api/github/install/callback` — store the installation, resolve the repo,
     set the config-repo `origin`.
   - `POST /api/github/test` / `POST /api/github/disconnect`.
   The two callbacks are **auth-exempt** (a cross-site redirect has no ADMZ session)
   and self-authenticate via an **HMAC-signed, 15-min `state`** (precedent:
   `/api/acs/rule-fired`); `connect`/`test`/`disconnect` require an authenticated
   principal.

4. **Push token injection** (`snapshot/git_repo.py`) — `_do_push` mints a fresh
   installation token and hands it to git via **`GIT_ASKPASS`** + an env var, with
   `-c credential.helper=` to disable ambient helpers (Windows Credential Manager).
   The token never appears in the command line or the persisted remote URL (which
   stays `https://x-access-token@github.com/<owner>/<repo>.git`). No App connected →
   the plain push path is unchanged. `_run_git` gained an `env=` param;
   `set_remote_url()` sets/removes `origin` at runtime.

5. **Settings UI** — a "GitHub config backup" card: **Connect GitHub** / **Test** /
   **Disconnect** with a status badge.

## Consequences

- Setup is one click → approve on GitHub → done; no secret to paste. Tokens are
  short-lived, repo-scoped, auto-rotated; revoke by uninstalling the App on GitHub.
- The App **private key** does live on the ADMZ host (Fernet-encrypted) — inherent to
  GitHub Apps. It's the operator's own App on their own account.
- Builds on PR #105: even if a token mint or push fails, the background push path
  degrades harmlessly and never blocks the server.
- **Deferred:** org-owned Apps (the connect flow targets a personal account by
  default), and single-use `state` (HMAC + 15-min expiry is the CSRF guard today;
  the manifest `code` is itself single-use server-side).
