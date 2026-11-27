# ADR-0075 — A release is built once and installed everywhere: dev, the lab instance, then production sites

**Status:** Proposed (2026-11-23), revised 2026-11-25 with the owner's answers. Docs-only. A plan with PR-sized slices follows acceptance.
**Relates to:** [ADR-0054](0054-separate-production-tree-and-venv.md) (production's own tree and interpreter; its decisions 6, 7 and 8 were never built, and this record finishes them in a different shape) · [ADR-0042](0042-machine-level-data-directory.md) (the data directory and the Windows service) · [ADR-0052](0052-advanced-capability-switches.md) (capability switches) · [ADR-0010](0010-fernet-encryption.md) (the encryption key) · [ADR-0061](0061-entry-credentials-and-the-admz-account.md) and [ADR-0068](0068-root-is-a-break-glass-credential-admz-sets-and-never-stores.md) (the accounts an instance sets on a device) · [review-2026-11-09](../review-2026-11-09.md) O-1, O-2, O-3 and its lab-conveniences section · #426, #377, #233, #238, #534, #540, #546

## Context

**What the owner decided.** Production will be separate machines at sites. The first is a local production site, separate from development: a physical machine, an AXIS S2208 appliance (a Camera Station recorder with a built-in PoE switch), which is being set up. The machine everything runs on today is a development machine, and its conveniences stay (#540). The full list of the owner's answers is at the end of this record.

**What "production" is today.** A git clone at a detached commit, inside the development root, on the development machine, updated by checking out a new commit and restarting the service (ADR-0054). It manages the lab's real devices, so it is protected like production. It is not what a site can run:

- **An update is a checklist.** ADR-0054 decided on one deploy script, a deploy log kept on the host, and the service setup script in the repository. None of the three was built (#426, #377). The update of 2026-11-13 was twelve manual steps.
- **An install needs the repository.** The Windows deployment guide starts from a checkout, git, and a setup script that is not in the repo. A site machine would need all of that, plus network access to GitHub and to a private catalog repository.
- **What runs is not what was tested.** The instance's packages are outside `requirements.txt`'s own bounds (review O-2), because nothing builds its environment from a fixed list.
- **The interpreter is borrowed.** The instance's virtual environment sits on a Python installed in the operator's own user profile. Updating or removing that installation breaks a service that runs as LocalSystem.
- **The build cannot name itself without git.** `/api/health` reads the commit from `.git`. An install with no `.git` would report nothing.
- **Nothing tells a lab from a production host.** One kind of install serves both, so the things that make development easy would arrive at a site with it.

## Decision

### 1. Three kinds of place, and one instance per device

| Place | What it is | Posture |
|---|---|---|
| **dev** | Working trees on the development machine. Throwaway data. Never a service. | none |
| **the lab instance** | The live service on the development machine, managing the devices used for development and testing. | `lab` |
| **production sites** | Separate machines. The first is the local site, on an AXIS S2208 appliance. | `hardened` |

The lab instance is today's `production` entry in `docs/ENVIRONMENTS.md`. It keeps that name, its port and every protection it has until the local site is running, with `posture: lab` added. Renaming something that manages real devices is a way to get it treated as less than it is. Once the local site is running, the lab instance is the rehearsal stop, and the present `staging` entry, which cannot run (#238), is retired.

**A device belongs to exactly one instance.** Each instance creates its own account on a device and sets the device's root password (ADR-0061, ADR-0068), so two instances managing one device would lock each other out. A device is removed from one instance before it is added to another. For the local site the cabling settles most of it: devices on the appliance's own switch normally sit on its camera network, which the development machine does not reach directly, so they belong to the site's instance.

### 2. A build is an artifact, made once, and a release is a build that was promoted

- **CI makes a build from a commit on master,** on Windows, when one is asked for. Nothing else makes one.
- **It is self-contained:** the interpreter, every package at a locked version, the catalog at its pinned commit, the service wrapper, and a manifest holding the version, the build id, the commit, the catalog commit and a hash of every file. Installing it fetches nothing.
- **A build is named by date, and a release also by number.**
  - Every build gets an id from its date and that day's count: `2026.11.25.1`. Builds can be frequent.
  - The source carries the version it is working towards, so a build reports both: `2.1.0 (2026.11.25.1)`.
  - A **release** is a build the owner promotes for sites. Promoting declares that build to be `2.1.0`: a tag on its commit and a line in the release list, with the artifact's hash. Nothing is rebuilt, and the source moves on to the next number.
  - The number is `major.minor.patch`. The minor number rises with each promoted release. A fix to a release already at sites is a patch, `2.1.1`. The major number is kept for a release that needs attention at upgrade, which is anything §6's additive rule cannot cover.
- **The version and the build id are baked in,** so `/api/health` reports them without git.
- **The same artifact is installed everywhere.** What the lab instance ran for a week is, byte for byte, what a site gets.
- **A build is private material.** It contains the private catalog, so it cannot be published with this public repository.
- **The tag names what was promoted. The host still records what it runs:** a line in a deploy log on that machine, as ADR-0054's decision 7 required.

### 3. Promotion is one command on the target host

`install` on a new host and `upgrade` on an existing one, the same on the lab instance and at a site:

1. verify the artifact against its manifest;
2. check the host (§4), and refuse a hardened host that fails;
3. back up the database and its key;
4. unpack the build beside the one that is running;
5. import every module on the new build's own interpreter;
6. switch the `current` pointer and restart the service;
7. wait for a healthy answer that carries the new build id;
8. on failure, switch the pointer back, restart, and stop;
9. append to the host's deploy log.

Builds sit side by side and the service runs through `current`. An upgrade therefore never edits the service definition, and a rollback is a pointer switch. This is ADR-0054's decision 6 with the checkout replaced by an unpack. The installer takes over what `setup-admz-service.ps1` does today, which settles #377.

**At a site, a person runs the installer on that machine.** Nothing at a site fetches anything in this version. A site updater that fetches releases, queues them, and applies them on approval or automatically is the owner's idea for later, and is pinned as #546.

### 4. Posture is declared, and a host can check itself

A host is `lab` or `hardened`, and that is written down when it is installed.

**`hardened`** is the table in #540:

- the code lives under a parent only administrators can change. This is the lesson of #442: locking a folder is not enough while its parent can be renamed;
- a dedicated service account, in place of LocalSystem;
- the data folder open to SYSTEM, Administrators and that account only;
- the encryption key wrapped for that account (an amendment to ADR-0010);
- no development tree, and no `dev-only` capability switched on;
- upgrades run elevated, by a person.

**`lab`** allows everything that list forbids, on purpose.

A site has no repository and no `tools/`, so the check ships in the product. `python -m admz doctor` compares the installed files with the manifest and the host with its declared posture, and exits non-zero on a difference. `tools/environments.py` remains the development machine's checker and learns the same `posture` key.

### 5. One stop at a time, and a person moves it

dev, then the lab instance, then the local production site, then the other sites.

- **The lab instance takes any build. A site takes only a release.**
- A release reaches a site only after it has run on the lab instance and on the local site.
- Nothing promotes itself. Each stop is the owner's decision.
- On the lab instance the operator promotes, or an agent does on the operator's word, as today.
- On a hardened host, a person with administrator rights on that host runs the installer. Agents hold no credentials for site machines and are not given any.

### 6. Data never travels with a build

- Every host keeps its own data folder. A build carries no devices, credentials or settings.
- A build must start on the previous one's data, and the previous one must still start after the new one has run. So schema changes are additive.
- The backup in step 3 is taken regardless.

Together these answer the question ADR-0054 left open about a rollback across a schema change: snapshot first, and keep migrations additive so that a code rollback still starts.

## Consequences

- A build pipeline: lock, bundle and manifest, on a Windows runner, using the catalog deploy key CI already holds.
- The lab instance changes how it is updated, from a checkout to an unpack and a pointer, so that every build exercises the path a site will use.
- A new command surface in the product: `install`, `upgrade`, `doctor`.
- The version number starts to mean something. It has read `2.0.0` for months.
- Windows only. The service wrapper, the Windows sign-in and the ACS Pro connection all assume it.
- **The first version is not signed,** which the owner has accepted for the local site and the first real one. The manifest catches a damaged or incomplete artifact. It does not catch a replaced one, so a release is only as trustworthy as the way it reached the host. Signing is the follow-up, and #546 cannot be built without it.
- The catalog now ships inside something that leaves the building. Whoever holds a build holds the catalog.

## Build order

1. **This record, then a plan.**
2. **Identity and locked versions.** A build reports its version and build id. Dependencies are locked, aligned forward to what the lab instance runs today, and its environment is rebuilt from the lock (#233, review O-2).
3. **`upgrade` for the lab instance in its present layout,** with the deploy log and the backup before the switch: the checklist of 2026-11-13 as a command (#426, and the first slice of #534). It is useful on its own, and it is where the checks get written.
4. **The artifact,** made by CI, with `install` and `upgrade` from it and builds side by side. The lab instance moves onto it.
5. **`hardened`:** the installer creates the account and the permissions, `doctor` checks them, and the key is wrapped (#540). The local production site is the first host installed this way.
6. **Sites:** a one-page install and upgrade guide, the release list, and a list of which site runs which release.

Steps 2 and 3 change nothing about where anything lives.

## Alternatives considered

- **Keep checking out commits, on every site.** It is what exists. Every site would need git, the repository, access to the private catalog and a package index at install time, and each would resolve its own versions. That is review O-2 repeated at every site.
- **Containers.** They solve the packaging. They do not suit a Windows service that signs people in with Windows accounts and talks to ACS Pro as its own Windows identity.
- **An MSI or a signed installer.** Probably the right end state for many sites. It can wrap the same artifact later without changing anything above.
- **Dates only, or numbers only, as names.** Dates alone say when and not which builds matter. Numbers alone make every frequent build look like a release. The owner asked for both, and §2 gives each a job.
- **Sites that fetch their own updates.** Not rejected. It is pinned as #546 and needs signing first.

## Decided by the owner

**2026-11-23**
- Production is separate machines at sites, starting with a local site that is separate from development.

**2026-11-25**
- The local site is a separate physical machine, an AXIS S2208 appliance.
- A release reaches a site by a person running the installer on that machine. A site updater is for later (#546).
- An unsigned first version is acceptable.
- Names carry a date as well as a version number, because builds will be frequent and only some are promoted.

## Still open

1. **Where are release files kept** until someone carries or downloads them? They cannot sit with this public repository. The proposal is the release page of a private repository, next to the catalog.
2. **Which of the lab's devices move to the local site?** §1's rule decides most of it: what is plugged into the appliance belongs to the appliance. The rest is the owner's choice, device by device.
