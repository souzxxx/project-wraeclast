"""Generate full PT-BR craft guides with GLM (Craft 4) — the craft analogue of guides.py.

One GLM call turns the EV-ranked craft methods into execution-ready tutorials (overview, ordered
steps, consumables + purpose, FAQ, sources), in Brazilian Portuguese. The guides are grounded in:
  - the EV-ranked methods (real expected cost + ROI from live prices — Craft 3/3.5),
  - the curated craft knowledge corpus (mechanics depth),
  - the current patch/league LABEL (config-driven, never hardcoded in prose).

Craft is NOT just currency: the prompt spans essences, omens, abyss, runes, catalysts. The
cost/ROI COLUMNS come from the EV engine, not the LLM — `to_rows` matches each guide back to its
method by a verbatim `id` (with a normalised-name fallback) — and the prompt forbids the model
from quoting any figure in prose. Strict JSON, tolerant parsing (same as guides.py).
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

MAX_GUIDES = 8
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


class _CraftGuide(BaseModel):
    id: str = ""  # the method id (m0, m1, …) echoed back, so EV numbers match even if name drifts
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
    # 1-based numbers of the CRAFT KNOWLEDGE entries the model used; resolved to real chunk URLs in
    # to_rows (source_refs.resolve_source_refs). Raw here; resolution does the coercion.
    source_refs: list[Any] = []

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

    @field_validator("source_refs", mode="before")
    @classmethod
    def _source_refs(cls, v: Any) -> list[Any]:
        return v if isinstance(v, list) else []


class _GuidesResponse(BaseModel):
    guides: list[_CraftGuide]


_SYSTEM = (
    "You are a Path of Exile 2 CRAFTING coach. From the EV-ranked craft methods + craft knowledge, "
    f"write complete, execution-ready guides for up to {MAX_GUIDES} craft methods. Craft is NOT "
    "just currency orbs — cover the mechanic each method uses (essences, omens, abyss, runes, "
    "soul cores, catalysts, meta-crafting). Each guide must let a player execute it PERFECTLY and "
    "answer likely doubts. "
    "GROUNDING RULES: rely ONLY on the provided methods, knowledge and numbers. "
    "(1) Echo each method's `id` (e.g. m0) VERBATIM so its computed numbers attach back. "
    "(2) VERSION: name ONLY the patch in the PATCH header; if any provided knowledge mentions a "
    "different patch number, IGNORE that number — never write another version. "
    "(3) NEVER write a cost, ROI, percentage, chance or 'div' figure in any prose field "
    "(overview/steps/items/faq) — those are computed and attached separately; describe steps "
    "qualitatively instead. "
    "(4) Catalysts add quality to a Rare that boosts the magnitude of EXISTING modifiers of the "
    "matching type; a catalyst alone does not add a new mod. "
    "IMPORTANT: write every TEXT VALUE in BRAZILIAN PORTUGUESE (pt-BR) — overview, steps, item "
    "purposes, faq. Keep JSON keys in English exactly as the schema, and keep proper nouns "
    "(item/currency/mod names) in their in-game form. Output STRICT JSON only — no markdown. "
    'Schema: {"guides":[{"id"(the method id, e.g. m0),"name"(the method name),"item_base",'
    '"archetype","budget":"low|med|high","mechanics":["essence","omen",...],'
    '"overview"(2-3 frases),"steps":["passos concretos em ordem, SEM números de custo/ROI"],'
    '"items":[{"name","purpose"}](orbs/essences/omens/runas/catalysts e por quê),'
    '"faq":[{"q","a"}](dúvidas e erros comuns),"source_refs":[números do CRAFT KNOWLEDGE usado]}'
    "]}. "
    "The CRAFT KNOWLEDGE entries are numbered [1], [2], …; in `source_refs` list only the numbers "
    "of the entries that actually grounded each guide (e.g. [2,5]) — these are the [n] knowledge "
    "refs, NOT the method ids m#. "
    "Seja específico e prático."
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
            g
            for obj in iter_array_objects(cleaned, "guides")
            if (g := _validate_guide(obj)) is not None
        ]
        if not guides:
            raise ValueError("craft guides JSON unrecoverable") from None
        return _GuidesResponse(guides=guides)


def _validate_guide(obj: dict[str, Any]) -> _CraftGuide | None:
    try:
        return _CraftGuide.model_validate(obj)
    except ValidationError:
        return None


def _norm(s: str | None) -> str:
    return " ".join((s or "").casefold().split())


def to_rows(
    resp: _GuidesResponse,
    methods_ev: list[dict[str, Any]] | None = None,
    ref_map: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Project parsed guides to rows, taking cost/ROI from the EV engine — matched back to each
    method by its verbatim `id` (m0, m1, …), falling back to a normalised name — so the numbers
    are calculated, never LLM-invented even if the model tweaks the name. Best-ROI first (None
    last)."""
    methods_ev = methods_ev or []
    ref_map = ref_map or []
    by_id = {f"m{i}": m for i, m in enumerate(methods_ev)}
    by_name = {_norm(m.get("name")): m for m in methods_ev if m.get("name")}
    rows: list[dict[str, Any]] = []
    for g in resp.guides[:MAX_GUIDES]:
        ev = by_id.get(g.id.strip()) or by_name.get(_norm(g.name)) or {}
        # Prefer real chunk URLs resolved from the model's numeric citations; fall back to whatever
        # the model put in `sources` only when it gave no usable refs (keeps display non-empty).
        sources = resolve_source_refs(g.source_refs, ref_map) or g.sources
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
                "sources": sources,
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

    methods_block = "\n".join(
        f"m{i}: {fmt(m)}" for i, m in enumerate(methods_ev[:MAX_GUIDES])
    )
    numbered, _ = number_knowledge(knowledge[:_K_MAX], _K_CHARS)
    return (
        f"PATCH: PoE2 {patch} — league {league} (the ONLY version you may name)\n\n"
        "EV-RANKED CRAFT METHODS (each has an id m#; echo it back. Numbers are computed — use "
        "them, never write them in prose):\n"
        + methods_block
        + "\n\nCRAFT KNOWLEDGE:\n"
        + numbered
        + "\n\nWrite the PT-BR craft guides as strict JSON."
    )


def generate(
    methods_ev: list[dict[str, Any]], knowledge: list[dict[str, Any]], patch: str, league: str
) -> list[dict[str, Any]]:
    _, ref_map = number_knowledge(knowledge[:_K_MAX], _K_CHARS)
    text = glm_chat(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": build_prompt(methods_ev, knowledge, patch, league)},
        ],
        model=get_settings().glm_curation_model,
        temperature=0.4,
    )
    return to_rows(parse_guides_json(text), methods_ev, ref_map)


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
