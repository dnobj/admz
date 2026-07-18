# Session orchestration: the master-agent model

How multiple coding-assistant sessions coordinate on ADMZ. This layers a
*session* model on top of [process.md](process.md) — process.md defines the
two async loops (requirements ↔ implementation) and their interface (the
issue queue); this document defines **who runs each loop** and how work is
delegated, tracked, and validated across sessions.

## The model in one paragraph

The human owner talks to **one persistent Master session**. The Master turns
high-level goals into investigations, plans, implementation issues, and
validation passes, and delegates each to a specialist session. Specialists
do the work; the Master consumes their handoffs, keeps GitHub state truthful,
and surfaces only material decisions to the human. Durable state lives in
the repo and GitHub — never only in chat history.

## Session naming

| Pattern | Role |
|---|---|
| `ADMZ · Master` | Persistent owner-facing orchestration session |
| `ADMZ · Plan · <Topic>` | Investigation → plan doc → docs-only PR → issue |
| `ADMZ · Build · #<Issue>` | Owns one ready issue; isolated worktree; opens the PR |
| `ADMZ · Test · Browser` | Persistent manual/browser validation session |
| `ADMZ · Investigate · <Topic>` | Bounded read-only research or root-cause work |

One implementation issue → one owning Build session. Completed sessions are
renamed with a `(done)` suffix or archived so the sidebar stays readable.

## Roles

**Master** — restates each goal, checks for existing issues/plans/branches/
sessions before creating anything, delegates, reviews handoffs, updates
`status:` labels, and reports goal-level progress to the human. Does not
normally implement application changes.

**Plan** — investigates current state, writes the plan under
`docs/specification/plans/` (or an ADR under `decisions/`), opens a
**documentation-only PR**, and creates/updates the linked issue. Never
implements the runtime change. Per process.md: *merged to `master` is the
readiness signal.*

**Build** — starts from a **fresh worktree** (sibling checkout
`C:\admz\admz-<topic>`, branched from `origin/master`), implements code +
tests + doc-status flips (`📋→✅`) in the same PR, and maintains that PR to
merge. Scope is the issue; unrelated work goes back to the Master as a new
issue.

**Test** — maintains manual test cases, executes them against the dev
server, and records evidence (steps, environment, revision, pass/fail,
screenshots/logs) on the PR. Runs the full regression pass at release-group
boundaries — individually green PRs do not replace it.

**Investigate** — read-only unless explicitly authorized. Reports findings;
does not continue into implementation without reassignment.

## Workflow status labels

Every open issue carries exactly one `status:` label:

| Label | Meaning |
|---|---|
| `status: future` | Deferred, externally gated, or awaiting discussion |
| `status: investigate` | Needs reproduction, research, or verify-then-close |
| `status: planning` | Direction exists; plan or key decisions incomplete |
| `status: ready` | Plan merged + linked; safe to hand to a Build session |
| `status: in progress` | A Build session / PR is actively underway |
| `status: validation` | Implementation complete; awaiting review + testing |
| `status: blocked` | A *named* dependency, decision, or permission gate |

Type labels (`bug`, `enhancement`, `documentation`, `security`, `operations`,
`tech-debt`, `epic`) are orthogonal to status.

**"Ready" is earned, not asserted.** It requires: a merged, linked plan;
scope and non-goals; file-level guidance; acceptance criteria; automated +
manual test requirements; rollout/rollback notes; and no unresolved
product/architecture decisions. A detailed issue body alone does not qualify.

## Worktree and checkout safety

- The main checkout `C:\admz\admz` may be mid-work at any time. **Never**
  branch, reset, or commit there for delegated work — treat uncommitted
  changes as the human's.
- Build sessions use sibling worktrees: `git worktree add ../admz-<topic>
  -b <branch> origin/master` (existing examples: `admz-drift`,
  `admz-events`, `admz-wizard`).
- All PRs target `master` (the only long-lived branch).
- Planning changes and implementation changes ride separate PRs.

## Validation gates

Every implementation PR needs: the automated suite green (run with the
`.venv` interpreter — see `docs/DEV_AUTO_APPROVE.md` for gated end-to-end
runs), a manual test record from the Test session when behavior is
user-visible, and confirmation that the **deployed service and the live
device fleet were not modified** except where the test plan says so.

ADMZ's "production" is the deployed Windows service (`admz`,
Shawl-supervised, data under `C:\ProgramData\admz`) **plus the live Axis
fleet it manages**. Gates that always need explicit human authorization:
service upgrades/restarts outside a test plan, database migrations against
the service's DB, device-mutating operations beyond the confirm-gate demo
recipes, firmware pushes, and factory resets / re-provisioning.

## Cross-session mechanics

The platform exposes session APIs (list, read transcript, rename, message).
The Master uses them to monitor at natural checkpoints — investigation done,
plan drafted, PR opened, checks green, manual testing done, merged — rather
than polling. Where a live reply is needed and the platform can't provide
one, the durable queue is GitHub: issue comments, PR comments, and plan docs.

Every specialist finishes with a structured handoff: what was inspected,
what changed, commands/tests run, branch/worktree, issue/PR links, remaining
blockers, recommended next action. The Master consumes these and keeps the
labels, issues, and this spec's status markers agreeing with reality.
