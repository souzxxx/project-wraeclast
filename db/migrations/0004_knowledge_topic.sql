-- Project Wraeclast — tag knowledge_chunk with a coarse topic ('craft' | 'farm') so RAG/chat
-- can narrow retrieval to a single lane (the craft-intelligence epic). Backfilled by the next
-- ingest run (upsert sets topic); existing rows stay NULL until then, which search tolerates.

ALTER TABLE knowledge_chunk ADD COLUMN IF NOT EXISTS topic TEXT;  -- craft | farm
CREATE INDEX IF NOT EXISTS idx_knowledge_topic ON knowledge_chunk (topic);
