# ADR-0038: Chat conversation history (named, listable conversations)

**Status:** Accepted (2026-06-18).
**Date:** 2026-06-18.
**Relates to:** ADR-0024/0025 (Gemini chatbot), the context-preload work
(`chat_history` real-history threading), ADR-0033 (windows-local auth / principal).

## Context

The console chatbot kept exactly **one implicit conversation per principal**.
The `chat_history` table (`principal, role, text`) fed the last ~10 turns back
to Gemini as `contents=[...]`, and a single `chat_sessions` row pointed at it —
but the "Clear chat history" button **hard-deleted** everything. There was no
conversation id, no title, no list, and no way to look up or resume an earlier
exchange. Once you cleared (or wanted a clean slate), the prior conversation was
gone.

Operators wanted the normal chat-app affordance: *usually start a new
conversation, but be able to look up and continue a previous one.*

A simplifying fact made this cheap: the manual function-calling loop drives
context entirely from `chat_history`; Gemini's `previous_interaction_id` is
vestigial (ignored by the models API). So **a conversation is just a labelled
set of `chat_history` rows** plus a per-principal "active conversation" pointer.

## Decision

Add a lightweight grouping layer on top of the existing store rather than a new
subsystem.

- **`chat_conversations` table** (`id` uuid, `principal`, `title`,
  `title_source` ∈ pending|snippet|llm|manual|backfill, `created_at`,
  `updated_at`). `chat_history` gains a nullable `conversation_id`;
  `chat_sessions` gains `active_conversation_id`. Columns are added idempotently
  (`ALTER … ADD COLUMN` guarded by `PRAGMA table_info`).
- **Active conversation is server-side per-principal state** (on the
  `chat_sessions` row). `/chat/stream` and `/api/chat` are unchanged — a turn
  reads/writes the active conversation; `append_turn`/`get_history` are scoped to
  it (lazily creating one on first use). Switching conversations is a separate
  POST that flips the pointer. (Same one-session-per-principal model as before;
  multi-tab active-pointer reconciliation is left as a known limitation.)
- **Titles:** an instant snippet of the first user message, upgraded once — on
  the conversation's first turn — to a terse LLM-generated title via a single
  non-streaming, no-tools, low-token Gemini call. Title generation is
  **best-effort**: a failure leaves the snippet title and never affects the
  streamed answer.
- **"Clear chat" → "New chat":** the button now starts a *new* conversation
  (resets the session pointer, creates a fresh active conversation) and **leaves
  the previous conversation intact** in the list. Nothing is deleted.
- **Six owner-scoped REST routes** (`/api/chat/conversations[...]`: list, create,
  get-transcript, activate, rename, delete) back the UI; every route resolves
  through the signed-in principal and 404s on another principal's conversation.
- **UI:** a left slide-out drawer in the console (ChatGPT/Claude style) lists
  conversations newest-first with their titles, opens/continues one (replaying
  the transcript), starts a new one, and renames/deletes — refreshing after each
  turn so a new conversation and its generated title appear without a reload.
- **Migration** (idempotent, non-destructive, runs at store init): pre-existing
  `chat_history` rows are assigned to one "Earlier conversation" per principal
  and adopted as active only if none is set. No row loss; safe to re-run.

## Consequences

- Operators can keep a running set of conversations, look one up by its title,
  and continue it — the common "new chat by default, occasionally resume" flow.
- Browsing is **by recency** only; full-text search across conversations is
  deliberately out of scope for v1 (the model leaves room — add
  `GET …/conversations?q=` later).
- **Privacy posture is unchanged.** Message text continues to live only in
  `chat_history` (as it already did); the audit log still records only chat
  *metadata* (model, tokens, tool names) — never transcript text. Conversations
  are as private as the existing history and are owner-scoped. Titles see only
  the already-gate-cleaned user/assistant text, so no device credentials can
  enter them.
- Cross-process safety comes free from SQLite WAL + the atomic active pointer —
  no JSON merge hack.

## Alternatives considered

- **Modal picker / inline "Recents" accordion** instead of a drawer — rejected in
  favour of the slide-out pane (operator preference; best for managing many
  conversations and consistent across the dock + full-page).
- **Storing the active pointer in its own table** — folded onto the
  `chat_sessions` row instead (one row per principal already), using `''`
  interaction/model sentinels that read back as `None`.
- **Reconstructing history from the audit log** — rejected: the audit log
  intentionally stores no transcript text.
