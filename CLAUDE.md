# ADMZ — assistant guidance

Durable facts an assistant session needs before touching this repo. Read this first.

## Orchestration

This project runs the **[code-teem](https://github.com/pettheory/code-teem) playbook, pinned at `v0.13.1`** — a Master **role** implements serially and coordinates Plan / Decide / Investigate / Review / Converse specialists. The Master is a role any fresh session can assume, not a session to keep alive: see [The context-free tick](#the-context-free-tick). The project-specific adaptation lives in [`docs/specification/orchestration.md`](docs/specification/orchestration.md); the spec↔issue workflow is [`docs/specification/process.md`](docs/specification/process.md).

Practical consequences:

- **Writes serialize; reads parallelize.** The Master implements ready issues **itself**, one at a time, in an isolated worktree per PR. A dedicated `Build` session is the exception — only when the work needs a large sustained context the Master should not carry. Parallel implementation is reserved for hard resource boundaries (a separate repo with its own version stream and zero file overlap; `axis-api-atlas` qualifies, two issues here do not). The fan-out that pays is **review, research, and audit**. See [Why implementation is serial](docs/specification/orchestration.md#why-implementation-is-serial) — that section carries the evidence, from a day of running five concurrent writers on this repo.
- **Never do implementation work in the main checkout** — `C:\admz\admz` belongs to the human. Use a sibling worktree regardless of who is writing.
- **A plan is merged before implementation begins.** `status: planning` → docs-only PR → merge → `status: ready`.
- **The PR that ships behavior also fixes the docs describing it** (spec status markers `📋 → ✅` flip in the same PR).
- Every open issue carries exactly one `status:` label — see the playbook's `conventions/status-labels.md`.
- **Cockpit vs worker** (`patterns/cockpit-and-workers.md`): a session open in a human UI is a **cockpit**, never a delegation target — two live attachments fork its history silently, with no error. Workers are durable headless sessions.
- **Await or be watched.** Every delegation either blocks on a completion signal or ends its turn with the session on the watchdog list. A master that ends its turn waiting on an unsignaled callback is a *parked* master — this failure cost this project five recoveries on 2026-07-31/08-01, every time as a worker reporting "the suite is running, I'll report back" and then stopping.
- **Liveness is `list_sessions`, never a file count.** On 2026-08-05 two sessions died mid-task and were reported as "still building" for hours, because progress was inferred from the number of uncommitted files in their worktrees — a number that does not change when a session stops. `live: false` is the answer; `read_session` shows what the last turn actually did. Related: `continue_session` returning `status: "running"` means *queued*, not *accepted* — a dispatch rejected by the fork-guard fails 90 ms later and looks identical unless `get_job` is checked.

## The context-free tick

The Master can run as a loop: wake, do one bounded pass, end the turn. The tick is
**context-free by contract** — it orients from files, trusts only external state, and never
relies on transcript memory. The point is not automation; it is that a Master which survives a
context clear every cycle *proves* every cycle that its ledger is complete.

**Install (Claude Code):** the skill lives at `C:dmz\.claude\skills	ick\SKILL.md` —
**beside the ledger, not in the repo**, because sessions run rooted at `C:dmz` and skills are
discovered from the session's own `.claude/skills/`. The copy in this repo is the versioned
source; installing means copying it there. It also needs YAML frontmatter (`name`,
`description`) that the engine-neutral playbook template does not carry — "install per the
engine's skill mechanism" is a real step, not a formality. **A newly added skill is only
discovered when a session starts**, so `/tick` will not resolve in the session that installed it.

Ledger files, all outside this repo in `C:\admz\.claude\`:

| File | Rewritten or appended | Read by |
|---|---|---|
| `STATUS.md` | rewritten every tick, never appended | **the owner** |
| `HANDOFF.md` | rewritten at every tick boundary and before any deliberate clear | the next Master instance |
| `TICKS.log` | one appended line per tick | the tick's own stall check |
| `ATTENTION.md` | the durable queue; the question store is the record | the owner |

`HANDOFF.md` carries phase · item · anchor · done-so-far · **tried-and-failed** · next-step. That
tried-and-failed line is the one that saves the next instance an hour, and it is the line most
easily left vague — "verifiable facts only" is the standard, not "mostly done".

### Control-plane adapter block

Everything the playbook and the `/tick` skill name abstractly, bound to this machine. **Skills
stay portable because they never name tools; this block is the one place bindings live.** Swap
the control plane and only this block changes.

| Capability | Binding | Degraded rule |
|---|---|---|
| **Question store** | `mcp__sy__raise_question` (attach `proposedAnswer` wherever a default is defensible — one call, not a raise-then-answer two-step) · `mcp__sy__list_questions` · `mcp__sy__answer_question` (lands as a *proposal*; **only the owner resolves**) | Unreachable → hold questions in `HANDOFF.md`, say so in `STATUS.md`, continue. Never block the tick on it. |
| **Fleet / jobs** | `mcp__sy__list_sessions` · `continue_session` · `await_job` · `list_jobs` · `get_job` | Bridge paused (check the dashboard header) → dispatch sends are refused politely; **reconcile and orient are unaffected**. Work serially and reconcile next tick. |
| **Session liveness** | `mcp__sy__list_sessions` (`live` field) · `mcp__sy__read_session` to see what a stalled session last did | **Never infer progress from a file count** — it does not change when a session dies. `continue_session` returning `status: "running"` means *queued*, not *accepted*; confirm with `get_job`. |
| **Timeline / dashboard** | switchyard dashboard | Unreachable → note it in `STATUS.md`; the repo and GitHub remain truth. |

**Path→audit ripple matrix:** not yet defined for this project. Per v0.13.1 the tick uses the
default table in the playbook's `patterns/triggers-and-lanes.md` and raises a question proposing
a real one — that is the designed path, not a gap to paper over. Inventing an unvalidated matrix
would be worse than the default, because it would look authoritative.

## Owner-facing state outside this repo

Two files live in `C:\admz\.claude\` — deliberately **not** in the repo, because they change many times a day and in-repo means commits and PRs:

| File | What it is |
|---|---|
| `SESSIONS.md` | Session inventory — every worker, its state, and the reuse policy. Prefer resuming an idle listed session over spawning. |
| `ATTENTION.md` | **The single owner attention queue** (code-teem `patterns/attention-queue.md`). Every owner-facing decision goes here with a recommended default — never into a transcript, where it dies with the session. Ordered by tier then by what is blocked behind it, never by recency. **No credentials in it — location and procedure only.** An item that will not reduce to a one-word answer does not belong in the queue as one: brief a `Converse` session instead, and record the outcome here. Six items sat unanswered through 2026-08-05 largely because the queue's form did not fit the question. |
| `STATUS.md` | **The owner's one-page brief** — where things sit, what's next, what's waiting on you. Rewritten in full every reconciliation, never appended. If it is older than recent activity, treat it as wrong. |
| `HANDOFF.md` | Machine resume state for the Master **role**: phase · item · anchor · done-so-far · tried-and-failed · next-step. Written to be executable cold by a session with no memory of this one. |
| `TICKS.log` | One appended line per tick. The tick's own stall check reads the last 5 — mechanical, because a loop asked whether it is making progress will say yes. |
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

**It is live.** The service was repointed on **2026-08-04** and ADR-0054 records the
verification: the service configuration, production holding
`admz-prod\.venv\Scripts\python.exe` open while the dev interpreter is unlocked, and the
fleet poll resuming against live devices. So the split above is in effect, and the
shared-tree hazard it describes is **historical** — a dev `pull` or `pip install` can no
longer reach production.

> This paragraph said *"It is not live … the hazard above is real"* for most of a day
> after the split shipped, contradicting the ADR **and line 38 of this same file**
> (#214). It is the highest-cost staleness in the repo: every session reads this file
> first, and it told each one that the thing protecting production was not switched on.

Staging exists so UI and behavior can be exercised without touching production. It carries a **copy** of the real device data (so it has real credentials — treat its `ADMZ_HOME` as secret-bearing) and runs with health polling turned down and GitHub config-push disabled.

## Running things

```
C:/admz/admz/.venv/Scripts/python.exe -m pytest -q
```

- **Always use the `.venv` interpreter.** The base conda environment has an old `google-genai` that 400s on Gemini 3.x tool turns.
- The full suite takes **10–12 minutes**. Run it in the **foreground with a long timeout** — a two-minute default will kill it, and a partial run is not a green run. (The test *count* is deliberately not stated: it changes every merge, and a number nobody updates is worse than no number — the #303 rule.)
- **Test isolation matters more than usual here.** A test that doesn't isolate `ADMZ_HOME` will write into the operator's real database. If you add a writer, prove it cannot reach a real DB from a test run. (The stores no longer bind their path at *import* — #258 moved all 17 to a call-time `_db_path` property with schema-ensure inside `_connect()`. The isolation requirement is unchanged; the mechanism this warning used to name is not, and a reader debugging it would have looked in the wrong place.)

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

- **The confirmation gate** (ADR-0034): risk → level (`none` / `llm_confirm` / `url_only` / `url_and_password`), single-sourced in `admz/confirm_policy.py` (`_DEFAULT_CONFIRMATION_LEVELS`, with per-fleet overrides) and resolved through `operations.resolve_confirmation`. `confirm_store` re-exports the table but no longer defines it. Capabilities may change *who may approve*; they never remove a gate.
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
