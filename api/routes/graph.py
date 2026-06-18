"""GET /graph — the 'brain' graph snapshot (nodes + links) for the Obsidian-like view."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from api.graph import build_graph
from collector.config import get_settings

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("")
def get_graph() -> dict[str, Any]:
    from db.repo import (
        latest_farm_guides,
        latest_knowledge_chunks,
        latest_my_snapshot,
        latest_prices,
    )

    league = get_settings().poe2_league
    graph = build_graph(
        league=league,
        guides=latest_farm_guides(league),
        my_snapshot=latest_my_snapshot(),
        prices=latest_prices(league, limit=1000),
        knowledge=latest_knowledge_chunks(),
    )
    return {"league": league, **graph}
