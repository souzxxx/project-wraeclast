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


class CraftMethod(BaseModel):
    """A structured crafting method (the craft analogue of FarmStrategy). This is the recipe as
    DATA, not prose: ordered steps, the aggregate currency `inputs` ({name: expected_qty}) that
    the EV engine (Craft 3) crosses with live `price_snapshot`, the target mods, and a one-attempt
    `success_prob`. Output VALUE/ROI is deliberately out of scope here — that is Craft 3."""

    captured_at: datetime | None = None
    league: str
    name: str
    item_base: str
    archetype: str | None = None  # caster | attack | defence | … — coarse grouping
    target_mods: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)  # ordered, human-readable
    inputs: dict[str, float] = Field(default_factory=dict)  # {currency_name: expected_qty}
    success_prob: float | None = Field(default=None, ge=0, le=1)  # one-attempt chance, 0..1
    output: str = ""  # what it produces, e.g. "+3 Spell Skills caster wand"
    sources: list[dict[str, Any]] = Field(default_factory=list)
    notes: str = ""
