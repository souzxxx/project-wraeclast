"""Curated seed of structured craft methods — the recipe layer of the craft-intelligence epic.

This is Craft 2: a small, version-controlled set of real PoE2 0.5 craft methods expressed as
DATA (ordered steps + aggregate currency `inputs` + target mods + a one-attempt success_prob),
the craft analogue of the curated farm strategies. The EV engine (Craft 3) will cross each
method's `inputs` with live `price_snapshot` to compute expected cost (incl. retries) and ROI —
so the NUMBERS that matter (prices) still come from poe.ninja, never from here. The only
estimates baked in are the expected currency quantities and the per-attempt success chance,
which are the method's structure (mirroring how farm strategies carry an estimated profit/hour).

Seeded daily by `run_daily`; `replace_craft_methods` swaps the league's batch each run, so it is
idempotent. `seed_methods` is pure (no DB/network) and fully unit-testable offline.
"""

from __future__ import annotations

from db.models import CraftMethod


def seed_methods(league: str) -> list[CraftMethod]:
    """Return the curated craft methods for a league (pure — constructs validated models only)."""
    return [
        CraftMethod(
            league=league,
            name="+3 Spell Skills Wand (Essence → omen-targeted Exalts)",
            item_base="Siphoning Wand (ilvl 82+)",
            archetype="caster",
            target_mods=[
                "+3 to Level of all Spell Skills",
                "#% increased Spell Damage",
                "#% increased Cast Speed",
            ],
            steps=[
                "Buy an ilvl 82+ caster wand base (e.g. Siphoning Wand).",
                "Use a Greater Essence to make it Rare and guarantee the +Spell Skills prefix.",
                "With Omen of Sinistral Exaltation active, slam Exalted Orbs to add the remaining "
                "prefixes (spell damage, flat spell damage) without touching suffixes.",
                "Fill suffixes (cast speed, crit) with plain Exalted Orbs.",
                "Divine to push the +Spell Skills and the key numeric rolls.",
            ],
            inputs={
                "Greater Essence of Haste": 3,
                "Omen of Sinistral Exaltation": 2,
                "Exalted Orb": 6,
                "Divine Orb": 2,
            },
            success_prob=0.18,
            output="+3 Spell Skills caster wand",
            sources=[
                {
                    "url": "https://www.youtube.com/watch?v=XZyrv7q9d80",
                    "title": "+7 SPELL SKILLS WAND Craft Guide | PoE2 0.5.2",
                }
            ],
            notes="+Spell Skills is a prefix — Sinistral omens stop Exalts from bricking it. "
            "Demand peaks early league.",
        ),
        CraftMethod(
            league=league,
            name="Phys Quarterstaff (attack/monk)",
            item_base="Striking Quarterstaff (ilvl 82+)",
            archetype="attack",
            target_mods=[
                "#% increased Physical Damage",
                "Adds # to # Physical Damage",
                "#% increased Attack Speed",
                "#% increased Critical Hit Chance",
            ],
            steps=[
                "Buy an ilvl 82+ quarterstaff base.",
                "Greater Essence to guarantee the % Physical Damage prefix and make it Rare.",
                "Slam Exalted Orbs for flat phys (prefix) and attack speed / crit (suffixes).",
                "Annul + re-Exalt or use Dextral omens if a bad suffix lands.",
                "Divine to maximise the phys rolls.",
            ],
            inputs={
                "Greater Essence of Battle": 3,
                "Exalted Orb": 6,
                "Orb of Annulment": 1,
                "Divine Orb": 2,
            },
            success_prob=0.15,
            output="phys / attack-speed quarterstaff (monk)",
            sources=[
                {
                    "url": "https://maxroll.gg/poe2/resources/how-to-craft-in-path-of-exile-2",
                    "title": "PoE2 crafting fundamentals — Maxroll",
                }
            ],
            notes="Quarterstaff fits the owner's Spirit Walker monk. Local phys% + flat phys are "
            "both prefixes, so prefix pressure is the main risk.",
        ),
        CraftMethod(
            league=league,
            name="Triple-Resist Life Belt (low-risk beginner)",
            item_base="Heavy Belt (ilvl 75+)",
            archetype="defence",
            target_mods=[
                "+# to maximum Life",
                "+#% to Fire Resistance",
                "+#% to Cold Resistance",
            ],
            steps=[
                "Buy an ilvl 75+ Heavy Belt.",
                "Transmutation → Augmentation to roll toward Life / a resistance.",
                "Regal Orb to go Rare, then Exalted Orbs for the remaining resistances.",
                "A Greater Essence of the Body can guarantee Life if it won't roll.",
            ],
            inputs={
                "Orb of Transmutation": 1,
                "Orb of Augmentation": 1,
                "Regal Orb": 1,
                "Exalted Orb": 3,
            },
            success_prob=0.40,
            output="triple-resistance life belt",
            sources=[
                {
                    "url": "https://vulkk.com/2025/01/10/path-of-exile-2-crafting-recommendations-and-tips/",
                    "title": "PoE2 crafting recommendations — VULKK",
                }
            ],
            notes="Cheapest entry craft: belts have no prefixes competing with Life, so success is "
            "high. Great for steady low-margin flips.",
        ),
        CraftMethod(
            league=league,
            name="High-ES Helmet (Essence + Exalts)",
            item_base="Expert Cowl (ES base, ilvl 82+)",
            archetype="defence",
            target_mods=[
                "#% increased Energy Shield",
                "+# to maximum Energy Shield",
                "+#% to Lightning Resistance",
                "+# to Intelligence",
            ],
            steps=[
                "Buy an ilvl 82+ pure-ES helmet base.",
                "Greater Essence of the Body to make it Rare with guaranteed flat ES.",
                "Exalted Orbs to add % increased ES (prefix) and resistances / Intelligence "
                "(suffixes).",
                "Divine to maximise the ES rolls.",
            ],
            inputs={
                "Greater Essence of the Body": 3,
                "Exalted Orb": 5,
                "Divine Orb": 1,
            },
            success_prob=0.20,
            output="high-ES rare helmet",
            sources=[
                {
                    "url": "https://www.youtube.com/watch?v=mA6cjs1frao",
                    "title": "How I made 600 Divines Crafting ES Helmets — PoE2 0.5",
                }
            ],
            notes="% ES and flat ES are both prefixes, so prefix collisions are the failure mode. "
            "Sinistral Annulment can strip a bad prefix safely.",
        ),
        CraftMethod(
            league=league,
            name="Caster Amulet (+Spirit / Spell Damage)",
            item_base="Stellar Amulet (ilvl 81+)",
            archetype="caster",
            target_mods=[
                "+# to Spirit",
                "#% increased Spell Damage",
                "+#% to Critical Damage Bonus",
            ],
            steps=[
                "Buy an ilvl 81+ Stellar Amulet.",
                "Greater Essence to guarantee Spirit and make it Rare.",
                "Exalted Orbs for spell damage (prefix) and crit damage bonus (suffix).",
                "Divine to perfect Spirit and the damage rolls.",
            ],
            inputs={
                "Greater Essence of the Mind": 3,
                "Exalted Orb": 5,
                "Divine Orb": 1,
            },
            success_prob=0.22,
            output="endgame caster amulet (+Spirit)",
            sources=[
                {
                    "url": "https://www.youtube.com/watch?v=e1g9_wiHn-Q",
                    "title": "Insane Budget +3 Amulet Craft — PoE2",
                }
            ],
            notes="Spirit enables more buffs/auras, so caster amulets with Spirit + damage sell "
            "well. Verify the live sale price before committing currency.",
        ),
    ]


def run() -> dict[str, int]:
    """Replace the active league's craft methods with the curated seed (idempotent)."""
    from collector.config import get_settings
    from db.repo import replace_craft_methods

    league = get_settings().poe2_league
    return {"craft_methods": replace_craft_methods(league, seed_methods(league))}
