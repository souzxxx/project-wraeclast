-- Project Wraeclast — knowledge_chunk.discovery_query: record WHICH YouTube search query first
-- surfaced a chunk. This is the attribution the query-productivity analyzer (collector.query_stats)
-- needs to tighten youtube_queries from data — keep the queries whose results actually get cited in
-- guides, drop the dead ones — instead of guessing. Nullable: manual/RSS chunks have no query.

ALTER TABLE knowledge_chunk ADD COLUMN IF NOT EXISTS discovery_query TEXT;
