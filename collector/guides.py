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
from collector.json_salvage import iter_array_objects
from collector.llm import glm_chat
from collector.source_refs import number_knowledge, resolve_source_refs

MAX_GUIDES = 6
_K_MAX = 30  # knowledge entries fed to the model
_K_CHARS = 700  # chars of each entry's content


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
    atlas: str = ""
    faq: list[_Faq] = []
    sources: list[dict[str, Any]] = []
    # 1-based numbers of the COMMUNITY KNOWLEDGE entries the model used; resolved to real chunk
    # URLs in to_rows (source_refs.resolve_source_refs). Raw here; resolution does the coercion.
    source_refs: list[Any] = []

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

    @field_validator("source_refs", mode="before")
    @classmethod
    def _source_refs(cls, v: Any) -> list[Any]:
        return v if isinstance(v, list) else []


class _GuidesResponse(BaseModel):
    guides: list[_Guide]


_SYSTEM = (
    "You are a Path of Exile 2 farming coach. From the community knowledge + prices, write "
    f"complete, execution-ready guides for the top {MAX_GUIDES} farm strategies. One of them "
    "MUST be a TABLET farming strategy (precursor tablets / towers) if the data supports it. "
    "Each guide must let a player run it PERFECTLY and answer likely doubts. "
    "IMPORTANT: write every TEXT VALUE in BRAZILIAN PORTUGUESE (pt-BR) — overview, steps, "
    "item purposes, atlas, faq. Keep the JSON keys in English exactly as in the schema, and "
    "keep proper nouns (item/skill names) in their in-game form. Output STRICT JSON only — no "
    'markdown. Schema: {"guides":[{"name","profit_per_hour"(divine/h number),'
    '"risk":"low|med|high","target_currency","overview"(2-3 frases),'
    '"steps":["ações concretas em ordem"],"items":[{"name","purpose"}](mapas/tablets/scarabs/'
    'gear/gems necessários e por quê),"atlas"(como montar e upar a árvore do Atlas para esse '
    'farm: quais nós/notáveis priorizar, setup de torres/tablets),"faq":[{"q","a"}](dúvidas '
    'comuns e erros),"source_refs":[números das fontes usadas]}]}. '
    "As COMMUNITY KNOWLEDGE estão numeradas [1], [2], …; em `source_refs` liste apenas os números "
    "das entradas que realmente embasaram cada guia (ex.: [1,4]). "
    "Seja específico e prático. Tudo é ESTIMATIVA."
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
        return _GuidesResponse.model_validate(json.loads(cleaned))
    except (json.JSONDecodeError, ValidationError):
        # Salvage every complete guide from a truncated/garbled response (token overrun): a cut
        # tail then costs only the last guide, not the whole daily batch.
        guides = [
            g for obj in iter_array_objects(cleaned, "guides") if (g := _validate_guide(obj))
        ]
        if not guides:
            raise ValueError("guides JSON unrecoverable") from None
        return _GuidesResponse(guides=guides)


def _validate_guide(obj: dict[str, Any]) -> _Guide | None:
    try:
        return _Guide.model_validate(obj)
    except ValidationError:
        return None


def to_rows(
    resp: _GuidesResponse, ref_map: list[dict[str, str]] | None = None
) -> list[dict[str, Any]]:
    ref_map = ref_map or []
    rows: list[dict[str, Any]] = []
    for g in resp.guides[:MAX_GUIDES]:
        pph = g.profit_per_hour
        # Prefer real chunk URLs resolved from the model's numeric citations; fall back to whatever
        # the model put in `sources` only when it gave no usable refs (keeps display non-empty).
        sources = resolve_source_refs(g.source_refs, ref_map) or g.sources
        rows.append(
            {
                "name": g.name,
                "profit_per_hour": max(pph, 0.0) if pph is not None else None,
                "risk": g.risk,
                "target_currency": g.target_currency,
                "overview": g.overview,
                "steps": g.steps,
                "items": [i.model_dump() for i in g.items],
                "atlas": g.atlas,
                "faq": [f.model_dump() for f in g.faq],
                "sources": sources,
            }
        )
    rows.sort(key=lambda r: r["profit_per_hour"] or 0, reverse=True)
    return rows


def build_prompt(knowledge: list[dict[str, Any]], prices: list[dict[str, Any]]) -> str:
    numbered, _ = number_knowledge(knowledge[:_K_MAX], _K_CHARS)
    p = [
        f"- {x['name']}: {x.get('divine_value') or x.get('chaos_value')} div"
        for x in prices[:80]
        if (x.get("divine_value") or x.get("chaos_value")) is not None
    ]
    return (
        "COMMUNITY KNOWLEDGE:\n" + numbered + "\n\nPRICES (divine):\n" + "\n".join(p)
        + "\n\nWrite the farm guides as strict JSON."
    )


def generate(knowledge: list[dict[str, Any]], prices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    _, ref_map = number_knowledge(knowledge[:_K_MAX], _K_CHARS)
    text = glm_chat(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": build_prompt(knowledge, prices)},
        ],
        model=get_settings().glm_curation_model,
        temperature=0.4,
    )
    return to_rows(parse_guides_json(text), ref_map)


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
