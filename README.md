# Project Wraeclast

An auto-updating personal advisor for **Path of Exile 2**. Every day it pulls the league's
economy, the owner's build, and curated community knowledge into a single store, then exposes:

1. **Farm ranking** by estimated profit/hour (drops × ninja price ÷ clear time).
2. **Build diff** — the owner's character vs the meta (relevant with 0.5.0's ~200 new gems).
3. **Chat (RAG)** grounded in the growing curated corpus + the owner's profile.
4. **A site** + a daily **Obsidian** report.

The "brain" isn't fine-tuning — it's a growing, curated corpus in a vector store (RAG):
ingest daily, embed, and at question time retrieve what's relevant + the profile, then answer.

> Owner: Leonardo (`souzxxx`). Conversation language PT-BR; **all code/commits/docs in English.**
> Full design in [`docs/POE2_AGENT_SPEC.md`](docs/POE2_AGENT_SPEC.md) and [`CLAUDE.md`](CLAUDE.md).

## Architecture

```
 CRON (Cloudflare Worker) ──POST /internal/run──► FastAPI backend
                                                      │
   ninja (economy) ─┐                                 │ runs collector.run_daily
   ninja (build)  ──┼─► normalize ─► Neon (Postgres + pgvector)  ◄── source of truth
   reddit (scraper)─┘        embeddings ▲   │
                                        │   ├─► [farm]  ranking by profit/hour
                            GLM curation┘   ├─► [build] diff vs meta
                                            ├─► [chat]  RAG + profile
                                            └─► [site]  Next.js + Obsidian export
```

| Layer | Tech |
|---|---|
| Schedule | Cloudflare Cron Worker → backend `/internal/run` (or GitHub Actions) |
| Store | Neon Postgres + pgvector |
| Backend | FastAPI (Python 3.11+) |
| LLM | GLM via z.ai (OpenAI-compatible) |
| Economy / build | poe.ninja (public) |
| Account (opt., Phase 2) | GGG official API, OAuth 2.1 + PKCE |
| Site | Next.js (Vercel) |
| Reading | Markdown → Obsidian vault |

## Layout

```
collector/   ninja_client · ninja_build_client · pob_parser · ggg_client(F2)
             community_scraper · ingest · curate · run_daily
db/          models · repo · connection · migrations/
api/         main · rag · build_diff · routes/{farm,build,chat}
scripts/     export_obsidian
web/         Next.js dashboard
cloudflare/  cron worker + wrangler
routines/    Claude Code daily-curation routine
docs/        spec + phase-0 command sequence
tests/       pure-logic unit tests (no network/DB)
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # fill GLM_API_KEY, NEON_DATABASE_URL, NINJA_*, etc.

python -m db.connection ping    # verify the database connects
python -m db.connection migrate # create tables + pgvector index
```

### Run a daily collection by hand
```bash
python -m collector.ninja_client explore   # confirm the live ninja JSON shape first
python -m collector.run_daily               # ninja → build → scrape → curate → obsidian
```

### Backend + site
```bash
uvicorn api.main:app --reload               # http://localhost:8000  (/docs for OpenAPI)
cd web && npm install && npm run dev         # http://localhost:3000
```

## Phases (account data is a fallback ladder, never a blocker)

- **Phase 0 (done here):** economy + community + curation + ninja-build + chat/site/export.
- **Phase 1:** PoB-code/clipboard parser — universal, any character, offline (implemented).
- **Phase 2 (optional, only if GGG approves OAuth):** stash currency 24/7 + off-ladder chars.
  PKCE scaffolding is in `collector/ggg_client.py`; it plugs in without rework.

## Status

- ✅ Backend (FastAPI): `/farm`, `/build`, `/chat`, `/state`, `/health`, `/internal/run`.
- ✅ Collectors, curation (strict-JSON + computed profit/hour), embeddings, Obsidian export.
- ✅ PoB parser + GGG OAuth/PKCE scaffolding. Next.js dashboard. CI (ruff + pytest, 25 tests).
- ⏳ Needs live credentials to run end-to-end: `GLM_API_KEY`, `NEON_DATABASE_URL`, ninja profile.
- ⚠️ poe.ninja's PoE2 site is now an Astro SPA; the exact economy endpoint path must be
  confirmed via `python -m collector.ninja_client explore` in the deploy env — URLs are
  config-driven in `.env`, not hardcoded.

_All prices and profit/hour figures are estimates, not guarantees._
