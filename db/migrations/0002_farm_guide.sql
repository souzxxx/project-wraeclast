-- Project Wraeclast — farm_guide: full "concretized" farm tutorials (GLM-synthesized daily).
-- Distinct from farm_strategy (the live ranking): these are evergreen-style step-by-step guides.

CREATE TABLE IF NOT EXISTS farm_guide (
    id              BIGSERIAL PRIMARY KEY,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    league          TEXT NOT NULL,
    name            TEXT NOT NULL,
    profit_per_hour NUMERIC,
    risk            TEXT,                       -- low | med | high
    target_currency TEXT,
    overview        TEXT,
    steps           JSONB DEFAULT '[]'::jsonb,  -- ["step 1", "step 2", ...]
    items           JSONB DEFAULT '[]'::jsonb,  -- [{"name": "...", "purpose": "..."}]
    faq             JSONB DEFAULT '[]'::jsonb,  -- [{"q": "...", "a": "..."}]
    sources         JSONB DEFAULT '[]'::jsonb   -- [{"url": "...", "title": "..."}]
);
CREATE INDEX IF NOT EXISTS idx_farm_guide_league_time ON farm_guide (league, captured_at DESC);
