# Requirements: survey / contributor mode

An opt-in mode that lets an ADMZ install contribute what it learns about real
Axis devices back to the [axis-api-atlas](https://github.com/mrdnlabs/axis-api-atlas)
catalog — via a redacted bundle submitted as a GitHub PR (or written offline).
Distributed, read-only-by-default API discovery that improves the shared
catalog without ever leaking site secrets. See
[ADR-0030](../decisions/0030-survey-contributor-mode.md).

## Status legend
✅ implemented · 🚧 partial · ⚠️ known limitation · 📋 planned

## Functional requirements

### FR-SRV-001 — Off by default, explicit opt-in ✅
Survey mode does nothing until an operator enables it: the
`survey_mode_enabled` fleet setting must be truthy (`is_enabled()`,
`admz/survey/secrets.py`). `run_survey(respect_enabled=True)` returns
`status="disabled"` otherwise. Nothing is collected, bundled, or submitted
without that flag.

### FR-SRV-002 — Read-only discovery by default; tiered execution ✅
The collector surveys the fleet by reading API support and op specs. The
validation tier (`survey_validation_tier`, default `0`) bounds what may be
*executed* during a survey (`admz/survey/validate.py`):
- **Tier 0** — read-only ops only (GET / json-rpc *query*). Safe everywhere.
- **Tier 1** — service-affecting ops, **lab/test-tagged devices only**,
  per-op opt-in.
- **Tier 2** — dangerous ops are **never** executed; hard-blocked.

### FR-SRV-003 — Credentials and secrets never leave the site ✅
The submitted payload is the **redacted** snapshot (`redacted_snapshot`),
built through the survey redaction profile (`survey_redaction_profile`:
`hash-serial` | `keep-serial`). Device passwords, serials (when hashed), and
other site identifiers are stripped/hashed before anything is bundled. A
secret-scanner gate (`admz/survey/secrets.py` + the bundle validator) fails
**closed** — a bundle that trips the scanner is not submitted.

### FR-SRV-004 — Preview sends nothing ✅
`preview(device_ids?)` (`admz/survey/runner.py`) returns exactly the redacted
payload that *would* be submitted — models, included specs, skipped/errors —
without contacting GitHub or writing a bundle. Operators inspect what they'd
contribute before turning on submission.

### FR-SRV-005 — Submit as a GitHub PR, else write an offline bundle ✅
`run_survey(submit=True)`:
1. Collects → diffs against the installed atlas; if nothing is new,
   returns `status="no-changes"`.
2. Assembles a contribution bundle (schema-validated).
3. If a PAT is configured (`survey_github_pat`, stored **encrypted** with the
   same Fernet key as device passwords) → opens a PR on `survey_repo` via
   `GitHubSubmitter` (branch `contrib/<contributor>/<bundle_id>`) and returns
   `status="submitted"` with the `pr_url`.
4. Otherwise → writes a redacted offline `.zip` and returns
   `status="offline"`. **Nothing auto-merges**; a maintainer reviews every PR.

### FR-SRV-006 — Never raises per-device; returns a report ✅
`run_survey` returns a `SurveyRunReport` (`status`, `bundle_id`, `pr_url` /
`offline_path`, `models`, `skipped`, `errors`, `message`) and absorbs
per-device failures into `errors`/`skipped` rather than aborting the run.

### FR-SRV-007 — Web UI for config + on-demand run ✅
`/settings/survey` (`admz/api/routes/survey.py`) exposes enable/disable, the
PAT (entered via the protected-setting flow, never echoed), repo, redaction
profile, validation tier, contributor handle, and schedule; plus a
"run a survey now" action (read-only discovery; PRs only if a PAT is set,
else an offline bundle).

### FR-SRV-008 — Scheduled, unattended runs ✅
Survey rides the unified job scheduler as `job_type="survey"`
(`admz/snapshot/scheduler.py`, ADR-0026). The handler is gated by
`survey_mode_enabled` and attributed to the `scheduler` principal — no LLM, no
MCP subprocess. Interval comes from `survey_schedule_seconds`.

## Non-functional requirements

### NFR-SRV-001 — Single Fernet key for all secrets ✅
The survey PAT is encrypted at rest with the same `~/.admz/admz.key` Fernet
key used for device passwords — one key to back up, one to protect
(ADR-0010).

### NFR-SRV-002 — Catalog edits happen in the atlas, not ADMZ ✅
Survey contributes *to* axis-api-atlas; it does not write the local catalog
(which is the installed package). The contribution path is bundle → PR →
maintainer review → atlas release → `pip` upgrade.

## Known limitations

### KL-SRV-001 — Tier-1 needs lab tagging + per-op opt-in ⚠️
Service-affecting probes only run against devices explicitly tagged lab/test,
at tier 1, with per-op opt-in. This is deliberately conservative — a survey
must never disrupt a production device.

### KL-SRV-002 — Submission needs a maintainer in the loop ✅(by design)
A PAT yields a PR, not a merge. Bundles that fail the secret scanner are not
submitted at all. There is no path by which a survey auto-publishes to the
shared catalog.

## References

- ADRs: [0030](../decisions/0030-survey-contributor-mode.md), [0029](../decisions/0029-axis-api-atlas-as-maintained-reusable-asset.md), [0010](../decisions/0010-fernet-encryption.md), [0009](../decisions/0009-oob-credential-capture.md), [0026](../decisions/0026-unified-job-scheduler.md)
- Personas: [catalog-contributor](../personas/catalog-contributor.md)
- User stories: [survey-contribution](../user-stories/survey-contribution.md)
- Cross-cutting: [security.md](security.md)
- Code: `admz/survey/` (`runner.py`, `collector.py`, `validate.py`, `secrets.py`, `bundle.py`, `diff.py`, `github.py`, `redact.py`), `admz/api/routes/survey.py`
- Design (atlas repo): `docs/design/survey-contributor-mode.md`
