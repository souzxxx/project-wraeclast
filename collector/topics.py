"""Topic tagging for knowledge_chunk — lets RAG/chat filter craft knowledge specifically.

The corpus runs in two lanes: crafting and farming (see the YouTube queries in config.py).
Tagging every chunk lets the craft-intelligence epic — and chat — narrow retrieval to craft
without dragging in farm noise, and keeps farm/general questions broad.

Pure heuristic: keyword signal only, no network/DB/LLM, so it is unit-testable fully offline.
Per CLAUDE.md this stays QUALITATIVE — it classifies text, it never sources numbers/prices.
"""

from __future__ import annotations

import re
from typing import Final, Literal

KnowledgeTopic = Literal["craft", "farm"]

CRAFT: Final[KnowledgeTopic] = "craft"
FARM: Final[KnowledgeTopic] = "farm"

# Strong signals: a single one is enough to call a chunk "craft". These are the currency orbs,
# deterministic tools, and verbs that only crafting content talks about.
_STRONG_TERMS: Final[tuple[str, ...]] = (
    "craft",
    "crafting",
    "essence",
    "essences",
    "omen",
    "omens",
    "exalted orb",
    "regal orb",
    "chaos orb",
    "divine orb",
    "vaal orb",
    "orb of transmutation",
    "orb of augmentation",
    "orb of annulment",
    "annulment",
    "whittling",
    "fracturing",
    "reforge",
    "reforging",
    "meta-craft",
    "metacraft",
    "mirror-tier",
)

# Weak signals: shared with build/farm/loot talk, so they only tip the scale in pairs.
_WEAK_TERMS: Final[tuple[str, ...]] = (
    "modifier",
    "prefix",
    "suffix",
    "item level",
    "ilvl",
    "rare item",
    "base item",
    "affix",
)


def _matches(blob: str, term: str) -> bool:
    """Word-boundary match so 'craft' doesn't fire on 'Warcraft' and 'omen' not on 'omens' twice."""
    return re.search(rf"\b{re.escape(term)}\b", blob) is not None


def classify_topic(title: str, content: str) -> KnowledgeTopic:
    """Tag a knowledge chunk as 'craft' or 'farm' from its text. Defaults to 'farm' (the broad
    lane) unless there is clear crafting signal — one strong term, or two weak ones."""
    blob = f"{title}\n{content}".lower()
    if any(_matches(blob, t) for t in _STRONG_TERMS):
        return CRAFT
    weak = sum(1 for t in _WEAK_TERMS if _matches(blob, t))
    return CRAFT if weak >= 2 else FARM


def topic_for_question(question: str) -> KnowledgeTopic | None:
    """Pick a retrieval filter for a chat question: narrow to craft only when the question is
    clearly about crafting, else stay broad (None) so farm/build/general asks aren't starved."""
    return CRAFT if classify_topic("", question) == CRAFT else None
