"""GET /craft/knowledge — craft-lane knowledge cards for the Craft tab guides block."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from api.craft import craft_cards
from collector.config import get_settings

router = APIRouter(prefix="/craft", tags=["craft"])


@router.get("/knowledge")
def get_craft_knowledge(limit: int = 30) -> dict[str, Any]:
    from db.repo import latest_craft_knowledge

    rows = latest_craft_knowledge(limit=max(1, min(limit, 100)))
    return {
        "note": "Curated craft knowledge (qualitative). The bench costs are the calculated part.",
        "cards": craft_cards(rows),
    }


@router.get("/guides")
def get_craft_guides() -> dict[str, Any]:
    """Full PT-BR craft tutorials (the 'Craft' tab), best ROI first."""
    from db.repo import latest_craft_guides

    league = get_settings().poe2_league
    return {"league": league, "guides": latest_craft_guides(league)}


@router.get("/ev")
def get_craft_ev() -> dict[str, Any]:
    """Craft methods ranked by ROI — expected cost (live-priced inputs, incl. retries) vs the
    curated output value. Spans every craft mechanic, not just currency."""
    from api.craft_ev import rank_methods
    from db.repo import latest_craft_methods, latest_prices

    league = get_settings().poe2_league
    methods = latest_craft_methods(league)
    ranked = rank_methods(methods, latest_prices(league, limit=1000))
    return {
        "league": league,
        "note": "Input costs are live (poe.ninja); success chance + output value are estimates. "
        "ROI = profit / expected cost. 'missing_prices' lists inputs poe.ninja didn't price.",
        "methods": ranked,
    }
