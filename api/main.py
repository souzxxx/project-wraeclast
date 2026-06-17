"""FastAPI app: public read endpoints for the site + an internal cron-triggered run.

Run locally:  uvicorn api.main:app --reload
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.routes import build, chat, farm, ingest
from collector.config import get_settings

app = FastAPI(title="Project Wraeclast API", version="0.1.0")

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(farm.router)
app.include_router(build.router)
app.include_router(chat.router)
app.include_router(ingest.router)


@app.get("/")
def index() -> dict[str, Any]:
    """Friendly root so the deployment URL isn't a bare 404."""
    return {
        "service": "Project Wraeclast API",
        "league": get_settings().poe2_league,
        "endpoints": ["/health", "/state", "/farm", "/build", "/chat (POST)", "/docs"],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "league": get_settings().poe2_league}


@app.get("/state")
def league_state() -> dict[str, Any]:
    """'State of the league today' for the site home: top farms + owner snapshot + price count."""
    from db.repo import latest_farm_strategies, latest_my_snapshot, latest_prices

    league = get_settings().poe2_league
    prices = latest_prices(league, limit=1000)
    return {
        "league": league,
        "price_count": len(prices),
        "top_farms": latest_farm_strategies(league, limit=10),
        "my_snapshot": latest_my_snapshot(),
    }


@app.post("/internal/run")
async def internal_run(
    x_run_token: str = Header(default=""),
    pob_code: str | None = None,
) -> dict[str, Any]:
    """Cron-triggered daily collection. Protected by a shared secret (INTERNAL_RUN_TOKEN)."""
    settings = get_settings()
    if not settings.internal_run_token or x_run_token != settings.internal_run_token:
        raise HTTPException(status_code=401, detail="invalid run token")
    from collector.run_daily import run_all

    return await run_all(pob_code)
