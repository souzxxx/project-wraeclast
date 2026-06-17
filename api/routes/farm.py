"""GET /farm — current farm ranking by estimated profit/hour."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from collector.config import get_settings

router = APIRouter(prefix="/farm", tags=["farm"])


@router.get("")
def get_farm_ranking(limit: int = 20) -> dict[str, Any]:
    from db.repo import latest_farm_strategies

    league = get_settings().poe2_league
    strategies = latest_farm_strategies(league, limit=limit)
    return {
        "league": league,
        "note": "Profit/hour is an estimate in divine, grounded in community guides + ninja prices.",
        "strategies": strategies,
    }
