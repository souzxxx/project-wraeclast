-- Project Wraeclast — initial schema (Neon Postgres + pgvector)
-- Apply with: python -m db.connection migrate   (or psql -f this file)
--
-- IMPORTANT: the VECTOR dimension below MUST equal EMBEDDING_DIM in the environment
-- (z.ai embedding-2 = 1024). If you switch embedding models, create a new migration
-- that ALTERs/recreates the column — pgvector dimension is fixed at DDL time.

CREATE EXTENSION IF NOT EXISTS vector;

-- Economy snapshot (daily, from poe.ninja). Normalized to a base value for history.
CREATE TABLE IF NOT EXISTS price_snapshot (
    id            BIGSERIAL PRIMARY KEY,
    captured_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    league        TEXT NOT NULL,
    item_type     TEXT NOT NULL,            -- currency | unique | base | gem
    name          TEXT NOT NULL,
    chaos_value   NUMERIC,
    divine_value  NUMERIC,
    listing_count INT
);
CREATE INDEX IF NOT EXISTS idx_price_league_time ON price_snapshot (league, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_price_name ON price_snapshot (league, name);

-- Farm strategies (curated by GLM). profit/hour is computed, not free text.
CREATE TABLE IF NOT EXISTS farm_strategy (
    id                  BIGSERIAL PRIMARY KEY,
    captured_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    league              TEXT NOT NULL,
    name                TEXT NOT NULL,
    est_profit_per_hour NUMERIC,
    investment_required NUMERIC,
    risk                TEXT,                -- low | med | high
    summary             TEXT,
    sources             JSONB DEFAULT '[]'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_farm_league_time ON farm_strategy (league, captured_at DESC);

-- Owner profile (ninja-build in Phase 0, clipboard/PoB in Phase 1, OAuth in Phase 2).
CREATE TABLE IF NOT EXISTS my_snapshot (
    id                   BIGSERIAL PRIMARY KEY,
    captured_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    character_name       TEXT,
    char_class           TEXT,
    level                INT,
    total_currency_chaos NUMERIC,            -- net worth, normalized (OAuth-only for now)
    gear                 JSONB DEFAULT '{}'::jsonb,
    gems                 JSONB DEFAULT '[]'::jsonb,
    passive_tree         JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_my_snapshot_time ON my_snapshot (captured_at DESC);

-- Community knowledge for RAG. Embedding dim must match EMBEDDING_DIM.
CREATE TABLE IF NOT EXISTS knowledge_chunk (
    id          BIGSERIAL PRIMARY KEY,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_url  TEXT,
    title       TEXT,
    content     TEXT NOT NULL,
    embedding   VECTOR(1024)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_url ON knowledge_chunk (source_url);
-- Approximate-nearest-neighbor index for cosine similarity retrieval.
CREATE INDEX IF NOT EXISTS idx_knowledge_embedding
    ON knowledge_chunk USING hnsw (embedding vector_cosine_ops);
