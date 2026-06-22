"""GET /price-history — per-currency price sparklines for the 'Hoje' tab."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from api.price_history import build_sparklines
from collector.config import get_settings

router = APIRouter(prefix="/price-history", tags=["price"])


@router.get("")
def get_price_history(days: int = 14, limit: int = 12) -> dict[str, Any]:
    from db.repo import price_history_since

    league = get_settings().poe2_league
    rows = price_history_since(league, days=days)
    sparklines = build_sparklines(rows, max_series=limit, max_points=days)
    return {
        "league": league,
        "note": "Value per day (divine for PoE2; latest snapshot each day). poe.ninja estimates.",
        "sparklines": [s.model_dump() for s in sparklines],
    }
