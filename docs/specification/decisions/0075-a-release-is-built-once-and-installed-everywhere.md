# ADR-0075 — A release is built once and installed everywhere: dev, the lab instance, then production sites

**Status:** Proposed (2026-11-23). Docs-only. A plan with PR-sized slices follows acceptance.
**Relates to:** [ADR-0054](0054-separate-production-tree-and-venv.md) (production's own tree and interpreter; its decisions 6, 7 and 8 were never built, and this record finishes them in a different shape) · [ADR-0042](0042-machine-level-data-directory.md) (the data directory and the Windows service) · [ADR-0052](0052-advanced-capability-switches.md) (capability switches) · [ADR-0010](0010-fernet-encryption.md) (the encryption key) · [review-2026-11-09](../review-2026-11-09.md) O-1, O-2, O-3 and its lab-conveniences section · #426, #377, #233, #238, #534, #540

## Context

**What the owner decided (2026-11-23).** Production will be separate machines at sites. One of them should be a local production site, separate from development, and it does not exist yet. The machine everything runs on today is a development machine, and its conveniences stay (#540).

**What "production" is today.** A git clone at a detached commit, inside the development root, on the development machine, updated by checking out a new commit and restarting the service (ADR-0054). It manages the lab's real devices, so it is protected like production. It is not what a site can run:

- **An update is a checklist.** ADR-0054 decided on one deploy script, a deploy log kept on the host, and the service setup script in the repository. None of the three was built (#426, #377). The update of 2026-11-13 was twelve manual steps.
- **An install needs the repository.** The Windows deployment guide starts from a checkout, git, and a setup script that is not in the repo. A site machine would need all of that, plus network access to GitHub and to a private catalog repository.
- **What runs is not what was tested.** The instance's packages are outside `requirements.txt`'s own bounds (review O-2), because nothing builds its environment from a fixed list.
- **The interpreter is borrowed.** The instance's virtual environment sits on a Python installed in the operator's own user profile. Updating or removing that installation breaks a service that runs as LocalSystem.
- **The build cannot name itself without git.** `/api/health` reads the commit from `.git`. An install with no `.git` would report nothing.
- **Nothing tells a lab from a production host.** One kind of install serves both, so the things that make development easy would arrive at a site with it.

## Decision

### 1. Three kinds of place

| Place | What it is | Posture |
|---|---|---|
| **dev** | Working trees on the development machine. Throwaway data. Never a service. | none |
| **the lab instance** | The live service on the development machine, managing the lab's devices. | `lab` |
| **production sites** | Separate machines. The first is a local site, still to be built. | `hardened` |

The lab instance is today's `production` entry in `docs/ENVIRONMENTS.md`. It keeps that name, its port and every protection it has until the local site exists, with `posture: lab` added. Renaming something that manages real devices is a way to get it treated as less than it is. When the local site takes over, the lab instance becomes the rehearsal stop, and the present `staging` entry, which cannot run (#238), is retired.

### 2. A release is an artifact, built once

- **CI builds it from a tag on master,** on Windows. Nothing else builds one.
- **It is self-contained:** the interpreter, every package at a locked version, the catalog at its pinned commit, the service wrapper, and a manifest holding the release id, the commit, the catalog commit and a hash of every file. Installing it fetches nothing.
- **The release id is baked in,** so `/api/health` reports it without git.
- **The same artifact is installed everywhere.** What the lab instance ran for a week is, byte for byte, what a site gets.
- **A release is private material.** It contains the private catalog, so it cannot be published with this public repository.
- **The tag names what was built. The host still records what it runs:** a line in a deploy log on that machine, as ADR-0054's decision 7 required.

### 3. Promotion is one command on the target host

`install` on a new host and `upgrade` on an existing one, the same on the lab instance and at a site:

1. verify the artifact against its manifest;
2. check the host (§4), and refuse a hardened host that fails;
3. back up the database and its key;
4. unpack the release beside the one that is running;
5. import every module on the new release's own interpreter;
6. switch the `current` pointer and restart the service;
7. wait for a healthy answer that carries the new release id;
8. on failure, switch the pointer back, restart, and stop;
9. append to the host's deploy log.

Releases sit side by side and the service runs through `current`. An upgrade therefore never edits the service definition, and a rollback is a pointer switch. This is ADR-0054's decision 6 with the checkout replaced by an unpack. The installer takes over what `setup-admz-service.ps1` does today, which settles #377.

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

### 5. A release moves one stop at a time, and a person moves it

dev, then the lab instance, then the local production site, then the other sites.

- A release reaches a site only after it has run on the lab instance, and on the local site once there is one.
- Nothing promotes itself. Each stop is the owner's decision.
- On the lab instance the operator promotes, or an agent does on the operator's word, as today.
- On a hardened host, a person with administrator rights on that host runs the command. Agents hold no credentials for site machines and are not given any.

### 6. Data never travels with a release

- Every host keeps its own data folder. A release carries no devices, credentials or settings.
- A release must start on the previous release's data, and the previous release must still start after the new one has run. So schema changes are additive.
- The backup in step 3 is taken regardless.

Together these answer the question ADR-0054 left open about a rollback across a schema change: snapshot first, and keep migrations additive so that a code rollback still starts.

## Consequences

- A build pipeline: lock, bundle and manifest, on a Windows runner, using the catalog deploy key CI already holds.
- The lab instance changes how it is updated, from a checkout to an unpack and a pointer, so that every release exercises the path a site will use.
- A new command surface in the product: `install`, `upgrade`, `doctor`.
- Windows only. The service wrapper, the Windows sign-in and the ACS Pro connection all assume it.
- **The first version is not signed.** The manifest catches a damaged or incomplete artifact. It does not catch a replaced one, so a release is only as trustworthy as the way it reached the host. Signing the manifest is the follow-up.
- The catalog now ships inside something that leaves the building. Whoever holds a release holds the catalog.

## Build order

1. **This record, then a plan.**
2. **Release identity and locked versions.** A tag gives a release id that the build reports. Dependencies are locked, aligned forward to what the lab instance runs today, and its environment is rebuilt from the lock (#233, review O-2).
3. **`upgrade` for the lab instance in its present layout,** with the deploy log and the backup before the switch: the checklist of 2026-11-13 as a command (#426, and the first slice of #534). It is useful on its own, and it is where the checks get written.
4. **The artifact,** built by CI on a tag, with `install` and `upgrade` from it and releases side by side. The lab instance moves onto it.
5. **`hardened`:** the installer creates the account and the permissions, `doctor` checks them, and the key is wrapped (#540). The local production site is then built with it.
6. **Sites:** a one-page install and upgrade guide, and a list of which site runs which release.

Steps 2 and 3 change nothing about where anything lives.

## Alternatives considered

- **Keep checking out commits, on every site.** It is what exists. Every site would need git, the repository, access to the private catalog and a package index at install time, and each would resolve its own versions. That is review O-2 repeated at every site.
- **Containers.** They solve the packaging. They do not suit a Windows service that signs people in with Windows accounts and talks to ACS Pro as its own Windows identity.
- **An MSI or a signed installer.** Probably the right end state for many sites. It can wrap the same artifact later without changing anything above.
- **Sites that pull their own updates.** Ruled out for now by §5: a release moves when a person moves it.

## Open questions for the owner

1. **How does a release reach a site, and where are releases kept?** Carried by hand, fetched from a private location, or pushed over a remote-admin link. They cannot sit with this public repository.
2. **Who runs an upgrade at a site:** you, remotely, or someone there following a one-page guide?
3. **The local production site:** a separate PC, or a virtual machine? And does it take over the lab's devices from the lab instance?
4. **Is an unsigned first version acceptable** for the local site and the first real one?
5. **Release names:** by date (`2026.11.23-1`), which is the proposal, or version numbers?
