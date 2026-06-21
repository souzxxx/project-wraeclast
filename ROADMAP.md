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
### Craft intelligence 👑 (epic — make the agent the "king of craft")
> Same engine as farms, aimed at crafting: rank methods by **calculated EV** — input cost
> (via `price_snapshot`) × success chance × output value — never prose. Build it bottom-up,
> one layer per nightly run. Craft YouTube queries are already seeded in `config.py`.
- [x] **Craft 1 — knowledge corpus**: curated seed + craft `knowledge_chunk` topic tagging,
      so RAG/chat can filter the craft lane specifically. _(see Done)_
- [x] **Craft 2 — `craft_method` model**: structured methods (item base, ordered steps, inputs
      `{currency: qty}`, target mods, success probability). Pydantic schema + `db/migrations` + tests.
      _(see Done)_
- [x] **Craft 3 — calculated EV** (the differentiator): pure core crossing `craft_method` inputs
      with `price_snapshot` → expected cost (incl. retries) vs output value → ROI ranked per method.
      Unit-tested offline, same as farm profit/hour. _(see Done)_
- [ ] **Craft 4 — `craft_guide` (PT-BR)**: GLM generates per-archetype/budget guides, mirroring
      `guides.py` / `farm_guide`; refreshed daily in `run_daily`. This is the "huge craft guide".
- [ ] **Craft 5 — site + chat surface**: a "Craft" tab with EV-ranked methods + the guides.
- [ ] **Craft 6 — craft alerts**: flag when a craft crosses into profit (input dropped / output
      rose); surface on the site + daily report. _(was the standalone "Craft/price alerts" item)_

### Other features
- [ ] `/build` meta source: collect a few popular ninja builds for the owner's class so the
      build-diff stops degrading to "not comparable".
- [x] Price history: store/show sparklines per currency on the "Hoje" tab (data already in
      `price_snapshot` over time). _(see Done)_
- [ ] Mobile layout polish for the dashboard, farms, and graph.
- [ ] Phase 2 (optional, only if the owner enables it): GGG OAuth 2.1 + PKCE for real-time
      stash currency (net worth) and off-ladder characters. Scaffolding in `collector/ggg_client.py`.

## P3 — Tech debt / quality
- [ ] Add tests for any module under 80% of its public surface.
- [ ] Tighten the YouTube queries based on which sources actually inform good guides.

---

### Done (agent appends here)
<!-- The nightly agent moves completed items here with the PR number + date. -->
- **2026-06-21** — Craft 3: calculated EV. Pure `api/craft_ev` crosses each method's `inputs`
  with live `price_snapshot` → expected cost (incl. retries via `success_prob`) → ROI vs the
  curated `output_value_div`, ranked (fully-priced first, `missing_prices` flagged). Model gains
  `mechanics` + `output_value_div` (migration `0006`); seed enriched to span currency, essence,
  **omen, abyss, rune, catalyst**; `GET /craft/ev`; top methods fed into chat RAG context. +9 tests.
- **2026-06-21** — Craft 2 (#6): structured `craft_method` model (item_base, target_mods, ordered
  steps, `inputs` {currency: qty}, validated `success_prob`) + migration `0005` + repo
  `replace_craft_methods`/`latest_craft_methods` + curated seed of 5 source-attributed PoE2 0.5
  methods (incl. a monk quarterstaff), ingested daily. `daily.yml` now auto-applies migrations so
  schema changes deploy without intervention. +6 offline tests. Next: Craft 3 (EV/ROI).
- **2026-06-21** — Craft 1: tag `knowledge_chunk`s by `topic` (`craft` | `farm`) so RAG/chat can
  filter the craft lane. New pure `collector/topics.classify_topic` (offline keyword heuristic —
  one strong craft term, or two weak ones → `craft`, else `farm`), wired through `KnowledgeDoc`/
  `ingest_documents` (auto-classify when a producer doesn't set it) and the craft seed (tagged
  `craft` explicitly). Migration `0004` adds the `topic` column + index; `upsert_knowledge_chunk`
  persists it; `search_knowledge(..., topic=)` filters; chat narrows to craft only for clearly
  craft questions via `topic_for_question` (farm/general stay broad). +11 offline tests.
- **2026-06-20** — Price-history sparklines on the "Hoje" tab. Pure core
  `api/price_history.build_sparklines` buckets `price_snapshot` rows into one point per
  calendar day per currency (latest snapshot each day wins, defensive vs intra-day reruns),
  drops single-point series, and sorts by latest chaos value with a first→last change %.
  New `db.repo.price_history_since` query + `GET /price-history` route + an inline-SVG
  sparkline list on the home page (green/red trend, change %). +9 offline tests.
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
