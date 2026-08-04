# ADMZ — assistant guidance

Durable facts an assistant session needs before touching this repo. Read this first.

## Orchestration

This project runs the **[code-teem](https://github.com/pettheory/code-teem) playbook, pinned at `v0.8.0`** — a persistent Master session coordinates Plan / Decide / Build / Test / Investigate specialists. The project-specific adaptation lives in [`docs/specification/orchestration.md`](docs/specification/orchestration.md); the spec↔issue workflow is [`docs/specification/process.md`](docs/specification/process.md).

Practical consequences:

- **One issue → one Build session → one worktree.** Never do delegated work in the main checkout.
- **A plan is merged before implementation begins.** `status: planning` → docs-only PR → merge → `status: ready`.
- **The PR that ships behavior also fixes the docs describing it** (spec status markers `📋 → ✅` flip in the same PR).
- Every open issue carries exactly one `status:` label — see the playbook's `conventions/status-labels.md`.
- **Cockpit vs worker** (`patterns/cockpit-and-workers.md`): a session open in a human UI is a **cockpit**, never a delegation target — two live attachments fork its history silently, with no error. Workers are durable headless sessions.
- **Await or be watched.** Every delegation either blocks on a completion signal or ends its turn with the session on the watchdog list. A master that ends its turn waiting on an unsignaled callback is a *parked* master — this failure cost this project five recoveries on 2026-07-31/08-01, every time as a worker reporting "the suite is running, I'll report back" and then stopping.

## Owner-facing state outside this repo

Two files live in `C:\admz\.claude\` — deliberately **not** in the repo, because they change many times a day and in-repo means commits and PRs:

| File | What it is |
|---|---|
| `SESSIONS.md` | Session inventory — every worker, its state, and the reuse policy. Prefer resuming an idle listed session over spawning. |
| `ATTENTION.md` | **The single owner attention queue** (code-teem `patterns/attention-queue.md`). Every owner-facing decision goes here with a recommended default *and the date it fires* — never into a transcript, where it dies with the session. Ordered by tier then by what is blocked behind it, never by recency. **No credentials in it — location and procedure only.** |
| `loops/` + `handoffs/` | Autonomous audit-loop contracts, and the durable report-back channel workers write to on completion. |

## Environments — read this before running anything

| | Port | `ADMZ_HOME` | Code from | venv |
|---|---|---|---|---|
| **Production** | 4242 | `C:\ProgramData\admz` | `C:\admz\admz-prod` (detached, pinned) | `C:\admz\admz-prod\.venv` |
| **Staging** | 4243 | `C:\ProgramData\admz-staging` | `C:\admz\admz-staging-code` (detached) | *none — uses the dev venv* |
| **Dev** | — | — | `C:\admz\admz` | `C:\admz\admz\.venv` |

**Production manages a live Axis fleet and a live ACS install.** It runs as the Shawl-supervised Windows service `admz`. Never point tests, agents, or experiments at `:4242` or `C:\ProgramData\admz`. Restarting it, migrating its DB, or driving its devices requires explicit human authorization.

### Production has its own tree and interpreter (ADR-0054, live 2026-08-04)

`C:\admz\admz-prod` is an independent **clone** — not a `git worktree`, so a `git gc`,
branch delete or prune in the dev tree cannot reach production's object store. It is
checked out **detached at a pinned commit**, with its own `.venv` built from that commit's
`requirements.txt` and its own **non-editable** copy of `axis-api-atlas`.

**So `C:\admz\admz` is now purely a dev workspace.** Pulling, branching, installing and
breaking it is no longer a production event. That is the point of the split.

Why it exists: on **2026-08-04**, before the split, a merge landed code requiring `mcp` 2.x
in the then-shared checkout while the shared venv still held `mcp` 1.26. Production kept
serving because it had loaded its code hours earlier — but **any restart would have raised
`AttributeError` at import, and Shawl would have restarted it into a loop.** A Windows
update would have triggered it as surely as a deliberate restart.

Note that ADR-0042 had already separated production's *data*, and staging existed, which
made it easy to believe the environments were fully separated. They were not: code and
interpreter were shared until this landed.

**Two things that are easy to get wrong when updating production:**

- **`pip install -r requirements.txt` does not install atlas.** #235/#236 moved it to an
  `extras_require` entry, so a venv built from `requirements.txt` alone cannot
  `import admz` at all. Install it **non-editable** — the dev venv has it *editable* from
  `C:\admz\axis-api-atlas`, and copying that arrangement would re-create exactly the
  coupling this split removes.
- **The test suite cannot run on the production interpreter.** `requirements.txt` is
  runtime-only and carries no `pytest`, correctly. Verify a production venv by importing
  every module instead (`pkgutil.walk_packages`), which is what dependency completeness
  actually needs.

**Changing the service's configuration requires an elevated shell**; stopping and starting
it does not. `sc.exe config` also fails on this service's 401-character binPath
(`1639`, invalid command line) — use `Invoke-CimMethod -MethodName Change`, which passes
the string as a parameter rather than a command line.

**It is not live.** Repointing the service is the remaining step and needs an *elevated*
shell — changing service configuration requires Administrator, unlike stop/start. Until
then the table above is accurate and the hazard above is real.

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

**`gh issue view` does not work on this repo.** It fails with a GraphQL classic-Projects
deprecation error (`repository.issue.projectCards`) and prints no issue body — the
failure looks like an auth or network problem and is neither. Use the REST API instead;
`gh issue list`, `gh issue comment`, and `gh pr` are unaffected.

```sh
GH_TOKEN=$(gh auth token --user dnobj) gh api repos/dnobj/admz/issues/227 \
  --jq '.title + "\n---\n" + .body'
```

For private repos this machine's default identity cannot see, credentials can also be obtained through the operator's approval-gated access hub rather than by asking for tokens.

## Architecture orientation

`docs/specification/INDEX.md` is the table of contents; `docs/ARCHITECTURE.md` the overview. Decisions live in `docs/specification/decisions/` as ADRs — **read the relevant ADR before changing a subsystem**, and write a new one when a decision changes.

Load-bearing invariants worth knowing before you start:

- **The confirmation gate** (ADR-0034): risk → level (`none` / `llm_confirm` / `url_only` / `url_and_password`), single-sourced in `operations.py` + `confirm_store`. Capabilities may change *who may approve*; they never remove a gate.
- **Modules add zero footprint until enabled** (ADR-0039/0040) — one predicate, consulted everywhere.
- **Demo fragments are captured, never authored** (ADR-0047): capture only accepts keys currently *drifted* from baseline.
- **Advanced capability switches are declared in one registry** (`admz/capabilities.py`) — new dangerous or privileged features register there rather than inventing another env var.

## How workers run

Delegated work runs as **durable headless sessions through the switchyard bridge** (formerly claude-reach / session-bridge), on machine `dnlt`. Engines available: Claude and Codex — Codex is used for **cross-engine adversarial review**, which has previously found defects a same-engine review missed.

- **Trust mode** for this repo is `auto`; `C:\admz` and `C:\admz\admz` are both registered.
- **Dispatch shape:** short synchronous orientation turn → full brief asynchronously → `await_job`, or end the turn with the session on the watchdog. `create_session` runs its first turn synchronously, so a long first message will block the caller until it finishes.
- **Report-back is a handoff file** at `C:\admz\.claude\handoffs\<branch>.md`, because a worker cannot message an open cockpit session. GitHub stays the canonical work record.
- Ask the bridge for `recommendedResultSchema` and pass it as `resultSchema` when a machine-readable completion report is wanted; a malformed report is flagged, never failed.
- Never hand a worker a credential. Identities are injected per command (see above).

## Verifying UI work

Staging is the place to exercise the web UI. ADMZ authenticates with `windows-local` (Negotiate SSO), which a headless client cannot complete — so by default a browser session needs a human to sign in once, after which an agent can drive that authenticated tab.

**Which browser surface** (code-teem `patterns/browser-verification.md`): the **embedded browser is cockpit-only** — one pane, one session, unparallelizable in principle, and it is *not* the unattended default. Per-worker driven browsers are. Observed here on 2026-08-02: `get_page_text` and `screenshot` against the embedded browser each hung the full 300s while `tabs_context` still answered, so treat a hang as the expected failure mode rather than a puzzle, and do not build unattended verification on that surface.

For **unattended** verification, staging can run with `ADMZ_TEST_AUTH=1`: the `dev.test_auth` capability resolves an unauthenticated request to a synthetic `test\agent` principal, so an agent can drive the UI with no human step. It is dev-only, loud in all five capability surfaces, and the server **refuses to start** with it active on a non-loopback bind — production must never see it. It changes who the principal is, never whether a confirmation gate fires.

That principal is **authenticated but unprivileged — no group membership by default**. Reveal-gated surfaces (plaintext credentials, `/settings/advanced`) therefore refuse it, which is deliberate: staging carries a copy of real device credentials. Grant membership explicitly with `ADMZ_TEST_AUTH_GROUPS` when a specific authz path has to be exercised, so the privilege stays visible at the point of use.
