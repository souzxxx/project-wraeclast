-- Project Wraeclast — meta_build: popular builds aggregated from poe.ninja, per character class.
-- This is the meta REFERENCE the build-diff (api/build_diff) compares the owner's character
-- against, so /build stops degrading to "not comparable". Replaced per-league each day
-- (idempotent), like craft_method / farm_guide.

CREATE TABLE IF NOT EXISTS meta_build (
    id           BIGSERIAL PRIMARY KEY,
    captured_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    league       TEXT NOT NULL,
    char_class   TEXT NOT NULL,
    sample_size  INTEGER NOT NULL DEFAULT 0,  -- ladder characters of this class in the aggregate
    gems         JSONB DEFAULT '[]'::jsonb,   -- [{"name": "Comet", "usage_pct": 72.0}, …]
    sources      JSONB DEFAULT '[]'::jsonb    -- [{"url": "…", "title": "…"}]
);
CREATE INDEX IF NOT EXISTS idx_meta_build_league_class_time
    ON meta_build (league, char_class, captured_at DESC);
