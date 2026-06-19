# Roadmap — Project Wraeclast

Prioritized backlog for the **nightly agent** (see `routines/nightly_agent.md`). The agent
picks the highest-value item it can fully complete in one run, implements it on a `claude/`
branch, runs ruff + pytest, opens a PR, and checks the item off here in that same PR.

> Ordering = priority. Health first, then the daily intelligence layer, then features.
> Keep edits focused and tested. Never merge — the owner reviews.

## P0 — Health (always check first)
- [ ] `ruff check .` and `pytest -q` are green; if not, fix the breakage.
- [ ] No daily-collection step is silently failing (check the latest GitHub Actions run / logs).
- [ ] No secret committed; `.env` stays gitignored.

## P1 — Daily intelligence layer
- [x] Write a concise "what changed today" insight into `reports/` (top farms vs yesterday,
      notable price moves, new community guides) — human-readable, links back to sources.
      _(see Done)_
- [x] Flag anomalies (a currency that jumped/dropped sharply; a farm that left/entered the top 5).
      _(see Done — same module)_

## P2 — Features (pick the top unchecked one)
- [x] Enrich the Cérebro graph: add ALL `knowledge_chunk` videos as `source` nodes linked to
      the league. Update `build_graph` + its tests. _(see Done)_
- [x] **Stable farm comparison across runs** — `canonical_farm_key` collapses GLM renames by
      core mechanic in `daily_insight.farm_ranking_changes`, killing phantom enter/left churn.
      _(see Done)_
- [ ] `/build` meta source: collect a few popular ninja builds for the owner's class so the
      build-diff stops degrading to "not comparable".
- [ ] Price history: store/show sparklines per currency on the "Hoje" tab (data already in
      `price_snapshot` over time).
- [ ] Craft/price alerts: detect notable moves and surface them on the site + daily report.
- [ ] Mobile layout polish for the dashboard, farms, and graph.
- [ ] Phase 2 (optional, only if the owner enables it): GGG OAuth 2.1 + PKCE for real-time
      stash currency (net worth) and off-ladder characters. Scaffolding in `collector/ggg_client.py`.

## P3 — Tech debt / quality
- [ ] Add tests for any module under 80% of its public surface.
- [ ] Tighten the YouTube queries based on which sources actually inform good guides.

---

### Done (agent appends here)
<!-- The nightly agent moves completed items here with the PR number + date. -->
- **2026-06-19** — `canonical_farm_key` in `daily_insight`: collapse run-to-run GLM farm
  renames (e.g. "Abyss Lich Farming"/"Abyss Farm" → `abyss`) by core mechanic, so the
  day-over-day diff shows real ranking changes, not rename noise. Also dedupes same-day
  reruns. +4 tests. (Live: phantom anomalies 8 → 2.)
- **2026-06-19** — Daily "what changed today" insight + anomaly flagging (`scripts/daily_insight.py`):
  day-over-day diff of farm ranking (entered/left/moved within top 5), notable currency price
  moves (relative + absolute thresholds), and community sources captured today, rendered to an
  Obsidian-friendly note in `reports/`. Sharp moves and top-5 changes are flagged as anomalies.
  Pure comparison core is unit-tested offline (10 tests); wired into `run_daily` after the export.
- **2026-06-18** — Enrich the Cérebro graph with all `knowledge_chunk` videos as `source`
  nodes linked to the league (deduped with guide-cited sources). Designed by the nightly
  routine (which couldn't push due to missing write access); delivered locally.
