# User stories: install and upgrade

> **Status:** 🚧 Partly built, and only for an instance that is a git checkout, which is the lab
> instance today. Built: the upgrade with a backup first and a rollback (US-INS-002, criteria 1, 3
> and 4), the version and build in health and the footer, and the host's deploy log (US-INS-003,
> criteria 1 and 2). Not built, because each needs the self-contained build: installing at a site
> (US-INS-001), unpacking a release beside the running one (US-INS-002, criteria 2 and 5), an
> answer that needs no git on an installed build (US-INS-003, criterion 3), `doctor`
> (US-INS-004), and promotion (US-INS-005). The decision is
> [ADR-0075](../decisions/0075-a-release-is-built-once-and-installed-everywhere.md), the build
> order is the [release promotion plan](../plans/release-promotion.md), and the requirements are
> [release and promotion](../requirements/release-and-promotion.md).

The [site installer](../personas/site-installer.md) puts ADMZ on a machine at a site and keeps it
current. The owner decides which builds a site ever sees.

## US-INS-001 — Install at a site with nothing but the installer

**As a** site installer at a machine with no internet access and no development tools, **I want
to** run one installer and end up with ADMZ running as a service.

**Acceptance criteria:**
1. The machine needs no Python, no git and no network access beforehand.
2. One command, run as an administrator, installs the build, registers the service and starts it.
3. The installer says which version and build it installed, and where.
4. The host is hardened when the command finishes: the code cannot be changed by a non-administrator,
   and the data folder is closed to ordinary accounts.
5. If anything fails, the machine is left as it was, and the message says what failed.

## US-INS-002 — Upgrade, and get back if it goes wrong

**As a** site installer with a new release in hand, **I want to** upgrade with one command and be
back on the previous release without doing anything if the new one does not come up.

**Acceptance criteria:**
1. The upgrade backs up the database and its key before changing anything.
2. The new release is unpacked beside the old one. The old one is not touched.
3. The service is switched, restarted, and checked for a healthy answer from the new build.
4. If the check fails, the service is switched back and restarted, and the result says so.
5. Downtime is the restart, not the install.

## US-INS-003 — Know what is running

**As an** owner looking after several sites, **I want to** ask any instance what it is running
and get the release, the build and the date.

**Acceptance criteria:**
1. `/api/health` and the page footer show the version and the build id.
2. The host's deploy log lists every install, upgrade and rollback, with who did it.
3. The answer does not depend on git being present.

## US-INS-004 — Check that a host is still as it was installed

**As a** security-conscious operator, **I want to** run one check on a site machine and learn
whether the installed files or the host's protections have changed.

**Acceptance criteria:**
1. `python -m admz doctor` compares every installed file with the build's manifest.
2. It compares the host with its declared posture: who can change the code, who can read the data
   folder, which account runs the service, whether any development-only switch is on.
3. It exits non-zero on any difference, and names each one.
4. An upgrade refuses to run on a hardened host that fails the check.

## US-INS-005 — Promote a build to a release

**As the** owner, **I want to** try many builds on my lab instance and choose which one becomes a
release for sites.

**Acceptance criteria:**
1. Every build has a date id, and can be installed on the lab instance.
2. Promoting a build gives it a version number and records it in the release list. Nothing is
   rebuilt, so what ran in the lab is byte for byte what a site gets.
3. A site machine refuses a build that is not a release.
