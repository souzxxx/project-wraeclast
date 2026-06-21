"""Pydantic row models mirroring the Neon schema (db/migrations/0001_init.sql).

Validation is intentionally lenient on external-sourced fields (they may be missing),
strict on the few we compute ourselves.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ItemType = Literal["currency", "unique", "base", "gem"]
Risk = Literal["low", "med", "high"]


class PriceSnapshot(BaseModel):
    captured_at: datetime | None = None
    league: str
    item_type: ItemType
    name: str
    chaos_value: float | None = None
    divine_value: float | None = None
    listing_count: int | None = None


class FarmStrategy(BaseModel):
    captured_at: datetime | None = None
    league: str
    name: str
    est_profit_per_hour: float | None = None
    investment_required: float | None = None
    risk: Risk | None = None
    summary: str = ""
    sources: list[dict[str, Any]] = Field(default_factory=list)


class MySnapshot(BaseModel):
    captured_at: datetime | None = None
    character_name: str | None = None
    char_class: str | None = None
    level: int | None = None
    total_currency_chaos: float | None = None
    gear: dict[str, Any] = Field(default_factory=dict)
    gems: list[dict[str, Any]] = Field(default_factory=list)
    passive_tree: dict[str, Any] = Field(default_factory=dict)


class KnowledgeChunk(BaseModel):
    captured_at: datetime | None = None
    source_url: str
    title: str = ""
    content: str
    embedding: list[float] | None = None
    topic: str | None = None  # craft | farm — coarse lane for RAG/chat filtering
