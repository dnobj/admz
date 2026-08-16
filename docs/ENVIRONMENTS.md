# Environments

What exists, where it lives, and which one you are allowed to touch.

Distinct from [`ENVIRONMENT.md`](ENVIRONMENT.md), which documents the `ADMZ_*` *variables*.
That page is good and complete. This one answers a different question — *what is actually
running on this machine?* — and it exists because the answer has been written down wrongly
four times.

## Why this page carries a checker

Every environment fact is **observable**. A port is listening or it is not; a checkout is at
a commit; a venv exists and holds versions. Facts that are observable and get *asserted*
instead will eventually be asserted wrongly, and the gap between the error and its discovery
is unbounded:

| What a doc said | What was true | Cost |
|---|---|---|
| the dev/prod split "is not live" | it had been live for a day, contradicting a line in the same file | every session read it first (#214) |
| `:4243` is staging with `ADMZ_HOME=C:\ProgramData\admz-staging` | the launch config on `:4243` sets **no** `ADMZ_HOME`, so it gets production's | a second instance came up on production data (#399) |
| staging "borrows the dev venv" | true, and the reason it cannot start — the dev venv moved to `mcp` 2.x | "verify it on staging" was an unfollowable instruction for weeks (#238) |
| staging is "~94 commits behind" | 122 by the time anyone re-read it | the number was stale the week it was written |

None of those were carelessness. Three were written by someone who had just checked the thing
they then described, and the world moved underneath the sentence.

So the table below is not prose. It is **parsed** by
[`tools/environments.py`](../tools/environments.py), which reports observed reality beside
it and exits non-zero when they disagree. Run it whenever you are about to touch anything:

```
python tools/environments.py
```

Read-only. It opens no sockets and starts nothing — port state comes from `netstat`, not
from connecting.

**It is a machine-local tool, not a CI job**, and the distinction matters. On a CI runner
none of these paths exist, so it would report every environment missing and exit non-zero
for reasons that say nothing about the change under test. The CI-safe half is
[`tests/test_environments_doc.py`](../tests/test_environments_doc.py), which parses the
block and asserts every claim in it is one the checker knows how to observe — so an
unverifiable claim cannot be added to this page silently. That test observes nothing and
does not care what machine it runs on.

### It also answers "which atlas is this running?" (#424)

`axis-api-atlas` reports `__version__ = "0.1.0"` forever, which is why #232 pinned it by SHA
instead. But a **directory install records no commit**: PEP 610 writes a `dir_info` block, and
`.github/scripts/assert_atlas_provenance.py` skips its revision check for that shape — a
deliberate exemption so developer laptops keep working, which silently covered **production
too**, because ADR-0054's non-editable install is also a directory install.

That blind spot had a cost. Production ran an atlas in which `pwdgrp.cgi:add-user`,
`ssh:addUser` and `ssh:modifyUser` were `risk_level: normal` — which the confirmation gate maps
to `none` — so creating a root-group admin account on a camera ran inline with no human, while
*deleting* one required approval. It stayed live for six days after the fix merged, and nothing
on the machine could have said so.

The checker now compares **content** rather than trusting metadata: it digests the installed
data tree and the tree at `ATLAS_SHA` (read straight from the object store with `git archive`,
so no checkout is disturbed).

**Each environment declares the install shape it should have** — the `atlas:` key below, one of
`copy`, `editable` or `none` — and the checker compares observed against declared. That
direction matters. The first version of this asked the *installed package* what kind it was and
only checked it if the answer was `copy`, so every way an install could deviate — rebuilt
editable, pinned at a stale commit, atlas missing altogether — quietly exempted itself. A gate
keyed on the thing it is inspecting is not a gate.

| Observation | Fails the run? |
|---|---|
| installed from a package index | **yes** — #179, and this one is checked even for `atlas: none` |
| observed kind ≠ declared kind (either direction) | **yes** — that is the ADR-0054 violation |
| `content DOES NOT MATCH pin <sha>`, declared `copy` | **yes** |
| installed tree missing, empty or unreadable, declared `copy` | **yes** — for a deployment that is as alarming as being wrong |
| `content DOES NOT MATCH pin <sha>`, declared `editable` | no — ordinary atlas development |
| `BROKEN: …` — the check itself cannot run | **yes**, for either kind |
| `cannot verify` — no atlas repo, or a pin this clone has not fetched | no — a reason to look, not to block |

Comparing content beats recording a commit at install time: a stamp says what an installer
*intended*, while this observes what is actually on disk, and cannot be fooled by a source
directory that has moved on since. Line endings are flattened before hashing, because a git blob
holds LF and a Windows checkout writes CRLF — without that every file reads as different on this
machine, and a check that cries wolf is worse than no check.

`cannot verify` names its actual cause, because the earlier single message sent an operator
after a repo that was present while the real fix — fetch the clone, the pin moved — went
unmentioned. `BROKEN` is separated from it for the same reason: an atlas layout change would
otherwise disable this check permanently while blaming a missing repo.

The atlas repo is taken from `ADMZ_ATLAS_REPO`, otherwise the sibling directory beside this
repo. An override that is set but is **not** a git repo is reported as its own cause rather
than silently falling back to the sibling — an operator who set it deliberately would
otherwise be verifying against a repo they did not choose, with nothing on screen to say so.

`atlas: none` means there is no atlas in that environment to compare, and the content check
is skipped for it. The index check is not: #179 is about someone else's code running inside
the venv the service runs as LocalSystem, and declaring no atlas is not a reason to permit
that. A test keeps `atlas: none` and `venv: null` from drifting apart, since the checker
itself cannot notice the combination.

## The declaration

<!-- tools/environments.py parses this block. Keep it valid YAML. -->

```yaml
environments:
  production:
    port: 4242
    admz_home: 'C:\ProgramData\admz'
    checkout: 'C:\admz\admz-prod'
    venv: 'C:\admz\admz-prod\.venv'
    atlas: copy
    expect_listening: true
    touch: 'never without explicit authorization'
    note: >-
      Its own clone, not a worktree, checked out detached at a pinned commit with a
      non-editable atlas (ADR-0054). Runs as the Shawl-supervised service `admz`.
  staging:
    port: 4243
    admz_home: 'C:\ProgramData\admz-staging'
    checkout: 'C:\admz\admz-staging-code'
    venv: null
    atlas: none
    expect_listening: false
    touch: 'not runnable'
    note: >-
      Cannot start: no venv of its own, and its code uses the mcp 1.x decorator API while
      the dev venv it is documented to borrow has 2.x (#238). Retire-or-rebuild is an open
      owner decision.
  dev:
    port: null
    admz_home: null
    checkout: 'C:\admz\admz'
    venv: 'C:\admz\admz\.venv'
    atlas: editable
    expect_listening: false
    touch: 'freely, but it is the human working tree — never commit there'
    note: >-
      Not a running service. Stand one up on demand with an isolated ADMZ_HOME; verified
      to boot clean on master. Its HEAD is the human's and is routinely behind
      origin/master, which is normal and not drift.
```

## Standing up a dev instance

There is no dev service. Start one **only** with an isolated `ADMZ_HOME`, because an unset
one resolves to `C:\ProgramData\admz` — production. An absent variable is more dangerous
than a wrong one: a wrong path is visible in the config, an absent one is not.

The verified-safe shape binds no port at all — it drives the ASGI app in-process, which
still exercises the lifespan (schedulers, monitors, stores, migrations):

```python
os.environ["ADMZ_HOME"] = "<throwaway dir>"
os.environ["ADMZ_AUTO_PUSH"] = "false"      # default is ON; unset counts as ON
with TestClient(app) as client:             # the context manager runs the lifespan
    client.get("/api/health")
```

If you need a real listener, add `--port` on something that is neither 4242 nor 4243, and
**read `C:\admz\.claude\launch.json` first** — see below.

## Launch configs are part of the environment

The checker audits every `launch.json` it can find and reports the `ADMZ_HOME` each one
would actually resolve to. This is not incidental: #399 is a launch config named `admz`, on
staging's port, with no `ADMZ_HOME` — so anything that starts it gets a second instance on
**production's** database with authentication disabled.

A config's danger is in what it **omits**, which is why the checker resolves the effective
value rather than printing the file.
