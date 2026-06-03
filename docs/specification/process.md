# Spec process: requirements as source of truth, issues as work queue

How this specification and the project's GitHub issues work together, so
that **requirements** and **implementation** can run as two independent,
asynchronous loops without drifting apart.

## The split

The spec and GitHub issues answer different questions. Keep them that way.

| | **This spec** (personas / user-stories / requirements / decisions) | **GitHub issues** |
|---|---|---|
| Answers | *What should ADMZ be, and why?* | *What work is in flight to get there?* |
| Lifespan | Durable — versioned with the code, lives forever | Ephemeral — open → closed, then archived |
| Granularity | Behavior + decisions, with **stable IDs** (`FR-SCH-010`, `US-SCHED-007`, `ADR-0026`) | A **shippable increment** (PR-sized), usually spanning several IDs |
| Source of truth for | *Intended behavior* + *build status* | *Work state* — who, when, discussion, PR links |

An issue is **not** a user story. One issue often covers several
requirements and stories at once (e.g. #22 implements `FR-SCH-010..014`
plus the `US-SCHED-*` stories). The mapping is many-to-many, anchored by
IDs. The spec is the *map*; issues are the *trips you're currently
taking across it*.

## The one rule that prevents drift

**Issues reference the spec by ID; they never restate it.** An issue
carries only the *delta* — "implement `FR-SCH-010..014`, here's the
acceptance criteria for *this* slice, here's the scope cut." The durable
what/why stays here in the spec. The moment a requirement is
copy-pasted into an issue body, that copy is the thing that will go
stale.

**The status marker is the single source of truth for "is it built."**
`📋 planned → 🚧 partial → ✅ implemented` lives in the spec, is owned by
the *implementation* loop, and is flipped **in the same PR that does the
work** — the PR that ships `FR-SCH-010` also flips its marker to ✅ and
corrects anything it found inaccurate. (This is the rule that would have
prevented `scheduling.md` from claiming ✅ for a drift scheduler that
never existed — see that file's 2026-05-21 accuracy note.)

## The two loops

The interface between the loops is **the issue queue + "merged to
`master` = ready to build."**

**Loop A — requirements**
1. Draft and refine personas / stories / requirements / ADRs on the
   requirements branch. New material is `📋`.
2. When a slice is *accepted* (not a half-baked draft), **merge it to
   `master`.** That merge is the readiness signal.
3. File a GitHub issue: *"Implement `FR-SCH-010..014` — see ADR-0026."*
   Reference IDs; don't restate.

**Loop B — implementation (may be an autonomous agent)**
1. Pick up an open issue.
2. Read the referenced spec **from `master`** — always a coherent,
   merged document, never a half-edited draft.
3. Implement → open a PR that **flips the doc status `📋→✅` and corrects
   any drift** → close the issue.

Neither loop blocks the other. Loop A can be several features ahead in
`📋` drafts while Loop B grinds through accepted issues. The handshake is
explicit and asynchronous: *accepted requirement → issue → PR that flips
status*.

## Conventions

- **IDs are the join key.** The issue cites `FR-*` / `US-*` / `ADR-NNNN`;
  the PR cites the issue; the commit cites the issue. Any line of code
  traces back: `commit → PR → issue → spec ID → ADR`.
- **"Merged to `master`" = ready.** Don't file implementation issues
  against `📋` drafts that live only on the requirements branch — the
  implementer should always read a merged, coherent spec.
- **Status lives in the spec, not GitHub.** GitHub open/closed = *work*
  state; `📋/🚧/✅` = *build* state. Don't try to make GitHub the spec.
- **Every implementing PR updates status and corrects drift.**
  Non-negotiable — it's the anti-drift mechanism. "Where the spec and
  the code disagree, the spec wins, but the gap is flagged, not papered
  over" (see [README](README.md)).
- **One issue = one shippable increment.** Slice to PR size; reference
  the (possibly several) IDs it satisfies.

## Checklist for the implementing loop

Per issue:

1. Read the issue, then read every spec ID it references (from `master`).
2. Implement the increment.
3. Add/adjust tests.
4. In the same PR: flip the referenced `📋/🚧` markers to `✅`, and fix
   any inaccuracy you discover in those docs.
5. Reference the issue number in the PR and in commits.
6. Merge → the issue closes.

## How this maps to this repo

- The spec is drafted on a **requirements branch**, worktree-isolated
  from the code, then merged to `master` when accepted. Implementation
  happens against `master`. The two run in separate sessions/worktrees
  so they don't step on each other (shared `.git`, separate working
  trees and indexes).
- Issues live on `github.com/dnobj/admz`. Worked examples:
  [#22](https://github.com/dnobj/admz/issues/22) (unified scheduler ↔
  `FR-SCH-010..014`, `ADR-0026`) and
  [#23](https://github.com/dnobj/admz/issues/23) (drift-alert history ↔
  `FR-DRF-010`).
