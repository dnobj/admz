# Requirements: release and promotion

How a version of ADMZ is named, built, installed and moved from development to production
sites. Decided in
[ADR-0075](../decisions/0075-a-release-is-built-once-and-installed-everywhere.md). Built in the
order of the [release promotion plan](../plans/release-promotion.md). Stories are in
[install and upgrade](../user-stories/install-and-upgrade.md).

Three slices are built. A build reports its version and its build id (FR-DEP-001, FR-DEP-002).
Dependencies are locked, CI tests the lock, and an environment that differs from it is reported
(FR-DEP-003, FR-DEP-004). An instance that is a git checkout is upgraded by one command, with a
backup first, a rollback, and a log on the host (FR-DEP-005 in part, FR-DEP-006, FR-DEP-007).
Everything else is 📋, and each marker flips to ✅ in the PR that ships it.

## Status legend

✅ implemented · 🚧 partial · 📋 planned

## Functional requirements

### FR-DEP-001 — A build reports its version and its build id ✅
`/health`, `/api/health` and the page footer give the version and the build id of the running
code. An installed build reads its build id from a stamp, `admz/_build.json`, written when it was
built, so it needs no git. A checkout has no stamp and reads the commit from `.git`, as before. A
stamp that cannot be read or does not hold a valid build id and commit is reported as
`invalid-stamp`, and is never silently replaced by another answer. Health also carries `commit`.
`admz/build_info.py`; `tests/test_build_id.py`. The step that writes a stamp arrives with the
artifact (FR-DEP-008).

### FR-DEP-002 — The source carries the release it is working towards ✅
`__version__` names the next release, as `major.minor.patch`. It is `2.1.0`, the first line under
this scheme. Several builds may carry the same version. One of them is promoted, and the source
then moves on to the next number. Promotion itself is FR-DEP-010.

### FR-DEP-003 — Dependencies are locked, and CI tests the lock ✅
Every runtime package has one locked version, with hashes, in a file that serves both Windows and
Linux: `requirements.lock`. `requirements-dev.lock` holds the same pins plus the test tools. CI
installs the dev lock in hash mode into a virtual environment of its own, and then checks that
the environment it is about to test is that lock and nothing else, so what is tested is what a
build installs. A lock that no longer
matches the files it was made from fails a test. The catalog stays outside the locks, pinned by
commit. The first lock was aligned to the lab instance's own versions, so nothing it runs moved.
`tools/lock.py`; `tests/test_lockfiles.py`; `.github/actions/setup-admz/action.yml`.

### FR-DEP-004 — An environment that differs from the lock is reported ✅
`tools/environments.py` asks each environment's interpreter what it has installed, compares that
with the lock in the environment's own checkout, and prints the differences: a package missing,
at another version, or installed although the lock does not pin it. An environment declared
`locked: true` fails the run when it differs, when its packages cannot be listed, or when its
checkout holds no lock to compare with. `python tools/lock.py --verify-installed` makes the same
comparison for one interpreter. `tests/test_environments_lock.py`. No environment is declared
`locked` yet: the lab instance's packages match, and it gets the key with the first upgrade that
puts a lock in its own tree.

### FR-DEP-005 — An upgrade is one command, with a rollback 🚧
One command verifies what it is about to install, imports every module on the interpreter that
will run it, switches, restarts the service, and waits for a healthy answer that carries the new
build id. If that answer does not come, it switches back, restarts, and reports the failure.

Built for an instance that is a git checkout, which is the lab instance today:
`python -m admz upgrade --tree <tree> --home <data folder> --to <commit>`. Before changing
anything it checks that the tree is clean and at the commit it started from, that the target is
ahead of it, that the catalog pin does not move, that the installed packages are exactly the
target's lock, that the service is running and the instance on the port reports this tree's
build, and that every module of the target imports on the instance's interpreter. A failed check
is a refusal and changes nothing. `--check` stops there. Then it stops the service, checks out
the target, starts the service and waits for health from the target's build. Any failure from the
stop onwards, an interrupt from the keyboard included, goes back to the old commit and waits for
health from the old build. Four exit codes tell the endings apart: upgraded, refused, rolled
back, and a rollback that itself failed. The command runs in two stages so that every check is
the target's own code. `admz/release/`; `tests/test_release_*.py`.

Not built: installing packages or the catalog (it refuses when either would have to change), and
the same command for a self-contained build, which arrives with FR-DEP-008 and FR-DEP-009.

### FR-DEP-006 — The host records what it runs ✅
Every install, upgrade and rollback appends one line to a deploy log on that host: when, from
what, to what, by whom, and how it ended. The log is `deployed.log` in the instance's data
folder, one JSON object per line. A refused attempt is recorded too, with its reason. A line is
never written into a folder that does not hold an instance's database, so a mistyped data folder
gains no log. `admz/release/deploylog.py`.

### FR-DEP-007 — An upgrade backs up the database and its key first ✅
Before anything is switched, the upgrade takes a consistent copy of the database and a copy of
its key, with a manifest of sizes and hashes. A failed backup stops the upgrade. The copy is made
with SQLite's backup API while the service runs, never as a file copy, so writes still in the
write-ahead log are included; a test builds that state and shows a file copy missing them. The
copy is opened and checked before it is trusted. Backups go to `backups\` in the data folder and
are not pruned. A rollback does not restore the database (FR-DEP-012). `admz/release/backup.py`.

### FR-DEP-008 — A build is one self-contained artifact 📋
A build carries the interpreter, every locked package, the catalog at its pinned commit, the
service wrapper, and a manifest holding the version, the build id, both commits and a hash of
every file. Installing it fetches nothing.

### FR-DEP-009 — Builds sit side by side, and the service runs through a pointer 📋
An upgrade unpacks the new build beside the running one and switches a pointer. It never edits
the service definition. A rollback is the same switch in the other direction.

### FR-DEP-010 — A release is a promoted build, and a site installs only releases 📋
Every build has a date id. A release is a build the owner promotes for sites. It also carries a
version number, and promoting it rebuilds nothing. The lab instance may install any build. A
hardened host installs only a release.

### FR-DEP-011 — A host declares its posture and can check itself 📋
A host is `lab` or `hardened`, recorded when it is installed. `python -m admz doctor` compares
the installed files with the manifest and the host with its declared posture, and exits non-zero
on a difference. An upgrade refuses a hardened host that fails the check.

### FR-DEP-012 — Schema changes are additive 📋
A build starts on the previous build's data, and the previous build still starts after the new
one has run. A change that cannot meet this needs a major version and a written upgrade step.

### FR-DEP-013 — A device belongs to exactly one instance 📋
A device is removed from one instance before it is added to another. Each instance sets its own
accounts on a device, so two would lock each other out.

## Non-functional requirements

### NFR-DEP-001 — Installing needs no network 📋
A site machine installs and upgrades with nothing but the artifact. No package index, no git, no
access to the catalog repository.

### NFR-DEP-002 — Data never travels with a build 📋
A build contains no devices, credentials or settings. Each host keeps its own data folder.

### NFR-DEP-003 — A build is private material 📋
A build contains the private catalog. It is never published with this public repository, and
never uploaded as a workflow artifact of it.

### NFR-DEP-004 — Agents hold no credentials for site machines 📋
A promotion to a hardened host is made by a person with administrator rights on that host.

## Known limitations

- **The first version is unsigned.** The manifest catches a damaged or incomplete artifact, not a
  replaced one. A release is as trustworthy as the way it reached the host. Accepted by the owner
  on 2026-11-25 for the local site and the first real one. A site updater (#546) cannot be built
  before signing exists.
- **Windows only.** The service wrapper, the Windows sign-in and the ACS Pro connection assume it.
- **Nothing enforces FR-DEP-012 yet.** It is a rule a reviewer applies.
- **Where builds are made and kept is not decided.** See the plan's "Needs the owner".

## References

- [ADR-0075](../decisions/0075-a-release-is-built-once-and-installed-everywhere.md), and
  [ADR-0054](../decisions/0054-separate-production-tree-and-venv.md), whose decisions 6 to 8 this
  finishes.
- #426, #377, #233, #534, #540, #546.
