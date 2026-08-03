# CI

`ci.yml` is the only workflow. It runs on every pull request, on pushes to
`master`, and on demand via **Actions → CI → Run workflow**.

| Job | Runs on | What it proves | Blocking |
|---|---|---|---|
| `preflight` | ubuntu | The `axis-api-atlas` deploy key exists | yes |
| `quick` | ubuntu | Every test module and all of `admz/` imports cleanly (`pytest --collect-only`) | yes |
| `suite (ubuntu-latest)` | ubuntu | Full suite | yes |
| `suite (windows-latest)` | windows | Full suite on the deployment platform | yes |

`quick` gates `suite`, so a syntax error or bad import costs ~2 minutes instead
of two full 15-minute runs.

---

## One-time owner setup: the `axis-api-atlas` deploy key

**CI cannot pass until this is done.** Until then `preflight` fails with an
explicit message — that is the intended behaviour, not a bug to work around.

ADMZ depends on `axis-api-atlas`, which lives in the **private** repository
`mrdnlabs/axis-api-atlas` — a different GitHub account from this repo's
`dnobj`. `requirements.txt` installs it by direct git reference, so CI needs
read access to that repo.

A **deploy key** is used rather than a personal access token because it is
scoped to exactly one repository, is read-only, carries no user account's
wider permissions, does not expire, and can be revoked without affecting
anything else.

### Step 1 — generate the key pair

On your own machine, not in CI. `admz-ci` is just a label that will appear in
GitHub's UI; it is not a password.

```bash
ssh-keygen -t ed25519 -C "admz-ci deploy key" -f ~/.ssh/admz_ci_atlas -N ""
```

This writes two files:

| File | Half | Where it goes |
|---|---|---|
| `~/.ssh/admz_ci_atlas.pub` | **public** | the `mrdnlabs/axis-api-atlas` repo |
| `~/.ssh/admz_ci_atlas` | **private** | the `dnobj/admz` repo secret |

### Step 2 — register the public half on the atlas repo

As the **`mrdnlabs`** account:

`https://github.com/mrdnlabs/axis-api-atlas/settings/keys` →
**Add deploy key**

* **Title:** `admz CI (read-only)`
* **Key:** the entire contents of `~/.ssh/admz_ci_atlas.pub`
* **Allow write access:** **leave unchecked.** CI only ever reads.

Or from the CLI, without switching your global `gh` account:

```bash
GH_TOKEN=$(gh auth token --user mrdnlabs) gh repo deploy-key add \
  ~/.ssh/admz_ci_atlas.pub \
  --repo mrdnlabs/axis-api-atlas \
  --title "admz CI (read-only)"
```

### Step 3 — store the private half as a secret on this repo

As the **`dnobj`** account:

`https://github.com/dnobj/admz/settings/secrets/actions` →
**New repository secret**

* **Name:** `AXIS_API_ATLAS_DEPLOY_KEY` — exactly this; the workflow reads it by name
* **Value:** the entire contents of `~/.ssh/admz_ci_atlas` (the file **without**
  the `.pub` extension), including the `-----BEGIN OPENSSH PRIVATE KEY-----`
  and `-----END OPENSSH PRIVATE KEY-----` lines and the trailing newline

Or:

```bash
GH_TOKEN=$(gh auth token --user dnobj) gh secret set AXIS_API_ATLAS_DEPLOY_KEY \
  --repo dnobj/admz < ~/.ssh/admz_ci_atlas
```

### Step 4 — verify

```bash
# The key works:
GIT_SSH_COMMAND="ssh -i ~/.ssh/admz_ci_atlas -o IdentitiesOnly=yes" \
  git ls-remote ssh://git@github.com/mrdnlabs/axis-api-atlas.git HEAD
# -> prints a commit SHA. "Permission denied (publickey)" means step 2 did not take.

# The secret is registered (prints the name and update time, never the value):
GH_TOKEN=$(gh auth token --user dnobj) gh secret list --repo dnobj/admz
```

Then re-run the workflow: **Actions → CI → Run workflow**. `preflight` should
pass, and the `setup-admz` action's *"Assert axis-api-atlas provenance"* step
should print the git URL and resolved commit.

### Step 5 — delete your local copy of the private half

```bash
rm ~/.ssh/admz_ci_atlas ~/.ssh/admz_ci_atlas.pub
```

GitHub stores the secret; you do not need a second copy. To rotate, repeat
steps 1–4 and delete the old deploy key from the atlas repo.

---

## Why this fails closed

`requirements.txt` used to declare a bare `axis-api-atlas>=0.1.0`. That name is
**unregistered on PyPI**, so a clean `pip install` resolved it against a public
index where anyone could claim it — arbitrary code execution inside the venv
that the `admz` Windows service runs as LocalSystem. That is issue
[#179](https://github.com/dnobj/admz/issues/179).

Three independent latches now prevent CI from reintroducing it:

1. **`requirements.txt` uses a PEP 508 direct reference.** A direct reference
   never consults an index. With no credential, the git clone fails; there is
   nothing to silently fall back to.
2. **`preflight` requires the secret** before any install runs.
3. **`.github/scripts/assert_atlas_provenance.py`** inspects the *installed*
   package's PEP 610 `direct_url.json` after install. Index installs have no
   such file, so if the requirement ever regresses to a bare name — or a cached
   wheel sneaks in — the job fails with a message naming #179.

The third latch is the important one: latches 1 and 2 check intent, latch 3
checks what actually landed on disk.

**If CI fails with a missing-credential error, the fix is to add the
credential.** Relaxing `requirements.txt` back to a bare name would make CI
green by recreating the vulnerability.

---

## Deliberate non-goals

* **No lint job.** `master` is not currently conformant: `black --check` would
  reformat **350 of 409 files** and `flake8` reports **4294 violations** (4029
  of them `E501` against the default 79-column limit, with no `.flake8` or
  `setup.cfg` in the repo to set a project width). A blocking lint job would
  land CI red on day one; a permanently-yellow non-blocking one teaches people
  to ignore CI just as effectively. Adopting lint needs a line-length decision
  and a 350-file reformat commit sequenced against in-flight branches — its own
  PR. Tracked separately.
* **No `pytest-xdist`.** `tests/conftest.py:1-14` documents order-dependent
  shared singletons that already broke once when collection order shifted, and
  there are 17 further singletons that connect and run DDL at *import*.
  Parallelising this suite is the same project as issue #184.
* **No `pytest-timeout`.** A hung test currently runs to the job timeout
  (40 min). Worth adding, but the per-test cap needs tuning against real CI
  timings — a follow-up, not a guess made here.
* **No custom pytest markers.** `pytest.ini` sets `--strict-markers` with an
  empty `markers` list; every marker in use today comes from a plugin.
  Introducing one without registering it in `pytest.ini` errors the entire run.
* **No coverage.** `pytest.ini`'s `addopts` enables `--cov=admz` plus a
  `term-missing` and an HTML report. Useful locally, pure cost here, so CI
  passes `--no-cov`.
