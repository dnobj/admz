# Requirements: release and promotion

How a version of ADMZ is named, built, installed and moved from development to production
sites. Decided in
[ADR-0075](../decisions/0075-a-release-is-built-once-and-installed-everywhere.md). Built in the
order of the [release promotion plan](../plans/release-promotion.md). Stories are in
[install and upgrade](../user-stories/install-and-upgrade.md).

Nothing here is built yet. Every marker below is 📋, and each flips to ✅ in the PR that ships it.

## Status legend

✅ implemented · 🚧 partial · 📋 planned

## Functional requirements

### FR-DEP-001 — A build reports its version and its build id 📋
`/api/health` and the page footer give the version and the build id of the running code. An
installed build reads both from a stamp written when it was built, so it needs no git. A checkout
with no stamp reads the commit from `.git`, as it does today. A stamp that cannot be read is
reported as a fault, never silently replaced by another answer.

### FR-DEP-002 — The source carries the release it is working towards 📋
`__version__` names the next release. Several builds may carry the same version. One of them is
promoted, and the source then moves on to the next number.

### FR-DEP-003 — Dependencies are locked, and CI tests the lock 📋
Every runtime package has one locked version, with hashes, in a file that serves both Windows and
Linux. CI installs from the lock, so what is tested is what is built. A lock that no longer
matches the files it was made from fails a test.

### FR-DEP-004 — An environment that differs from the lock is reported 📋
`tools/environments.py` compares each environment's installed packages with the lock and prints
the differences. An environment declared `locked: true` fails the run when it differs.

### FR-DEP-005 — An upgrade is one command, with a rollback 📋
One command verifies what it is about to install, imports every module on the interpreter that
will run it, switches, restarts the service, and waits for a healthy answer that carries the new
build id. If that answer does not come, it switches back, restarts, and reports the failure.

### FR-DEP-006 — The host records what it runs 📋
Every install, upgrade and rollback appends one line to a deploy log on that host: when, from
what, to what, by whom, and how it ended.

### FR-DEP-007 — An upgrade backs up the database and its key first 📋
Before anything is switched, the upgrade takes a consistent copy of the database and a copy of
its key, with a manifest of sizes and hashes. A failed backup stops the upgrade.

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
