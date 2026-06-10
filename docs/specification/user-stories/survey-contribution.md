# User stories: survey / contributor mode

An ADMZ install can contribute what it learns about real Axis devices back to
the shared [axis-api-atlas](https://github.com/mrdnlabs/axis-api-atlas) catalog
— as a redacted bundle submitted via GitHub PR — without ever leaking site
secrets. Opt-in, read-only by default, maintainer-reviewed. See
[ADR-0030](../decisions/0030-survey-contributor-mode.md).

## US-SRV-001 — Contribute device knowledge upstream

**As a** catalog contributor running ADMZ against real hardware, **I want to**
submit what my fleet reveals about Axis APIs back to the atlas, **so that** the
shared catalog improves for everyone without me hand-authoring YAML.

**Acceptance criteria:**
1. With survey mode enabled and a PAT configured, `run_survey(submit=True)`
   collects fleet API support, diffs it against the installed atlas, and — if
   there's anything new — opens a GitHub PR on the survey repo
   (`status="submitted"`, with a `pr_url`).
2. If there's nothing new vs the installed atlas, it returns
   `status="no-changes"` and submits nothing.
3. Nothing auto-merges — a maintainer reviews every PR.

**Related requirements:** [survey](../requirements/survey.md).
**Related personas:** [catalog-contributor](../personas/catalog-contributor.md).

## US-SRV-002 — See exactly what would be sent, first

**As a** security-conscious operator, **I want to** preview the exact payload
before anything leaves my site, **so that** I can confirm no secrets or site
identifiers are included.

**Acceptance criteria:**
1. `preview(device_ids?)` returns the redacted snapshot that *would* be
   submitted (models, specs, skipped, errors) and contacts nothing external.
2. Passwords never appear; serials are hashed or kept per the
   `survey_redaction_profile` setting.
3. The secret-scanner gate fails **closed** — a bundle that trips it is never
   submitted.

**Related requirements:** [survey](../requirements/survey.md), [security](../requirements/security.md).
**Related personas:** [security-conscious-operator](../personas/security-conscious-operator.md).

## US-SRV-003 — Off until I turn it on; safe when I do

**As an** operator, **I want** survey mode to do nothing until I opt in, and to
stay read-only by default, **so that** contributing never risks my production
devices.

**Acceptance criteria:**
1. Survey mode is inert until `survey_mode_enabled=true`; a scheduled or
   manual run returns `status="disabled"` otherwise.
2. By default only read-only ops run (Tier 0). Service-affecting probes
   (Tier 1) run only against lab/test-tagged devices, per-op opt-in; dangerous
   ops (Tier 2) are hard-blocked.
3. Configuration lives at `/settings/survey` (enable, PAT via the protected
   flow, repo, redaction profile, validation tier, contributor, schedule),
   with a "run now" action.

**Related requirements:** [survey](../requirements/survey.md).

## US-SRV-004 — Contribute unattended, or work offline

**As an** operator, **I want** surveys to run on a schedule, and to still
produce something useful when I haven't set up a PAT, **so that** contributing
fits into normal operations.

**Acceptance criteria:**
1. A `survey` scheduler job (`job_type="survey"`, ADR-0026) runs unattended on
   `survey_schedule_seconds`, gated by the enabled flag, attributed to the
   `scheduler` principal.
2. With no PAT configured (or submit disabled), a run writes a redacted
   offline `.zip` bundle (`status="offline"`) instead of opening a PR.
3. Per-device failures are absorbed into the run report's `errors`/`skipped`
   rather than aborting the run.

**Related requirements:** [survey](../requirements/survey.md), [scheduling](../requirements/scheduling.md).

## Known limitations

- ⚠️ **Maintainer-in-the-loop by design.** A PAT yields a PR, never a merge;
  there is no path by which a survey auto-publishes to the shared catalog.
- ⚠️ **Tier-1 is deliberately constrained.** Service-affecting probes require
  explicit lab tagging and per-op opt-in so a survey never disrupts a
  production device.
