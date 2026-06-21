/* Curated, illustrative craft data for the bench.
 *
 * This is a SMALL hand-authored subset — a few popular bases, a handful of modifiers each, with
 * coarse value ranges and ilvl gates. It exists to teach the PoE2 0.5 currency FLOW, not to
 * mirror GGG's real spawn weights or full mod database. Costs come from live poe.ninja prices.
 * `priceName` maps an orb to its poe.ninja currency name (null = not priced; ledger shows n/d). */

import type { Base, OrbId } from "./engine";

export type OrbDef = {
  id: OrbId;
  label: string;
  priceName: string | null;
  color: string;
  blurb: string;
};

export const ORBS: OrbDef[] = [
  { id: "transmute", label: "Transmute", priceName: "Orb of Transmutation", color: "#9fbfff", blurb: "Normal → Magic, adds 1 modifier." },
  { id: "augment", label: "Augment", priceName: "Orb of Augmentation", color: "#7fa0ff", blurb: "Adds a modifier to a Magic item." },
  { id: "regal", label: "Regal", priceName: "Regal Orb", color: "#6f8fe0", blurb: "Magic → Rare, adds 1 modifier." },
  { id: "exalt", label: "Exalted", priceName: "Exalted Orb", color: "#e8c14f", blurb: "Adds a modifier to a Rare item (≤3 per side)." },
  { id: "annul", label: "Annul", priceName: "Orb of Annulment", color: "#6fd3c8", blurb: "Removes a random modifier." },
  { id: "alchemy", label: "Alchemy", priceName: "Orb of Alchemy", color: "#e0c64a", blurb: "Normal → Rare with 4 modifiers." },
  { id: "chaos", label: "Chaos", priceName: "Chaos Orb", color: "#4caa6a", blurb: "Removes one modifier and adds another." },
  { id: "divine", label: "Divine", priceName: "Divine Orb", color: "#f3ead0", blurb: "Rerolls the numeric values of modifiers." },
  { id: "vaal", label: "Vaal", priceName: "Vaal Orb", color: "#d0533c", blurb: "Corrupts — an unpredictable outcome." },
  { id: "essence", label: "Essence", priceName: null, color: "#8fd0a0", blurb: "Normal → Rare, guaranteeing one modifier." },
];

export const BASES: Base[] = [
  {
    id: "siphoning-wand",
    name: "Siphoning Wand",
    category: "Wand",
    itemLevel: 82,
    signature: "spell_dmg",
    mods: [
      { id: "spell_dmg", group: "spelldmg", affix: "prefix", tiers: [
        { ilvl: 1, text: "#% increased Spell Damage", rolls: [[15, 24]] },
        { ilvl: 60, text: "#% increased Spell Damage", rolls: [[35, 44]] },
      ] },
      { id: "cold_spell", group: "coldspell", affix: "prefix", tiers: [
        { ilvl: 1, text: "Adds # to # Cold Damage to Spells", rolls: [[3, 5], [8, 12]] },
        { ilvl: 55, text: "Adds # to # Cold Damage to Spells", rolls: [[10, 14], [20, 28]] },
      ] },
      { id: "light_spell", group: "lightspell", affix: "prefix", tiers: [
        { ilvl: 1, text: "Adds # to # Lightning Damage to Spells", rolls: [[1, 2], [18, 25]] },
      ] },
      { id: "fire_spell", group: "firespell", affix: "prefix", tiers: [
        { ilvl: 1, text: "Adds # to # Fire Damage to Spells", rolls: [[6, 9], [13, 18]] },
      ] },
      { id: "wand_mana", group: "mana", affix: "prefix", tiers: [
        { ilvl: 1, text: "+# to maximum Mana", rolls: [[20, 39]] },
        { ilvl: 50, text: "+# to maximum Mana", rolls: [[55, 75]] },
      ] },
      { id: "cast_speed", group: "castspeed", affix: "suffix", tiers: [
        { ilvl: 1, text: "#% increased Cast Speed", rolls: [[8, 12]] },
        { ilvl: 45, text: "#% increased Cast Speed", rolls: [[15, 19]] },
      ] },
      { id: "spell_crit", group: "spellcrit", affix: "suffix", tiers: [
        { ilvl: 1, text: "#% increased Critical Hit Chance for Spells", rolls: [[15, 25]] },
      ] },
      { id: "crit_multi", group: "critmulti", affix: "suffix", tiers: [
        { ilvl: 30, text: "+#% to Critical Damage Bonus", rolls: [[15, 24]] },
      ] },
      { id: "wand_fire_res", group: "fireres", affix: "suffix", tiers: [
        { ilvl: 1, text: "+#% to Fire Resistance", rolls: [[12, 20]] },
        { ilvl: 48, text: "+#% to Fire Resistance", rolls: [[26, 35]] },
      ] },
      { id: "wand_int", group: "int", affix: "suffix", tiers: [
        { ilvl: 1, text: "+# to Intelligence", rolls: [[10, 20]] },
      ] },
    ],
  },
  {
    id: "striking-quarterstaff",
    name: "Striking Quarterstaff",
    category: "Quarterstaff",
    itemLevel: 82,
    signature: "phys_pct",
    mods: [
      { id: "phys_pct", group: "physpct", affix: "prefix", tiers: [
        { ilvl: 1, text: "#% increased Physical Damage", rolls: [[40, 59]] },
        { ilvl: 60, text: "#% increased Physical Damage", rolls: [[80, 100]] },
      ] },
      { id: "flat_phys", group: "flatphys", affix: "prefix", tiers: [
        { ilvl: 1, text: "Adds # to # Physical Damage", rolls: [[5, 9], [14, 20]] },
      ] },
      { id: "qs_cold", group: "coldatk", affix: "prefix", tiers: [
        { ilvl: 1, text: "Adds # to # Cold Damage", rolls: [[4, 7], [10, 15]] },
      ] },
      { id: "qs_light", group: "lightatk", affix: "prefix", tiers: [
        { ilvl: 1, text: "Adds # to # Lightning Damage", rolls: [[1, 3], [20, 30]] },
      ] },
      { id: "qs_fire", group: "fireatk", affix: "prefix", tiers: [
        { ilvl: 1, text: "Adds # to # Fire Damage", rolls: [[6, 10], [15, 22]] },
      ] },
      { id: "attack_speed", group: "atkspeed", affix: "suffix", tiers: [
        { ilvl: 1, text: "#% increased Attack Speed", rolls: [[8, 12]] },
        { ilvl: 45, text: "#% increased Attack Speed", rolls: [[14, 18]] },
      ] },
      { id: "crit_chance", group: "critchance", affix: "suffix", tiers: [
        { ilvl: 1, text: "#% increased Critical Hit Chance", rolls: [[15, 25]] },
      ] },
      { id: "accuracy", group: "acc", affix: "suffix", tiers: [
        { ilvl: 1, text: "+# to Accuracy Rating", rolls: [[80, 150]] },
      ] },
      { id: "qs_dex", group: "dex", affix: "suffix", tiers: [
        { ilvl: 1, text: "+# to Dexterity", rolls: [[10, 20]] },
      ] },
      { id: "leech", group: "leech", affix: "suffix", tiers: [
        { ilvl: 40, text: "#% of Physical Attack Damage Leeched as Life", rolls: [[1, 2]] },
      ] },
    ],
  },
  {
    id: "sapphire-ring",
    name: "Sapphire Ring",
    category: "Ring",
    itemLevel: 80,
    signature: "ring_life",
    mods: [
      { id: "ring_fire", group: "ringfire", affix: "prefix", tiers: [
        { ilvl: 1, text: "Adds # to # Fire Damage to Attacks", rolls: [[3, 5], [7, 11]] },
      ] },
      { id: "ring_cold", group: "ringcold", affix: "prefix", tiers: [
        { ilvl: 1, text: "Adds # to # Cold Damage to Attacks", rolls: [[2, 4], [6, 10]] },
      ] },
      { id: "ring_light", group: "ringlight", affix: "prefix", tiers: [
        { ilvl: 1, text: "Adds # to # Lightning Damage to Attacks", rolls: [[1, 2], [15, 22]] },
      ] },
      { id: "ring_life", group: "life", affix: "prefix", tiers: [
        { ilvl: 1, text: "+# to maximum Life", rolls: [[15, 29]] },
        { ilvl: 50, text: "+# to maximum Life", rolls: [[40, 55]] },
      ] },
      { id: "ring_mana", group: "mana", affix: "prefix", tiers: [
        { ilvl: 1, text: "+# to maximum Mana", rolls: [[20, 39]] },
        { ilvl: 50, text: "+# to maximum Mana", rolls: [[55, 70]] },
      ] },
      { id: "ring_fire_res", group: "fireres", affix: "suffix", tiers: [
        { ilvl: 1, text: "+#% to Fire Resistance", rolls: [[12, 20]] },
        { ilvl: 48, text: "+#% to Fire Resistance", rolls: [[26, 35]] },
      ] },
      { id: "ring_cold_res", group: "coldres", affix: "suffix", tiers: [
        { ilvl: 1, text: "+#% to Cold Resistance", rolls: [[12, 20]] },
        { ilvl: 48, text: "+#% to Cold Resistance", rolls: [[26, 35]] },
      ] },
      { id: "ring_light_res", group: "lightres", affix: "suffix", tiers: [
        { ilvl: 1, text: "+#% to Lightning Resistance", rolls: [[12, 20]] },
      ] },
      { id: "ring_all_attr", group: "allattr", affix: "suffix", tiers: [
        { ilvl: 1, text: "+# to all Attributes", rolls: [[5, 9]] },
      ] },
      { id: "ring_mana_regen", group: "manaregen", affix: "suffix", tiers: [
        { ilvl: 1, text: "#% increased Mana Regeneration Rate", rolls: [[10, 20]] },
      ] },
    ],
  },
  {
    id: "stellar-amulet",
    name: "Stellar Amulet",
    category: "Amulet",
    itemLevel: 81,
    signature: "amu_spirit",
    mods: [
      { id: "amu_life", group: "life", affix: "prefix", tiers: [
        { ilvl: 1, text: "+# to maximum Life", rolls: [[20, 34]] },
        { ilvl: 50, text: "+# to maximum Life", rolls: [[45, 60]] },
      ] },
      { id: "amu_mana", group: "mana", affix: "prefix", tiers: [
        { ilvl: 1, text: "+# to maximum Mana", rolls: [[25, 44]] },
      ] },
      { id: "amu_spell_dmg", group: "spelldmg", affix: "prefix", tiers: [
        { ilvl: 1, text: "#% increased Spell Damage", rolls: [[15, 24]] },
      ] },
      { id: "amu_phys", group: "physpct", affix: "prefix", tiers: [
        { ilvl: 1, text: "#% increased Physical Damage", rolls: [[20, 30]] },
      ] },
      { id: "amu_spirit", group: "spirit", affix: "prefix", tiers: [
        { ilvl: 1, text: "+# to Spirit", rolls: [[10, 20]] },
        { ilvl: 55, text: "+# to Spirit", rolls: [[25, 35]] },
      ] },
      { id: "amu_all_res", group: "allres", affix: "suffix", tiers: [
        { ilvl: 1, text: "+#% to all Elemental Resistances", rolls: [[8, 14]] },
      ] },
      { id: "amu_crit_multi", group: "critmulti", affix: "suffix", tiers: [
        { ilvl: 30, text: "+#% to Critical Damage Bonus", rolls: [[15, 24]] },
      ] },
      { id: "amu_all_attr", group: "allattr", affix: "suffix", tiers: [
        { ilvl: 1, text: "+# to all Attributes", rolls: [[6, 10]] },
      ] },
      { id: "amu_cast_speed", group: "castspeed", affix: "suffix", tiers: [
        { ilvl: 1, text: "#% increased Cast Speed", rolls: [[8, 12]] },
      ] },
      { id: "amu_life_regen", group: "liferegen", affix: "suffix", tiers: [
        { ilvl: 1, text: "Regenerate # Life per second", rolls: [[3, 6]] },
      ] },
    ],
  },
  {
    id: "vaal-cuirass",
    name: "Vaal Cuirass",
    category: "Body Armour",
    itemLevel: 82,
    signature: "ba_life",
    mods: [
      { id: "ba_life", group: "life", affix: "prefix", tiers: [
        { ilvl: 1, text: "+# to maximum Life", rolls: [[30, 49]] },
        { ilvl: 60, text: "+# to maximum Life", rolls: [[70, 90]] },
      ] },
      { id: "ba_armour_pct", group: "armourpct", affix: "prefix", tiers: [
        { ilvl: 1, text: "#% increased Armour", rolls: [[40, 59]] },
        { ilvl: 60, text: "#% increased Armour", rolls: [[90, 120]] },
      ] },
      { id: "ba_flat_armour", group: "flatarmour", affix: "prefix", tiers: [
        { ilvl: 1, text: "+# to Armour", rolls: [[50, 90]] },
      ] },
      { id: "ba_mana", group: "mana", affix: "prefix", tiers: [
        { ilvl: 1, text: "+# to maximum Mana", rolls: [[25, 44]] },
      ] },
      { id: "ba_evasion", group: "evasionpct", affix: "prefix", tiers: [
        { ilvl: 1, text: "#% increased Evasion Rating", rolls: [[40, 60]] },
      ] },
      { id: "ba_fire_res", group: "fireres", affix: "suffix", tiers: [
        { ilvl: 1, text: "+#% to Fire Resistance", rolls: [[18, 26]] },
        { ilvl: 60, text: "+#% to Fire Resistance", rolls: [[31, 40]] },
      ] },
      { id: "ba_cold_res", group: "coldres", affix: "suffix", tiers: [
        { ilvl: 1, text: "+#% to Cold Resistance", rolls: [[18, 26]] },
      ] },
      { id: "ba_light_res", group: "lightres", affix: "suffix", tiers: [
        { ilvl: 1, text: "+#% to Lightning Resistance", rolls: [[18, 26]] },
      ] },
      { id: "ba_chaos_res", group: "chaosres", affix: "suffix", tiers: [
        { ilvl: 45, text: "+#% to Chaos Resistance", rolls: [[8, 14]] },
      ] },
      { id: "ba_str", group: "str", affix: "suffix", tiers: [
        { ilvl: 1, text: "+# to Strength", rolls: [[15, 25]] },
      ] },
    ],
  },
];

export function getBase(id: string): Base {
  return BASES.find((b) => b.id === id) ?? BASES[0];
}
