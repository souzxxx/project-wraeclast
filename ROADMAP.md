# Roadmap — Project Wraeclast

Prioritized backlog for the **nightly agent** (see `routines/nightly_agent.md`). The agent
picks the highest-value item it can fully complete in one run, implements it on a `claude/`
branch, runs ruff + pytest, opens a PR, and checks the item off here in that same PR.

> Ordering = priority. Health first, then the daily intelligence layer, then features.
> Keep edits focused and tested. Never merge — the owner reviews.

## P0 — Health (always check first)
- [ ] `ruff check .` and `pytest -q` are green; if not, fix the breakage.
- [ ] No daily-collection step is silently failing (check the latest GitHub Actions run / logs).
      _(now enforced, not just eyeballed: `run_daily` exits non-zero + emits Actions annotations
      when any step fails, so a swallowed collector error goes red instead of silently green — see Done 2026-07-04.)_
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
- [x] Mobile layout polish for the dashboard, farms, and graph. _(see Done)_
- [ ] Phase 2 (optional, only if the owner enables it): GGG OAuth 2.1 + PKCE for real-time
      stash currency (net worth) and off-ladder characters. Scaffolding in `collector/ggg_client.py`.

## P3 — Tech debt / quality
- [x] Add tests for any module under 80% of its public surface.
      _(done — `collector/ninja_build_client.py` 39% → 81%, see Done 2026-06-23;
      `collector/youtube_client.py` 46% → 99%, see Done 2026-06-24;
      `collector/ninja_client.py` 51% → 99%, see Done 2026-06-25;
      `collector/llm.py` 25% → 100%, see Done 2026-06-26;
      `db/repo.py` 30% → 100% and `db/connection.py` 33% → 98%, see Done 2026-06-27;
      `collector/ninja_meta_client.py` 68% → 99%, see Done 2026-06-29;
      `collector/ggg_client.py` 0% → 100%, see Done 2026-06-30.
      Every pure/collector module now clears the 80% bar — including the dormant Phase 2
      OAuth client, hardened ahead of any future enablement. The HTTP route layer
      (`api/routes/*` + `api/main.py` read endpoints) is now covered offline too, driven
      through `TestClient` with the repo layer monkeypatched (see Done 2026-07-02). The last
      two 0%-coverage modules — the daily orchestrator `collector/run_daily.py` and the Obsidian
      exporter `scripts/export_obsidian.py` — are now covered offline too (95% / 98%, only the
      `__main__` guards remain), so **every module in the project clears the 80% bar** (see Done
      2026-07-05).)_
- [x] Tighten the YouTube queries based on which sources actually inform good guides.
      _(see Done — shipped the data-driven analyzer; the actual query edits are now a
      report-driven decision instead of guesswork.)_

---

### Done (agent appends here)
<!-- The nightly agent moves completed items here with the PR number + date. -->
- **2026-07-08** (#40) — P0 health: make the one persistently-failing daily step (`meta_builds`)
  resilient + self-diagnosing. Since it shipped (2026-06-22) the step has 404'd **every run** —
  its poe.ninja builds path is a single unconfirmed guess (`/poe2/api/builds/overview`), and since
  2026-07-04 that hard-fails the run with a bare `step meta_builds FAILED: 404`, nothing
  actionable. Root fix for the finding-the-route problem, done the same config-driven way the other
  ninja endpoints were bootstrapped: `fetch_popular_builds`/`explore` now try an **ordered list of
  candidate paths** (`ninja_builds_path` preferred, then `ninja_builds_fallback_paths` — PoE2-shaped
  alternates mirroring the confirmed economy endpoint `/poe2/api/economy/exchange/0/overview`),
  returning the FIRST that yields characters. A 404/transport error or an empty-character payload
  just advances to the next candidate; only when **all** fail does it raise the new
  `NinjaBuildsUnavailable`, whose message lists every path + status tried and points at
  `python -m collector.ninja_meta_client explore`. This preserves the red-run failure-surfacing
  contract (Done 2026-07-04) while turning a mystery 404 into a one-shot route diagnosis, and gives
  the deploy a real chance to self-heal without a human guessing. `explore` now reports which
  candidate worked. New `Settings.ninja_builds_path_list` (preferred-first, deduped, empties
  dropped). All config-driven; no league/endpoint hardcoded beyond the documented candidates, which
  are env-overridable. +7 offline tests (respx: primary-404 → fallback, empty-payload skip,
  transport-error skip, all-fail actionable raise, explore success/all-fail; + the path-list
  property). `ruff check .` clean; `pytest -q` 350 → 357. Does NOT tick the P0 "no step silently
  failing" box — the exact live route is still unconfirmed (needs one `explore` run in the deploy),
  but that run is now trivial and the interim failure is loud + actionable instead of a bare 404.
- **2026-07-06** — P0 health: fix a daily-collection step that was **silently failing every run**.
  The `daily.yml` job is green (its steps swallow per-collector exceptions and only summarize at
  the end), but the 2026-07-06 run log shows `step daily_insight FAILED: unsupported operand
  type(s) for *: 'decimal.Decimal' and 'float'` — the P1 "what changed today" insight report
  (`scripts/daily_insight.py`) has produced nothing in production since prices went
  divine-denominated. Root cause: psycopg returns NUMERIC columns as `Decimal`, and
  `notable_price_moves` did `(now - old) / old * 100.0`, mixing `Decimal` with `float`. The pure
  tests never caught it because they feed Python floats. `_row_value` claimed to "mirror
  `api.craft_ev.price_index`" but omitted exactly that module's `_f()` Decimal→float coercion, so
  the fix restores it at that single boundary (craft_ev/craft_alerts already coerce and were
  unaffected). +2 offline regression tests feeding `Decimal` rows exactly as the DB does
  (`notable_price_moves` for both the chaos and divine columns, and the full `compute_insight` →
  `render_insight` path). ruff clean; `pytest -q` 322 → 324. One-line production change; no schema
  or league hardcoding. **Still failing in that same run (out of scope tonight, needs live endpoint
  exploration):** `step meta_builds FAILED: 404` on `poe.ninja/poe2/api/builds/overview` — the
  PoE2 builds path was flagged "unconfirmed" back in the 2026-06-22 note and needs a live
  `explore` run against the deploy to find the right route; can't be verified offline.
- **2026-07-05** — P3 coverage: cover the last two 0%-coverage modules offline — the daily
  orchestrator `collector/run_daily.py` (0% → 95%) and the Obsidian exporter
  `scripts/export_obsidian.py` (0% → 98%). These were the only modules the coverage sweep still
  excluded as "pipeline glue that only makes sense against the live app/DB", but both defer their
  `db.repo` / `api.craft_ev` imports to call time (same seam the route layer used on 2026-07-02),
  so they drive fully offline — no DB, no network. New `tests/test_export_obsidian.py` exercises
  the pure `render_report` across every branch (frontmatter + `price_count` line; farms numbered
  with `n/a` fallbacks for absent risk/investment and the summary-bullet only when present; priced
  crafts showing ROI vs the unpriced `missing_prices` branch, incl. `roi_pct=None` routing there
  and the empty-mechanics → `"craft"` default; a snapshot with mixed dict/str gems where nameless
  gems are filtered, vs the `?`-placeholder path; the `today` default), plus `run()` wired to a
  tmp vault with `db.repo.*` + `rank_methods` + `get_settings` monkeypatched (dated filename from
  the configured league, content, and the idempotent same-day overwrite — one `.md`, not two). New
  `tests/test_run_daily.py` covers `_step` (success record vs exception swallowed into
  `{"ok": False, "error": …}`) and `run_all` with every step's `run` patched — async stubs for the
  awaited network steps, plain stubs for the `to_thread` sync steps — asserting the 12-step order,
  the `pob_code` passthrough into `my_build`, the `ok_steps`/`failed_steps` summary split, and the
  resilience contract at the middle and both edges (one failing step is isolated and everything
  downstream still runs). No production code changed — tests only. +15 offline tests (322 → 337);
  `run_daily.py` and `export_obsidian.py` now clear the 80% bar, completing the coverage sweep.
  ruff clean.
- **2026-07-04** — P0 health: stop the daily collection from failing **silently**. `run_all`
  wraps every step so one failure is logged and the rest still run (resilient collection) — but
  it recorded failures only in an in-memory `results` dict and the process always exited 0. So a
  collector could fail **every single day** and the Actions run would still show a green ✓; the
  only trace was a buried `run_daily` log line nobody reads. The P0 "no step is silently failing"
  check had no enforcement — it relied on the owner manually eyeballing Actions logs. Fixed the
  gap without weakening resilience: added pure, offline-testable `render_annotations` (one
  `::error title=Daily collection::…` workflow command per failed step, whitespace-collapsed to a
  single line) and `render_step_summary` (a `$GITHUB_STEP_SUMMARY` OK/failed recap table), and a
  `main()` that runs the collection, emits both, and **returns exit code 1 when any step failed**
  so the run goes red. The per-step try/except and full-sequence execution are untouched — every
  step still runs, the failure is just no longer invisible. `daily.yml`'s "Commit daily report"
  step now uses `if: always()`, so a red run still commits the day's report (the data lands **and**
  the owner sees the X). New `tests/test_run_daily.py` covers the annotation/summary rendering
  (empty when all-ok, one line per failure, multiline collapse, missing-error-field default),
  `main`'s exit code (0 clean / 1 on failure) + annotation emission + step-summary write + graceful
  survival of an unwritable summary path, and that `_step` records a failure without stopping later
  steps. +11 offline tests (322 → 333). ruff clean. No collector logic changed — only failure
  surfacing.
- **2026-07-02** — P3 coverage: harden the HTTP route layer (`api/routes/*` + `api/main.py`
  read endpoints), which sat at **0% coverage** — the public contract the Next.js site depends
  on had zero regression protection, so a renamed field or a wrong status code would have shipped
  silently. The prior P3 note excluded these as "integration glue needing the live app," but every
  route defers its `db.repo` import to call time, so the whole layer is drivable offline through
  FastAPI's `TestClient` with `db.repo.*` monkeypatched — no network, no Neon, same pattern the
  rest of the suite already uses. New `tests/test_routes_http.py` exercises: the static endpoints
  (`/health` incl. the read-cache header, `/`); `/farm` + `/farm/guides` (shape, `note`, and the
  `max(1, min(limit, 100))` clamp at both ends); `/price-history` (the `days` floor/ceiling guard
  before the query, empty-rows → empty sparklines); `/graph` (real `build_graph` over an empty
  corpus still yields nodes/links); `/build` (404 without a snapshot, graceful "not comparable"
  degrade without meta, comparable-with-meta, and the `_load_meta_build` short-circuit that must
  NOT query when the class is unset); every `/craft/*` route (`knowledge` card projection + clamp,
  `guides`, `alerts`, `ev` note/ranking); the gated `POST /ingest` (401 without token, fail-closed
  503 when unconfigured, happy path asserting the strip-then-ingest contract, `min_length` rejection
  of an empty payload); and `main.py`'s `/state` aggregation + `/prices` currency-only projection.
  Also pins the base-`Exception` handler: an unhandled error returns a JSON 500 **with the CORS
  origin echoed** (the contract that keeps the browser from seeing an opaque NetworkError, per the
  handler's own comment). League is always read from `get_settings()`, never hardcoded. No
  production code changed — tests only. +23 offline tests (299 → 322); `api/routes/*` and
  `api/main.py` now at 100%. ruff clean.
- **2026-07-01** — P2: mobile layout polish (dashboard, farms, graph). The shared `Nav` had no
  mobile breakpoint, so on phones (≤640px) the brand sat vertically centered against a 3-line
  wrapped tab block — a genuinely messy header on every page (confirmed via Playwright screenshots
  at 375px). Added a focused, desktop-first mobile block in `web/app/globals.css`: at ≤640px the
  nav wraps so **WRAECLAST** takes its own row with the five tabs in one tidy row beneath it
  (active underline preserved), and `main` gains a touch more content width; the farms accordion
  header (`.guide-head`) now lets a long guide name shrink/wrap instead of shoving the profit/risk
  meta off-row, dropping the meta to its own line on narrow screens; and at ≤460px dashboard price
  sparklines clip an over-long currency name (ellipsis) so the value/change stay aligned. CSS-only,
  no component/logic changes; desktop and tablet (>640px, verified at 768px) are untouched.
  Verified offline: `ruff check .` clean + `pytest -q` 299 passed (Python unaffected); web
  `tsc --noEmit` clean, `vitest run` 21 passed, `next build` green; before/after 375px screenshots
  confirm the nav fix across Hoje/Farms/Cérebro.
- **2026-06-30** — P3 coverage: harden `collector/ggg_client.py` (0% → 100%). This was the one
  substantive module with **no test file at all** — never imported by the suite, so the coverage
  report skipped it entirely. It is dormant Phase 2 OAuth (skill §2, not in the daily path), but
  the prior note's "by design" exclusion meant the GGG token flow had zero regression protection
  before any future enablement. Added offline tests (no network, no DB — never touch
  pathofexile.com), following the established pattern: pure `generate_pkce_pair` (the challenge is
  the S256 of the verifier; both url-safe + unpadded per the PKCE spec; verifier is random per
  call); pure `build_authorize_url` (all seven OAuth params present and correctly encoded; reads
  `client_id` from settings, falling back to `get_settings`); and the httpx token surface mocked
  with respx — `exchange_code` (returns a `TokenSet`; posts the `authorization_code` grant with
  code/verifier/redirect; an empty secret is sent as `null` for the public/PKCE client, while a
  configured secret is forwarded for the confidential client; missing `refresh_token`/`expires_in`
  default to `None`/`0`; `get_settings` fallback) and `refresh_token` (posts the `refresh_token`
  grant; **keeps the currently-held refresh token when GGG's response omits a rotated one** — the
  `data.get("refresh_token", refresh)` contract; `get_settings` fallback). No production code
  changed — tests only. +12 offline tests (287 → 299), ruff clean.
- **2026-06-29** — P3 coverage: harden `collector/ninja_meta_client.py` (68% → 99% — clears the
  80% bar). The 2026-06-27 note claimed "every module now clears the 80% bar," but the `/build`
  meta-source client (shipped 2026-06-22, after most of the coverage sweep) was still at 68%:
  only its pure aggregation (`aggregate_meta_builds`/`extract_characters`/`_char_class`/
  `_char_gems`) was tested, while the network/dispatch surface had no coverage. Added offline
  tests (no network, no DB) following the established pattern: `fetch_popular_builds` (respx —
  aggregates from the endpoint, attaches the poe.ninja source, reads `league` from config not
  hardcoded; truncates to `ninja_meta_max_chars` before aggregating); `run` (monkeypatched
  `fetch_popular_builds` + `db.repo.replace_meta_builds` — write wiring + count + print);
  `explore` (respx — character count + sampled JSON dump); the `_main` run/explore/default/
  unknown-command dispatch; and the pure empty-gems branch (a class whose gems all fall below
  `min_usage` is dropped, never emitted as an empty `MetaBuild`). No production code changed —
  tests only. +8 offline tests (279 → 287), ruff clean. (Line 172, the `if __name__` guard,
  is the only line left, conventionally excluded — same as ninja_client's 99%.) Corrected the
  P3 note to scope the "every module" claim to pure/collector modules and list what stays
  sub-80% by design: route/wiring glue and the dormant Phase 2 `ggg_client.py`.
- **2026-06-28** — P3: make YouTube-query tightening data-driven (the "which sources actually
  inform good guides" item). Until now the only signal for pruning `youtube_queries` was a hunch;
  there was no record of which query surfaced which video, nor whether that video ever fed a guide.
  Added that signal end-to-end: migration `0009` adds `knowledge_chunk.discovery_query`;
  `fetch_youtube` now attributes each deduped video to the FIRST query that surfaced it (no
  double-counting across queries); `KnowledgeDoc`/`ingest_documents`/`KnowledgeChunk`/
  `upsert_knowledge_chunk` thread it through, and the upsert `COALESCE`s so a re-found chunk keeps
  its original attribution. New pure analyzer `collector/query_stats.py` crosses that attribution
  with the URLs cited across `farm_guide`/`craft_guide`/`farm_strategy` → per-query
  `discovered`/`cited`/`citation_rate`, flags configured-but-uncited queries as **drop candidates**,
  and surfaces drift (queries only in history after a config edit). `python -m collector.query_stats`
  renders the markdown report the owner uses to tighten the config. All changes additive; migrations
  apply before collection in `daily.yml`, so the live path stays safe. +16 offline tests
  (245 → 261), ruff clean. (Actual config edits await a few days of attributed data — the analyzer
  is the deliverable that makes that decision evidence-based.)
- **2026-06-27** — P3 coverage: harden the data layer — `db/repo.py` (30% → 100%) and
  `db/connection.py` (33% → 98%; only the `__main__` guard line remains). These were the last
  two modules under the 80% bar, so **every module in the project now clears it.** The note had
  flagged them as "need a live DB", but both are pure SQL-dispatch: by faking the
  connection/cursor (and `psycopg.connect` + `get_settings` for connection.py) the whole surface
  is exercised offline — no network, no Neon. `test_db_connection.py` covers `get_connection`
  (RuntimeError when `NEON_DATABASE_URL` unset; yields the conn + closes it in `finally`, even on
  exception; `dict_row` row factory passed through), `fetch_all`/`execute` (query + params
  dispatch, `None` → `()` default, commit), `ping` (True only on `{"ok": 1}`), `migrate` (applies
  every `db/migrations/*.sql` in lexical order, one commit each — asserted against the real
  migrations dir and a tmp dir), and the `_main` ping/migrate/default/unknown dispatch.
  `test_db_repo.py` covers every write (empty-batch short-circuit with no connection opened;
  JSON-encoding of list/dict columns; the pgvector text literal with and without an embedding;
  the DELETE-then-`executemany` replace pattern, incl. the DELETE still firing on an empty batch;
  `dict.get` defaults for the guide writers) and every read (league/limit/days binding, the
  twice-bound league in `latest_farm_strategies`, first-row-or-None, the `topic`-clause branch in
  `search_knowledge`). No production code changed — tests only. +48 offline tests (197 → 245),
  ruff clean. **The 80%-coverage P3 item is now complete.**
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
