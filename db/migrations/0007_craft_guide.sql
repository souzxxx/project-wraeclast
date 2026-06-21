-- Project Wraeclast — craft_guide: full PT-BR craft tutorials (GLM-synthesized daily, Craft 4).
-- The craft analogue of farm_guide: execution-ready guides grounded in the EV-ranked craft
-- methods + craft knowledge. Numbers (expected_cost_div, roi_pct) come from the EV engine, not
-- the LLM. Replaced per-league each run (idempotent), like farm_guide.

CREATE TABLE IF NOT EXISTS craft_guide (
    id                BIGSERIAL PRIMARY KEY,
    captured_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    league            TEXT NOT NULL,
    name              TEXT NOT NULL,
    item_base         TEXT,
    archetype         TEXT,                       -- caster | attack | defence | budget | …
    budget            TEXT,                       -- low | med | high
    mechanics         JSONB DEFAULT '[]'::jsonb,  -- ["essence","omen",…]
    expected_cost_div NUMERIC,                    -- from the EV engine (live-priced inputs)
    roi_pct           NUMERIC,                    -- from the EV engine
    overview          TEXT,
    steps             JSONB DEFAULT '[]'::jsonb,  -- ["passo 1", …] (pt-BR)
    items             JSONB DEFAULT '[]'::jsonb,  -- [{"name","purpose"}] consumables + why
    faq               JSONB DEFAULT '[]'::jsonb,  -- [{"q","a"}] (pt-BR)
    sources           JSONB DEFAULT '[]'::jsonb   -- [{"url","title"}]
);
CREATE INDEX IF NOT EXISTS idx_craft_guide_league_time ON craft_guide (league, captured_at DESC);
