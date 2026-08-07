---
name: tick
description: Run one Master tick for ADMZ per the code-teem playbook pinned in CLAUDE.md — orient from the ledger (HANDOFF.md, STATUS.md, the question store), run the stall check over TICKS.log, reconcile answers and merge clean PRs, work the top ready item serially, dispatch readers non-blocking, then rewrite STATUS.md and HANDOFF.md and append a TICKS.log line. Context-free by contract: trust only files and external state, never transcript memory. Use when the user types /tick, or asks to run a Master tick, resume the loop, or pick up ADMZ work from the ledger.
---

# /tick — one Master tick

_The loop contract from [PLAYBOOK.md](https://github.com/pettheory/code-teem/blob/v0.13.1/PLAYBOOK.md) ("Running the master as a loop") as an installable skill. Deliberately **tool- and engine-neutral**: capabilities are named ("the question store", "the ledger"), and everything machine-specific — which tools reach the store, which identity reaches which remote — comes from the project's agent file, per its control-plane adapter block ([../conventions/agent-file.md](https://github.com/pettheory/code-teem/blob/v0.13.1/conventions/agent-file.md)). The same skill drops unchanged into any project on any engine; only the agent file varies._

_Install per the engine's skill mechanism, fill `ADMZ`, and drive it with the engine's loop facility (fixed interval recommended) or external kicks — the contract is identical either way._

---

Run one Master tick for `ADMZ`, per the code-teem playbook at the tag pinned in this repository's agent file. The tick is context-free: orient from files, trust only external state, and never rely on transcript memory.

## 1 · Orient — files only

Agent file → `.claude/HANDOFF.md` (resume from the **phase** recorded there) → `.claude/STATUS.md` → the question store (via the adapter block; if unreachable, hold questions in the handoff, say so in the status brief, and continue) → spot-check actual git/GitHub state. The handoff is pointers; git and GitHub are truth.

**Stall check** — read the last 5 lines of `.claude/TICKS.log` and test:

| Trigger | Threshold |
|---|---|
| Same item, anchor unmoved | worked ≥3 consecutive ticks with no new commits |
| Next step unchanged | the handoff's next-step text survives ≥2 rewrites verbatim |
| Ping-pong | alternating between two items, neither shipping |
| Attempts without outcomes | ≥5 `progressed` ticks with nothing reaching `shipped` |

On any trigger: **do not re-attempt.** Park the item with an honest tried-and-failed, then either raise the question the retries were avoiding, or dispatch an independent tick-review reader — the loop does not grade its own homework. A blocker string repeated across ≥3 tick lines escalates to blocker severity in the question store.

## 2 · Reconcile

Apply the owner's answers and record them durably (issues, labels, defaults). Fold in completed reader results — including findings from audits and any periodic loops (their cadence is not this tick's business; their findings are).

Merge **only** PRs whose reviews returned clean **and** whose in-PR obligations rode along: tests green · the docs this change contradicts fixed in the same PR · timeline row present.

**After each merge, fire the ripple audits**: look up the merged PR's touched paths in the project's path→audit matrix (it lives in the agent file) and dispatch the implicated audits against merged mainline — they propose, never merge. **No matrix in the agent file?** Use the default table in [../patterns/triggers-and-lanes.md](https://github.com/pettheory/code-teem/blob/v0.13.1/patterns/triggers-and-lanes.md) for this tick, and raise a question proposing a project-specific one.

At a release-group boundary, dispatch the regression run and prepare the owner's focused test script.

## 3 · Work — serial, one item

Pick or continue the top ready item, in its worktree. **Done means:** tests written and passing · **the in-PR doc obligations met** — every doc this change contradicts is fixed in the same PR: spec status markers, decision records, inline docs, and **the agent file whenever a command, constraint, or adapter binding changed** · timeline row in the shipping PR · reviews dispatched. The PR that ships the behavior fixes the docs that describe it — drift the author could see never survives a merge. If the item outlasts the tick, park cleanly: commit to the anchor, record done-so-far / tried-and-failed / next-step. If nothing is ready, skip to externalize — an idle tick is cheap and correct.

## 4 · Dispatch — non-blocking, never await

Reviews for anything opened. New owner questions to the store, each with a proposed answer where one is defensible. Completion signals land at the next tick's reconcile.

Ripple audits were already fired at reconcile, per merge — drift detection is merge-triggered, not scheduled, so a context-free tick never has to answer "when was this last run?". Audits that are genuinely periodic (coverage, architecture review) run as **their own scheduled loops** per the loop catalog; this tick consumes their findings and never owns their cadence.

## 5 · Externalize, then end the turn

Rewrite `STATUS.md` (waiting-on-you generated from the store) and `HANDOFF.md` (phase · item · anchor · done-so-far · tried-and-failed · next-step). Append one line to `.claude/TICKS.log`:

```
<ISO time> | <phase reached> | <item or none> | <anchor sha or -> | shipped|progressed|parked|idle|blocked:<why> | <cost if known>
```

Then end the turn. Never park the loop itself.
