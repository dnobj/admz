# Session orchestration: the master-agent model

How multiple coding-assistant sessions coordinate on ADMZ. This layers a
*session* model on top of [process.md](process.md) — process.md defines the
two async loops (requirements ↔ implementation) and their interface (the
issue queue); this document defines **who runs each loop** and how work is
delegated, tracked, and validated across sessions.

## The model in one paragraph

The human owner talks to **one persistent Master session**. The Master turns
high-level goals into investigations, plans, implementation issues, and
validation passes. **It implements them itself, serially.** What it delegates
is the *read* side — research, review, audit — which touches no shared mutable
state and never blocks the next piece of work. The Master consumes those
findings, keeps GitHub state truthful, and surfaces only material decisions to
the human. Durable state lives in the repo and GitHub — never only in chat
history.

**Writes serialize; reads parallelize.** This is a deliberate revision of the
model this document described until 2026-08-06, in which every ready issue was
handed to its own Build session — see [Why implementation is serial](#why-implementation-is-serial).

## Session naming

| Pattern | Role |
|---|---|
| `ADMZ · Master` | Persistent owner-facing orchestration session. **Implements.** |
| `ADMZ · Plan · <Topic>` | Investigation → plan doc → docs-only PR → issue |
| `ADMZ · Investigate · <Topic>` | Bounded read-only research or root-cause work |
| `ADMZ · Decide · <Topic>` | One cluster of open questions → decision briefing |
| `ADMZ · Converse · <Topic>` | Pre-briefed back-and-forth with the owner on a queue item |
| `ADMZ · Review · <PR/Topic>` | Adversarial review of a diff the Master wrote |
| `ADMZ · Test · Browser` | Persistent manual/browser validation session |
| `ADMZ · Build · #<Issue>` | **Exception only** — see below |

Completed sessions are renamed with a `(done)` suffix or archived so the
sidebar stays readable.

**A `Build` session is now the exception, not the default.** Use one only when
the work fails the *continuity test* — it needs a large sustained context the
Master should not carry — and then one issue, one owning session, one worktree.
Parallel implementation is reserved for **hard resource boundaries**: a separate
repository with its own version stream and zero file overlap, which is to say
effectively another project. The `axis-api-atlas` catalog qualifies; two issues
in this repo do not.

## Roles

**Master** — restates each goal, checks for existing issues/plans/branches/
sessions before creating anything, **implements ready issues serially in an
isolated worktree per PR**, dispatches read-side work, reviews findings,
updates `status:` labels, and reports goal-level progress to the human.

**Plan** — investigates current state, writes the plan under
`docs/specification/plans/` (or an ADR under `decisions/`), opens a
**documentation-only PR**, and creates/updates the linked issue. Never
implements the runtime change. Per process.md: *merged to `master` is the
readiness signal.*

**Build** — the exception path. Starts from a **fresh worktree** (sibling
checkout `C:\admz\admz-<topic>`, branched from `origin/master`), implements
code + tests + doc-status flips (`📋→✅`) in the same PR, and maintains that PR
to merge. Scope is the issue; unrelated work goes back to the Master as a new
issue. Only spawned when the work fails the continuity test.

**Decide** — owns one coherent cluster of open product or architecture
questions, gathers its own evidence, returns a briefing with options,
tradeoffs, and a recommendation. Does not own priorities or the backlog.

**Converse** — holds a real back-and-forth with the owner on a queue item that
needs conversation rather than a one-word answer. Pre-briefed by the Master
with the question, its briefing, and the status brief, so the owner never
opens a session cold. Returns answers to the Master; never writes the ledger
itself.

**Review** — adversarial read of a diff the Master wrote. This is the fan-out
that pays: several reviewers on one PR cost nothing but tokens, block nothing,
and have repeatedly found what the author could not.

**Test** — maintains manual test cases, executes them against the dev
server, and records evidence (steps, environment, revision, pass/fail,
screenshots/logs) on the PR. Runs the full regression pass at release-group
boundaries — individually green PRs do not replace it.

**Investigate** — read-only unless explicitly authorized. Reports findings;
does not continue into implementation without reassignment.

## Why implementation is serial

Recorded because a convention without its reasoning gets reverted by the next
person who thinks parallel writers sound faster.

**The claim being retired:** that handing each ready issue to its own Build
session increases throughput.

**What actually happened on 2026-08-05**, running five concurrent Build
sessions against this repo for a day — 43 PRs merged, 31 issues closed:

- **Throughput was not gained.** Every PR still waited 10–13 minutes on the
  Windows CI leg, and merged one at a time. The serial sections — merge order,
  CI, the owner's review — stayed serial, so concurrent writing only moved the
  queue, it did not shorten it.
- **Coordination cost was real and recurring.** Holding one branch off
  `redact.py` while another was open; sequencing #314 before #313; five
  worktrees to track. That is Master effort spent on contention that would not
  exist with one writer.
- **Three failures were pure coordination failures.** Merging with
  `--delete-branch` closed a *stacked* PR whose base it removed (#317), costing
  a rebase-off-squash — precisely the "work merged into an abandoned base"
  failure the upstream playbook names. A dispatch was rejected by the
  bridge's fork-guard and never noticed, because the tool returned
  `status: running` at call time. And two sessions died mid-task and were
  reported as "still building" for hours, because progress was inferred from a
  file count rather than from liveness.
- **Every one of the highest-value outcomes came from the read side.** The
  best results of that day were workers *refuting the Master's premises*: that
  a proposed ordering fix was unbuildable; that an issue's own suggested fix
  was hollow; that the canonical `is_sensitive_key` predicate did not
  recognise `pwd`, the wire key for a device password, so device passwords
  were reaching the audit log unmasked. None of those required a writer.

**The conclusion:** the speed lever is fewer approval gates on routine
reversible work, not more concurrent writers. The fan-out that pays is
review, research, and audit — none of which touch shared mutable state, and
none of which block the next piece of work.

This matches [code-teem v0.11.0](https://github.com/pettheory/code-teem),
which revised its own step 6 from *"Hand off implementation"* to *"Implement"*
after the same feedback from this project.

## Workflow status labels

Every open issue carries exactly one `status:` label:

| Label | Meaning |
|---|---|
| `status: future` | Deferred, externally gated, or awaiting discussion |
| `status: investigate` | Needs reproduction, research, or verify-then-close |
| `status: planning` | Direction exists; plan or key decisions incomplete |
| `status: ready` | Plan merged + linked; safe to implement |
| `status: in progress` | Being implemented; a branch or PR is underway |
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
- Implementation uses sibling worktrees: `git worktree add ../admz-<topic>
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
