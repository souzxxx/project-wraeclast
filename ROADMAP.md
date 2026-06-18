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
- [ ] Write a concise "what changed today" insight into `reports/` (top farms vs yesterday,
      notable price moves, new community guides) — human-readable, links back to sources.
- [ ] Flag anomalies (a currency that jumped/dropped sharply; a farm that left/entered the top 5).

## P2 — Features (pick the top unchecked one)
- [x] Enrich the Cérebro graph: add ALL `knowledge_chunk` videos as `source` nodes linked to
      the league. Update `build_graph` + its tests. _(see Done)_
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
- **2026-06-18** — Enrich the Cérebro graph with all `knowledge_chunk` videos as `source`
  nodes linked to the league (deduped with guide-cited sources). Designed by the nightly
  routine (which couldn't push due to missing write access); delivered locally.
