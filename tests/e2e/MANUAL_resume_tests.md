# Manual: the continuation turn (#444 / ADR-0066)

The server half is covered by `tests/test_chat_resume.py`. **The browser half
is not, and cannot be**: this repo has no JavaScript test tooling at all — no
`package.json`, no jest/vitest/playwright config anywhere. The three triggers in
`admz/api/static/chat.js` are therefore verified by hand, here.

Run against a **local dev instance**. Staging is unusable (#238), and nothing
below should ever be pointed at production.

## Setup

1. Start a dev instance with a Gemini key configured (`/settings/chat`).
2. Open `/chat`.

## Cases

| # | Steps | Expected |
|---|---|---|
| M1 | Ask for something that raises an approval card (e.g. a reboot). Approve it **in the chat tab**. | A new assistant bubble appears on its own and reports the outcome. **No user bubble** appears — you typed nothing. No reload. |
| M2 | Ask for something needing credentials so a capture card appears. Click **Open capture form** (opens a second tab), submit, then use the done page's link back to `/chat`. | On that load the continuation fires **and the restored transcript is intact** — the earlier turns are still above it. (This is the load-ordering trap: if the bubble is appended before the restore completes, history silently vanishes.) |
| M3 | Repeat M2, but instead of the done page's link, switch back to the **original** chat tab without reloading it. | The continuation fires on refocus, within a second or so. |
| M4 | Repeat M2 leaving **both** chat tabs open, then focus each in turn. | **Exactly one** continuation, not two. Reload both afterwards to confirm only one model reply was persisted. |
| M5 | With nothing pending, switch away from the chat tab and back several times. | No turn fires. The usage counter on `/settings/chat` does not move. |
| M6 | Raise an approval card and **Deny** it. | The continuation acknowledges the denial and does **not** re-propose the action. (A denial note is an event row too, so it is "due" — due-ness is deliberately uniform rather than sniffing the note's text.) |
| M7 | Start a capture, and **while it is open** click **New chat** so a different conversation is active. Complete the capture, return to `/chat`. | The answer lands in the conversation that resolved, and the **active conversation does not change** — your next typed message still goes to the new chat. |
| M8 | Get **three** approval cards in one reply (e.g. a drift review: one revert, two accepts). Approve all three quickly, while the first continuation is still writing. | The first continuation reports the first action. Then **one more** continuation runs by itself and reports the other two as done. No reply says an approved card is still awaiting approval. |
| M9 | Type a message, and while its reply is still streaming, approve a card from an earlier reply. | The typed reply finishes on its own. Then a continuation answers the approval. The two never stream into the transcript at the same time. |

## What a failure looks like

- **A user bubble you didn't type** → the continuation is being persisted with
  `append_turn` instead of `append_model_turn`.
- **Transcript empty after M2** → the load trigger is not chained behind
  `restoreActiveConversation()`.
- **Two replies in M4** → the claim lease is not being taken, or the two tabs
  are racing ahead of it.
- **M7 moves your active chat** → the turn is resolving the active conversation
  instead of the one passed to it.
- **M8 says an approved card is still pending, and nothing follows** → notes
  written mid-turn are not being re-filed after the reply
  (`_refile_unseen_notes`), or the console dropped the request that arrived
  mid-reply (`resumeWanted`).
- **M9 streams two replies at once** → `maybeResumeConversation` is not treating
  a typed reply as in flight.
