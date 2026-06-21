# Design — Craft tab (live crafting bench), Chat tab, and frontend uplift

- **Date:** 2026-06-21
- **Status:** Approved (owner) — ready for implementation
- **Author:** Claude (brainstormed with owner)
- **Topic:** A new `/craft` tab with an interactive crafting bench + live cost, a dedicated
  multi-turn `/chat` tab, and an on-theme visual uplift across the whole site.

---

## 1. Context & goals

The site (`web/`, Next.js App Router) has three tabs — `Hoje` (`/`), `Farms` (`/farms`),
`Cérebro` (`/cerebro`) — in a dark/gold PoE-flavored style that is functional but plain. The
chat and "add knowledge" widgets are buried at the bottom of the home page.

We have a `knowledge_chunk.topic = 'craft'` lane (shipped 2026-06-21) but **no structured craft
EV engine yet** — Craft 2 (`craft_method` model) and Craft 3 (calculated EV) are still on the
roadmap for the nightly agent. So the Craft tab is built from what exists today (craft knowledge
text + live currency prices) and is designed so EV-ranked methods plug in later without rework.

**Goals**
1. A `/craft` tab whose centerpiece is an **interactive crafting bench** that teaches the PoE2
   currency flow and shows a **live cost ledger** from real poe.ninja prices — plus the curated
   craft guides from the corpus.
2. A dedicated `/chat` tab with a **multi-turn** conversational UI (history + follow-ups).
3. An **on-theme visual uplift** applied to every tab — keep the dark/gold soul, raise the bar.

**Non-goals (v1)** — see §9.

---

## 2. Locked decisions

| Decision | Choice |
|---|---|
| Simulator type | **Hybrid**: interactive bench + live currency cost ledger |
| Redesign depth | **Elevate the current identity** (rarity colors, type/spacing scale, depth, motion, shared components) across all tabs |
| Chat | **Multi-turn** conversation with history (small backend change) |
| Mod fidelity | Curated, hand-authored mod pool per base — labeled illustrative, **not** GGG weights |
| Cost fidelity | **Real** — live `price_snapshot` values via the API |

---

## 3. Architecture overview

**Frontend (all new UI built with the `frontend-design` skill):**
- `web/app/globals.css` — design-system overhaul: color tokens (incl. item-rarity colors),
  type scale, spacing scale, elevation/glow, motion, reusable component classes.
- `web/app/nav.tsx` — add `Craft` and `Chat`; final order: **Hoje · Farms · Craft · Cérebro · Chat**.
- `web/app/page.tsx` — declutter: remove the embedded Chat + AddKnowledge (they move to `/chat`).
- `web/app/craft/page.tsx` — NEW: bench + guides.
- `web/app/craft/engine.ts` — NEW: **pure** craft simulation logic (no React, unit-testable).
- `web/app/craft/data.ts` — NEW: curated bases, mod pools, orb definitions.
- `web/app/chat/page.tsx` — NEW: multi-turn chat + a discreet AddKnowledge panel.
- `web/app/lib.ts` — shared types/helpers (API base already here).

**Backend (small, read-only, tested — `api/`, `db/`):**
- `GET /prices` — latest currency prices for the bench (reuses `repo.latest_prices`).
- `GET /craft/knowledge` — latest `topic='craft'` chunks for the guides (new repo query + route).
- `POST /chat` — gains optional `history`; `api/rag.answer` threads prior turns into GLM.

**No new tables, no migration, no new writes.** (See §8.)

---

## 4. The crafting bench (the centerpiece)

### 4.1 Item & affix model (PoE2 0.5 rules)
- An item has a **rarity** (`normal | magic | rare`), a **base** (with `item_level`), and a list
  of rolled **mods**, each tagged `prefix | suffix`, with a `group` (to forbid duplicate groups)
  and a chosen `tier` with numeric value(s).
- Affix caps: **magic** = 1 prefix + 1 suffix (max 2). **rare** = 3 prefix + 3 suffix (max 6).
- `item_level` gates which mod tiers are eligible (a tier has a minimum `ilvl`).

### 4.2 Orb mechanics (deterministic transitions are exact; rolled mod is drawn from the curated pool)
| Orb | Precondition | Effect |
|---|---|---|
| Transmutation | normal | → magic; add 1 random eligible mod |
| Augmentation | magic, open affix | add 1 random eligible mod |
| Regal | magic | → rare; add 1 random eligible mod |
| Exalted | rare, open affix (≤3/side) | add 1 random eligible mod |
| Annulment | has ≥1 mod | remove 1 random mod |
| Alchemy | normal | → rare with 4 random mods |
| Chaos | magic/rare | remove 1 random mod **and** add 1 random mod (PoE2 0.5 behavior) |
| Divine | has ≥1 mod | reroll numeric values of all mods within their tier ranges |
| Vaal | any | corrupt — one of a small labeled outcome set (reroll/add/remove/no-op) |
| Essence (1–2) | normal | → rare guaranteeing one mod of the essence's type, fill the rest |

Mod selection rule: pick from `data.ts` mods whose `affix` side has a free slot, whose `ilvl ≤
item_level`, excluding groups already present; choose the highest eligible tier band by default
(documented), value rolled uniformly within range.

### 4.3 Engine shape (`engine.ts`, pure)
```ts
type Rarity = "normal" | "magic" | "rare";
type Mod = { id: string; group: string; affix: "prefix" | "suffix";
             text: string; tier: number; values: number[] };
type Item = { base: string; itemLevel: number; rarity: Rarity; mods: Mod[] };
type OrbId = "transmute" | "augment" | "regal" | "exalt" | "annul"
           | "alchemy" | "chaos" | "divine" | "vaal" | "essence_x";

// Pure. `rng` injected for deterministic tests. Returns the new item + a human log line,
// or an `error` (e.g. "Exalted needs a rare with an open affix") when the orb can't apply.
applyOrb(item: Item, orb: OrbId, rng: () => number):
  { ok: true; item: Item; log: string } | { ok: false; reason: string };

canApply(item: Item, orb: OrbId): boolean;   // for enabling/disabling buttons
newBase(baseId: string): Item;               // fresh normal item
```
Determinism via an injected `rng` makes every transition unit-testable offline (Vitest).

### 4.4 Live cost ledger
- On mount, the page fetches `GET /prices`. Each orb maps to its poe.ninja `name`
  (e.g. `exalt → "Exalted Orb"`). Every successful `applyOrb` appends `{ orb, chaos_value }`
  to a ledger; the panel shows **total chaos** and the **divine** equivalent (via the Divine
  Orb's chaos price), with a per-orb breakdown. Reset clears item + ledger; Undo steps back one.
- If a price is missing, that orb shows "preço n/d" and contributes 0 — the bench still works.

### 4.5 Honesty
A persistent note on the bench: *deterministic transitions follow PoE2 0.5 rules exactly; the
mod pool shown is a small curated, illustrative subset — not GGG's real spawn weights — so use it
to learn the flow, not to predict your exact roll. Costs are real (live poe.ninja prices).*

### 4.6 Craft guides block
Below the bench: cards from `GET /craft/knowledge` (title, source link, snippet), styled like the
Farms guides. Empty-state and error-state handled like the existing pages.

---

## 5. The Chat tab (multi-turn)

- `web/app/chat/page.tsx`: a message thread (user/assistant bubbles), input pinned at the bottom,
  sources rendered under each assistant message. Same password gate (localStorage `wraeclast_chat_token`)
  already used today; 401 clears the token, 503 = not configured.
- Client keeps an in-memory `messages: {role, content}[]` and sends the **last ~6** turns as
  `history` with each request (bound to cap tokens).
- Backend: `ChatRequest` gains `history: list[{role: "user"|"assistant", content: str}] = []`
  (length- and size-bounded server-side). `api/rag.answer(question, history)` prepends the
  trimmed history into the GLM message list, after the system prompt and RAG context, before the
  current question. RAG retrieval still keys off the **current** question (incl. the existing
  craft-lane narrowing). Backwards compatible: omitting `history` behaves exactly as today.
- A discreet collapsible **AddKnowledge** panel lives on this tab (same `/ingest` call, same gate).

---

## 6. Design system uplift (frontend-design skill)

Applied in `globals.css` and reused everywhere:
- **Tokens:** existing bg/panel/border/text/muted/accent **plus** rarity colors
  — `--rarity-normal #c8c8c8`, `--rarity-magic #8a8aff`, `--rarity-rare #ffff77`,
  `--rarity-unique #af6025`, `--rarity-currency #c9a227` — and semantic up/down already present.
- **Type scale & spacing scale**, consistent radii, and arcane depth (subtle inner glow on panels,
  layered borders) — no heavy textures, keep it fast.
- **Motion:** hover/focus transitions, a short "slam" animation when an orb is applied, smooth
  rarity-color transitions. Respect `prefers-reduced-motion`.
- **Components:** `.card`, `.btn` (+ `.btn-ghost`), `.tag`/`.pill`, section headers, list rows —
  refactor the current ad-hoc styles onto these so Hoje/Farms/Cérebro inherit the uplift too.
- Mobile: the bench collapses to a single column; nav wraps cleanly.

---

## 7. Data flow

```
/craft  ──GET /prices──────────►  repo.latest_prices(league)      (read)
        ──GET /craft/knowledge─►  repo.latest_craft_knowledge()   (read)
        bench logic + ledger run fully client-side (engine.ts + data.ts)

/chat   ──POST /chat {question, history}──►  rag.answer(q, history)
        password via X-Access-Token header (unchanged gate)
```

---

## 8. Cost / Neon impact (owner asked — verified)

- **No new tables, no migration, no new writes.** `/prices` and `/craft/knowledge` are read-only
  `SELECT`s on existing `price_snapshot` / `knowledge_chunk`. The bench is client-side.
- **Storage growth: zero** beyond what the daily collector already writes.
- **Compute:** a couple of light indexed reads when someone opens `/craft` or `/chat`. Neon free
  tier autosuspends on idle and bills compute-hours; a personal-traffic site won't dent it.
- **LLM tokens:** multi-turn chat sends ≤6 prior turns → modestly more tokens per question, but
  GLM is the flat-rate Coding Plan (no per-call overage). `/chat` stays password-gated and
  fail-closed. **No free-tier limit is at risk** (YouTube/Gemini are untouched by this change).

---

## 9. Out of scope (v1)

- Omens (they modify other orbs — extra mechanic layer) — future.
- Full Monte-Carlo EV / success-probability simulation — that **is** Craft 3 (nightly agent).
- EV-ranked craft methods on the tab — plug in once Craft 2/3 land (the tab is built to host them).
- GGG real mod spawn weights / full base+mod database — curated subset only.

---

## 10. Testing strategy

- **Backend (pytest, offline — matches repo culture):**
  - `/prices` route returns the expected shape (mock `latest_prices`).
  - `repo.latest_craft_knowledge` builds the right query; `/craft/knowledge` route shape.
  - `rag.answer` threads `history` correctly (prior turns present, bounded; empty history ==
    today's behavior); `ChatRequest` validates/bounds `history`.
- **Craft engine (Vitest, pure + deterministic via injected rng):**
  - each orb's precondition gating (`canApply`) and transition (rarity change, affix caps 1/1,
    3/3, group-dedup, ilvl gating), annul/chaos/divine behavior, vaal outcome set.
  - cost mapping: orb → price name → ledger total + divine conversion.
  - (Adds a minimal Vitest setup to `web/` — dev-only, no runtime/deploy impact.)
- **Manual/visual:** run the app, exercise the bench end-to-end, confirm live prices populate.

---

## 11. Implementation phases (build order)

1. **Backend** (TDD): `GET /prices`; `repo.latest_craft_knowledge` + `GET /craft/knowledge`;
   multi-turn `history` in `ChatRequest` + `rag.answer`. Tests green, ruff clean.
2. **Design system**: rework `globals.css` (tokens, scale, components, motion); update `nav.tsx`;
   declutter `page.tsx`. Verify existing tabs still look right (now uplifted).
3. **Craft engine + data** (TDD with Vitest): `engine.ts`, `data.ts` (curated bases incl. a
   quarterstaff for the owner's monk), green tests.
4. **Craft tab UI** (frontend-design): bench component (item card, orb buttons, ledger, reset/undo,
   honesty note) + guides block wired to `/craft/knowledge` and `/prices`.
5. **Chat tab UI** (frontend-design): multi-turn thread, password gate, sources, AddKnowledge panel.
6. **Verify**: `ruff`, `pytest`, `vitest`, and a manual run of every tab. Then a focused review pass.

---

## 12. File manifest

**New:** `web/app/craft/page.tsx`, `web/app/craft/engine.ts`, `web/app/craft/data.ts`,
`web/app/chat/page.tsx`, `api/routes/craft.py`, plus tests
(`tests/test_craft_route.py`, `tests/test_chat_history.py`, `tests/test_prices_route.py`,
`web/app/craft/engine.test.ts`) and a small Vitest config in `web/`.

**Changed:** `web/app/globals.css`, `web/app/nav.tsx`, `web/app/page.tsx`, `web/app/lib.ts`,
`api/main.py` (register craft route + GET /prices), `api/routes/chat.py` (`history` field +
`ChatTurn` model, both local to this module), `api/rag.py` (thread history), `db/repo.py`
(add `latest_craft_knowledge`).
