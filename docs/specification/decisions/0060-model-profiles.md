# ADR-0060 — Model profiles: derive what the API knows, declare what it doesn't, and check the difference

**Status:** Proposed (2026-08-16).
**Relates to:** ADR-0025 (Gemini chatbot, MCP-native — the decision this
refines), ADR-0052 (advanced capability switches — the "one declared registry"
pattern this copies), FR-CB-007 (no provider abstraction, deliberately),
FR-CB-008 (per-user model selection), FR-CB-009 (chat disabled by default —
the constraint that stops this becoming a runtime dependency on Google),
NFR-CB-003 (cost telemetry, which is what makes pricing load-bearing).

## Context

Model identifiers are hardcoded in **six files**:

| File | What it hardcodes |
|---|---|
| `admz/chatbot/config.py` | `SELECTABLE_MODELS`, `DEFAULT_MODEL` |
| `admz/chatbot/voice.py` | live-audio model list, `DEFAULT_VOICE_MODEL`, `STT_MODELS` |
| `admz/chatbot/usage.py` | `PRICING` — $/M-token per model |
| `admz/api/templates/chat_settings.html` | **a second copy of the pricing table**, as HTML |
| `admz/chatbot/client.py` | family conditionals — thinking budget, the 3.x AFC workaround, `thought_signature` handling |
| `admz/api/routes/chat.py` | family conditionals in the empty-response recovery path |

Pricing exists twice, so it is two things to update and one to forget. The
family conditionals are worse: they encode *which wire format a model wants*
as branching inside the call path, which means a new model is a code change
in `client.py` rather than a data change anywhere.

### The trigger: gemini-3.7-flash cannot be added by editing a list

`gemini-3.7-flash` went GA on 2026-08-13. Adding it to `SELECTABLE_MODELS`
would make it *selectable* and *broken*, because it changes the request shape:

- `thinking_budget` is **replaced** by `thinking_level` (`low`/`medium`/`high`)
- `temperature`, `top_p`, `top_k` are removed
- `candidate_count` is removed
- prefilled model turns are removed

ADMZ sets `thinking_config: {thinking_budget: …}` at four call sites in
`client.py`, defaulting to `-1` (dynamic). That default is load-bearing, not
cosmetic: `client.py:64` records that with thinking disabled, 2.5-flash answers
device-operation questions from wrong training priors instead of calling
`query_catalog`, and the `-pro` models reject a budget of `0` outright. So the
2.5/3.5 dialect cannot simply be dropped in favour of the 3.7 one — **both must
coexist**, selected per model.

That is the whole argument for this ADR. Not tidiness: a correctness
requirement that the current shape cannot express.

### What the API actually tells us — measured, not assumed

`GET /v1beta/models` returned **53 entries** on 2026-08-16 with twelve fields:
`name`, `displayName`, `description`, `version`, `inputTokenLimit`,
`outputTokenLimit`, `supportedGenerationMethods`, `thinking`, `temperature`,
`maxTemperature`, `topK`, `topP`.

`supportedGenerationMethods` separates the capability classes cleanly:

| Method | Class | ADMZ list it would replace |
|---|---|---|
| `generateContent` | text / multimodal chat | `SELECTABLE_MODELS` |
| `bidiGenerateContent` | live realtime audio | `voice.py`'s model list |
| `embedContent` | embeddings | *(none — ADMZ has no embedding use)* |
| `createCachedContent` | supports context caching | *(none yet)* |
| `predict` / `predictLongRunning` | imagen / veo | n/a |

So **three of the six hardcoded lists are derivable**, along with both token
limits and a `thinking` boolean.

**Three things the API does not report, and they are exactly the load-bearing
ones:**

1. **Pricing.** Not present in any form. ADMZ bills cost telemetry against it
   (NFR-CB-003), and `gemini-3.7-flash`'s $0.75/$3.75 is an *introductory* rate
   that expires **2026-12-31** — a dated fact no endpoint will correct.
2. **The thinking dialect.** `thinking: true` says the model thinks. It does
   not say whether it wants `thinking_budget` or `thinking_level`. This is
   precisely the fact that breaks 3.7.
3. **GA vs preview.** Only inferable from the name, and that inference is
   wrong: `gemini-embedding-2` and `gemini-embedding-2-preview` both exist, as
   do `gemini-3-pro-image` and `gemini-3-pro-image-preview`.

## Decision

Introduce a **model profile table** — one entry per model ADMZ is willing to
use — built in three layers.

**Naming.** *Profiles*, not "registry" or "catalog". `registry` already means
the device registry (`DeviceRegistry`) and `catalog` already means the atlas
API catalog (`query_catalog`). A third meaning for either word would cost more
than the name saves.

### Layer 1 — derived facts

Read from `models.list`: existence, token limits, `supportedGenerationMethods`,
`thinking`. Cached to disk so it is a *refresh*, not a per-call dependency.

### Layer 2 — declared facts

Hand-maintained, because nothing reports them: pricing **with a
`price_valid_until` date**, the thinking dialect (`budget` | `level` | `none`),
GA/preview status, and ADMZ policy (is this model offered to operators at all;
is it the default).

### Layer 3 — a checker that fails when the layers disagree

`tools/models.py`, in the shape of `tools/environments.py`: read-only, prints
declared beside observed, **exits non-zero on disagreement**. It catches a
model that vanished, a token limit that moved, a declared model the API has
never heard of, and a `price_valid_until` that has passed.

This layer is not optional. A hand-declared table is a claim about the world,
and this project has been bitten by exactly that three times — the environment
table that went false three times over (#398), the atlas pin that sat on a
pre-security-fix commit for five days while a weekly job called it routine
(#392), and the staging row that was stale the week it was written (#238).
Declaring without checking is how all three happened.

### The dialect adapter

ADMZ expresses **intent**; the adapter emits the family's wire form.

```
reasoning="default" | "off" | "hard"
    ->  {"thinking_config": {"thinking_budget": -1}}     # 2.5, 3.1, 3.5, 3.6
    ->  {"thinking_level": "medium"}                      # 3.7+
```

Sampling parameters are emitted only for families that accept them. The four
`thinking_budget` call sites in `client.py` and the recovery path in
`chat.py` call the adapter instead of composing config inline.

This is the piece that makes a new model a table row. Everything else in this
ADR is cleanup; this part is the requirement.

### Selection by capability

Callers ask for what they need — `needs=("tools", "vision")`, cheapest GA —
rather than naming a string. `voice.py` asks for `bidiGenerateContent` instead
of maintaining its own list.

## What this explicitly does not do

- **No provider abstraction.** FR-CB-007 records the deliberate decision not to
  build the `LlmProvider` ABC without a concrete second consumer, and that
  decision stands. This ADR is about variation *within* Gemini. If a second
  provider ever arrives, the profile table is the natural seam — but that is an
  observation, not a plan, and nothing here should be shaped around it.
- **No rolling aliases as the default.** `gemini-flash-latest`,
  `gemini-flash-lite-latest` and `gemini-pro-latest` are real and were
  considered. Rejected as a default: `client.py` is substantially a record of
  version-specific breakage (the 3.x AFC empty-turn bug, `thought_signature`
  round-tripping, the dynamic-budget empty-response bug), and an alias moves
  underneath all of it with no signal. They stay *selectable* for operators who
  want them; ADMZ does not pin to one.
- **No new models are enabled by this ADR.** Adding 3.7, embeddings,
  computer-use or TTS are separate decisions with their own costs. This ADR
  makes them cheap to add; it does not add them.

## Consequences

**Good.** A new model is a table row plus, at most, one new dialect. The
duplicated pricing table collapses to one source the settings page renders.
`voice.py`'s list stops being hand-maintained. The checker turns "is our model
list still true?" into a command instead of a code review.

**The cost, stated plainly.** This adds a subsystem where there were literals.
Six files get simpler; one new module and one new tool appear. That trade is
only worth it because of the dialect requirement — if 3.7 had kept
`thinking_budget`, editing three lists would have been the right answer and
this ADR would be over-engineering.

**The constraint that shapes layer 1.** FR-CB-009 says ADMZ runs fine with no
Gemini API key at all, and the MCP and REST surfaces must be entirely
unaffected. So the derived layer **must be optional**: no key, no network, or a
failed refresh degrades to the declared table alone, and the checker reports
"could not verify" rather than failing the process. ADMZ must never acquire a
startup dependency on Google being reachable.

**What would falsify this.** If the next three model releases keep the same
request shape, the dialect adapter earns nothing and this becomes a table
nobody needed. That is a real possibility and worth revisiting after 3.7's
successor: if the dialect layer is still one entry wide in six months, collapse
it back.
