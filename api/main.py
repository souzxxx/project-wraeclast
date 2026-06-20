"""FastAPI app: public read endpoints for the site + token-gated chat/ingest.

Run locally:  uvicorn api.main:app --reload
(Daily collection runs in GitHub Actions via `python -m collector.run_daily`, not over HTTP.)
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import build, chat, farm, graph, ingest, price
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
app.include_router(graph.router)
app.include_router(price.router)


@app.get("/")
def index() -> dict[str, Any]:
    """Friendly root so the deployment URL isn't a bare 404."""
    return {
        "service": "Project Wraeclast API",
        "league": get_settings().poe2_league,
        "endpoints": [
            "/health", "/state", "/farm", "/build", "/price-history", "/chat (POST)", "/docs",
        ],
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
