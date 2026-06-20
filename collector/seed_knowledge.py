"""Curated seed knowledge — hand-distilled craft fundamentals from canonical PoE2 sources.

Unlike youtube/rss (automated discovery) or add_knowledge (the owner drops in one URL/text),
this is a small, version-controlled set of high-signal craft notes distilled from canonical
community sources (Maxroll, the PoE2 wiki, VULKK). It seeds the corpus so chat/curation know
crafting from day one, instead of waiting for the YouTube queries to surface good videos.

Ingested daily by `run_daily`; `ingest_documents` upserts by `source_url`, so re-running is
idempotent (no duplicates). The `ingest` import is lazy inside `run()` so this module stays
import-light and the curated content is unit-testable fully offline (no DB/network/creds).

Per the source-of-truth rule in CLAUDE.md, these notes are QUALITATIVE mechanics only —
numbers/prices always come from poe.ninja, never from here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeedDoc:
    """A distilled, source-attributed craft note. `source_url` is the canonical source and the
    dedup key; `content` is a faithful hand-distilled summary, not a raw page scrape."""

    source_url: str
    title: str
    content: str


_SEED_DOCS: list[SeedDoc] = [
    SeedDoc(
        source_url="https://maxroll.gg/poe2/resources/how-to-craft-in-path-of-exile-2",
        title="PoE2 craft fundamentals — currency orbs and the crafting flow",
        content=(
            "Path of Exile 2 crafting fundamentals (qualitative mechanics; live prices come "
            "from poe.ninja, never from this note).\n\n"
            "Core currency orbs and what each does:\n"
            "- Orb of Transmutation: Normal -> Magic item with one modifier.\n"
            "- Orb of Augmentation: adds a second modifier to a Magic item.\n"
            "- Regal Orb: upgrades a Magic item (2 mods) to Rare, adding a random third modifier.\n"
            "- Exalted Orb: adds a random modifier to a Rare item that has an open slot.\n"
            "- Chaos Orb: rerolls up to half of an item's modifiers at random.\n"
            "- Orb of Annulment: removes one random modifier.\n"
            "- Divine Orb: rerolls the numeric values of existing modifiers (does not change "
            "which mods are present).\n"
            "- Vaal Orb: corrupts the item with an unpredictable, irreversible outcome (adds "
            "sockets, rerolls, enchants, or randomizes values).\n"
            "Greater and Perfect versions of Transmutation/Augmentation/Regal/Exalted/Chaos "
            "exist and raise the minimum power level (tier) of the modifiers they can roll.\n\n"
            "Basic crafting flow:\n"
            "1) Normal -> Magic with an Orb of Transmutation on a chosen base.\n"
            "2) Magic -> Rare with a Regal Orb, or a Greater Essence to guarantee a third mod.\n"
            "3) Improve the Rare with Exalted Orbs (add mods) or Perfect Essences (replace a "
            "mod with a guaranteed one).\n"
            "Item level (ilvl) of the base is the single most important property: it caps which "
            "modifier tiers can appear. Endgame crafts generally want ilvl 75+ bases."
        ),
    ),
    SeedDoc(
        source_url="https://pathofexile2.wiki.fextralife.com/Essences",
        title="PoE2 essences — guaranteed modifiers and determinism",
        content=(
            "Essences add determinism to Path of Exile 2 crafting by guaranteeing a specific "
            "modifier, removing one layer of RNG. They come in four tiers: Lesser, Normal, "
            "Greater, and Perfect.\n\n"
            "- Using an essence upgrades an item and guarantees the one modifier tied to it.\n"
            "- Greater Essences upgrade a Magic item to Rare while guaranteeing a chosen "
            "modifier — trading raw potential for certainty.\n"
            "- Perfect Essences remove one modifier from a Rare item and replace it with a "
            "guaranteed specific one — the key tool for targeting a desirable stat instead of "
            "gambling.\n"
            "- Vaal Orbs used on an essence can raise its tier (e.g. Normal -> Greater) or turn "
            "it into a Corrupted Essence with a unique modifier.\n\n"
            "Essence crafting is usually the smartest first step when you need a known mod, "
            "because it converts a coin-flip into a guarantee. Perfect Essences combine well "
            "with omens (e.g. Crystallisation) to deal with otherwise-bad modifiers."
        ),
    ),
    SeedDoc(
        source_url="https://pathofexile2.wiki.fextralife.com/Omens",
        title="PoE2 omens — deterministic meta-crafting control",
        content=(
            "Omens are meta-crafting currencies in Path of Exile 2: you toggle one active in "
            "your inventory and it changes how your NEXT crafting currency behaves, giving "
            "precise control. Omens are obtained from Ritual (bought with tribute).\n\n"
            "Prefix/suffix targeting (Sinistral = prefix; Dextral = suffix):\n"
            "- Omen of Sinistral/Dextral Exaltation: your next Exalted Orb adds only a prefix / "
            "only a suffix.\n"
            "- Omen of Sinistral/Dextral Coronation: your next Regal Orb adds only a prefix / "
            "only a suffix.\n"
            "- Omen of Sinistral/Dextral Annulment: your next Orb of Annulment removes only a "
            "prefix / only a suffix (safely strip an unwanted mod).\n\n"
            "Enhanced-effect omens:\n"
            "- Omen of Greater Exaltation: your next Exalted Orb adds two random modifiers.\n"
            "- Omen of Greater Annulment: your next Orb of Annulment removes two modifiers.\n"
            "- Omen of Whittling: your next Chaos Orb removes the LOWEST item-level modifier. "
            "It is the most expensive and powerful omen, but the trap is that a strong mod added "
            "by an essence can have a low level requirement and get removed — use it carefully.\n\n"
            "Omens are the backbone of deterministic high-end crafting, but the omens themselves "
            "are expensive."
        ),
    ),
    SeedDoc(
        source_url=(
            "https://vulkk.com/2025/01/10/path-of-exile-2-crafting-recommendations-and-tips/"
        ),
        title="PoE2 crafting — profit methods and best practices",
        content=(
            "Practical, profit-oriented crafting in Path of Exile 2 (qualitative guidance; exact "
            "profit/hour must be computed from live poe.ninja prices, never assumed here).\n\n"
            "Best practices:\n"
            "- Item level matters most: use ilvl 75+ bases to access the top modifier tiers.\n"
            "- Progress Transmutation -> Augmentation -> Regal to build a controlled magic item "
            "before risking rare upgrades.\n"
            "- Prefer essences for determinism (guarantee the mod you need); use omens "
            "(Annulment/Whittling) to safely target or strip mods.\n"
            "- Never corrupt (Vaal) or sanctify an item you cannot replace.\n"
            "- Use PoE2DB and Craft of Exile to check modifier availability and simulate a craft "
            "before spending currency.\n"
            "- 3-to-1 reforging combines three similar items for a fresh attempt, salvaging bad "
            "rolls.\n\n"
            "Commonly profitable craft-and-sell targets (always verify against current prices): "
            "belts (low-risk resistance recipes), +3 skill amulets (high early-league demand), "
            "and breach rings crafted/flipped in bulk. A broader strategy is 'craft & flip': buy "
            "undervalued transitional gear, apply one cheap finishing step, resell. Mirror-tier "
            "crafting is the high end. In the current 0.5 (Runes of Aldor) league, Expedition "
            "merged with the rune mechanic is among the most lucrative sources of bases/currency."
        ),
    ),
]


def seed_documents() -> list[SeedDoc]:
    """Return the curated craft seed docs (pure — no network/DB; safe to import offline)."""
    return list(_SEED_DOCS)


def run() -> dict[str, int]:
    """Ingest the curated seed docs into knowledge_chunk (idempotent via source_url upsert).

    The `ingest` import is lazy so this module stays import-light for offline tests/tools.
    """
    from collector.ingest import KnowledgeDoc, ingest_documents

    docs = [
        KnowledgeDoc(source_url=d.source_url, title=d.title, content=d.content)
        for d in seed_documents()
    ]
    return {"seeded": ingest_documents(docs)}
