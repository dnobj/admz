"""Model profiles — one declared table per model (ADR-0060, FR-CB-015).

Model identifiers used to be hardcoded in six files, pricing in two, and the
request dialect as conditionals inside the call path. That last one is why this
module exists rather than being tidy-up: ``gemini-3.7-flash`` **replaced**
``thinking_budget`` with ``thinking_level``, so adding it to a list would have
made it selectable *and broken*, while dropping the old key would break 2.5 —
``client.py`` records that with thinking disabled, ``gemini-2.5-flash`` answers
device-operation requests from its wrong training priors instead of calling
``query_catalog``, and the ``-pro`` models reject a budget of ``0`` outright.

Both dialects must coexist, selected per model. A list cannot express that.

WHAT LIVES HERE AND WHAT DOES NOT
---------------------------------
This is the **declared** layer of ADR-0060: facts no API reports — pricing (with
the date it stops being true), the request dialect, GA-vs-preview, and whether
ADMZ offers the model at all. The **derived** layer (token limits and
capabilities read from the provider's ``models.list``) and the checker that
fails when the two disagree are NFR-CB-008, and are deliberately not in this
slice — see #407.

Nothing here contacts the provider. FR-CB-009 requires ADMZ to run with no
Gemini key at all, so the model table must be readable with no network.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


#: How a family expresses "how hard to think".
#:
#: ``budget`` — ``thinking_config: {thinking_budget: <int>}``; ``-1`` is dynamic.
#: ``level``  — ``thinking_level: "low"|"medium"|"high"`` (3.7+). The numeric
#:              form is REMOVED there, not merely deprecated.
#: ``none``   — the model does not take a thinking parameter.
DIALECT_BUDGET = "budget"
DIALECT_LEVEL = "level"
DIALECT_NONE = "none"

#: What a caller asks for. ADMZ expresses intent; the adapter emits the wire
#: form. Callers never name a dialect.
REASONING_DEFAULT = "default"
REASONING_OFF = "off"
REASONING_HARD = "hard"


@dataclass(frozen=True)
class ModelProfile:
    """One model ADMZ is willing to use."""

    id: str
    label: str
    dialect: str
    #: $/1M tokens. Informational — see ``usage.estimate_cost_usd``.
    input_usd: float
    output_usd: float
    #: The date the price above stops being true, when that is known.
    #: ``gemini-3.7-flash`` launched on an introductory rate that expires, and a
    #: hardcoded table with no expiry would have gone quietly wrong in January.
    price_valid_until: Optional[str] = None
    preview: bool = False
    #: Offered in the chat model picker.
    selectable: bool = True
    #: Realtime audio (``bidiGenerateContent``), not text generation.
    live_audio: bool = False
    note: str = ""


#: The table. Order is the order the picker shows.
#:
#: 3.7 and 3.6 are added here as part of #407 — the owner asked for the newer
#: models to be selectable, which ADR-0060 had deliberately left as a separate
#: decision. Embeddings, computer-use and TTS are NOT added: those are new
#: capabilities needing new call paths, not list entries.
PROFILES: Tuple[ModelProfile, ...] = (
    # --- Gemini 3.x ---------------------------------------------------------
    ModelProfile(
        "gemini-3.7-flash", "Gemini 3.7 Flash", DIALECT_LEVEL,
        0.75, 3.75, price_valid_until="2026-12-31",
        note="Newest workhorse. Introductory pricing — see price_valid_until.",
    ),
    ModelProfile(
        "gemini-3.6-flash", "Gemini 3.6 Flash", DIALECT_LEVEL,
        1.00, 6.00,
        note="Previous-generation 3.x flash.",
    ),
    ModelProfile(
        "gemini-3.5-flash", "Gemini 3.5 Flash", DIALECT_BUDGET,
        1.50, 9.00,
        note="Agent-tuned. ~5x the cost of 2.5-flash.",
    ),
    ModelProfile(
        "gemini-3.5-flash-lite", "Gemini 3.5 Flash Lite", DIALECT_BUDGET,
        0.35, 2.00,
    ),
    ModelProfile(
        "gemini-3.1-pro-preview", "Gemini 3.1 Pro (preview)", DIALECT_BUDGET,
        2.00, 12.00, preview=True,
        note="Most capable. Rejects a thinking budget of 0.",
    ),
    ModelProfile(
        "gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite", DIALECT_BUDGET,
        0.25, 1.50,
    ),
    # --- Gemini 2.5 (proven stable line) ------------------------------------
    ModelProfile(
        "gemini-2.5-pro", "Gemini 2.5 Pro", DIALECT_BUDGET,
        1.25, 10.00,
        note="Rejects a thinking budget of 0.",
    ),
    ModelProfile(
        "gemini-2.5-flash", "Gemini 2.5 Flash", DIALECT_BUDGET,
        0.30, 2.50,
        note="Default. Proven, cheap floor for chat-style turns.",
    ),
    ModelProfile(
        "gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite", DIALECT_BUDGET,
        0.10, 0.40,
    ),
    # --- Realtime audio (voice console) -------------------------------------
    ModelProfile(
        "gemini-3.1-flash-live-preview", "Gemini 3.1 Flash Live (preview)",
        DIALECT_NONE, 0.0, 0.0, preview=True,
        selectable=False, live_audio=True,
        note="Default voice model. Audio-to-audio.",
    ),
    ModelProfile(
        "gemini-2.5-flash-native-audio-latest", "Gemini 2.5 Native Audio (latest)",
        DIALECT_NONE, 0.0, 0.0, selectable=False, live_audio=True,
    ),
    ModelProfile(
        "gemini-2.5-flash-native-audio-preview-12-2025",
        "Gemini 2.5 Native Audio (12-2025)",
        DIALECT_NONE, 0.0, 0.0, preview=True, selectable=False, live_audio=True,
    ),
    ModelProfile(
        "gemini-2.5-flash-native-audio-preview-09-2025",
        "Gemini 2.5 Native Audio (09-2025)",
        DIALECT_NONE, 0.0, 0.0, preview=True, selectable=False, live_audio=True,
    ),
)

_BY_ID: Dict[str, ModelProfile] = {p.id: p for p in PROFILES}


def get(model_id: str) -> Optional[ModelProfile]:
    return _BY_ID.get(model_id)


def selectable_models() -> List[str]:
    """Chat-picker models, in table order."""
    return [p.id for p in PROFILES if p.selectable]


def live_audio_models() -> List[str]:
    """Realtime-audio models, in table order."""
    return [p.id for p in PROFILES if p.live_audio]


def dialect_for(model_id: str) -> str:
    """The thinking dialect for ``model_id``.

    An unknown model gets ``budget``, which is what every family except 3.7+
    uses. That is a guess either way; guessing the older form means an unknown
    model behaves like the nine that came before it rather than like the one
    that changed, and a wrong ``thinking_budget`` is a rejected parameter rather
    than silently un-configured reasoning.
    """
    profile = get(model_id)
    return profile.dialect if profile else DIALECT_BUDGET


def stale_prices(today: Optional[_dt.date] = None) -> List[str]:
    """Model ids whose ``price_valid_until`` has passed.

    Cost telemetry (NFR-CB-003) bills operators against these numbers, so a
    price that has expired is wrong rather than merely old. Surfaced as data so
    a checker or a settings page can say so; nothing here fails on its own.
    """
    day = today or _dt.date.today()
    out = []
    for p in PROFILES:
        if not p.price_valid_until:
            continue
        try:
            if _dt.date.fromisoformat(p.price_valid_until) < day:
                out.append(p.id)
        except ValueError:
            continue
    return out


def thinking_config(
    model_id: str,
    reasoning: str = REASONING_DEFAULT,
    *,
    budget_override: Optional[int] = None,
) -> Dict:
    """Translate ADMZ's intent into the family's wire form.

    This is the piece ADR-0060 exists for. Callers say what they want; nothing
    outside this function names ``thinking_budget`` or ``thinking_level``, so a
    new model is a table row rather than a change in the call path.

    ``default`` maps to dynamic thinking on the budget dialect (``-1``), which
    is load-bearing: ``client.py`` records that with thinking disabled,
    2.5-flash answers device questions from wrong priors instead of calling
    ``query_catalog``, and the ``-pro`` models reject ``0`` outright.

    ``budget_override`` carries ``ADMZ_GEMINI_THINKING_BUDGET`` and the fixed
    budget the empty-candidate retry uses. It applies to the **budget dialect
    only** — 3.7+ removed the numeric parameter, so there is nothing for a
    number to mean there, and silently accepting one would be the "selectable
    and broken" failure this table exists to prevent. On a level model the
    ``reasoning`` intent decides, which is why the retry passes ``hard``
    rather than only a number.
    """
    dialect = dialect_for(model_id)
    if dialect == DIALECT_NONE:
        return {}
    if dialect == DIALECT_LEVEL:
        return {"thinking_level": {
            REASONING_OFF: "low",
            REASONING_HARD: "high",
        }.get(reasoning, "medium")}
    if budget_override is not None:
        return {"thinking_config": {"thinking_budget": budget_override}}
    budget = {
        REASONING_OFF: 0,
        REASONING_HARD: 24576,
    }.get(reasoning, -1)
    return {"thinking_config": {"thinking_budget": budget}}
