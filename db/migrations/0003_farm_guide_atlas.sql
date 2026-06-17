-- Add per-farm Atlas guidance (how to spec/level the atlas tree for the strategy).
ALTER TABLE farm_guide ADD COLUMN IF NOT EXISTS atlas TEXT;
