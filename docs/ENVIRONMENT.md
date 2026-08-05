# Environment variables

Every `ADMZ_*` variable the code reads, grouped by the decision it belongs to
rather than alphabetically — because the decisions are not equally weighted. The
variable that decides whether an unauthenticated request becomes an
authenticated principal does not belong in the same list as the one that caps
how many characters of a tool result reach the model.

**Where the truth lives.** Anything that weakens a guarantee is declared in the
capability registry (`admz/capabilities.py`, ADR-0052), which is what
`/settings/advanced`, `/api/health` and the topbar chip all render. A test
fails if a new `ADMZ_*` name is neither registered there nor listed in
`ORDINARY_CONFIG`, so the *classification* cannot silently drift. This page is
the human-facing half of that: it says what each one does to a running system.

Defaults below were read out of the code, not restated from other docs.

---

## 1. Standing an instance up

The variables you must get right before anything works. `ADMZ_HOME` is the one
that matters most: everything else resolves under it unless individually
overridden (ADR-0042).

| Variable | Default | What it does |
|---|---|---|
| `ADMZ_HOME` | `C:\ProgramData\admz` on Windows | The data directory: database, Fernet key, config repo, firmware cache. **Secret-bearing** — it holds the key that decrypts every device credential (#252 hardens its ACL). |
| `ADMZ_PORT` | `4242` | The port ADMZ believes it is serving on. Used to build absolute URLs when a request carries no `Host` header. Setting it does **not** bind the port — `--port` does that. |
| `ADMZ_AUTH_BACKEND` | `none` | `none` / `api-key` / `windows` / `windows-local` / `composite`. `none` maps every caller to the anonymous principal, which can read and make low-risk changes but not mint API keys, delete devices or write protected settings. |
| `ADMZ_BASE_URL` | derived from the request | Absolute base for capture and confirmation URLs handed to a human. Set it when ADMZ sits behind a proxy that rewrites the host. |
| `ADMZ_LOG_LEVEL` | `INFO` | `CRITICAL` / `ERROR` / `WARNING` / `INFO` / `DEBUG`. |
| `ADMZ_LOG_FORMAT` | plain | Log line format. |

Individual path overrides, each of which wins over `ADMZ_HOME`:
`ADMZ_DB_PATH`, `ADMZ_KEY_PATH`, `ADMZ_CONFIG_REPO_PATH`, `ADMZ_CATALOG_PATH`,
`ADMZ_REPO_PATH_ROOT`, `ADMZ_SURVEY_OUT`, `ADMZ_SURVEY_WORK`.

> `ADMZ_KEY_PATH` points at the Fernet key that encrypts device credentials
> *and*, since #296, the fleet-setting secrets. Move it and previously stored
> values stop decrypting — they are reported as unset, and deliberately left
> untouched, so pointing it back recovers them.

---

## 2. Reproducing staging

`CLAUDE.md` describes staging as running "with health polling turned down and
GitHub config-push disabled". These are the variables that produce that, and
they are the reason this page exists: the effects were documented while the
controls were not, so the claim could not be verified or reproduced.

| Variable | Default | Set it to… |
|---|---|---|
| `ADMZ_AUTO_PUSH` | **ON** | `false` / `0` / `no` / `off` to stop pushing the config repo to its origin. Anything else — **including leaving it unset** — is ON: the check is `raw not in ("false","0","no","off")`. |
| `ADMZ_HEALTH_INTERVAL_SECONDS` | `60` | A larger number to poll a real fleet less often from a second process. |
| `ADMZ_HEALTH_TIMEOUT_SECONDS` | `5` | Per-probe timeout. |
| `ADMZ_PORT` | `4242` | `4243` for staging. |

**The `ADMZ_AUTO_PUSH` default is the trap.** A second instance built from the
documentation alone would push its config repo to the configured origin, and
staging carries a copy of real device data. Configurations are in git and
credentials never are (ADR-0014), so this is not a credential leak — but it is
a second writer against a shared remote, which is not what anyone intends.

---

## 3. Switches that weaken a guarantee

Each of these is in the capability registry with a danger class, is loud in all
five capability surfaces, and none is appropriate in production. What follows is
the plain statement of what each one gives up.

### `ADMZ_TEST_AUTH` — *dev-only*

Resolves an **unauthenticated** request to a synthetic principal, so an agent can
drive a staging UI with no human sign-in.

- The principal is **authenticated but unprivileged** — no group membership by
  default, so reveal-gated surfaces (plaintext credentials, `/settings/advanced`)
  still refuse it. Grant membership deliberately with `ADMZ_TEST_AUTH_GROUPS`,
  and `ADMZ_TEST_AUTH_USER` names it.
- It changes **who the principal is**, never whether a confirmation gate fires.
- `python -m admz api` **refuses to start** (exit 2) when this is active and
  `--host` is not loopback. There is deliberately **no override** — the comment
  at `admz/__main__.py::_check_test_auth_bind` explains why: nothing legitimately
  needs a synthetic principal exposed off-box.
- That refusal lives in the CLI entry point. Production launches through
  `python -m admz api` (see `DEPLOYMENT_WINDOWS.md`), so it runs — but a
  deployment that invoked `uvicorn admz.api.main:app` directly would not get it.

### `ADMZ_DEV_AUTO_APPROVE` — *dev-only*

Lets the unattended approver in `tools/dev_auto_approve.py` satisfy `url_*`
confirmation gates meant for a human, so end-to-end tests can run without one.

The gate still **fires** — this only changes *who may satisfy it*, and ADR-0034
is untouched. The approver posts to the real endpoint exactly as a browser
does, so the server cannot tell the difference. Companions:
`ADMZ_DEV_API_KEY`, `ADMZ_DEV_CONFIRM_PASSWORD`.

### `ADMZ_ACS_RULE_WRITE` — *dangerous, and not yet implemented*

Registered, classified, and **read by nothing**. The registry row is a
declaration ahead of #131 building it. Setting it today has no effect; it is
listed here so that is a documented fact rather than something you discover by
experiment.

### `ADMZ_AUTH_INSECURE_BIND_OK`

Suppresses the refusal to bind a non-loopback address without a trusted reverse
proxy. It exists because a proxy deployment can legitimately need a private-NIC
bind. It does **not** suppress the `ADMZ_TEST_AUTH` refusal, which is separate
and has no override.

### `ADMZ_VERIFY_SSL`

**Defaults to `false`** — device TLS is not verified, a backward-compatible
default (#1). It governs ADMZ→device connections, not the browser→ADMZ side.

### Test suppressors — never set these outside a test run

`ADMZ_DISABLE_ONBOARDING_PROBES` and `ADMZ_DISABLE_GITHUB_APP_PUSH` turn off
real behaviour so the suite does not reach the network. Both are classified
`test-suppressor` / not production-appropriate. A suppressor left set in a
deployment is silent: the behaviour simply never happens.

### Privileged switches (appropriate in production, deliberately off by default)

`ADMZ_SURVEY_MODE`, `ADMZ_EVENT_INGEST`, `ADMZ_ACS_EVENT_INGEST`,
`ADMZ_ACS_FIREBIRD`. Each turns on a subsystem that reaches something outside
ADMZ — the atlas repo, device event streams, an ACS install. `ADMZ_SURVEY_MODE`
in particular makes ADMZ probe devices across a subnet and open upstream PRs.

---

## 4. Authentication and session

| Variable | Notes |
|---|---|
| `ADMZ_REVEAL_GROUPS` | Groups granting plaintext-credential reveal. Default is the `Administrators` / `ADMZ-Admins` pair. Since #274 both sides are resolved to SIDs when the names do not match, so the English default still matches a localised built-in group. |
| `ADMZ_SESSION_TTL_SECONDS` | Inactivity before a web session expires. Default `43200` (12 h). |
| `ADMZ_SESSION_COOKIE_SECURE` | Forces the `Secure` cookie attribute. Set it when ADMZ is behind TLS. |
| `ADMZ_SSO_NEGOTIATE` | Enables the in-process Negotiate SSO login path (ADR-0035). |
| `ADMZ_AUTH_REMOTE_USER_HEADER`, `ADMZ_AUTH_TRUSTED_PROXIES` | Reverse-proxy IWA (ADR-0021). The header is only trusted from a listed proxy. |
| `ADMZ_TRUSTED_ORIGINS`, `ADMZ_ALLOWED_ORIGINS` | CSRF origin allow-list and CORS origins. |
| `ADMZ_LDAP_ENABLED` | Turns on LDAP group enrichment (ADR-0023). |
| `ADMZ_LDAP_SERVER`, `ADMZ_LDAP_BASE_DN` | Directory to query and where to start. |
| `ADMZ_LDAP_BIND_USER`, `ADMZ_LDAP_BIND_PASSWORD` | Bind credentials. The password is a secret; it is read from the environment and never persisted. |
| `ADMZ_LDAP_GROUP_CACHE_TTL` | How long an enriched group set is reused. |

---

## 5. Tuning

Nothing here changes a guarantee; all of it changes timing, volume or cost.

| Variable | Default | Effect |
|---|---|---|
| `ADMZ_GIT_LOCAL_TIMEOUT_SECONDS` | `30` | Timeout for local git operations. |
| `ADMZ_GIT_NETWORK_TIMEOUT_SECONDS` | `60` | Timeout for `push` / `fetch`. |
| `ADMZ_GIT_AUTHOR_NAME` | `ADMZ` | Commit identity on config commits. |
| `ADMZ_GIT_AUTHOR_EMAIL` | — | As above. |
| `ADMZ_CONFIG_REPO_REMOTE`, `ADMZ_GH_TOKEN` | — | Config-repo origin and its token. |
| `ADMZ_SNAPSHOT_FLEET_CONCURRENCY` | `50` | Devices snapshotted in parallel. |
| `ADMZ_VAPIX_RETRIES` | `1` | Executor retry count per request. |
| `ADMZ_MCP_POOL_IDLE_SECONDS` | `300` | Idle time before a per-principal MCP subprocess is reaped. |
| `ADMZ_CHAT_EVENT_TIMEOUT_SECONDS` | `120` | SSE event timeout on the chat route. |
| `ADMZ_CHAT_MAX_TOOL_RESULT_CHARS` | unset (no cap) | Truncates a tool result before it reaches the model. |
| `ADMZ_GEMINI_API_KEY`, `ADMZ_GEMINI_DEFAULT_MODEL` | — | Bootstrap the corresponding fleet settings on first run. The API key is a secret and is stored encrypted (#296). |
| `ADMZ_GEMINI_THINKING_BUDGET` | `-1` (dynamic) | `0` disables thinking, `>0` fixes the budget. |
| `ADMZ_GEMINI_EMPTY_RETRIES` | `4` | Retries when the model returns an empty part; `0` disables. |
| `ADMZ_GEMINI_EMPTY_RETRY_THINKING_BUDGET` | — | Thinking budget used for those retries specifically. |
| `ADMZ_GEMINI_MANUAL_TOOL_LOOP` | ON | `0` falls back to the SDK's automatic loop. ADR-0025 records why the manual loop is the default. |
| `ADMZ_GEMINI_MAX_TOOL_ITERATIONS`, `ADMZ_GEMINI_RETRY_MAX_ATTEMPTS`, `ADMZ_GEMINI_RETRY_BASE_DELAY` | — | Tool-loop bound and retry backoff. |

---

## 6. Internal — set by ADMZ, not by you

`ADMZ_PRINCIPAL_NAME`, `ADMZ_PRINCIPAL_DISPLAY_NAME`, `ADMZ_PRINCIPAL_DOMAIN`,
`ADMZ_PRINCIPAL_GROUPS`, `ADMZ_PRINCIPAL_SOURCE`.

These are an **IPC seam, not a configuration surface**. An
already-authenticated parent process (`chatbot/mcp_pool.py`, `chatbot/voice.py`)
passes the resolved principal down to the MCP subprocess it spawns, and
`mcp/server.py` reads them on that side. Setting them yourself requires the
ability to set the environment of the ADMZ process, at which point the principal
is not the interesting problem.

Worth knowing, because it is not obvious: with `ADMZ_PRINCIPAL_NAME` **unset**,
a directly launched `python -m admz mcp` runs as a fixed `mcp-standalone`
principal which is **not anonymous** but carries **no groups**. So it clears
gates that only require an authenticated identity, and is refused by every
group-gated surface — reveal, approve, `/settings/advanced`.

`ADMZ_MCP_NO_SCHEDULER` is likewise internal: it stops the MCP subprocess
starting a second scheduler alongside the web process's.

### Two names in `ORDINARY_CONFIG` that are not environment variables

`ADMZ_VERSION` is an import alias (`from admz import __version__ as ADMZ_VERSION`
in `survey/runner.py`) and `ADMZ_WEBHOOK_PATH` is a module constant in
`demos/inference/observability.py`. Neither is ever read from the environment.

They are listed in `ORDINARY_CONFIG` because the drift guard scans for the
`ADMZ_*` **name pattern** in source, so any identifier shaped like one has to be
classified or the test fails. Deliberately absent from this page: documenting
them as environment variables would be wrong. Noted because anyone repeating the
"which names are undocumented?" sweep will find them and wonder.

---

## Verifying this page

`grep -rhoE 'ADMZ_[A-Z0-9_]+' admz/ --include=*.py | sort -u` against the names
here, minus the two above. Not enforced by a test, on purpose: the guard that
would catch a *missing* entry would also fire on every prose rewording, and the
sweep is two commands. The classification — which is the part that must not
drift silently — is already enforced in `tests/test_advanced_capabilities.py`.

---

## Adding a new one

Declare it. `admz/capabilities.py` is the registry; put it in `CAPABILITIES` if
it weakens or enables something, `ORDINARY_CONFIG` if it does not. A test fails
if you do neither, which is the point — the classification is deny-by-default,
so the failure direction is "you must say what this is", not "someone will
notice later".

Then add it here, in the section matching what it does. If it belongs in §3, say
plainly what it gives up; a switch documented without its cost is worse than an
undocumented one, because it reads as safe.
