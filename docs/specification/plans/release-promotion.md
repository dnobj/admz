# Plan: Release promotion — identity, locked versions, the upgrade command, the artifact, the hardened install

Status: **approved 2026-11-26; PR 1 and PR 2 built.** The owner accepted
[ADR-0075](../decisions/0075-a-release-is-built-once-and-installed-everywhere.md) and asked for
building to start. Six slices, built one at a time. Requirements are
[release and promotion](../requirements/release-and-promotion.md). File references are against
master `c94aad5`.

## Context

Production will be separate machines at sites, the first a local site on an AXIS S2208 appliance.
Today's instance is a git clone on the development machine, updated by a manual checklist. ADR-0075
replaces that with one self-contained build, installed by one command, on a host that declares
whether it is a lab or hardened. This plan is the order in which that gets built.

The first three slices change nothing about where anything lives. They are worth having even if
the rest took a year.

## What was measured on 2026-11-26

| Fact | Where |
|---|---|
| The lab instance violates exactly one declared bound: starlette 1.3.1 against `>=0.52,<0.53` | `requirements.txt:90`, `pip list` on its venv |
| 28 of the 66 packages the lab instance and the dev environment share are at different versions (fastapi 0.141.1 and 0.129.0, pydantic 2.13.4 and 2.12.5, anyio 4.14.2 and 4.12.1) | `pip list` on both |
| There is no lock. Transitive packages are bounded only where an upstream happens to cap them | #233 |
| `build_id()` reads the commit from `.git`, and returns `None` when there is no `.git` | `admz/build_info.py:122-160` |
| `__version__` is `"2.0.0"`, and has named every build for months | `admz/__init__.py:17` |
| No `deployed.log` exists on the host, and no `.ps1` is tracked | ADR-0054 decisions 6 to 8 |
| The lab instance's virtual environment sits on a Python in the operator's own profile | its `pyvenv.cfg` |
| Neither `uv` nor `pip-tools` is installed in the dev environment | |

## Decisions taken by default (the owner may override)

| Decision | Default | Why |
|---|---|---|
| The first release line | `2.1.0` | `2.0.0` has already named many different builds |
| Build id | `YYYY.MM.DD.N`, where `N` is the next free number among the `build/YYYY.MM.DD.*` tags | ADR-0075 §2 |
| Lock tool | `uv pip compile --universal --generate-hashes`, as a maintainer's tool. Nothing at run time or in CI needs it | One file serves Windows and Linux, which is #233's "it must be multi-platform" |
| Lock files | `requirements.lock` for the runtime, `requirements-dev.lock` for the runtime plus the test tools | pip's hash checking is all or nothing, so the test tools need hashes too |
| Deploy log | `ADMZ_HOME\deployed.log`, one JSON object per line | ADR-0054 decision 7 |
| The backup an upgrade takes | `ADMZ_HOME\backups\<timestamp>\`, holding the database and the key | It protects against a bad upgrade, not a lost disk. #534 covers the rest |
| Where the release code lives | `admz/release/` | It ships in the product, because a site has no `tools/` |

## PR 1 — Identity: a build reports its version and its build id

- **`admz/__init__.py`:** `__version__ = "2.1.0"`. The source now carries the release it is working
  towards.
- **`admz/build_info.py`:**
  - A build stamp, `admz/_build.json`, written by the build step and absent from a checkout:
    `{"build", "commit", "catalog_commit", "built_at"}`.
  - `build_id()` returns the stamp's build id when a stamp is present. With no stamp it reads
    `.git` exactly as it does today, so the lab instance in its present layout is unchanged.
  - A stamp that cannot be read or parsed is reported as `invalid-stamp`. It must not fall back to
    git: an artifact with a broken stamp is a fault somebody has to see.
  - `describe()` returns the version, the build, the commit and which of the two sources answered.
- **`/api/health`** keeps `version` and `build`, and adds `commit` when it is known. Additive only:
  the deploy check reads `build` today.
- **The page footer** shows the version beside the build.
- **`.gitignore`** lists the stamp, and a test fails if one is ever tracked.
- **Tests** (`tests/test_build_id.py`): the stamp wins over git; a broken stamp is `invalid-stamp`;
  no stamp behaves as before; health carries `2.1.0`.
- Flips FR-DEP-001 and FR-DEP-002.

## PR 2 — Locked versions: CI tests what the lab instance runs

- **`requirements.txt`:** the starlette bound moves to the line the lab instance is on. The
  "installed" notes on the lines the lock moves are corrected.
- **`requirements.lock` and `requirements-dev.lock`:** universal, hashed, made by one documented
  command, starting from the lab instance's own versions so that the lock is aligned forward to what
  already runs.
- **CI** (`.github/actions/setup-admz/action.yml`) installs from `requirements-dev.lock` with
  `--require-hashes` on both legs, then the package and the catalog as it does now.
- **Guard tests** (`tests/test_lockfiles.py`):
  - every pin satisfies the bound declared for it;
  - the runtime lock is a subset of the dev lock, at the same versions;
  - each lock records a hash of the files it was made from, so an edited `requirements.txt` with a
    stale lock fails;
  - every entry carries at least one hash.
- **`tools/environments.py`** compares each environment's installed packages with the lock and
  prints the differences. A new declared key, `locked: true`, makes a difference fail the run. The
  lab instance gets it once its environment has been shown to match.
- **The suite has to pass on the locked versions before this merges.** Whatever fails under
  starlette 1.x or fastapi 0.141 is fixed here, or split into its own PR ahead of this one.
- Flips FR-DEP-003 and FR-DEP-004. Closes #233: a lock, where #233 proposed constraints. Its four
  objections to a lock are answered by a universal lock, by the catalog staying outside it, and by
  guard tests standing in for line-by-line review.

**As built (2026-11-26).** Four things differ from the list above.

- **The suite needed no fixes.** On the lab instance's versions it gave 6112 passed and 1 failed,
  and the one failure was the test that compares the installed starlette with the old bound. The
  risk this slice carried turned out to be empty.
- **CI checks the result of its own install.** After installing, it runs
  `python tools/lock.py --verify-installed dev`, which fails if any pinned package is missing or
  at another version, or if anything is installed that the lock does not pin. The catalog is
  installed outside hash mode, so the install commands alone could not promise that.
- **`locked: true` compares with the lock in the environment's own checkout,** and a checkout with
  no lock fails closed. Comparing a deployment with the development tree's lock would report it as
  wrong whenever a pin moved here first. So the lab instance is not declared `locked` in this PR.
  Its packages were shown to match (64 of 64, nothing else installed), and it gets the key in
  PR 3, after the first upgrade that puts a lock in its tree.
- **The tool reads the lock's platform markers itself,** with the standard library. `packaging`
  is a test tool and is not installed in a deployment, and PR 3 needs this comparison to run on
  the instance's own interpreter. A test holds the reader to `packaging`'s answer on every marker
  in the locks.

## PR 3 — `upgrade` for the lab instance, in its present layout

The checklist of 2026-11-13 as one command. New package `admz/release/`.

- **One command, two stages.** `python -m admz upgrade --tree <instance tree> --to <commit>`.
  - Stage 1 resolves the commit, fetches, makes a throwaway detached worktree of it, and re-runs
    itself from there on the instance's interpreter. The code doing the upgrade is then the new
    code, and it is not replaced under its own feet.
  - Stage 2 is ADR-0075 §3: check the tree is at the expected commit and clean; refuse if the
    target's lock differs from what is installed, unless `--sync-env`; import every module on the
    instance's interpreter with a throwaway `ADMZ_HOME`; back up the database and its key; check
    out; restart; wait for health carrying the new build; roll back on failure; write the deploy
    log. The lock comparison is PR 2's (`tools/lock.py`), which runs on the standard library.
- **After the first real upgrade** the instance's tree holds a lock of its own. `production` is
  then declared `locked: true` in `docs/ENVIRONMENTS.md`, and from there a difference fails
  `tools/environments.py`.
- **Pieces, each small and testable alone:**
  - `walk.py`: the import walk. It passes `onerror` to `pkgutil.walk_packages`, which otherwise
    swallows an `ImportError` raised while descending, and it refuses an `ADMZ_HOME` it was not
    given on purpose.
  - `backup.py`: the SQLite backup API (never a file copy of a WAL database), the key, and a
    manifest of sizes and hashes.
  - `service.py`: stop, start and status behind one interface, with the Windows implementation and
    a fake for tests.
  - `health.py`: poll until healthy, then require the expected build.
  - `deploylog.py`: append one JSON line with time, from, to, operator and outcome.
- **Tests never touch a real service or a real data folder.** The orchestration takes its service
  and its health probe as parameters, so every path is driven with fakes: success, a failed walk, a
  failed health check with rollback, a rollback that itself fails. One end-to-end test runs both
  stages against a temporary git repository and a stub service.
- **Docs:** `DEPLOYMENT_WINDOWS.md` gains "Upgrading"; `CLAUDE.md`'s notes on updating production
  point at the command.
- Flips FR-DEP-005, FR-DEP-006 and FR-DEP-007. Closes #426. It is the first slice of #534, which
  stays open for scheduled backups, the config history and a checked restore.

## PR 4 — The artifact, and installing from it

- **`tools/build_release.py`** (Windows): an embedded CPython, every package from
  `requirements.lock` installed with `--require-hashes`, the catalog built from `ATLAS_SHA`, the
  service wrapper, the stamp from PR 1, and a manifest hashing every file. Output is one archive
  named with the version and the build id.
- **`install` and `upgrade` from an archive:** builds sit side by side under a `releases` folder,
  and the service runs through a `current` pointer, so an upgrade never edits the service
  definition and a rollback is a pointer switch.
- **The lab instance moves onto it,** on the owner's word.
- **Where a build is made is not settled.** ADR-0075 says CI makes builds, and a build carries the
  private catalog, so it cannot be an artifact of this public repository's workflows. Until the
  owner decides where builds are made and kept, the script runs on the development machine. A
  build made there may go to the lab instance. Whether it may go to the local site is the owner's
  call.
- Flips FR-DEP-008, FR-DEP-009 and FR-DEP-010.

## PR 5 — The hardened install, and `doctor`

- The installer creates the service account, applies the permissions, and installs under a parent
  only administrators can change (#540, #377).
- `python -m admz doctor` compares the installed files with the manifest and the host with its
  declared posture.
- `docs/ENVIRONMENTS.md` and `tools/environments.py` learn `posture`.
- Key wrapping is its own change, an amendment to ADR-0010, and is not a condition for the first
  local-site install.
- The local production site is the first host installed this way.
- Flips FR-DEP-011.

## PR 6 — Sites

A one-page install and upgrade guide for the [site installer](../personas/site-installer.md), the
release list, and the list of which site runs which release.

## Needs the owner

1. **Where builds are made and kept.** It blocks the CI half of PR 4 and the first release.
2. **A word before each change to the lab instance:** the first real `upgrade` in PR 3, and the
   move to the artifact layout in PR 4. PR 2's comparison is read-only.
3. **Agents and the local site.** ADR-0075 §5 says agents hold no credentials for site machines.
   The owner has since asked for the local site to be deployed by an agent through a remote
   console. The two fit together if the record says so: on the owner's own local site an agent may
   run the installer through a console session the owner has opened, and it still holds no
   credential of its own. That amendment is written when PR 5 is near, on the owner's word.

## Risks found while planning

- **The suite under starlette 1.x and fastapi 0.141.** The lab instance has run them since August.
  The tests never have. This is the one slice whose size is unknown until it is measured.
- **pip's hash mode on two platforms** from one universal lock. Proven in CI by PR 2 itself.
- **`pywin32` and `cryptography` in an embedded layout.** `pywin32` relies on a `.pth` file and on
  DLLs being found. PR 4 proves the import walk on the built artifact before anything is installed
  from it.
- **A junction as the `current` pointer,** with a service holding files open under it. PR 4 tests
  the switch with the service stopped, which is the order §3 already uses.
- **Schema changes.** ADR-0075 §6 requires them to be additive. Nothing enforces that yet, and a
  guard for it is not in this plan.

## Verification

- Each PR: its own tests, the full suite locally (`-n 8 --dist loadfile`), and CI on both legs.
- PR 2: `tools/environments.py` shows the lab instance matching the lock.
- PR 3: one real upgrade of the lab instance with the command, on the owner's word, compared step
  by step with the manual procedure recorded in #426.
- PR 4: the import walk on the built artifact, and an install on a clean Windows machine.

## Sequence

PR 1, PR 2, PR 3, then the owner's decision on where builds are made, then PR 4, PR 5, PR 6.
