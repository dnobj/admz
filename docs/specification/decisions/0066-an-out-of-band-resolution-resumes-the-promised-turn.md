# ADR-0066 — A resolved out-of-band step resumes the turn it was waiting on: the browser fires one gated continuation, as the operator, once

**Status:** Accepted — 2026-09-14 · **Shipped:** 2026-09-14 (#482 plan, #483 code) — #444 closed · **Amended:** 2026-09-23 (a note that lands while a reply is running is still answered)
**Closes when shipped:** #444
**Relates to:** [ADR-0009](0009-oob-credential-capture.md) (the out-of-band capture this resumes after) · [ADR-0034](0034-uniform-widget-gating.md) (the one gate every follow-on write still hits) · [ADR-0038](0038-chat-conversation-history.md) (the conversation the note lands in) · [ADR-0062](0062-approve-an-envelope-not-a-step-list.md) / #440 (what an approval authorises when work continues) · [ADR-0064](0064-a-device-admz-cannot-authenticate-to-is-never-online.md) / #443 (an unwatched state, one layer up) · #438 (the chat never plans — why this job was a sequence of one-off gates in the first place) · FR-CB-004/005/006, and the new FR-CB-016

_Plan-first per `process.md`: this document merges before any code. File:line references are against master `eb57892`._

## Context

**It has happened twice, and the second time was worse.**

The first (2026-08-17) cost a nudge. An operator completed a credential capture and had to type *"any luck?"*:

```
20:01 [model] "A secure credential capture card has appeared... Once submitted,
               I will capture its baseline configuration."
20:01 [event] [console] The user submitted credentials for device B8A44F832415
               via the secure capture form; they were stored server-side.
20:02 [user]  any luck?
20:02 [model] ...successfully captured and committed as its blessed baseline
               (11 facets captured).
```

The second (2026-09-14) left a **dangerous operation half-done**. The operator asked to upgrade an AXIS C8110's firmware. The model reported the path (`12.9.57 → 12.11.77`), raised a `dangerous` approval card to import the binary, and said:

> *"Once approved, I will verify the file and proceed with initiating the upgrade."*

The operator approved. The import ran — `C8110_12_11_77.bin` landed in the cache at 12:00:48 UTC. Then nothing. There are **zero** `firmwaremanagement.cgi:upgrade` rows in the entire production audit history; the camera is still on 12.9.57 with an inert staged binary, and the conversation's last row is the approval event note. Nobody was prodded this time, so nobody noticed until the operator went looking days later.

In both cases the model *said* it would continue, the out-of-band step resolved, and the work it would have resumed took **one turn**.

### What already works

The passive half is sound and is **not** what this changes:

- **The resolution lands in the right conversation.** `chat_action_links` (`admz/chatbot/sessions.py:67`) records, at token-creation time, which principal's conversation spawned every confirm/capture token. On resolution the note path writes a `role='event'` `[console]` row into that conversation (`append_event`, `sessions.py:746`) and pops the link (`pop_action_link`, `sessions.py:683`) — capture at `admz/api/routes/capture.py:347`, approve/deny at `admz/api/routes/confirm.py:410` and `:796`.
- **The model is given that note on its next turn.** `_build_contents` (`admz/chatbot/client.py:521`) includes `role='event'` rows in the Gemini `contents`, normalized to the `user` role but carrying the `[console]` marker so `system_prompt.py` reads them as system events, not user forgeries.

So the model has the right context whenever it next runs. **The single missing thing is that nothing makes it run.**

### The gap, precisely

Chat turns are entirely browser-driven — `POST /chat/stream` (SSE) and its JSON twin `POST /api/chat`, both through `_run_chat_turn` (`admz/api/routes/chat.py:620`). There is no server-side turn runner. An out-of-band resolution therefore writes a note that sits unanswered until a human sends the next message. #443 is the same shape one layer up: a state nobody is watching.

### The two resolution flows are not symmetric

| | On resolution | What is left undone |
|---|---|---|
| **Approve** (`confirm.py` `_approve_session:189`) | the held work **executes synchronously** and the POST returns its outcome; the inline card resolves in-pane (`chat.js:submitApproval:601`) | only the chat's narration — the work is done |
| **Capture** (`capture.py`) | only the **credential is stored**; the form opens in a **new tab** (`chat.js:708`, `target="_blank"`), so the chat tab learns nothing until refocused or reloaded | the follow-on the model promised — never run |

Both reported incidents are the second row. The capture session records **no** resumable "next operation" — only device/account/purpose — so a "re-run the recorded operation" resume cannot fix them without first teaching capture to record an intended follow-on. The evidence says it does not need to: with the event note in history, one ordinary turn continues correctly. That is exactly what *"any luck?"* produced.

## Decision

**When an out-of-band step resolves, the browser fires one continuation turn — an ordinary, fully-gated chat turn, run as the operator, into the conversation that resolved, at most once per resolution.** It is the *"any luck?"* the operator types today, sent automatically.

### 1. Browser-driven, not a server-side actor

The continuation is a normal turn initiated by the operator's own page, through a new `POST /api/chat/resume` that shares `_run_chat_turn`'s policy (budget, audit, usage, principal-into-MCP) with `/chat/stream`.

- It runs **as the operator's authenticated principal** (FR-CB-006), so `audit_log.requester` is a real person. No `Principal` is ever constructed. There is therefore no "which principal does an unattended turn run as" question — the one [ADR-0062](0062-approve-an-envelope-not-a-step-list.md) exists to answer. **This ADR does not open the autonomous-turn envelope**; it moves the operator's own next turn earlier.
- A server-side runner would have to invent a principal, run with no browser attached, and decide an approval story for work it starts alone. That is the "broad" option #444 raised and deferred. Not built here.

The endpoint must never become a general way to run an ungated turn. The due-check is therefore re-evaluated **inside** the POST (§4); the GET is advisory only.

### 2. Approval is never widened — and the resume carries no instruction of its own

A resumed turn has no privilege a typed turn lacks (NFR-CB-004). Every follow-on is classified by the confirmation gate (ADR-0034) exactly as always: a **risky** follow-on raises a **new** card and stops; only already-approved or low-risk promised work completes.

**The turn is seeded with nothing.** `message` is empty and `_build_contents` (`client.py:560-563`) stops appending the live message when it is empty, so the model is handed history alone. This is legal precisely because an `event` row already normalizes to Gemini's `user` role (`client.py:556-559`) — a history-only `contents` still ends in a user turn, with no special casing. `stream_turn` refuses an empty `contents` outright rather than calling the SDK.

A text seed was considered and rejected on two grounds:

- It would be a **second, unmarked channel of ADMZ-authored instruction text** — the exact ambiguity `[console]` and the #167 forgery guard (`client.py:506-518`, `security.md:343-352`) exist to close. Phrasing around that guard is a workaround, not an answer.
- It forces a choice between two bad persistences: persist it, and the operator sees a message they never typed; don't, and the model acted on an instruction absent from history, so the *next* turn sees a different conversation than this one did.

The event note is already the instruction. The gate is the guarantee. The operator approved a capture, not a free follow-on turn with tools — and after this change they still have not, because the continuation is bound by the same gate a manual *"any luck?"* would have been.

### 3. The continuation is scoped to the conversation that resolved

`_run_chat_turn` takes **no conversation id** today; it resolves the principal's *active* conversation implicitly in four places — `get_history` (`chat.py:672`), the persistence call (`:835`), the one-time title (`:845`), and `link_action` (`:872`). A resume must not inherit that.

**`conversation_id` is threaded through instead**, defaulting to `None` (today's behaviour) so `/chat/stream` and `/api/chat` are provably unchanged.

- The **active pointer is operator-visible state** — it drives the drawer, the next page load, and decisively *where the operator's next typed message lands*. Resuming conversation A by switching the active pointer to A would silently redirect a message the operator is composing in B. The firmware incident is exactly that shape: a multi-minute wait is when someone opens a second chat.
- **This repo already made this call one layer down and wrote down why.** `append_event` takes an explicit conversation id "precisely because the resolution may land while the principal has a different (or no) active conversation" (`sessions.py:749-754`). A resume is that same event one layer up.
- Site `:872` is **load-bearing**: `_scan_action_tokens` → `link_action` is what makes the *next* resolution write a note at all. A continuation that opens a new card and links it to the wrong conversation kills the chain silently, one step later.

Persistence also changes shape: `append_turn` (`sessions.py:599-643`) always writes a user row *and* a model row, and no model-only writer exists. A new `append_model_turn` — mirroring `append_event`'s ownership check, with no lazy conversation creation — is what lets a continuation persist without inventing a user message.

### 4. Exactly once — the trailing event row, plus a leased claim

A resume is **due** for a conversation iff its most recent `chat_history` row is a `role='event'` note:

- after capture/approve the newest row is the event note → **due**;
- the continuation persists a `model` row → no longer due;
- a reload, or the operator typing first, leaves a non-event newest row → not due.

Ordering is **by `id`, never `created_at`** — `append_turn` stamps its user and model rows with one identical timestamp (`sessions.py:618`, `:623`, `:629`), so ties are routine and a timestamp ordering would be nondeterministic exactly on the rows that decide this. The existing `idx_chat_history_conv(conversation_id, id)` covers the read.

That predicate alone is not enough, and the gap is the *normal* path rather than an edge case. Capture opens in a second tab, and the capture-done page links back to `/chat` — so the standard flow ends with **two** `/chat` tabs, one firing on load while the other fires on focus. Both read due before either persists.

**A small `chat_resume_claims` table closes it**, keyed on the trailing event row's `id` — a natural idempotency key. The claim is **leased**, not permanent (lease = the per-event chat timeout + 30s, default 150s, so it never expires under a turn still legitimately streaming):

- a duplicate tab loses the claim and does nothing;
- a resume that **fails** persists no model row, so it stays due — and once the lease expires it will retry on the operator's next reload. A permanent tombstone would trade "fires twice" for "never fires again", reintroducing the reported bug on the error path. Self-healing and operator-paced is the better failure mode.

Nothing releases the claim on success: the persisted model row ends due-ness, and the next resolution writes a new event row with a new id, so chaining needs no bookkeeping.

### 5. Where the browser notices, and fires

One guarded rule — "when the conversation has a due resume, call `/api/chat/resume` once" — reached from the three points where awareness arrives:

- **in-tab approval success** (`chat.js:submitApproval`, the `completed` branch at `:623-637`) — the note is already written by the POST that branch just awaited;
- **tab refocus** — a `visibilitychange` handler, which **does not exist today**; this is the trigger that fixes the reported incidents most directly, because capture completes in a *different* tab and the original may never reload;
- **page load** — but **chained after** `restoreActiveConversation` (`:961`), never in parallel: restore bails when `transcript.children.length` is non-zero (`:964`, `:979`), so appending a continuation bubble first would abort the transcript restore on exactly the load that matters. A fast localhost load hides this.

The continuation renders through the existing `renderAssistantBubble` (`:205`) + `consumeSse` (`:127`) with **no** user bubble; `replayMessage` (`:917-931`) already renders a model row with no preceding user row, so later reloads need no renderer change.

### 6. Anonymous may resume

`/api/chat` and `/chat/stream` already accept the synthetic anonymous principal; `GET /api/chat/pending-actions` refuses it (`chat.py:501`). The refusal rule has a shape, and resume sits outside it: `pending-actions` **discloses live tokens the caller never had**, which is why *listing* is guarded. A resume discloses no token and mints nothing.

Refusing would also leave the bug unfixed in the default dev mode — the operator would watch the model promise to continue while ADMZ declined, and then be allowed to type the same continuation by hand. Due-ness bounds the spend: each resolution permits exactly one continuation, and each resolution required a real human approval or credential submission, so this cannot become a free turn generator.

The asymmetry is deliberate and gets a test saying so, or someone will "fix" it in the wrong direction.

## What this does not do

- **Run turns with no browser attached.** If the operator closes the tab and never returns, nothing fires until they come back — then page-load detection continues it. No worse than today, and every turn stays attended.
- **Open ADR-0062's envelope.** No autonomous, unattended, tool-wielding turn is introduced.
- **Record a capture's follow-on operation.** The model infers the promised step from the event note, as it already does on a manual nudge.
- **Change the note or the gate.** Both are reused verbatim; this only adds a trigger.
- **Treat a denial specially.** A denied approval is also an event row, so it is due too. Due-ness stays uniform rather than sniffing note text — the prompt already tells the model to drop a denied action.
- **Guarantee a failed resume never repeats.** It stays due and may fire again after the lease expires (§4) — chosen deliberately over never firing again.
- **Leave the history window untouched.** `get_history` fetches `max_turns * 2` rows; event and model-only rows each consume one, so a resume-heavy conversation surfaces slightly less prior dialogue. Nothing asserts row parity; worth knowing, not worth fixing here.

## Decisions taken — the owner may override any before it ships

| # | Question | Decision |
|---|---|---|
| 1 | Server-side resume, or browser-driven? | **Browser-driven** — attended, attributed, no new principal (§1) |
| 2 | Re-run the recorded op, or a continuation turn? | **A gated continuation turn** — the recorded-op path cannot fix the capture case, and the gate makes a continuation safe (§2) |
| 3 | Does the turn carry a resume instruction? | **No — seed-free.** History alone; a text seed would be a second unmarked instruction channel (§2) |
| 4 | Which conversation does it run in? | **The one that resolved** — `conversation_id` threaded through `_run_chat_turn`; the active pointer is never moved (§3) |
| 5 | How is "resume needed" tracked? | **Trailing event row, ordered by `id`, plus a leased claim** for the two-tab case (§4) |
| 6 | Is the continuation shown as a user bubble? | **No** — `append_model_turn` persists the model row only |
| 7 | Where does the browser fire? | **Three triggers**: in-tab approval, tab refocus, page load (chained after restore) (§5) |
| 8 | Anonymous? | **Allowed**, with the `pending-actions` asymmetry pinned by test (§6) |
| 9 | Approvals too, not just captures? | **Yes** — both land as events; approvals gain the missing narration |

## Slices

**S1 — server.** `sessions.py`: the `chat_resume_claims` table, `append_model_turn`, `resume_due`, `try_claim_resume`, and `get_history(conversation_id=…)`. `client.py`: the empty-message guard in `_build_contents` and the empty-`contents` refusal in `stream_turn`. `chat.py`: `conversation_id` + `resume` on `_run_chat_turn` threaded to all four sites, `"resume"` in the `chat_turn` audit details, and the two endpoints.

**S2 — browser.** `chat.js`: the guarded `maybeResumeConversation()` and its three triggers.

Ship in one PR unless review prefers the safety-relevant server half alone; S1 is gated on the full existing suite before any endpoint exists.

## Verification

| Claim | Test | Control / mutation |
|---|---|---|
| Due iff the trailing row is an event note | seed a conversation ending in `role='event'` → due | after `append_model_turn` → not due |
| Ordering is by `id` | freeze the clock so user/model/event share a timestamp → still correct | **unfrozen it passes either way**; frozen, a `created_at` ordering fails |
| The continuation persists a model row and no user row | roles read `[user, model, event, model]` | the `user` count stays 1 — an anti-`append_turn` pin |
| **A resume does not move the active-conversation cursor** | conv A due, active is B, POST A → the row lands in A and active is still **B** | a `set_active_conversation`-first build fails exactly here |
| New tokens link to the **resumed** conversation | `pop_action_link(token)["conversation_id"] == A` while active is B | without it the next resolution writes no note and the chain dies |
| It goes through the policy chokepoint | budget exhausted → error, nothing persisted, `chat_budget_exceeded` audited | pins "never call `stream_turn` directly" |
| Seed-free | captured kwargs show `user_message == ""` and `history[-1]["role"] == "event"` | `_build_contents([event], "")` appends nothing; a non-empty message still does |
| One continuation per resolution | POST twice → second is `409 not_due`; two claimants → one wins | lease expiry lets a **failed** resume retry |
| Anonymous may resume | backend `none`: GET + POST succeed | **`pending-actions` still 403s the same client** |
| The gate is untouched | a service-affecting follow-on raises a card rather than executing | — |

The browser half is **unpinnable by unit test** — this repo has no JS test tooling at all (no `package.json`, no jest). It gets `tests/e2e/MANUAL_resume_tests.md` in the same PR, following the existing `tests/e2e/MANUAL_*.md` precedent, covering: approve in-tab; capture in a second tab then return (transcript intact); refocus without reloading; two tabs → exactly one continuation; nothing due → no turn; a denial acknowledged rather than re-proposed.

Then per the playbook: an adversarial review in its own worktree, a mutation harness on a quiet tree, the full suite, and green CI before merge.

## Consequences

- The assistant keeps the promise it makes — *"once you submit, I will…"* — instead of stranding the operator with a turn-shaped obligation the architecture declined to discharge. The firmware case is the one that matters: a dangerous operation no longer stops half-done with nobody watching.
- Two new endpoints, one small table, one new store writer, and one additive parameter on the turn runner. No new principal, no change to the gate, no change to the note.
- `_run_chat_turn` gains an explicit conversation scope it should arguably always have had; the implicit active-conversation coupling is now visible at its call sites.
- Approvals gain the narration they were missing, so both out-of-band flows behave the same way.
- Every resumed turn is attended and attributed, so the audit log still answers "who" for every tool call — the property ADR-0062 protects. `chat_turn` rows now also answer "typed or resumed?".

## Amendment 2026-09-23 — a note that lands while a reply is running

§4's predicate, "due iff the newest row is a console note", assumed the reply to a note is filed after everything it saw. It is not: a turn reads its history when it **starts** and writes its reply when it **ends**. Any note written in between gets an id before the reply, so the reply "answers" it by position although the model never saw it.

The owner hit exactly that. A drift review raised three cards, and they were approved within six seconds. The first approval's continuation read the conversation and claimed its note. The other two approvals wrote their notes while it ran. Then it saved its reply after all three. The browser had also skipped both later requests: `maybeResumeConversation` returned early while a continuation was in flight, and nothing looked again. The final reply told the operator that two baseline accepts were still awaiting approval. Both had executed at 18:12:01 and 18:12:03 (audit, notices and the three completed confirm sessions agree).

**Decision: a reply is filed before the notes it never saw.**

- **Server.** `get_history_and_watermark` returns the id of the newest row the turn read. When the turn persists its reply (`append_turn` for a typed turn, `append_model_turn` for a continuation), console notes newer than that watermark are re-filed after the reply: deleted and re-inserted with the same role, text and timestamp. So §4's predicate now tells the truth, and they stay due.
  - A typed turn re-files only when its rows land in the conversation the watermark was read from, because the active conversation can change mid-turn.
  - A resume claim on a re-filed note follows it, so a tab already answering it is not doubled.
- **Browser.** One reply at a time, and nothing dropped. A continuation requested while any reply is streaming (typed or continued) sets a flag instead of returning. When that reply ends, the console looks again once. Once, so a failed continuation, which stays due and claimed, cannot loop on 409s.

Considered and not taken:

- **Reserving the reply's row when the turn starts.** Every reader would then have to skip half-written rows, a failed turn would have to clean up, and a first message would create its conversation at a different moment. Re-filing touches only the two writers.
- **Ordering history by a per-turn snapshot.** Every reader of `chat_history` would have to agree on a second ordering. §4 chose ordering by id for exactly that reason.

Concurrent turns in one conversation from two tabs remain possible. There the worst case is a note acknowledged twice, never one lost.

## What would falsify this

If resumed turns routinely produce a **new** approval card the operator then has to handle, the "one bounded promise" framing is wrong and the model is treating a resume as licence to start work — the answer would be scoping the resume to the exact promised operation (decision 2's rejected alternative), not more automation. If operators habitually close the tab and never return, page-load resumption is not enough and the honest next step is a notification, not a louder auto-run. And if the lease is never contended in practice, §4's claim table is ceremony and the trailing-row predicate alone was sufficient.
