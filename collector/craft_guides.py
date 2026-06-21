"""Generate full PT-BR craft guides with GLM (Craft 4) — the craft analogue of guides.py.

One GLM call turns the EV-ranked craft methods into execution-ready tutorials (overview, ordered
steps, consumables + purpose, FAQ, sources), in Brazilian Portuguese. The guides are grounded in:
  - the EV-ranked methods (real expected cost + ROI from live prices — Craft 3/3.5),
  - the curated craft knowledge corpus (mechanics depth),
  - the current patch/league LABEL (config-driven, never hardcoded in prose).

Craft is NOT just currency: the prompt spans essences, omens, abyss, runes, catalysts. The
NUMBERS (cost/ROI) are taken from the EV engine, not the LLM — `to_rows` overrides them by name —
so a guide can't quote an invented figure. Strict JSON, tolerant parsing (same as guides.py).
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError, field_validator

from collector.config import get_settings
from collector.llm import glm_chat

MAX_GUIDES = 8


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


class _CraftGuide(BaseModel):
    name: str
    item_base: str = ""
    archetype: str | None = None
    budget: str | None = None  # low | med | high
    mechanics: list[str] = []
    overview: str = ""
    steps: list[str] = []
    items: list[_Item] = []
    faq: list[_Faq] = []
    sources: list[dict[str, Any]] = []

    @field_validator("steps", "mechanics", mode="before")
    @classmethod
    def _strlist(cls, v: Any) -> list[str]:
        return [str(x) for x in v if x] if isinstance(v, list) else []

    @field_validator("sources", mode="before")
    @classmethod
    def _sources(cls, v: Any) -> list[dict[str, Any]]:
        if not isinstance(v, list):
            return []
        return [x if isinstance(x, dict) else {"url": str(x)} for x in v]


class _GuidesResponse(BaseModel):
    guides: list[_CraftGuide]


_SYSTEM = (
    "You are a Path of Exile 2 CRAFTING coach. From the EV-ranked craft methods + craft knowledge, "
    f"write complete, execution-ready guides for up to {MAX_GUIDES} craft methods. Craft is NOT "
    "just currency orbs — cover the mechanic each method uses (essences, omens, abyss, runes, "
    "soul cores, catalysts, meta-crafting). Each guide must let a player execute it PERFECTLY and "
    "answer likely doubts. "
    "GROUNDING RULES: write for the patch/league given in context; rely ONLY on the provided "
    "methods, knowledge and numbers — do NOT invent patch-specific balance values, and do NOT "
    "quote a cost or ROI yourself (those are computed and attached separately). Keep each guide's "
    "`name` EXACTLY as the provided method name so the numbers can be matched back. "
    "IMPORTANT: write every TEXT VALUE in BRAZILIAN PORTUGUESE (pt-BR) — overview, steps, item "
    "purposes, faq. Keep JSON keys in English exactly as the schema, and keep proper nouns "
    "(item/currency/mod names) in their in-game form. Output STRICT JSON only — no markdown. "
    'Schema: {"guides":[{"name"(exact method name),"item_base","archetype","budget":"low|med|high",'
    '"mechanics":["essence","omen",...],"overview"(2-3 frases),"steps":["passos concretos em '
    'ordem"],"items":[{"name","purpose"}](orbs/essences/omens/runas/catalysts e por quê),'
    '"faq":[{"q","a"}](dúvidas e erros comuns),"sources":[{"url","title"}]}]}. '
    "Seja específico e prático. Custo e ROI são ESTIMATIVAS calculadas dos preços vivos."
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
        raise ValueError(f"craft guides JSON invalid: {exc}") from exc
    try:
        return _GuidesResponse.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f"craft guides JSON failed schema: {exc}") from exc


def to_rows(
    resp: _GuidesResponse, ev_by_name: dict[str, dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Project parsed guides to rows, taking the cost/ROI from the EV engine (by name match) so
    the numbers are calculated, not LLM-invented. Sorted best-ROI first (None last)."""
    ev_by_name = ev_by_name or {}
    rows: list[dict[str, Any]] = []
    for g in resp.guides[:MAX_GUIDES]:
        ev = ev_by_name.get(g.name, {})
        rows.append(
            {
                "name": g.name,
                "item_base": g.item_base or ev.get("item_base", ""),
                "archetype": g.archetype or ev.get("archetype"),
                "budget": g.budget,
                "mechanics": g.mechanics or ev.get("mechanics", []),
                "expected_cost_div": _coerce_float(ev.get("expected_cost_div")),
                "roi_pct": _coerce_float(ev.get("roi_pct")),
                "overview": g.overview,
                "steps": g.steps,
                "items": [i.model_dump() for i in g.items],
                "faq": [f.model_dump() for f in g.faq],
                "sources": g.sources,
            }
        )
    rows.sort(key=lambda r: (r["roi_pct"] is not None, r["roi_pct"] or 0), reverse=True)
    return rows


def build_prompt(
    methods_ev: list[dict[str, Any]], knowledge: list[dict[str, Any]], patch: str, league: str
) -> str:
    def fmt(m: dict[str, Any]) -> str:
        cost = m.get("expected_cost_div")
        roi = m.get("roi_pct")
        mech = ", ".join(m.get("mechanics") or []) or "craft"
        if m.get("priced") and roi is not None:
            econ = f"cost ~{cost} div, ROI ~{roi}%"
        else:
            miss = ", ".join(m.get("missing_prices") or []) or "n/a"
            econ = f"cost not yet priceable (missing: {miss})"
        return (
            f"- {m.get('name')} | base {m.get('item_base')} | [{mech}] | makes {m.get('output')} | "
            f"{econ} | success {m.get('success_prob')} | steps: {' / '.join(m.get('steps') or [])}"
        )

    methods_block = "\n".join(fmt(m) for m in methods_ev[:MAX_GUIDES])
    k = [f"- {x.get('title')}: {(x.get('content') or '')[:700]}" for x in knowledge[:30]]
    return (
        f"PATCH: PoE2 {patch} — league {league}\n\n"
        "EV-RANKED CRAFT METHODS (numbers are computed from live prices; use them, don't invent):\n"
        + methods_block
        + "\n\nCRAFT KNOWLEDGE:\n"
        + "\n".join(k)
        + "\n\nWrite the PT-BR craft guides as strict JSON."
    )


def generate(
    methods_ev: list[dict[str, Any]], knowledge: list[dict[str, Any]], patch: str, league: str
) -> list[dict[str, Any]]:
    text = glm_chat(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": build_prompt(methods_ev, knowledge, patch, league)},
        ],
        model=get_settings().glm_curation_model,
        temperature=0.4,
    )
    ev_by_name = {m.get("name"): m for m in methods_ev if m.get("name")}
    return to_rows(parse_guides_json(text), ev_by_name)


def run() -> int:
    from api.craft_ev import rank_methods
    from db.repo import (
        latest_craft_knowledge,
        latest_craft_methods,
        latest_prices,
        replace_craft_guides,
    )

    settings = get_settings()
    league = settings.poe2_league
    methods_ev = rank_methods(latest_craft_methods(league), latest_prices(league, limit=1000))
    knowledge = latest_craft_knowledge(limit=40)
    rows = generate(methods_ev, knowledge, settings.poe2_patch, league)
    replace_craft_guides(league, rows)
    print(f"craft_guide: wrote {len(rows)} guides for {league} (patch {settings.poe2_patch})")
    return len(rows)


if __name__ == "__main__":
    raise SystemExit(0 if run() >= 0 else 1)
