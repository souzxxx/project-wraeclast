# Routine: nightly_agent

> Operating manual for the scheduled cloud agent (runs ~07:17 BRT / 10:17 UTC, comfortably
> after the daily GitHub Actions collection at 02:23 UTC, so it always reads fresh data). It
> assesses everything and does the single highest-value thing it can finish well, then opens a
> PR for the owner to review. Never merges.

## Procedure

```
Read CLAUDE.md, ROADMAP.md, and the skill .claude/skills/poe2-data-collection/SKILL.md.

1. HEALTH FIRST. Run `pip install -e ".[dev]"` then `ruff check .` and `pytest -q`.
   If anything is red, fixing it IS the task for tonight. Also glance at whether the latest
   daily collection looks healthy.

2. PICK ONE THING. If health is green, choose the highest-priority item in ROADMAP.md that
   you can FULLY implement and test in this run (P0 → P1 → P2 → P3). Prefer one complete,
   well-tested change over several half-done ones. If P1's "insight" item applies and the
   day's data is fresh, that's a great low-risk choice.

3. IMPLEMENT on a branch named `claude/nightly-<YYYY-MM-DD>`:
   - Follow existing patterns and conventions (English code/commits; type hints; httpx async;
     pydantic; defensive parsing; never hardcode league/secrets).
   - Add/adjust tests. Keep `ruff check .` and `pytest -q` green.

4. OPEN A PR (do NOT merge). The PR body must state: what you changed, why it was the
   highest-value item, and how you verified it (commands + output). Check the item off in
   ROADMAP.md within the same PR and move it to the "Done" section with the PR number + date.

5. IF NOTHING is worth doing safely tonight, open no PR — just report that and why.
```

## Guardrails
- Touch only what the chosen task needs; no drive-by refactors.
- Don't add heavy dependencies without strong justification.
- Respect external API terms (Reddit stays dormant; YouTube via official API only).
- One PR per run. The owner reviews and merges.
