"""GET /craft/knowledge — craft-lane knowledge cards for the Craft tab guides block."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from api.craft import craft_cards

router = APIRouter(prefix="/craft", tags=["craft"])


@router.get("/knowledge")
def get_craft_knowledge(limit: int = 30) -> dict[str, Any]:
    from db.repo import latest_craft_knowledge

    rows = latest_craft_knowledge(limit=max(1, min(limit, 100)))
    return {
        "note": "Curated craft knowledge (qualitative). The bench costs are the calculated part.",
        "cards": craft_cards(rows),
    }
