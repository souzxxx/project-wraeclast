# Routine: daily_curation

> Definition for a Claude Code Routine (runs in Anthropic's cloud, ~1x/day, no local file
> access). It does the **intelligent curation** layer on top of the raw collection that
> Cloudflare Cron already wrote to Neon. Push only to `claude/` branches — owner reviews.

## Schedule
Once per day, early morning (after the Cloudflare Cron collection window).

## Preconditions
- `NEON_DATABASE_URL`, `GLM_API_KEY` available as routine env vars/secrets.
- Today's raw data already in Neon (`price_snapshot`, `knowledge_chunk`) via Cloudflare Cron.

## Task

```
Read CLAUDE.md and the skill poe2-data-collection.

1. Run `python -m collector.curate` to pull today's knowledge_chunk + latest price_snapshot,
   ask GLM for the top farm strategies, compute profit/hour, and write farm_strategy.
2. Run `python -m scripts.export_obsidian` to regenerate today's Obsidian report.
3. In a `claude/daily-<date>` branch, commit the generated Obsidian markdown under vault/
   with a conventional commit (`chore: daily curation <date>`), and open a PR summarizing:
   - the top 3 farm strategies and why they gained traction today,
   - any notable price movement,
   - anything that failed to collect.
Do NOT merge — leave the PR for the owner to review.
```

## Notes
- Cap ~15 runs/day/account, shares the subscription limit. One nightly run is plenty.
- If a step fails, report it in the PR body instead of silently skipping.
- This routine is the "intelligent" layer; the reliable raw collection is Cloudflare Cron
  hitting `POST /internal/run` (see cloudflare/). Either path is resilient on its own.
