# Persona: Site installer

## Profile

**Who:** The person standing at a machine at a site, putting ADMZ on it or bringing it up to
date. Often an integrator or a technician. Sometimes the owner, at their own local site.

**Technical level:** Comfortable with Windows and with running a command as an administrator.
Not a developer. Does not have git, Python or the source, and should not need them.

**Scale:** One machine at a time. A site machine is frequently a recorder or a small server that
is already doing another job, and may have no internet access.

**Frequency of use:** Once to install. Then a few times a year to upgrade.

## Goals

- **Install with one command,** from one file, with nothing else to fetch.
- **Upgrade without fear.** If the new release does not come up, be back on the old one without
  having to work out how.
- **Leave the machine safe.** The installer should apply the protections, not a checklist the
  installer has to remember.
- **Be able to say what is installed,** when asked by the owner on the phone.

## Pains today (without this)

- "It needs a checkout." An install starts with git, Python and a script that is not in the
  repository.
- "It needs the internet, and access I don't have." Packages come from an index and the catalog
  from a private repository.
- "I don't know what version this is." The version has read the same for months, and the build is
  a commit id.
- "The update is twelve steps." The only person who can run them is the one who wrote them down.

## Use cases (links to user stories)

- [Install and upgrade](../user-stories/install-and-upgrade.md): install, upgrade and roll back,
  and check a host.
