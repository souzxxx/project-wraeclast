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
from collector.topics import topic_for_question

_SYSTEM = (
    "You are a Path of Exile 2 advisor for the league given in context. Answer ONLY from the "
    "provided context (community knowledge, current prices/farms, and the owner's character). "
    "Prices and profit/hour are ESTIMATES from poe.ninja + community text — say so. If the "
    "context doesn't cover the question, say what's missing instead of inventing numbers. "
    "Reply in the user's language."
)

# Cap how many prior messages we replay so a long thread can't balloon the prompt.
_MAX_HISTORY_MESSAGES = 6


@dataclass
class RagContext:
    chunks: list[dict[str, Any]]
    farms: list[dict[str, Any]]
    my_snapshot: dict[str, Any] | None
    prices: list[dict[str, Any]]
    craft_methods: list[dict[str, Any]]


def _price_value(p: dict[str, Any]) -> float | None:
    return p.get("divine_value") if p.get("divine_value") is not None else p.get("chaos_value")


def retrieve(question: str, k: int = 6) -> RagContext:
    from api.craft_ev import rank_methods
    from db.repo import (
        latest_craft_methods,
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
        chunks=search_knowledge(query_vec, limit=k, topic=topic_for_question(question)),
        farms=latest_farm_strategies(league, limit=5),
        my_snapshot=latest_my_snapshot(),
        prices=prices[:25],
        craft_methods=rank_methods(latest_craft_methods(league), prices)[:5],
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
    if ctx.craft_methods:
        parts.append(
            "TOP CRAFT METHODS (EV-ranked; input cost is live, output value/success estimated). "
            "Craft spans currency, essences, omens, abyss, runes, catalysts — not just orbs:"
        )
        for m in ctx.craft_methods:
            mech = ", ".join(m.get("mechanics") or []) or "craft"
            head = f"- {m.get('name')} [{mech}] → makes {m.get('output')}:"
            if m.get("priced") and m.get("roi_pct") is not None:
                parts.append(
                    f"{head} ~{m.get('expected_cost_div')} div expected cost, "
                    f"ROI ~{m.get('roi_pct')}% (success {m.get('success_prob')})"
                )
            else:
                miss = ", ".join(m.get("missing_prices") or []) or "n/a"
                parts.append(f"{head} cost not yet priceable (unpriced inputs: {miss})")
    if ctx.chunks:
        parts.append("COMMUNITY KNOWLEDGE (qualitative):")
        parts += [f"- [{c.get('title')}] {(c.get('content') or '')[:500]}" for c in ctx.chunks]
    return "\n".join(parts)


def build_messages(
    context_block: str,
    question: str,
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Assemble the GLM message list: system + freshly-retrieved context, then the last
    `_MAX_HISTORY_MESSAGES` valid prior messages, then the current question last. Pure (no I/O) so
    the history threading/bounding is unit-testable. RAG context is keyed off the *current*
    question and shared across the whole conversation."""
    messages: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": f"CONTEXT (for the whole conversation):\n{context_block}"},
    ]
    # Filter to valid messages FIRST, then keep the most recent ones, so invalid/blank entries
    # near the end can't crowd out genuine recent context.
    valid = [
        {"role": role, "content": content}
        for turn in (history or [])
        for role in [turn.get("role")]
        for content in [(turn.get("content") or "").strip()]
        if role in ("user", "assistant") and content
    ]
    messages.extend(valid[-_MAX_HISTORY_MESSAGES:])
    messages.append({"role": "user", "content": question})
    return messages


def answer(question: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    ctx = retrieve(question)
    text = glm_chat(
        build_messages(build_context_block(ctx), question, history),
        model=get_settings().glm_chat_model,
        temperature=0.4,
    )
    return {
        "answer": text,
        "sources": [{"url": c.get("source_url"), "title": c.get("title")} for c in ctx.chunks],
    }
