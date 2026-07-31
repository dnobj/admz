# ADMZ — assistant guidance

Durable facts an assistant session needs before touching this repo. Read this first.

## Orchestration

This project runs the **[code-teem](https://github.com/pettheory/code-teem) playbook, pinned at `v0.3.0`** — a persistent Master session coordinates Plan / Build / Test / Investigate specialists. The project-specific adaptation lives in [`docs/specification/orchestration.md`](docs/specification/orchestration.md); the spec↔issue workflow is [`docs/specification/process.md`](docs/specification/process.md).

Practical consequences:

- **One issue → one Build session → one worktree.** Never do delegated work in the main checkout.
- **A plan is merged before implementation begins.** `status: planning` → docs-only PR → merge → `status: ready`.
- **The PR that ships behavior also fixes the docs describing it** (spec status markers `📋 → ✅` flip in the same PR).
- Every open issue carries exactly one `status:` label — see the playbook's `conventions/status-labels.md`.

## Environments — read this before running anything

| | Port | `ADMZ_HOME` | Code from |
|---|---|---|---|
| **Production** | 4242 | `C:\ProgramData\admz` | `C:\admz\admz` (the human's checkout) |
| **Staging** | 4243 | `C:\ProgramData\admz-staging` | `C:\admz\admz-staging-code` (detached on `origin/master`) |

**Production manages a live Axis fleet and a live ACS install.** It runs as the Shawl-supervised Windows service `admz`. Never point tests, agents, or experiments at `:4242` or `C:\ProgramData\admz`. Restarting it, migrating its DB, or driving its devices requires explicit human authorization.

Staging exists so UI and behavior can be exercised without touching production. It carries a **copy** of the real device data (so it has real credentials — treat its `ADMZ_HOME` as secret-bearing) and runs with health polling turned down and GitHub config-push disabled.

## Running things

```
C:/admz/admz/.venv/Scripts/python.exe -m pytest -q
```

- **Always use the `.venv` interpreter.** The base conda environment has an old `google-genai` that 400s on Gemini 3.x tool turns.
- The full suite is **~3,000 tests and takes 10–12 minutes**. Run it in the **foreground with a long timeout** — a two-minute default will kill it, and a partial run is not a green run.
- **Test isolation matters more than usual here.** Several singletons (tasks store, confirm store, audit) bind their DB path at *import*. A test that doesn't isolate `ADMZ_HOME` will write into the operator's real database. If you add a writer, prove it cannot reach a real DB from a test run.

## Worktrees

```
git fetch origin master
git worktree add ../admz-<topic> -b <branch> origin/master
```

Sibling worktrees under `C:\admz\`, always branched from `origin/master`. The main checkout `C:\admz\admz` belongs to the human — treat its uncommitted state as theirs, never commit there, never `reset` it. Before dispatching parallel implementation work, check for file overlap across in-flight branches; two correct PRs that touch the same file cannot both merge.

## GitHub identities

Three accounts exist in the keyring, and they see different repositories:

| Identity | Repos |
|---|---|
| `dnobj` | **this repo** (`dnobj/admz`) |
| `mrdnlabs` | `mrdnlabs/axis-api-atlas` |
| `pettheory` | `pettheory/code-teem`, `pettheory/claude-reach` |

**Inject credentials per command; never switch the global active account.** `gh auth switch` is global state shared with every other session on this machine — flipping it silently breaks concurrent work in another repo.

```sh
GH_TOKEN=$(gh auth token --user dnobj) gh issue list
TOK=$(gh auth token --user mrdnlabs); B64=$(printf 'x-access-token:%s' "$TOK" | base64 -w0)
git -c http.https://github.com/.extraheader="AUTHORIZATION: basic $B64" push origin <branch>
```

For private repos this machine's default identity cannot see, credentials can also be obtained through the operator's approval-gated access hub rather than by asking for tokens.

## Architecture orientation

`docs/specification/INDEX.md` is the table of contents; `docs/ARCHITECTURE.md` the overview. Decisions live in `docs/specification/decisions/` as ADRs — **read the relevant ADR before changing a subsystem**, and write a new one when a decision changes.

Load-bearing invariants worth knowing before you start:

- **The confirmation gate** (ADR-0034): risk → level (`none` / `llm_confirm` / `url_only` / `url_and_password`), single-sourced in `operations.py` + `confirm_store`. Capabilities may change *who may approve*; they never remove a gate.
- **Modules add zero footprint until enabled** (ADR-0039/0040) — one predicate, consulted everywhere.
- **Demo fragments are captured, never authored** (ADR-0047): capture only accepts keys currently *drifted* from baseline.
- **Advanced capability switches are declared in one registry** (`admz/capabilities.py`) — new dangerous or privileged features register there rather than inventing another env var.

## Verifying UI work

Staging is the place to exercise the web UI. ADMZ authenticates with `windows-local` (Negotiate SSO), which a headless client cannot complete — so by default a browser session needs a human to sign in once, after which an agent can drive that authenticated tab.

For **unattended** verification, staging can run with `ADMZ_TEST_AUTH=1`: the `dev.test_auth` capability resolves an unauthenticated request to a synthetic `test\agent` principal, so an agent can drive the UI with no human step. It is dev-only, loud in all five capability surfaces, and the server **refuses to start** with it active on a non-loopback bind — production must never see it. It changes who the principal is, never whether a confirmation gate fires.
