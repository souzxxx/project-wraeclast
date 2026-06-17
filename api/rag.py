"""Retrieval-Augmented Generation for /chat.

Embeds the question, retrieves the closest knowledge_chunks (pgvector cosine), folds in the
owner's latest snapshot + current top farms, and asks GLM to answer grounded in that context.
The "mega brain" is the growing curated corpus, not model weights (see CLAUDE.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from collector.config import get_settings
from collector.ingest import embed_texts
from collector.llm import glm_chat

_SYSTEM = (
    "You are a Path of Exile 2 advisor for the league given in context. Answer ONLY from the "
    "provided context (community knowledge, current prices/farms, and the owner's character). "
    "Prices and profit/hour are ESTIMATES from poe.ninja + community text — say so. If the "
    "context doesn't cover the question, say what's missing instead of inventing numbers. "
    "Reply in the user's language."
)


@dataclass
class RagContext:
    chunks: list[dict[str, Any]]
    farms: list[dict[str, Any]]
    my_snapshot: dict[str, Any] | None
    prices: list[dict[str, Any]]


def _price_value(p: dict[str, Any]) -> float | None:
    return p.get("divine_value") if p.get("divine_value") is not None else p.get("chaos_value")


def retrieve(question: str, k: int = 6) -> RagContext:
    from db.repo import (
        latest_farm_strategies,
        latest_my_snapshot,
        latest_prices,
        search_knowledge,
    )

    league = get_settings().poe2_league
    query_vec = embed_texts([question])[0]
    prices = sorted(
        latest_prices(league, limit=1000),
        key=lambda p: _price_value(p) or 0,
        reverse=True,
    )
    return RagContext(
        chunks=search_knowledge(query_vec, limit=k),
        farms=latest_farm_strategies(league, limit=5),
        my_snapshot=latest_my_snapshot(),
        prices=prices[:25],
    )


def build_context_block(ctx: RagContext) -> str:
    parts: list[str] = [f"LEAGUE: {get_settings().poe2_league}"]
    if ctx.prices:
        parts.append("CURRENT PRICES (top items, in divine):")
        parts += [f"- {p['name']}: {_price_value(p)}" for p in ctx.prices]
    if ctx.farms:
        parts.append("CURRENT TOP FARMS (estimates):")
        parts += [
            f"- {f['name']}: ~{f.get('est_profit_per_hour')} div/h (risk {f.get('risk')})"
            for f in ctx.farms
        ]
    if ctx.my_snapshot:
        s = ctx.my_snapshot
        parts.append(
            f"OWNER CHARACTER: {s.get('character_name')} — "
            f"{s.get('char_class')} lvl {s.get('level')}"
        )
    if ctx.chunks:
        parts.append("COMMUNITY KNOWLEDGE (qualitative):")
        parts += [f"- [{c.get('title')}] {(c.get('content') or '')[:500]}" for c in ctx.chunks]
    return "\n".join(parts)


def answer(question: str) -> dict[str, Any]:
    ctx = retrieve(question)
    text = glm_chat(
        [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": f"CONTEXT:\n{build_context_block(ctx)}\n\nQUESTION: {question}",
            },
        ],
        model=get_settings().glm_chat_model,
        temperature=0.4,
    )
    return {
        "answer": text,
        "sources": [{"url": c.get("source_url"), "title": c.get("title")} for c in ctx.chunks],
    }
