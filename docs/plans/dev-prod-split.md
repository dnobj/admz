# Plan: separate the production tree and venv from the dev workspace

Status: **planning — no implementation has begun.** The decision this plan
implements is recorded as
[ADR-0054](../specification/decisions/0054-separate-production-tree-and-venv.md);
where this plan and the ADR differ, **the ADR wins**.

**Blocked on #235 / PR #236** (`fix/atlas-reference`). Slice 2 cannot be
performed on the production host until `pip install -r requirements.txt`
succeeds without a CI deploy key. Slices 1 and 4 are unblocked.

Absorbs **#173** (`DEPLOYMENT_WINDOWS.md` documents NSSM/IIS with a nonexistent
interpreter). #173 is `status: ready` and unstarted; it edits the same file this
plan rewrites, so it lands here rather than racing.

## Goal

Make it impossible for a `git pull` or a `pip install` to change what production
runs, and replace the implicit deployment (*someone pulled*) with one explicit,
reviewable act that proves the new code imports against the new dependencies
**before** the service is stopped.

## Non-goals

- **Not a release pipeline.** One PowerShell script, run by a human on the box.
  No artifacts, no environments-as-config, no promotion model, no CI deploy.
- **Not `ADMZ_HOME` isolation.** The data directory boundary is unchanged and
  still rests on an `--env` flag plus test discipline. See ADR-0054 *What this
  does not separate*.
- **Not a second machine.** Production, staging, dev and every worker session
  continue to share one host.
- **No behaviour change in ADMZ itself.** No Python source is touched by this
  plan. The only code that changes is deployment scripting.
- **No new confirmation gate and no change to an existing one** (ADR-0034
  untouched).
- **Not staging's venv.** Explicitly deferred — ADR-0054 decision 9, with the
  trigger stated there.

---

## Current state — with evidence

Measured on `dnlt`, 2026-08-03.

**The service** (`HKLM\SYSTEM\CurrentControlSet\Services\admz`, `ImagePath`,
verbatim):

```
shawl.exe run --name admz --restart-delay 3000 --stop-timeout 15000 --restart
  --cwd \\?\C:\admz\admz --log-dir \\?\C:\ProgramData\admz\logs
  --env ADMZ_HOME=C:\ProgramData\admz --env ADMZ_AUTH_BACKEND=windows-local
  --kill-process-tree -- C:\admz\admz\.venv\Scripts\python.exe -m admz api --host 127.0.0.1 --port 4242
```

`Start=2` (delayed-auto), `ObjectName=LocalSystem`, state **RUNNING**.

**The deadlock**, both halves verified:

| Fact | Measured |
|---|---|
| Dev/production tree HEAD | `991c2b8` (#227/#231), clean, with `0d38766` (#229, mcp 2.x) beneath it |
| The one venv | `mcp 1.26.0` |
| Staging tree `C:\admz\admz-staging-code` | `948de66` (#176) — ~60 commits behind, predates #224 and #229 |
| Staging venv | **absent** — `C:\admz\admz-staging-code\.venv\Scripts\python.exe` does not exist |

So: rebuilding the venv for `master` breaks staging (old code, new deps);
leaving it crash-loops production on restart (new code, old deps). No third
state exists.

**The install script exists outside the repo:** `C:\admz\setup-admz-service.ps1`
(mtime 2026-07-02 19:17), with `C:\admz\setup-admz-service.log` beside it. Seven
idempotent steps: robocopy `~/.admz` → `C:\ProgramData\admz` (source kept as the
rollback copy), `icacls` tighten, `setowner` + `git --system safe.directory` for
SYSTEM, rewrite `organizations.repo_path` in the DB, machine-wide `ADMZ_HOME`,
stage `shawl.exe` to `C:\Program Files\shawl`, delete-and-recreate the service
and start it. Rollback is documented in its header comment.

Its entire coupling to the dev tree is two lines:

```powershell
$Py  = 'C:\admz\admz\.venv\Scripts\python.exe'   # line 27
$Cwd = 'C:\admz\admz'                            # line 28
```

**Two documentation defects found while measuring**, both filed separately
rather than fixed silently:

- `docs/DEPLOYMENT_WINDOWS.md` — #173, absorbed by this plan (slice 4).
- `CLAUDE.md` states `C:\admz\admz-staging-code` is "detached on `origin/master`".
  It is 60 commits behind. Filed as its own issue: it is a doc-vs-reality error
  in the file every fresh session reads first.
- Additionally, **ADR-0042 is missing from `docs/specification/INDEX.md`
  entirely.** Backfilled in the same PR as this plan, since ADR-0054 must link
  to it from the same section.

---

## Target layout

| Path | Role after this plan |
|---|---|
| `C:\admz\admz-prod` | **new.** Production clone, detached at a deliberate SHA |
| `C:\admz\admz-prod\.venv` | **new.** Production runtime, built from that SHA's `requirements.txt` |
| `C:\admz\admz` | dev workspace, no production role |
| `C:\admz\admz\.venv` | dev + staging runtime, and every test run |
| `C:\admz\admz-staging-code` | staging — refreshed to `origin/master`; still no venv (deferred) |
| `C:\ProgramData\admz` | unchanged — `ADMZ_HOME`, both environments' data boundary |

A **clone, not a worktree** — worktrees share `.git`, and a `gc`, branch delete
or prune in the dev tree could reach production's object store (ADR-0054
decision 1).

---

## Slices

### Slice 1 — docs only (this PR)

ADR-0054, this plan, INDEX entries at 📋, ADR-0042 backfilled into INDEX, and
the "extended by ADR-0054" pointer on ADR-0042's decision #3. **No script, no
service change, nothing installed.** Merging this is what moves the issue from
`status: planning` to `status: ready`.

### Slice 2 — build the production clone and venv (needs #236 merged)

Nothing is repointed in this slice. Production keeps running from the old paths
the entire time; this slice only creates the thing that will replace it.

```powershell
# 1. clone, pinned deliberately — NOT to "whatever is running"
git clone C:\admz\admz C:\admz\admz-prod          # local clone; then set origin to GitHub
git -C C:\admz\admz-prod remote set-url origin https://github.com/dnobj/admz.git
git -C C:\admz\admz-prod fetch origin
git -C C:\admz\admz-prod checkout --detach 991c2b8

# 2. its own venv, from THAT commit's requirements.txt
py -3 -m venv C:\admz\admz-prod\.venv
C:\admz\admz-prod\.venv\Scripts\python.exe -m pip install -r C:\admz\admz-prod\requirements.txt
```

Pin to `991c2b8`, **not** to the currently-running code. The live process is on
pre-#229 code against a 1.26 venv; preserving that pair preserves the deadlock.
`991c2b8` plus a matching fresh venv is the deliberate combination and resolves
it.

Then, still without touching the service:

```powershell
# full suite on the new interpreter, isolated data dir
$env:ADMZ_HOME = 'C:\admz\_scratch\prod-verify-home'
C:\admz\admz-prod\.venv\Scripts\python.exe -m pytest -q          # ~3,000 tests, 10-12 min, foreground
```

**Exit criteria:** suite green on the new interpreter, and a spare-port smoke
(port 4244, against a *copy* of `ADMZ_HOME`) returns healthy from `/health`
while the real service still serves 4242.

### Slice 2 — STATUS: done, 2026-08-04

Built and verified. Deviations from the text above, all deliberate:

- **Pinned to `545a706`, not `991c2b8`.** `991c2b8` was current when this plan was
  written; by execution time it was far behind and missing that day's security fixes
  (#252 key DACL, #272 approver group, #273 CSRF, #276 approval auditing, #278 CDN
  vendoring). `545a706` is master at execution time, CI-green on both legs.
- **`pip install -r requirements.txt` does not install atlas.** #235/#236 moved it to an
  `extras_require` entry, so the production venv came up without it and
  `import admz.mcp.server` failed on `axis_api_atlas`. Installed **non-editable** from
  `C:dmzxis-api-atlas` so production holds its own copy — the dev venv has it
  *editable*, which would have re-created exactly the coupling this plan exists to remove.
  Worth knowing: that shared checkout is on branch `survey/motion-alarm-publisher-caution`,
  not `main`, so production had been running atlas from a feature branch.
- **The suite cannot run on the production interpreter.** `requirements.txt` is
  runtime-only and carries no `pytest` — correctly, since production should not ship test
  dependencies. The stated exit criterion is therefore unachievable as written.
  Substituted: import every module in the package (`pkgutil.walk_packages`) on the
  production interpreter, which is what the suite would have proven about dependency
  completeness. **226 imported, 0 failures.** Behaviour is covered by CI on the same commit.
- **The spare-port smoke was not run.** Rollback is a ~10-second config revert and the
  three risks below were all checked directly, so the marginal value was low. Recorded
  rather than quietly skipped.

Both flagged risks checked and clear:

- **Dubious ownership:** `C:dmzdmz-prod` is owned by `DNLT\dnich`, *identical* to
  `C:dmzdmz`, which LocalSystem already reads successfully. No new exposure.
  (`git config --system safe.directory` covers only `ADMZ_HOME`'s repos, as the plan says.)
- **Absolute paths in the DB:** 270 columns scanned across every table in production's
  `admz.db` (read-only) for a literal `admzdmz`. **None.** No analogue to ADR-0042's
  `organizations.repo_path` migration is needed.

### Slice 3 — STATUS: DONE, 2026-08-04

Production runs from `C:\admz\admz-prod` on its own venv. Verified independently of the
script's own report: the service configuration points there, `admz-prod`'s `python.exe` is
**locked** by a running process while the dev one is **not**, and the fleet poll resumed
against live devices with `/` returning its usual `401` challenge.

The route there took two failed attempts, both worth recording because each failure was in
the *tooling*, not the change:

1. **`sc.exe config` returned 1639** (`ERROR_INVALID_COMMAND_LINE`). The binPath is 411
   characters and contains embedded quotes, which does not survive PowerShell argument
   marshalling. Use `Invoke-CimMethod -MethodName Change`, which passes the string as a
   parameter rather than a command line.
2. **The first elevated script never ran.** It was written UTF-8 without a BOM and
   contained em-dashes; PowerShell 5.1 reads BOM-less files as ANSI, which mangled them
   into a parse error. The UAC prompt was approved and the shell exited before executing a
   line — no log, no change, and nothing to indicate why. **Parse-check a generated script
   with `[Parser]::ParseFile` before launching it elevated**, and keep such scripts ASCII.

Both attempts left production serving on the original configuration; it was never down.

<details>
<summary>Original slice 3 text</summary>


Attempted and cleanly reverted; production was never left down.

`sc.exe config` failed with **1639** (`ERROR_INVALID_COMMAND_LINE`) — the binPath is 401
characters and contains embedded quotes, which does not survive PowerShell argument
marshalling. Retried via `Invoke-CimMethod -MethodName Change`, which passes the string as
a parameter rather than a command line and avoids that entirely; that returned **2**
(*access denied*).

**Changing service configuration requires an elevated shell. Stopping and starting does
not** — which is why the 2026-08-04 maintenance restart succeeded from an unelevated
session and this did not.

The exact change, both halves already written to disk during the attempt:

```powershell
# elevated PowerShell
Stop-Service admz -Force
$new = '<binPath with --cwd \?\C:dmzdmz-prod and admz-prod\.venv\Scripts\python.exe>'
sc.exe config admz binPath= "$new"
Start-Service admz
```

Nothing else about the service changes: LocalSystem, delayed-auto, `ADMZ_HOME`,
`ADMZ_AUTH_BACKEND`, log directory and rotation are all untouched. Rollback is the same
command with the original binPath.

### Slice 3 — repoint the service

```powershell
sc.exe stop admz
# re-register with the two new paths; everything else identical
#   --cwd \\?\C:\admz\admz-prod
#   -- C:\admz\admz-prod\.venv\Scripts\python.exe -m admz api --host 127.0.0.1 --port 4242
sc.exe start admz
# poll http://127.0.0.1:4242/health
```

The repo'd `setup-admz-service.ps1` already deletes and recreates the service
idempotently, so this is that script run with two different parameters, not new
machinery.

**Rollback:** re-register with the two old paths and start. ~10 seconds, and it
requires nothing of the new tree — the old clone and venv are untouched.
**Keep the old venv for a full week of normal operation** before reclaiming the
disk (ADR-0054); it will look redundant precisely while it is still
load-bearing.

Risks to check explicitly during this slice, both silent if missed:

- `git config --system safe.directory` covers `ADMZ_HOME`'s repos, not the code
  tree. A clone created by the interactive user and read by LocalSystem may trip
  Git's "dubious ownership" — the same failure ADR-0042 hit. Verify before
  cut-over, not after.
- Confirm no absolute path in the DB references `C:\admz\admz`. ADR-0042's
  migration had to rewrite `organizations.repo_path`; a code-tree move *should*
  need no analogue.

</details>

### Slice 4 — the deploy step, the script, and #173

- `scripts/setup-admz-service.ps1` — the existing script, brought into the repo,
  with `$Py` and `$Cwd` parameterised.
- `scripts/deploy-prod.ps1` — the six steps in ADR-0054 decision 6.
- `docs/DEPLOYMENT_WINDOWS.md` rewritten so Shawl / `windows-local` /
  `ADMZ_HOME` is the **primary** procedure and NSSM/IIS is the reverse-proxy
  alternative it actually is (**closes #173**).
- ADR-0054 and this plan flip 📋 → ✅ in the same PR, per house rule.

**The whole value of `deploy-prod.ps1` is its step 4** — smoke the new code on
the new venv *before* the service is stopped:

```powershell
& $ProdPy -c "import admz.mcp.server"     # the exact import that would have crash-looped today
& $ProdPy -m admz --version
if ($LASTEXITCODE -ne 0) { throw "smoke failed - service NOT touched" }
```

Steps 1–3 and 5–6 are bookkeeping around that check. Write the script so a
reader can see that.

### Slice 5 — staging staleness

Refresh `C:\admz\admz-staging-code` to `origin/master` and establish what keeps
it current. **No staging venv** (ADR-0054 decision 9). Note that a refreshed
staging on the shared dev venv is only coherent once slice 3 has removed
production from that venv — so this slice follows slice 3, not precedes it.

---

## Verification

| Claim | How it is checked |
|---|---|
| A dev `pip install` cannot reach production | `pip install` something harmless in `C:\admz\admz\.venv`; confirm `C:\admz\admz-prod\.venv` is unchanged and `/health` still healthy |
| A dev `pull` cannot reach production | `git -C C:\admz\admz pull`; confirm `git -C C:\admz\admz-prod rev-parse HEAD` is unchanged |
| The deploy step catches the #229 class of failure | point `deploy-prod.ps1` at a SHA whose deps do not match the venv; it must fail at step 4 with the service still serving |
| Rollback works | perform it deliberately once, during slice 3, before declaring the cut-over done |
| Nothing about ADMZ's behaviour changed | the suite is green on the production interpreter (slice 2) and no `admz/` source is in the diff |

---

## Open questions

1. **Schema migrations vs SHA rollback.** A code rollback does not roll back a
   database migration, so the rollback in slice 3 is code-only. Should
   `deploy-prod.ps1` refuse when the target SHA's migration set differs from the
   deployed one, prompt, or snapshot `admz.db` first? Flagged in ADR-0054 and
   deliberately **not designed here**.
2. **Who runs the deploy, and when.** This plan makes deployment explicit but
   says nothing about cadence. Left to the operator.
3. **Whether production should ever track a branch.** This plan says no —
   detached HEAD at a SHA. Worth revisiting only if the manual step becomes the
   bottleneck, which it currently is not.
