"""Curated seed of structured craft methods — the recipe layer of the craft-intelligence epic.

A small, version-controlled set of real PoE2 0.5 craft methods expressed as DATA (ordered steps +
the craft `mechanics` they use + aggregate `inputs` {consumable: expected_qty} + target mods + a
one-attempt success_prob + a curated output value), the craft analogue of the curated farm
strategies.

Craft is NOT just currency orbs — these methods deliberately span the whole craft surface:
**essences, omens, abyss (abyssal jewels), runes/soul cores, catalysts** and meta-crafting.
The EV engine (Craft 3, `api.craft_ev`) crosses each method's `inputs` with live `price_snapshot`
to compute expected cost (incl. retries) and ROI vs `output_value_div`. The numbers that matter —
the consumable PRICES — come from poe.ninja, never from here; the only curated estimates are the
expected quantities, the per-attempt success chance, and the output sale value (mirroring how a
farm strategy carries an estimated profit/hour).

Seeded daily by `run_daily`; `replace_craft_methods` swaps the league's batch each run (idempotent).
`seed_methods` is pure (no DB/network) and fully unit-testable offline.
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
            mechanics=["essence", "omen", "currency"],
            target_mods=[
                "+3 to Level of all Spell Skills",
                "#% increased Spell Damage",
                "#% increased Cast Speed",
            ],
            steps=[
                "Buy an ilvl 82+ caster wand base (e.g. Siphoning Wand).",
                "Use a Greater Essence to make it Rare and guarantee the +Spell Skills prefix.",
                "With Omen of Sinistral Exaltation active, slam Exalted Orbs to add the remaining "
                "prefixes (spell damage, flat spell) without touching suffixes.",
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
            output_value_div=60,
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
            mechanics=["essence", "currency"],
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
            output_value_div=40,
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
            mechanics=["currency", "essence"],
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
            output_value_div=3,
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
            mechanics=["essence", "omen", "currency"],
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
                "Omen of Sinistral Annulment to strip a bad prefix safely if % ES collides.",
                "Divine to maximise the ES rolls.",
            ],
            inputs={
                "Greater Essence of the Body": 3,
                "Exalted Orb": 5,
                "Omen of Sinistral Annulment": 1,
                "Divine Orb": 1,
            },
            success_prob=0.20,
            output="high-ES rare helmet",
            output_value_div=25,
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
            mechanics=["essence", "currency"],
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
            output_value_div=30,
            sources=[
                {
                    "url": "https://www.youtube.com/watch?v=e1g9_wiHn-Q",
                    "title": "Insane Budget +3 Amulet Craft — PoE2",
                }
            ],
            notes="Spirit enables more buffs/auras, so caster amulets with Spirit + damage sell "
            "well. Verify the live sale price before committing currency.",
        ),
        # ── breadth: craft is far more than currency orbs ───────────────────────────────────
        CraftMethod(
            league=league,
            name="Omen meta-craft finisher (Whittling + targeted Annul)",
            item_base="Near-perfect Rare (any slot, ilvl 82+)",
            archetype="finisher",
            mechanics=["omen", "currency"],
            target_mods=[
                "Remove the single worst (lowest-ilvl) modifier",
                "Re-add a top-tier modifier in its place",
            ],
            steps=[
                "Take an almost-perfect rare with one weak modifier.",
                "With Omen of Whittling active, use a Chaos Orb to remove the LOWEST item-level "
                "mod specifically (beware: an essence mod with a low level req can be the target).",
                "Use Omen of Sinistral/Dextral Exaltation + Exalted Orbs to re-add the wanted "
                "prefix/suffix deterministically.",
                "Divine to finish.",
            ],
            inputs={
                "Omen of Whittling": 1,
                "Chaos Orb": 1,
                "Omen of Dextral Exaltation": 1,
                "Exalted Orb": 2,
                "Divine Orb": 2,
            },
            success_prob=0.55,
            output="upgraded near-mirror rare (one tier better)",
            output_value_div=150,
            sources=[
                {
                    "url": "https://pathofexile2.wiki.fextralife.com/Omens",
                    "title": "PoE2 Omens — deterministic meta-crafting",
                }
            ],
            notes="Pure meta-craft: no rarity change, just omen-driven surgery on an existing "
            "rare. Whittling is the most powerful (and expensive) omen.",
        ),
        CraftMethod(
            league=league,
            name="Abyssal Jewel craft (life + damage)",
            item_base="Abyssal Jewel (ilvl 80+)",
            archetype="jewel",
            mechanics=["abyss", "essence", "currency"],
            target_mods=[
                "+# to maximum Life",
                "Adds # to # Physical/Elemental Damage to Attacks",
                "#% increased Attack/Cast Speed",
            ],
            steps=[
                "Get an Abyssal Jewel from Abyss content (for an Abyssal Socket).",
                "Essence to guarantee Life and make it Rare.",
                "Exalted Orbs for the damage and speed suffixes.",
                "Divine to push the life/damage rolls; Abyssal jewels with life + double damage "
                "sell very well.",
            ],
            inputs={
                "Greater Essence of the Body": 2,
                "Exalted Orb": 4,
                "Divine Orb": 1,
            },
            success_prob=0.25,
            output="life + damage abyssal jewel",
            output_value_div=15,
            sources=[
                {
                    "url": "https://www.youtube.com/watch?v=-VpDwcqnyN4",
                    "title": "Massive Currency Farm with this Abyss Strategy — PoE2",
                }
            ],
            notes="Abyss is its own craft lane: abyssal jewels socket into Abyssal Sockets and "
            "follow jewel mod rules. Life + two damage mods is the premium combo.",
        ),
        CraftMethod(
            league=league,
            name="Rune / Soul Core socketing (deterministic budget upgrade)",
            item_base="Rare gear with open sockets",
            archetype="budget",
            mechanics=["rune"],
            target_mods=[
                "Guaranteed resistance / attribute / damage from the socketed rune",
            ],
            steps=[
                "Take a rare with open rune sockets.",
                "Socket Greater Runes (resistance, life, or damage) or Soul Cores for a "
                "GUARANTEED, deterministic mod — no RNG.",
                "This is the cheapest way to patch a missing resistance or add flat damage to an "
                "otherwise-finished item.",
            ],
            inputs={
                "Greater Rune of the Body": 2,
            },
            success_prob=1.0,
            output="resistance/attribute-patched gear (deterministic)",
            output_value_div=8,
            sources=[
                {
                    "url": "https://maxroll.gg/poe2/resources/how-to-craft-in-path-of-exile-2",
                    "title": "PoE2 crafting fundamentals — Maxroll",
                }
            ],
            notes="100% deterministic (success_prob = 1): runes/soul cores guarantee their mod. "
            "The league is literally 'Runes of Aldur' — runes are core to crafting here.",
        ),
        CraftMethod(
            league=league,
            name="Catalyst quality boost (ring/amulet stats)",
            item_base="Finished Rare Ring or Amulet",
            archetype="finisher",
            mechanics=["catalyst"],
            target_mods=[
                "Up to +20% to the values of the targeted modifier type (e.g. resistances)",
            ],
            steps=[
                "Take a finished rare ring/amulet.",
                "Apply matching Catalysts (e.g. resistance catalysts) to add quality that boosts "
                "that modifier type's values by up to 20%.",
                "Cheap, deterministic value bump on an already-good item before selling.",
            ],
            inputs={
                "Catalyst": 10,
            },
            success_prob=1.0,
            output="catalyst-quality ring/amulet (boosted stats)",
            output_value_div=5,
            sources=[
                {
                    "url": "https://vulkk.com/2025/01/10/path-of-exile-2-crafting-recommendations-and-tips/",
                    "title": "PoE2 crafting recommendations — VULKK",
                }
            ],
            notes="Catalysts are a finishing-quality mechanic for rings/amulets — they scale a "
            "specific mod type's values, not RNG. Cheap last step to squeeze more out of a sale.",
        ),
    ]


def run() -> dict[str, int]:
    """Replace the active league's craft methods with the curated seed (idempotent)."""
    from collector.config import get_settings
    from db.repo import replace_craft_methods

    league = get_settings().poe2_league
    return {"craft_methods": replace_craft_methods(league, seed_methods(league))}
