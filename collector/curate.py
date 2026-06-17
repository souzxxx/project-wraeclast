"""GLM curation (skill §4 & §5): turn raw knowledge + prices into ranked farm strategies.

The LLM proposes strategies and the raw inputs (expected drops, clear time, entry cost);
profit/hour is then COMPUTED here, not taken as free text. Output is strict JSON validated
with pydantic. Also emits a human-readable markdown block for the Obsidian export.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError, field_validator

from collector.config import get_settings
from collector.llm import glm_chat
from db.models import FarmStrategy


def _coerce_float(value: Any) -> float | None:
    """Accept numbers or strings like '12 divine' / '~5'; pull the leading number."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+\.?\d*", str(value))
    return float(match.group()) if match else None


def _normalize_risk(value: Any) -> str | None:
    if not value:
        return None
    text = str(value).strip().lower()
    if text.startswith("l"):
        return "low"
    if text.startswith("h"):
        return "high"
    return "med"  # medium/moderate/mid/etc.


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
    # Direct, source-grounded estimate (divine/hour). Community guides usually state this.
    est_profit_per_hour: float | None = None
    # Components for the formula cross-check (often less reliable than the direct estimate).
    expected_drops_per_map: float = 0.0
    unit_price_chaos: float = 0.0
    clear_time_minutes: float = 0.0
    entry_cost_chaos: float = 0.0
    investment_required: float | None = None
    risk: str | None = None
    summary: str = ""
    sources: list[dict[str, Any]] = []

    @field_validator(
        "expected_drops_per_map", "unit_price_chaos", "clear_time_minutes", "entry_cost_chaos",
        mode="before",
    )
    @classmethod
    def _req_float(cls, v: Any) -> float:
        return _coerce_float(v) or 0.0

    @field_validator("est_profit_per_hour", "investment_required", mode="before")
    @classmethod
    def _opt_float(cls, v: Any) -> float | None:
        return _coerce_float(v)

    @field_validator("risk", mode="before")
    @classmethod
    def _risk(cls, v: Any) -> str | None:
        return _normalize_risk(v)

    @field_validator("sources", mode="before")
    @classmethod
    def _sources(cls, v: Any) -> list[dict[str, Any]]:
        if not isinstance(v, list):
            return []
        out: list[dict[str, Any]] = []
        for x in v:
            if isinstance(x, dict):
                out.append(x)
            elif isinstance(x, str):
                out.append({"url": x})
        return out


class _LLMResponse(BaseModel):
    strategies: list[_LLMStrategy]


_SYSTEM = (
    "You are a Path of Exile 2 economy analyst. From the community knowledge + current prices, "
    "identify the farm strategies with the most traction right now. For each, give "
    "`est_profit_per_hour`: your best estimate of NET profit per hour in DIVINE orbs, grounded "
    "in the community sources (guides often state a per-hour figure directly — use it; never "
    "negative). Also fill the cross-check components (expected_drops_per_map, unit_price_chaos "
    "in divine, clear_time_minutes, entry_cost) when you can. Output STRICT JSON only — no "
    'markdown, no prose outside the JSON. Schema: {"strategies":[{"name","est_profit_per_hour",'
    '"expected_drops_per_map","unit_price_chaos","clear_time_minutes","entry_cost_chaos",'
    '"investment_required","risk":"low|med|high","summary","sources":[{"url","title"}]}]}. '
    "Everything is an ESTIMATE."
)


def _price_value(p: dict[str, Any]) -> float | None:
    """PoE2 prices are denominated in divine; fall back to chaos for PoE1-style data."""
    return p.get("divine_value") if p.get("divine_value") is not None else p.get("chaos_value")


def build_user_prompt(knowledge: list[dict[str, Any]], prices: list[dict[str, Any]]) -> str:
    price_lines = [
        f"- {p['name']} ({p['item_type']}): {_price_value(p)} divine"
        for p in prices[:120]
        if _price_value(p) is not None
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
    """Parse the model's JSON defensively: strip code fences, isolate the JSON object/array,
    accept a bare list of strategies, and validate (lenient field coercion in _LLMStrategy)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1] if "```" in cleaned[3:] else cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    # Isolate the outermost JSON structure in case the model added stray prose.
    start = min((i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1), default=-1)
    if start > 0:
        cleaned = cleaned[start:]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM did not return valid JSON: {exc}") from exc
    if isinstance(data, list):
        data = {"strategies": data}
    try:
        return _LLMResponse.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"LLM JSON failed schema validation: {exc}") from exc


def to_farm_strategies(resp: _LLMResponse, league: str) -> list[FarmStrategy]:
    out: list[FarmStrategy] = []
    for s in resp.strategies:
        # Prefer the model's source-grounded per-hour estimate; the naive formula on
        # hallucinated components tends to go negative. Fall back to the formula otherwise.
        formula = estimate_profit_per_hour(
            s.expected_drops_per_map, s.unit_price_chaos, s.clear_time_minutes, s.entry_cost_chaos
        )
        pph = s.est_profit_per_hour if s.est_profit_per_hour is not None else formula
        pph = max(pph, 0.0)
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
        lines.append(f"- **~{s.est_profit_per_hour} div/h** · risk: {s.risk or 'n/a'} "
                     f"· investment: {s.investment_required or 'n/a'}")
        if s.summary:
            lines.append(f"- {s.summary}")
        lines.append("")
    return "\n".join(lines)


def curate(
    knowledge: list[dict[str, Any]], prices: list[dict[str, Any]], league: str
) -> tuple[list[FarmStrategy], str]:
    settings = get_settings()
    text = glm_chat(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": build_user_prompt(knowledge, prices)},
        ],
        model=settings.glm_curation_model,
        temperature=0.3,
    )
    parsed = parse_llm_json(text)
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
