"""GLM curation (skill §4 & §5): turn raw knowledge + prices into ranked farm strategies.

The LLM proposes strategies and the raw inputs (expected drops, clear time, entry cost);
profit/hour is then COMPUTED here, not taken as free text. Output is strict JSON validated
with pydantic. Also emits a human-readable markdown block for the Obsidian export.
"""

from __future__ import annotations

from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from collector.config import get_settings
from db.models import FarmStrategy, Risk


def estimate_profit_per_hour(
    expected_drops: float,
    unit_price_chaos: float,
    clear_time_minutes: float,
    entry_cost_chaos: float = 0.0,
) -> float:
    """skill §4 formula. Returns chaos/hour. Defensive against zero/negative clear time."""
    if clear_time_minutes <= 0:
        return 0.0
    profit_per_map = expected_drops * unit_price_chaos - entry_cost_chaos
    maps_per_hour = 60.0 / clear_time_minutes
    return round(profit_per_map * maps_per_hour, 2)


class _LLMStrategy(BaseModel):
    name: str
    expected_drops_per_map: float = 0.0
    unit_price_chaos: float = 0.0
    clear_time_minutes: float = 0.0
    entry_cost_chaos: float = 0.0
    investment_required: float | None = None
    risk: Risk | None = None
    summary: str = ""
    sources: list[dict[str, Any]] = []


class _LLMResponse(BaseModel):
    strategies: list[_LLMStrategy]


_SYSTEM = (
    "You are a Path of Exile 2 economy analyst. Identify the farm strategies with the most "
    "community traction right now and estimate, per strategy, the expected valuable drops per "
    "map, the unit price in chaos (cross-referenced with the provided prices), the average clear "
    "time in minutes, and the entry cost. Output STRICT JSON only — no markdown, no prose outside "
    'the JSON. Schema: {"strategies":[{"name","expected_drops_per_map","unit_price_chaos",'
    '"clear_time_minutes","entry_cost_chaos","investment_required","risk":"low|med|high",'
    '"summary","sources":[{"url","title"}]}]}. Everything is an ESTIMATE.'
)


def _glm_client() -> OpenAI:
    s = get_settings()
    if not s.glm_api_key:
        raise RuntimeError("GLM_API_KEY is not set.")
    return OpenAI(api_key=s.glm_api_key, base_url=s.glm_base_url)


def build_user_prompt(knowledge: list[dict[str, Any]], prices: list[dict[str, Any]]) -> str:
    price_lines = [
        f"- {p['name']} ({p['item_type']}): {p.get('chaos_value')} chaos"
        for p in prices[:120]
        if p.get("chaos_value") is not None
    ]
    knowledge_lines = [
        f"- {k.get('title') or k.get('source_url')}: {(k.get('content') or '')[:600]}"
        for k in knowledge[:40]
    ]
    return (
        "CURRENT PRICES (chaos):\n" + "\n".join(price_lines)
        + "\n\nCOMMUNITY KNOWLEDGE (qualitative):\n" + "\n".join(knowledge_lines)
        + "\n\nReturn the top farm strategies as strict JSON."
    )


def parse_llm_json(text: str) -> _LLMResponse:
    """Tolerate a stray code fence; raise ValueError if it still isn't valid JSON/schema."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1] if "```" in cleaned[3:] else cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    try:
        return _LLMResponse.model_validate_json(cleaned)
    except ValidationError as exc:
        raise ValueError(f"LLM JSON failed schema validation: {exc}") from exc


def to_farm_strategies(resp: _LLMResponse, league: str) -> list[FarmStrategy]:
    out: list[FarmStrategy] = []
    for s in resp.strategies:
        pph = estimate_profit_per_hour(
            s.expected_drops_per_map, s.unit_price_chaos, s.clear_time_minutes, s.entry_cost_chaos
        )
        out.append(
            FarmStrategy(
                league=league,
                name=s.name,
                est_profit_per_hour=pph,
                investment_required=s.investment_required,
                risk=s.risk,
                summary=s.summary,
                sources=s.sources,
            )
        )
    out.sort(key=lambda x: x.est_profit_per_hour or 0, reverse=True)
    return out


def to_markdown(strategies: list[FarmStrategy], league: str) -> str:
    lines = [f"## Top farm strategies — {league}", "", "_All figures are estimates._", ""]
    for i, s in enumerate(strategies, 1):
        lines.append(f"### {i}. {s.name}")
        lines.append(f"- **~{s.est_profit_per_hour} chaos/h** · risk: {s.risk or 'n/a'} "
                     f"· investment: {s.investment_required or 'n/a'}")
        if s.summary:
            lines.append(f"- {s.summary}")
        lines.append("")
    return "\n".join(lines)


def curate(
    knowledge: list[dict[str, Any]], prices: list[dict[str, Any]], league: str
) -> tuple[list[FarmStrategy], str]:
    client = _glm_client()
    resp = client.chat.completions.create(
        model=get_settings().glm_curation_model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": build_user_prompt(knowledge, prices)},
        ],
        temperature=0.3,
    )
    parsed = parse_llm_json(resp.choices[0].message.content or "")
    strategies = to_farm_strategies(parsed, league)
    return strategies, to_markdown(strategies, league)


def run() -> int:
    from db.repo import insert_farm_strategies, latest_prices

    settings = get_settings()
    league = settings.poe2_league
    prices = latest_prices(league)
    knowledge = _recent_knowledge()
    strategies, markdown = curate(knowledge, prices, league)
    insert_farm_strategies(strategies)
    print(markdown)
    print(f"\nfarm_strategy: wrote {len(strategies)} strategies for league={league}")
    return len(strategies)


def _recent_knowledge() -> list[dict[str, Any]]:
    from db.connection import fetch_all

    return fetch_all(
        "SELECT source_url, title, content FROM knowledge_chunk "
        "ORDER BY captured_at DESC LIMIT 60"
    )


if __name__ == "__main__":
    raise SystemExit(0 if run() >= 0 else 1)
