# ADR-0054 — Production gets its own clone and its own venv: separating what runs from what is being changed

**Status:** Accepted (2026-08-03) — decision taken, implementation pending (📋).
Implementation plan: [`docs/plans/dev-prod-split.md`](../../plans/dev-prod-split.md).
Absorbs issue #173 (the deployment guide documents a procedure production does
not use). **Blocked on #235 / PR #236** — see *Prerequisite*, which is
load-bearing rather than adjacent.
**Relates to:** ADR-0042 (machine-level data directory + Windows-service
deployment — **0042 decided where production's *data* lives; 0054 decides where
production's *code and interpreter* live**, and extends its decision #3),
ADR-0052 (advanced capability switches — the switches are `--env` flags on the
service definition this ADR repoints, and "an env var means a restart" is why a
restart is the moment of risk), ADR-0034 (confirmation gates — untouched here;
this ADR changes no gate, no approver, and no risk level).

## Context

### The deadlock

**There is currently no state of the shared venv that satisfies both
environments.**

- **Rebuild it** to match `origin/master` and **staging breaks** — staging's
  checkout is ~60 commits behind, predating both the Starlette 1.x (#224) and
  mcp 2.x (#229) migrations, so new dependencies would meet old code.
- **Leave it** and **production crash-loops on its next restart** — the tree
  production reads from is at `991c2b8`, which contains mcp-2.x-only code, while
  the venv reports `mcp 1.26.0`. The import fails; Shawl restarts on failure
  every 3 seconds.

That is not a risk of a future collision. It is a live contradiction, measurable
on this machine today, and it exists because one virtualenv is the runtime for
production, for staging, and for every test run. No amount of care resolves it,
because care cannot make one directory hold two dependency sets.

Everything else in this record follows from that sentence.

### The layout that produces it

Measured 2026-08-03, not assumed:

| Path | Serves | Consequence |
|---|---|---|
| `C:\admz\admz` | production source **and** the human's dev workspace **and** the tree `master` is pulled into | every `git pull` changes what production loads on next restart |
| `C:\admz\admz\.venv` | production runtime **and** staging runtime **and** all ~3,000 tests | every `pip install` changes production's dependencies, invisibly |
| `C:\admz\admz-staging-code` | staging — **no venv of its own**, so it runs on *production's interpreter* | staging cannot isolate a dependency change at all; rehearsing one *is* the production operation |

The service definition confirms both couplings in one line
(`HKLM\SYSTEM\CurrentControlSet\Services\admz`, verbatim):

```
shawl.exe run --name admz --restart-delay 3000 --stop-timeout 15000 --restart
  --cwd \\?\C:\admz\admz --log-dir \\?\C:\ProgramData\admz\logs
  --env ADMZ_HOME=C:\ProgramData\admz --env ADMZ_AUTH_BACKEND=windows-local
  --kill-process-tree -- C:\admz\admz\.venv\Scripts\python.exe -m admz api --host 127.0.0.1 --port 4242
```

`--cwd` names the dev tree. The interpreter after `--` is the dev venv. Note
also `--restart --restart-delay 3000`: that pair is the mechanism that converts
a failed import into a loop rather than a stopped service.

### How the deadlock arrived

Three incidents on 2026-08-03, all with the same shape — a **good** change
reaching production through a path nobody chose:

1. **#229 (mcp 2.x) merged into the tree production reads from**, while the venv
   stayed on mcp 1.26. Nothing was wrong with the change; it was reviewed,
   tested and correct. It became an outage risk purely by landing in a directory
   that doubles as a deployment.
2. **The staging rehearsal was impossible as designed.** Rehearsing the venv
   rebuild on staging *is* the production operation, because they share the
   venv. It had to be rehearsed against a 162 MB scratch copy instead.
3. **Every test run that day used production's interpreter.** `ADMZ_HOME` was
   isolated each time by discipline, not by structure.

The common cause is not carelessness. It is that **deployment is currently
implicit**: the act that changes what production runs is `git pull`, performed
for unrelated reasons, with no moment at which anyone decides "production should
now run this."

### What the documentation says, and what is true

Issue #173 is correct and this ADR absorbs it. `docs/DEPLOYMENT_WINDOWS.md`
Steps 1–5 describe **NSSM + IIS** with interpreter `C:\admz\.venv\Scripts\python.exe`
(one directory too shallow — that path does not exist) and no `ADMZ_HOME`. The
deployment that actually runs — `windows-local` under **Shawl** with
`ADMZ_HOME=C:\ProgramData\admz` — appears as an "Alternative" section.

The script that performs the real install, `setup-admz-service.ps1`, **exists but
is not in the repository**: it sits at `C:\admz\setup-admz-service.ps1` (mtime
2026-07-02) with its run log beside it. It is a good script — seven idempotent
steps, a documented rollback, and the delete-and-recreate service path this
migration needs. Its entire coupling to the dev tree is two variables:

```powershell
$Py  = 'C:\admz\admz\.venv\Scripts\python.exe'   # line 27
$Cwd = 'C:\admz\admz'                            # line 28
```

Bringing that script into the repo is therefore both the migration mechanism and
the fix for #173, which is why they ship together rather than racing on the same
file.

## Decision

1. **Production gets its own clone at `C:\admz\admz-prod`, checked out
   detached at a deliberate commit.** A *clone*, not a `git worktree`.
   Worktrees share one `.git`; a `git gc`, a branch delete or a
   `git worktree prune` in the dev tree — the tree most likely to be
   experimented in — can reach production's object store. Disk is the correct
   thing to spend here.

2. **Production gets its own virtualenv at `C:\admz\admz-prod\.venv`, built
   from that commit's `requirements.txt`.** The venv and the checkout move
   together, always. This is the half that resolves the deadlock: dev and
   staging may then rebuild freely, because production's runtime is no longer
   downstream of anyone's `pip install`.

3. **Both halves land in one operation.** The tree pin is what makes the venv
   pin *checkable*: "this venv was built from this commit's `requirements.txt`"
   is only a verifiable claim if the commit is fixed. A private venv on a shared
   tree would institutionalise the exact skew — code moving without
   dependencies — that caused incident 1.

4. **The service is repointed** to `--cwd \\?\C:\admz\admz-prod` and interpreter
   `C:\admz\admz-prod\.venv\Scripts\python.exe`. Nothing else about the service
   changes: LocalSystem, delayed-auto, `ADMZ_HOME=C:\ProgramData\admz`,
   `ADMZ_AUTH_BACKEND=windows-local`, log directory and rotation all stay.

5. **`C:\admz\admz` becomes what it is already treated as — a dev workspace with
   no production role.** Pulling, branching, installing and breaking it stops
   being a production event.

6. **Deployment becomes one explicit, reviewable act: `scripts/deploy-prod.ps1`.**
   Not a pipeline. Six steps:

   1. take a ref (default `origin/master`), resolve it to a SHA, refuse a dirty
      production tree;
   2. `fetch` and `checkout --detach <sha>` in `C:\admz\admz-prod`;
   3. rebuild the venv from **that commit's** `requirements.txt`;
   4. **smoke the new code on the new venv before the service sees it** —
      `python -c "import admz.mcp.server"` and `python -m admz --version`, run
      with the production interpreter against the production tree;
   5. `sc stop admz` → `sc start admz` → poll `/health`; on failure, restore the
      recorded previous SHA and restart;
   6. append to `C:\ProgramData\admz\deployed.log`: timestamp, SHA, previous
      SHA, operator.

   **Step 4 is the point of this entire ADR. The other five steps are
   bookkeeping around it.** The exact import in step 4 —
   `import admz.mcp.server` — is the one that would have crash-looped
   production today. A deploy step that runs the new code against the new
   dependencies *before* the service is stopped converts that class of outage
   into a script that exits non-zero with the service still serving.

7. **The host owns the record of what it runs**: a detached HEAD plus
   `deployed.log`, both on the production machine. Not a git tag. *A tag is a
   claim about production made somewhere production can't enforce it.* If a
   `prod` tag is ever wanted, it is a **consequence** of step 6, never the
   source of truth.

8. **`setup-admz-service.ps1` comes into the repository** as
   `scripts/setup-admz-service.ps1`, with `$Py` and `$Cwd` parameterised rather
   than hard-coded, and `docs/DEPLOYMENT_WINDOWS.md` is rewritten so the Shawl /
   `windows-local` / `ADMZ_HOME` path is the **primary** procedure (#173). The
   NSSM/IIS material is retained only as the reverse-proxy alternative it
   actually is.

9. **Staging's own venv is deferred, deliberately, with a stated trigger.**
   Once production has its own, staging sharing the *dev* venv is an ordinary
   dev-grade arrangement — the harm was always that it shared *production's*.
   Staging's live defect is that it is ~60 commits stale, which a venv does not
   fix. **Trigger:** the first dependency change that genuinely needs rehearsing
   against staging's data before production sees it. Until then, refreshing
   staging to `origin/master` is the higher-value work.

## What this does not separate

This section is not optional. Someone will read this ADR and believe more is
separated than is.

- **`ADMZ_HOME` is untouched.** Production and staging still have one data
  directory each, and the boundary between them is still an `--env` flag on the
  service plus discipline in every test run. **A test that forgets to isolate
  `ADMZ_HOME` can still write the operator's real database.** This ADR separates
  the *interpreter*, not the data.
- **Git configuration is machine-wide.** `git config --system safe.directory`
  entries and the credential helper are shared by every tree on the box.
- **The three `gh` identities are machine-wide.** One keyring; `gh auth switch`
  is global state. Separate trees separate nothing here — per-command credential
  injection remains the only protection.
- **The device fleet and the ACS install are singletons.** Staging carries a
  *copy* of real device credentials and can reach the same real devices. Nothing
  here sandboxes the network.
- **It is still one machine** — shared CPU, disk, clock and Windows event log. A
  runaway test run still degrades production.
- **Shawl's `--restart` is unchanged.** A genuinely broken deploy that passes the
  step-4 smoke check still loops. Step 4 narrows the window; it does not remove
  the mechanism.
- **The database is not versioned with the code.** *Open question, deliberately
  not designed here:* rolling back to the previous SHA does **not** roll back a
  schema migration, so the rollback in the next section is a code rollback only.
  What `deploy-prod.ps1` should do when the target SHA's migration set differs
  from the deployed one — refuse, prompt, or snapshot first — is left to a
  follow-up.

## Migration and rollback

Staged so that the old tree and the old venv stay byte-identical on disk
throughout, and production keeps serving until the final seconds.

1. Clone `C:\admz\admz-prod` pinned to `991c2b8` and build its venv to match.
   **Not** "pin to whatever is running": the live process is on pre-#229 code
   against a 1.26 venv, and preserving that pair preserves the deadlock. Pin to
   the *deliberate* matched pair, which also resolves it.
2. Run the full suite with the new interpreter and an isolated `ADMZ_HOME` —
   now possible without touching production, which is the point of the change.
3. Smoke on a spare port (4244) against a **copy** of `ADMZ_HOME`. The old
   service keeps serving 4242 throughout.
4. Cut over: `sc stop admz`, re-register with the two new paths, `sc start admz`,
   poll `/health`.
5. **Rollback is re-registering the service with the two old paths and
   starting.** Roughly ten seconds, and it requires nothing of the new tree —
   the old clone and old venv are untouched and still correct.
6. **Keep the old venv for a full week of normal operation before reclaiming the
   disk.** It is stated here because it will look redundant precisely when it is
   still load-bearing.

Two risks worth naming rather than discovering:

- `git config --system safe.directory` currently covers `ADMZ_HOME`'s repos, not
  the code tree. A clone created by the interactive user and read by LocalSystem
  may need its own entry and ACL — the same "dubious ownership" failure ADR-0042
  hit, and a classically silent one.
- Confirm no absolute path stored in the database references `C:\admz\admz`.
  ADR-0042's migration had to rewrite `organizations.repo_path`; nothing
  analogous should be needed for a code-tree move, but "should" is not
  "verified."

## Prerequisite

**#235 must be fixed before step 3 of the migration is performable on any
machine that is not a CI runner.** `pip install -r requirements.txt` currently
fails on the `git+ssh` reference to `axis-api-atlas`, whose deploy key exists
only as a GitHub Actions secret. PR #236 (`fix/atlas-reference`) moves that
reference out of `requirements.txt` and pins it to a SHA.

This is load-bearing, not adjacent: `deploy-prod.ps1` step 3 builds a venv from
`requirements.txt` on the production host, so a credential-free
`requirements.txt` is a precondition for the deploy step existing at all.

## Consequences

- The three failure modes of 2026-08-03 become structurally impossible in their
  current form: a `pull` cannot change what production loads, a `pip install`
  cannot change production's dependencies, and a test run cannot use
  production's interpreter.
- Deployment gains a moment. Someone decides that production should run a
  specific commit, and there is a file on the host recording that they did.
- One additional clone (~1.5 GB with its venv) and one more thing to keep
  current. Production will drift behind `master` by default — which is the
  intended behaviour, not a regression.
- ADR-0042's decision #3 is **extended, not superseded**: `ADMZ_HOME`,
  LocalSystem, and the Shawl service shape are all unchanged. Only the two paths
  the service points at move.
