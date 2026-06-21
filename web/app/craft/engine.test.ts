import { describe, expect, it } from "vitest";
import { BASES, getBase } from "./data";
import {
  applyOrb,
  canApply,
  newBase,
  type Base,
  type Item,
  type OrbId,
  type Rng,
} from "./engine";

const wand = getBase("siphoning-wand");

/** rng cycling through a fixed sequence — fully deterministic for tests. */
function seq(values: number[]): Rng {
  let i = 0;
  return () => values[i++ % values.length];
}
const constRng = (v: number): Rng => () => v;

function counts(item: Item) {
  const prefix = item.mods.filter((m) => m.affix === "prefix").length;
  const suffix = item.mods.filter((m) => m.affix === "suffix").length;
  return { prefix, suffix };
}

function apply(item: Item, orb: OrbId, rng: Rng): Item {
  const r = applyOrb(wand, item, orb, rng);
  if (!r.ok) throw new Error(`expected ${orb} to apply: ${r.reason}`);
  return r.item;
}

describe("newBase", () => {
  it("is a normal item with no mods", () => {
    const item = newBase(wand);
    expect(item.rarity).toBe("normal");
    expect(item.mods).toEqual([]);
    expect(item.itemLevel).toBe(wand.itemLevel);
  });
});

describe("canApply gating", () => {
  const normal = newBase(wand);
  const magic = apply(normal, "transmute", seq([0.1, 0.2]));
  const rare = apply(magic, "regal", seq([0.4, 0.3]));

  it("transmute/alchemy/essence require a normal item", () => {
    for (const orb of ["transmute", "alchemy", "essence"] as OrbId[]) {
      expect(canApply(wand, normal, orb)).toBe(true);
      expect(canApply(wand, magic, orb)).toBe(false);
    }
  });
  it("regal requires magic; exalt requires rare", () => {
    expect(canApply(wand, magic, "regal")).toBe(true);
    expect(canApply(wand, normal, "regal")).toBe(false);
    expect(canApply(wand, rare, "exalt")).toBe(true);
    expect(canApply(wand, magic, "exalt")).toBe(false);
  });
  it("annul/divine/chaos require modifiers; chaos not on normal", () => {
    expect(canApply(wand, normal, "annul")).toBe(false);
    expect(canApply(wand, rare, "annul")).toBe(true);
    expect(canApply(wand, normal, "chaos")).toBe(false);
    expect(canApply(wand, rare, "chaos")).toBe(true);
  });
});

describe("deterministic transitions", () => {
  it("transmute makes a magic item with exactly one mod", () => {
    const item = apply(newBase(wand), "transmute", seq([0.1, 0.5]));
    expect(item.rarity).toBe("magic");
    expect(item.mods).toHaveLength(1);
  });

  it("magic never exceeds 1 prefix + 1 suffix", () => {
    let item = apply(newBase(wand), "transmute", seq([0.0, 0.5]));
    const aug = applyOrb(wand, item, "augment", seq([0.9, 0.5]));
    if (aug.ok) item = aug.item;
    expect(item.mods.length).toBeLessThanOrEqual(2);
    expect(counts(item).prefix).toBeLessThanOrEqual(1);
    expect(counts(item).suffix).toBeLessThanOrEqual(1);
    // a full magic item can no longer be augmented
    if (item.mods.length === 2) expect(canApply(wand, item, "augment")).toBe(false);
  });

  it("regal upgrades magic to rare", () => {
    const magic = apply(newBase(wand), "transmute", seq([0.1, 0.5]));
    const rare = apply(magic, "regal", seq([0.6, 0.3]));
    expect(rare.rarity).toBe("rare");
    expect(rare.mods.length).toBeGreaterThanOrEqual(magic.mods.length);
  });

  it("exalting a rare never breaks the 3/3 cap and keeps groups unique", () => {
    let item = apply(newBase(wand), "alchemy", seq([0.13, 0.37, 0.61, 0.07, 0.91, 0.5, 0.29]));
    expect(item.rarity).toBe("rare");
    // hammer it with exalts using varied rng
    const rng = seq([0.05, 0.17, 0.41, 0.63, 0.82, 0.29, 0.55, 0.71, 0.09, 0.93]);
    for (let i = 0; i < 12; i++) {
      const r = applyOrb(wand, item, "exalt", rng);
      if (r.ok) item = r.item;
    }
    expect(counts(item).prefix).toBeLessThanOrEqual(3);
    expect(counts(item).suffix).toBeLessThanOrEqual(3);
    expect(item.mods.length).toBeLessThanOrEqual(6);
    const groups = item.mods.map((m) => m.group);
    expect(new Set(groups).size).toBe(groups.length); // no duplicate groups
  });

  it("annul removes exactly one modifier", () => {
    const rare = apply(newBase(wand), "alchemy", seq([0.1, 0.4, 0.7, 0.2]));
    const before = rare.mods.length;
    const after = apply(rare, "annul", constRng(0));
    expect(after.mods.length).toBe(before - 1);
  });

  it("chaos keeps the modifier count stable (remove + add)", () => {
    const rare = apply(newBase(wand), "alchemy", seq([0.1, 0.4, 0.7, 0.2, 0.5]));
    const before = rare.mods.length;
    const after = apply(rare, "chaos", seq([0.0, 0.9, 0.5]));
    expect(after.mods.length).toBe(before);
  });

  it("chaos never re-adds the exact modifier it just removed", () => {
    const oneModRare: Item = {
      baseId: wand.id,
      name: wand.name,
      category: wand.category,
      itemLevel: wand.itemLevel,
      rarity: "rare",
      mods: [
        { id: "spell_dmg", group: "spelldmg", affix: "prefix", tierIndex: 1, text: "x", values: [40] },
      ],
    };
    const after = apply(oneModRare, "chaos", seq([0.0, 0.0]));
    expect(after.mods).toHaveLength(1);
    expect(after.mods[0].group).not.toBe("spelldmg"); // removed group excluded from the re-roll
  });

  it("divine keeps mods/tiers and only rerolls values within range", () => {
    const rare = apply(newBase(wand), "alchemy", seq([0.13, 0.37, 0.61, 0.07]));
    const divined = apply(rare, "divine", seq([0.99, 0.99, 0.99, 0.99, 0.99, 0.99]));
    expect(divined.mods.map((m) => m.id)).toEqual(rare.mods.map((m) => m.id));
    expect(divined.mods.map((m) => m.tierIndex)).toEqual(rare.mods.map((m) => m.tierIndex));
    for (const m of divined.mods) {
      const def = wand.mods.find((d) => d.id === m.id)!;
      const tier = def.tiers[m.tierIndex];
      m.values.forEach((v, i) => {
        expect(v).toBeGreaterThanOrEqual(tier.rolls[i][0]);
        expect(v).toBeLessThanOrEqual(tier.rolls[i][1]);
      });
    }
  });

  it("essence guarantees the base's signature modifier", () => {
    const item = apply(newBase(wand), "essence", seq([0.1, 0.4, 0.7]));
    expect(item.rarity).toBe("rare");
    expect(item.mods.some((m) => m.id === wand.signature)).toBe(true);
  });
});

describe("ilvl gating", () => {
  it("never rolls a tier above the item level", () => {
    const lowBase = { ...wand, itemLevel: 10 };
    let item = newBase(lowBase);
    const rng = seq([0.1, 0.3, 0.5, 0.7, 0.9, 0.2, 0.4]);
    item = (applyOrb(lowBase, item, "alchemy", rng) as { ok: true; item: Item }).item;
    for (const m of item.mods) {
      const def = lowBase.mods.find((d) => d.id === m.id)!;
      expect(def.tiers[m.tierIndex].ilvl).toBeLessThanOrEqual(10);
    }
  });
});

describe("vaal outcomes", () => {
  const rare = apply(newBase(wand), "alchemy", seq([0.1, 0.4, 0.7, 0.2]));
  it("low roll does nothing", () => {
    const r = applyOrb(wand, rare, "vaal", constRng(0.1));
    expect(r.ok && r.item.mods.length).toBe(rare.mods.length);
  });
  it("mid roll can remove a modifier", () => {
    const r = applyOrb(wand, rare, "vaal", seq([0.4, 0.0]));
    expect(r.ok && r.item.mods.length).toBe(rare.mods.length - 1);
  });
  it("never converts a Normal item into a rolled rare", () => {
    for (const v of [0.1, 0.4, 0.6, 0.9]) {
      const r = applyOrb(wand, newBase(wand), "vaal", seq([v, 0.5, 0.5, 0.5, 0.5]));
      expect(r.ok && r.item.rarity).toBe("normal");
      expect(r.ok && r.item.mods.length).toBe(0);
    }
  });
  it("reroll keeps the item's rarity (a magic item stays magic)", () => {
    const magic = apply(newBase(wand), "transmute", seq([0.1, 0.5]));
    const r = applyOrb(wand, magic, "vaal", seq([0.9, 0.1, 0.5, 0.5]));
    expect(r.ok && r.item.rarity).toBe("magic");
    expect(r.ok && r.item.mods.length).toBeLessThanOrEqual(2);
  });
});

describe("canApply ↔ applyOrb contract", () => {
  // A base whose only modifier group is a single prefix — once it is on the item, an open
  // suffix/prefix slot has no eligible group left, so exalt must be both un-appliable and failing.
  const tiny: Base = {
    id: "tiny",
    name: "Tiny",
    category: "Test",
    itemLevel: 82,
    signature: "a",
    mods: [{ id: "a", group: "ga", affix: "prefix", tiers: [{ ilvl: 1, text: "+# foo", rolls: [[1, 1]] }] }],
  };
  it("exalt's gating matches whether applyOrb actually succeeds", () => {
    let item = (applyOrb(tiny, newBase(tiny), "transmute", () => 0) as { ok: true; item: Item }).item;
    item = (applyOrb(tiny, item, "regal", () => 0) as { ok: true; item: Item }).item;
    // rare with the one and only prefix group present; slots open but nothing eligible
    expect(item.rarity).toBe("rare");
    expect(canApply(tiny, item, "exalt")).toBe(false);
    expect(applyOrb(tiny, item, "exalt", () => 0).ok).toBe(false);
  });
});

describe("determinism", () => {
  it("same rng sequence yields an identical item", () => {
    const a = apply(newBase(wand), "alchemy", seq([0.13, 0.37, 0.61, 0.07, 0.5]));
    const b = apply(newBase(wand), "alchemy", seq([0.13, 0.37, 0.61, 0.07, 0.5]));
    expect(a).toEqual(b);
  });
});

describe("all bases are well-formed", () => {
  it("each base can be alchemy'd into a valid rare", () => {
    for (const base of BASES) {
      const rng = seq([0.1, 0.3, 0.5, 0.7, 0.9, 0.2, 0.4, 0.6, 0.8]);
      const r = applyOrb(base, newBase(base), "alchemy", rng);
      expect(r.ok).toBe(true);
      if (r.ok) {
        expect(r.item.rarity).toBe("rare");
        const c = counts(r.item);
        expect(c.prefix).toBeLessThanOrEqual(3);
        expect(c.suffix).toBeLessThanOrEqual(3);
        expect(base.mods.some((m) => m.id === base.signature)).toBe(true);
      }
    }
  });
});
