"""Generate full "concretized" farm guides with GLM, from the curated community knowledge.

One streamed GLM call synthesizes the top farms into step-by-step tutorials (overview, steps,
items + purpose, FAQ, sources), grounded in the YouTube/community knowledge + current prices.
Strict JSON, validated with pydantic and the same tolerant parsing as curate.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError, field_validator

from collector.config import get_settings
from collector.llm import glm_chat

MAX_GUIDES = 5


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"-?\d+\.?\d*", str(value))
    return float(m.group()) if m else None


class _Item(BaseModel):
    name: str = ""
    purpose: str = ""


class _Faq(BaseModel):
    q: str = ""
    a: str = ""


class _Guide(BaseModel):
    name: str
    profit_per_hour: float | None = None
    risk: str | None = None
    target_currency: str | None = None
    overview: str = ""
    steps: list[str] = []
    items: list[_Item] = []
    faq: list[_Faq] = []
    sources: list[dict[str, Any]] = []

    @field_validator("profit_per_hour", mode="before")
    @classmethod
    def _pph(cls, v: Any) -> float | None:
        return _coerce_float(v)

    @field_validator("steps", mode="before")
    @classmethod
    def _steps(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(x) for x in v if x]
        return []

    @field_validator("sources", mode="before")
    @classmethod
    def _sources(cls, v: Any) -> list[dict[str, Any]]:
        if not isinstance(v, list):
            return []
        return [x if isinstance(x, dict) else {"url": str(x)} for x in v]


class _GuidesResponse(BaseModel):
    guides: list[_Guide]


_SYSTEM = (
    "You are a Path of Exile 2 farming coach. From the community knowledge + prices, write "
    f"complete, execution-ready guides for the top {MAX_GUIDES} farm strategies. Each guide must "
    "let a player run it PERFECTLY and answer likely doubts. Output STRICT JSON only — no "
    'markdown. Schema: {"guides":[{"name","profit_per_hour"(divine/h number),'
    '"risk":"low|med|high","target_currency","overview"(2-3 sentences),'
    '"steps":["ordered, concrete actions"],"items":[{"name","purpose"}](maps/tablets/scarabs/'
    'gear/gems needed and why),"faq":[{"q","a"}](common pitfalls & doubts),'
    '"sources":[{"url","title"}](from the provided knowledge)}]}. Be specific and practical. '
    "Everything is an ESTIMATE."
)


def parse_guides_json(text: str) -> _GuidesResponse:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1] if "```" in cleaned[3:] else cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    start = cleaned.find("{")
    if start > 0:
        cleaned = cleaned[start:]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"guides JSON invalid: {exc}") from exc
    try:
        return _GuidesResponse.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"guides JSON failed schema: {exc}") from exc


def to_rows(resp: _GuidesResponse) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for g in resp.guides[:MAX_GUIDES]:
        pph = g.profit_per_hour
        rows.append(
            {
                "name": g.name,
                "profit_per_hour": max(pph, 0.0) if pph is not None else None,
                "risk": g.risk,
                "target_currency": g.target_currency,
                "overview": g.overview,
                "steps": g.steps,
                "items": [i.model_dump() for i in g.items],
                "faq": [f.model_dump() for f in g.faq],
                "sources": g.sources,
            }
        )
    rows.sort(key=lambda r: r["profit_per_hour"] or 0, reverse=True)
    return rows


def build_prompt(knowledge: list[dict[str, Any]], prices: list[dict[str, Any]]) -> str:
    k = [f"- {x.get('title')}: {(x.get('content') or '')[:700]}" for x in knowledge[:30]]
    p = [
        f"- {x['name']}: {x.get('divine_value') or x.get('chaos_value')} div"
        for x in prices[:80]
        if (x.get("divine_value") or x.get("chaos_value")) is not None
    ]
    return (
        "COMMUNITY KNOWLEDGE:\n" + "\n".join(k) + "\n\nPRICES (divine):\n" + "\n".join(p)
        + "\n\nWrite the farm guides as strict JSON."
    )


def generate(knowledge: list[dict[str, Any]], prices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    text = glm_chat(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": build_prompt(knowledge, prices)},
        ],
        model=get_settings().glm_curation_model,
        temperature=0.4,
    )
    return to_rows(parse_guides_json(text))


def run() -> int:
    from db.connection import fetch_all
    from db.repo import latest_prices, replace_farm_guides

    settings = get_settings()
    league = settings.poe2_league
    knowledge = fetch_all(
        "SELECT source_url, title, content FROM knowledge_chunk ORDER BY captured_at DESC LIMIT 40"
    )
    rows = generate(knowledge, latest_prices(league))
    replace_farm_guides(league, rows)
    print(f"farm_guide: wrote {len(rows)} guides for league={league}")
    return len(rows)


if __name__ == "__main__":
    raise SystemExit(0 if run() >= 0 else 1)
