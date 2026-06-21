-- Project Wraeclast — Craft 3 columns on craft_method:
--   mechanics: which craft systems the method spans (currency | essence | omen | abyss | rune |
--              catalyst | meta) — craft is not just currency, so the EV engine + chat reason across all.
--   output_value_div: a curated estimate of the crafted item's sale value (the EV engine crosses
--              this with the live-priced inputs to rank methods by ROI).
-- Idempotent (IF NOT EXISTS); existing rows backfill on the next daily seed.

ALTER TABLE craft_method ADD COLUMN IF NOT EXISTS mechanics JSONB DEFAULT '[]'::jsonb;
ALTER TABLE craft_method ADD COLUMN IF NOT EXISTS output_value_div NUMERIC;
