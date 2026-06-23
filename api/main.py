"""FastAPI app: public read endpoints for the site + token-gated chat/ingest.

Run locally:  uvicorn api.main:app --reload
(Daily collection runs in GitHub Actions via `python -m collector.run_daily`, not over HTTP.)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import build, chat, craft, farm, graph, ingest, price
from collector.config import get_settings

log = logging.getLogger("api")

app = FastAPI(title="Project Wraeclast API", version="0.1.0")

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def _on_unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Return a JSON 500 for unhandled errors WITH CORS headers. A base-Exception handler runs in
    Starlette's outermost ServerErrorMiddleware, i.e. OUTSIDE the CORS middleware, so we echo the
    allowed Origin ourselves — otherwise the browser sees an opaque 'NetworkError' (which is what
    masked the /craft 500s when the craft tables were unmigrated) instead of a real 500."""
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    resp = JSONResponse(status_code=500, content={"detail": "internal server error"})
    origin = request.headers.get("origin")
    if origin and origin in _settings.cors_origin_list:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
    return resp


@app.middleware("http")
async def _cache_reads(request: Request, call_next: Any) -> Any:
    """The data refreshes once a day, so let browsers/CDN cache successful GETs briefly — cuts
    repeat DB load on /state, /prices, /farm, /craft/*, etc. (POST /chat + /ingest untouched)."""
    resp = await call_next(request)
    if request.method == "GET" and resp.status_code == 200:
        resp.headers.setdefault("Cache-Control", "public, max-age=300")
    return resp

app.include_router(farm.router)
app.include_router(build.router)
app.include_router(chat.router)
app.include_router(craft.router)
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
            "/health", "/state", "/farm", "/build", "/prices", "/price-history",
            "/craft/knowledge", "/chat (POST)", "/docs",
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


@app.get("/prices")
def prices() -> dict[str, Any]:
    """Live currency prices for the crafting bench's cost ledger (read-only)."""
    from api.prices import currency_prices
    from db.repo import latest_prices

    league = get_settings().poe2_league
    return {"league": league, "prices": currency_prices(latest_prices(league, limit=1000))}
