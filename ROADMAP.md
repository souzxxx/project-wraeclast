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
- [x] **Craft 4 — `craft_guide` (PT-BR)**: GLM generates per-archetype/budget guides, mirroring
      `guides.py` / `farm_guide`; refreshed daily in `run_daily`. This is the "huge craft guide".
      _(see Done)_
- [x] **Craft 5 — site + chat surface**: a "Craft" tab with EV-ranked methods + the guides.
      _(see Done — chat surface already shipped in Craft 3.5)_
- [x] **Craft 6 — craft alerts**: flag when a craft crosses into profit (input dropped / output
      rose); surface on the site + daily report. _(see Done — the craft epic is complete 👑)_

### Other features
- [x] `/build` meta source: collect a few popular ninja builds for the owner's class so the
      build-diff stops degrading to "not comparable". _(see Done)_
- [x] Price history: store/show sparklines per currency on the "Hoje" tab (data already in
      `price_snapshot` over time). _(see Done)_
- [ ] Mobile layout polish for the dashboard, farms, and graph.
- [ ] Phase 2 (optional, only if the owner enables it): GGG OAuth 2.1 + PKCE for real-time
      stash currency (net worth) and off-ladder characters. Scaffolding in `collector/ggg_client.py`.

## P3 — Tech debt / quality
- [ ] Add tests for any module under 80% of its public surface.
      _(in progress — `collector/ninja_build_client.py` 39% → 81%, see Done 2026-06-23;
      `collector/youtube_client.py` 46% → 99%, see Done 2026-06-24;
      `collector/ninja_client.py` 51% → 99%, see Done 2026-06-25;
      `collector/llm.py` 25% → 100%, see Done 2026-06-26.
      Still under 80%: `db/repo.py`, `db/connection.py` (need a live DB).)_
- [ ] Tighten the YouTube queries based on which sources actually inform good guides.

---

### Done (agent appends here)
<!-- The nightly agent moves completed items here with the PR number + date. -->
- **2026-06-26** — P3 coverage: harden `collector/llm.py` (25% → 100% — clears the 80% bar;
  this was the last non-DB module under the line). The shared GLM (z.ai) chat helper was the
  most-used LLM seam in the project (curate/guides/craft_guides/chat all route through it) yet
  only its module import was covered — `_client` construction/guarding and the whole `glm_chat`
  streaming body were untested. Added offline tests (no network, OpenAI client faked) for:
  `_client` (RuntimeError when `GLM_API_KEY` unset; api_key/base_url/timeout passed through to
  `OpenAI`); and `glm_chat` (assembles streamed deltas in order; skips chunks with no choices /
  `None` delta / empty content; uses `glm_chat_model` + `glm_max_tokens` defaults with
  `stream=True` and no `with_options`; honors model/temperature/max_tokens overrides; routes a
  per-call `timeout` through `with_options(timeout=...)` while still issuing exactly one create).
  No production code changed — tests only. +7 offline tests (190 → 197), ruff clean. Only
  `db/repo.py` + `db/connection.py` (need a live DB) remain sub-80%.
- **2026-06-25** — P3 coverage: harden `collector/ninja_client.py` (51% → 99% — clears the
  80% bar). The economy collector is the heart of the project but only its pure
  `normalize_exchange` + config parsing were tested; the network/dispatch surface was untested.
  Added offline tests for: `_num` (happy path + TypeError/ValueError → None); `normalize_exchange`
  edge branches (non-dict line skipped, unknown core base recorded under divine, positional
  item fallback when no id match); `fetch_economy` (per-category GET + distinct `item_type`
  tagging; one 500-ing category swallowed without sinking the rest) mocked with `respx`; `run`
  (fetch + DB write wiring, monkeypatched); `explore` (dict sampled-to-2 + non-dict payload);
  and the `_main` run/explore/default/unknown-command dispatch. No production code changed —
  tests only. +12 offline tests (178 → 190), ruff clean. Only `db/repo.py`, `db/connection.py`
  (need a live DB) and `collector/llm.py` remain sub-80%.
- **2026-06-24** — P3 coverage: harden `collector/youtube_client.py` (46% → 99% — clears the
  80% bar). Added offline tests for the previously-untested async surface: `fetch_youtube`
  (no-API-key short-circuit; cross-query id dedup keeping insertion order; a failing `search.list`
  query swallowed without sinking the run; a failing `videos.list` batch dropped, not fatal; 60
  ids batched 50 + 10) mocked with `respx`; `run` (ingest wiring, monkeypatched); `explore`; and
  the `_main` run/explore/unknown-command dispatch. No production code changed — tests only.
  +10 offline tests (168 → 178), ruff clean. Remaining sub-80% modules noted under the open P3 item.
- **2026-06-23** — P3 coverage: harden `collector/ninja_build_client.py` (39% → 81% — clears
  the 80% bar). Added offline tests for the previously-untested surface: `fetch_my_build`
  (happy path + empty/non-list/HTTP-404 → `CharacterNotOnLadder`) mocked with `respx`; `run`
  (ninja success, off-ladder-without-PoB → False, PoB-code fallback) with the DB write
  monkeypatched; plus `_profile_endpoint`, `_int`, `from_pob_code` (garbage → `PoBParseError`),
  the `pick_character` first-char fallback, defensive `normalize_profile_character`, and the
  `_main` unknown-command path. No production code changed — tests only. +14 offline tests
  (154 → 168), ruff clean. Remaining sub-80% modules noted under the open P3 item.
- **2026-06-22** — `/build` meta source. New `collector/ninja_meta_client.py` aggregates
  poe.ninja's PoE2 builds ladder per character class: groups characters by class, counts each
  skill gem once per character, and keeps the most-used gems (≥`ninja_meta_min_usage`, capped,
  deterministic tie-break) as a `MetaBuild`. Pure `aggregate_meta_builds` + defensive
  `extract_characters`/`_char_gems` (tolerate list-or-wrapped payloads and gem field-name drift).
  Model `MetaBuild` + migration `0008_meta_build` + repo `replace_meta_builds`/`latest_meta_build`
  (per-league idempotent daily replace). Route `_load_meta_build` now reads the owner's class meta
  so `/build` compares for real (still degrades gracefully when none collected). Wired into
  `run_daily` after `my_build`. The live builds path is config-driven (`ninja_builds_path`,
  unconfirmed for PoE2 — validated in deploy via the `explore` CLI, like the other ninja clients).
  +11 offline tests.
- **2026-06-21** — Craft 6: craft profit alerts (**craft epic complete 👑**). Pure
  `api/craft_alerts.craft_alerts` diffs craft EV across the two latest price days → flags methods
  that crossed INTO / OUT of profit (driver = live input prices). Wired into `scripts/daily_insight`
  (a "Craft alerts" report section + an anomaly line) and exposed via `GET /craft/alerts`, surfaced
  as a banner atop the Craft tab. Conservative (only fires on a real 0%-line crossing). +7 tests.
- **2026-06-21** — Craft 5: site surface. The "Craft" tab now leads with **EV-ranked methods**
  (`GET /craft/ev`, ROI ranking with cost/mechanics/priced flag, green/red ROI, near-zero-cost
  shown as a multiplier), the **PT-BR guides** accordion (`GET /craft/guides` — overview/steps/
  insumos/FAQ), then the interactive bench, then sources. Restructured `web/app/craft/page.tsx`
  + arcane-ledger styles. (Chat surface was already shipped in Craft 3.5.) Next build green.
- **2026-06-21** — Craft 4: PT-BR craft guides. `collector/craft_guides.py` (GLM) writes
  execution-ready pt-BR tutorials grounded in the EV-ranked methods + craft knowledge, anchored to
  the live patch (config `poe2_patch=0.5.3`, env-overridable) so guides never claim a stale
  version; the NUMBERS (cost/ROI) come from the EV engine, not the LLM. Migration `0007` + repo
  replace/latest + `GET /craft/guides` + run_daily wiring. +6 offline tests.
- **2026-06-21** — Craft 3.5: price the whole craft surface. `ninja_client.fetch_economy` now
  pulls every poe.ninja PoE2 category (currency, essences, omens via Ritual, catalysts via Breach,
  liquid emotions via Delirium, runes, soul cores, abyss, expedition — ~450 priced rows/day,
  config-driven `ninja_economy_types`, tagged by `item_type`). The EV engine now prices
  essence/omen/rune/catalyst/abyss inputs by name, so every seed method ranks by real ROI
  end-to-end (verified against the live feed). Bench/sparklines still filter to currency. +2 tests.
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
