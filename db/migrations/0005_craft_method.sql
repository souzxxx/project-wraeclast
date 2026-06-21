-- Project Wraeclast — craft_method: structured crafting recipes (the craft analogue of
-- farm_strategy). This is the DATA layer the EV engine (Craft 3) will cross with price_snapshot
-- to rank crafts by ROI. Seeded daily and replaced per-league (idempotent), like farm_guide.

CREATE TABLE IF NOT EXISTS craft_method (
    id            BIGSERIAL PRIMARY KEY,
    captured_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    league        TEXT NOT NULL,
    name          TEXT NOT NULL,
    item_base     TEXT NOT NULL,
    archetype     TEXT,                       -- caster | attack | defence | …
    target_mods   JSONB DEFAULT '[]'::jsonb,  -- ["+3 to Level of all Spell Skills", …]
    steps         JSONB DEFAULT '[]'::jsonb,  -- ["step 1", "step 2", …]
    inputs        JSONB DEFAULT '{}'::jsonb,  -- {"Exalted Orb": 6, "Divine Orb": 2}
    success_prob  NUMERIC,                    -- one-attempt chance, 0..1
    output        TEXT,                       -- what the method produces
    sources       JSONB DEFAULT '[]'::jsonb,  -- [{"url": "…", "title": "…"}]
    notes         TEXT
);
CREATE INDEX IF NOT EXISTS idx_craft_method_league_time ON craft_method (league, captured_at DESC);
