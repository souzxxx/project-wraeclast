/* Crafting-bench engine — pure PoE2 0.5 currency mechanics over a curated mod pool.
 *
 * No React, no I/O, `rng` injected — every transition is deterministic and unit-testable.
 * Deterministic transitions (rarity changes, affix caps, group de-dup, ilvl gating) follow the
 * real rules; WHICH modifier is rolled is drawn from the curated illustrative pool in data.ts,
 * NOT GGG's real spawn weights. Costs are handled by the UI from live poe.ninja prices. */

export type Rarity = "normal" | "magic" | "rare";
export type AffixKind = "prefix" | "suffix";

export type ModTier = { ilvl: number; text: string; rolls: [number, number][] };
export type ModDef = { id: string; group: string; affix: AffixKind; tiers: ModTier[] };

export type Base = {
  id: string;
  name: string;
  category: string;
  itemLevel: number;
  signature: string; // mod id an Essence guarantees
  mods: ModDef[];
};

export type Mod = {
  id: string;
  group: string;
  affix: AffixKind;
  tierIndex: number;
  text: string;
  values: number[];
};

export type Item = {
  baseId: string;
  name: string;
  category: string;
  itemLevel: number;
  rarity: Rarity;
  mods: Mod[];
};

export type OrbId =
  | "transmute"
  | "augment"
  | "regal"
  | "exalt"
  | "annul"
  | "alchemy"
  | "chaos"
  | "divine"
  | "vaal"
  | "essence";

export type Rng = () => number;
export type ApplyResult = { ok: true; item: Item; log: string } | { ok: false; reason: string };

/** Affixes allowed PER SIDE (prefix/suffix) at each rarity. */
const CAP: Record<Rarity, number> = { normal: 0, magic: 1, rare: 3 };

const ok = (item: Item, log: string): ApplyResult => ({ ok: true, item, log });
const fail = (reason: string): ApplyResult => ({ ok: false, reason });

export function newBase(base: Base): Item {
  return {
    baseId: base.id,
    name: base.name,
    category: base.category,
    itemLevel: base.itemLevel,
    rarity: "normal",
    mods: [],
  };
}

function sideCounts(item: Item): { prefix: number; suffix: number } {
  let prefix = 0;
  let suffix = 0;
  for (const m of item.mods) m.affix === "prefix" ? (prefix += 1) : (suffix += 1);
  return { prefix, suffix };
}

function openSides(item: Item): AffixKind[] {
  const cap = CAP[item.rarity];
  const c = sideCounts(item);
  const sides: AffixKind[] = [];
  if (c.prefix < cap) sides.push("prefix");
  if (c.suffix < cap) sides.push("suffix");
  return sides;
}

function eligibleDefs(
  base: Base,
  item: Item,
  sides: AffixKind[],
  exclude?: Set<string>,
): ModDef[] {
  const present = new Set(item.mods.map((m) => m.group));
  return base.mods.filter(
    (d) =>
      sides.includes(d.affix) &&
      !present.has(d.group) &&
      !exclude?.has(d.group) &&
      d.tiers.some((t) => t.ilvl <= item.itemLevel),
  );
}

function pick<T>(arr: T[], rng: Rng): T {
  return arr[Math.floor(rng() * arr.length)];
}

/** Highest-ilvl tier the item level can roll (documented default). -1 if none eligible. */
function bestTierIndex(def: ModDef, itemLevel: number): number {
  let best = -1;
  let bestIlvl = -1;
  def.tiers.forEach((t, i) => {
    if (t.ilvl <= itemLevel && t.ilvl > bestIlvl) {
      bestIlvl = t.ilvl;
      best = i;
    }
  });
  return best;
}

function rollTier(def: ModDef, tierIndex: number, rng: Rng): Mod {
  const tier = def.tiers[tierIndex];
  const values = tier.rolls.map(([lo, hi]) => lo + Math.floor(rng() * (hi - lo + 1)));
  let i = 0;
  const text = tier.text.replace(/#/g, () => String(values[i++]));
  return { id: def.id, group: def.group, affix: def.affix, tierIndex, text, values };
}

/** Roll a fresh modifier for an open side, or null when nothing is eligible. */
function addRandomMod(
  base: Base,
  item: Item,
  rng: Rng,
  forceSides?: AffixKind[],
  exclude?: Set<string>,
): Mod | null {
  const sides = forceSides ?? openSides(item);
  if (sides.length === 0) return null;
  const defs = eligibleDefs(base, item, sides, exclude);
  if (defs.length === 0) return null;
  const def = pick(defs, rng);
  return rollTier(def, bestTierIndex(def, item.itemLevel), rng);
}

function fillTo(base: Base, item: Item, target: number, rng: Rng): Item {
  let next = item;
  while (next.mods.length < target) {
    const m = addRandomMod(base, next, rng);
    if (!m) break;
    next = { ...next, mods: [...next.mods, m] };
  }
  return next;
}

/** Whether an orb can legally be applied right now (drives button enable/disable). */
export function canApply(base: Base, item: Item, orb: OrbId): boolean {
  switch (orb) {
    case "transmute":
    case "alchemy":
    case "essence":
      return item.rarity === "normal";
    case "augment":
      return item.rarity === "magic" && eligibleDefs(base, item, openSides(item)).length > 0;
    case "regal":
      return item.rarity === "magic";
    case "exalt":
      return item.rarity === "rare" && eligibleDefs(base, item, openSides(item)).length > 0;
    case "annul":
    case "divine":
      return item.mods.length > 0;
    case "chaos":
      return item.rarity !== "normal" && item.mods.length > 0;
    case "vaal":
      return true;
  }
}

export function applyOrb(base: Base, item: Item, orb: OrbId, rng: Rng): ApplyResult {
  switch (orb) {
    case "transmute": {
      if (item.rarity !== "normal") return fail("Transmutation needs a Normal item.");
      const m = addRandomMod(base, { ...item, rarity: "magic", mods: [] }, rng);
      if (!m) return fail("No eligible modifier for this base.");
      return ok({ ...item, rarity: "magic", mods: [m] }, `Transmuted → Magic: ${m.text}`);
    }
    case "augment": {
      if (item.rarity !== "magic") return fail("Augmentation needs a Magic item.");
      const m = addRandomMod(base, item, rng);
      if (!m) return fail("No open affix to augment.");
      return ok({ ...item, mods: [...item.mods, m] }, `Augmented: ${m.text}`);
    }
    case "regal": {
      if (item.rarity !== "magic") return fail("Regal needs a Magic item.");
      const upgraded: Item = { ...item, rarity: "rare" };
      const m = addRandomMod(base, upgraded, rng);
      return ok(
        m ? { ...upgraded, mods: [...item.mods, m] } : upgraded,
        m ? `Regal → Rare: ${m.text}` : "Regal → Rare (no new modifier fit).",
      );
    }
    case "exalt": {
      if (item.rarity !== "rare") return fail("Exalted needs a Rare item.");
      const m = addRandomMod(base, item, rng);
      if (!m) return fail("All affixes are full.");
      return ok({ ...item, mods: [...item.mods, m] }, `Exalted: ${m.text}`);
    }
    case "annul": {
      if (item.mods.length === 0) return fail("Nothing to annul.");
      const idx = Math.floor(rng() * item.mods.length);
      const removed = item.mods[idx];
      return ok(
        { ...item, mods: item.mods.filter((_, i) => i !== idx) },
        `Annulled: ${removed.text}`,
      );
    }
    case "alchemy": {
      if (item.rarity !== "normal") return fail("Alchemy needs a Normal item.");
      const filled = fillTo(base, { ...item, rarity: "rare", mods: [] }, 4, rng);
      return ok(filled, `Alchemy → Rare with ${filled.mods.length} modifiers.`);
    }
    case "chaos": {
      if (item.rarity === "normal" || item.mods.length === 0)
        return fail("Chaos needs a Magic or Rare item with modifiers.");
      const idx = Math.floor(rng() * item.mods.length);
      const removed = item.mods[idx];
      const trimmed: Item = { ...item, mods: item.mods.filter((_, i) => i !== idx) };
      // exclude the removed mod's group so Chaos always adds a DIFFERENT modifier (PoE2 rule)
      const m = addRandomMod(base, trimmed, rng, undefined, new Set([removed.group]));
      return ok(
        m ? { ...trimmed, mods: [...trimmed.mods, m] } : trimmed,
        m ? `Chaos: swapped a modifier → ${m.text}` : "Chaos: removed a modifier.",
      );
    }
    case "divine": {
      if (item.mods.length === 0) return fail("Nothing to divine.");
      const mods = item.mods.map((m) => {
        const def = base.mods.find((d) => d.id === m.id);
        return def ? rollTier(def, m.tierIndex, rng) : m;
      });
      return ok({ ...item, mods }, "Divined: numeric values rerolled.");
    }
    case "essence": {
      if (item.rarity !== "normal") return fail("Essence needs a Normal item.");
      const sig = base.mods.find((d) => d.id === base.signature);
      let next: Item = { ...item, rarity: "rare", mods: [] };
      if (sig) {
        const ti = bestTierIndex(sig, item.itemLevel);
        if (ti >= 0) next = { ...next, mods: [rollTier(sig, ti, rng)] };
      }
      next = fillTo(base, next, 4, rng);
      return ok(next, `Essence → Rare, guaranteed: ${next.mods[0]?.text ?? "—"}`);
    }
    case "vaal": {
      // Corruption never rolls a white base into a rare — a Normal item is left untouched.
      if (item.rarity === "normal") return ok(item, "Vaal Orb: nothing happened.");
      const r = rng();
      if (r < 0.25) return ok(item, "Vaal Orb: nothing happened.");
      if (r < 0.5 && item.mods.length > 0) {
        const idx = Math.floor(rng() * item.mods.length);
        return ok(
          { ...item, mods: item.mods.filter((_, i) => i !== idx) },
          "Corrupted: a modifier was lost.",
        );
      }
      if (r < 0.75) {
        const m = addRandomMod(base, item, rng);
        if (m) return ok({ ...item, mods: [...item.mods, m] }, `Corrupted: ${m.text} emerged.`);
        return ok(item, "Vaal Orb: nothing happened.");
      }
      // reroll the modifiers but keep the item's current rarity (magic stays magic, rare rare)
      const target = item.rarity === "rare" ? 3 + Math.floor(rng() * 4) : 1 + Math.floor(rng() * 2);
      const rerolled = fillTo(base, { ...item, mods: [] }, target, rng);
      return ok(rerolled, "Corrupted: rerolled its modifiers.");
    }
  }
}
