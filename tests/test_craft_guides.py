"""Offline tests for the PT-BR craft guide generator (pure parsing/projection — no GLM/DB)."""

import pytest

from collector.craft_guides import build_prompt, parse_guides_json, to_rows

RAW = """```json
{"guides":[
  {"name":"+3 Spell Skills Wand","item_base":"Siphoning Wand","archetype":"caster",
   "budget":"high","mechanics":["essence","omen"],
   "overview":"Crafte um cetro de +3 spell skills.","steps":["Transmutation","Essence","Exalt"],
   "items":[{"name":"Exalted Orb","purpose":"adicionar modificadores"}],
   "faq":[{"q":"Caro?","a":"Sim, alto risco."}],
   "sources":["https://youtu.be/x"]},
  {"name":"Belt barato","item_base":"Heavy Belt","steps":["transmute"]}
]}
```"""

METHODS = [
    {"name": "+3 Spell Skills Wand", "expected_cost_div": 11.42, "roi_pct": 425,
     "item_base": "Siphoning Wand", "mechanics": ["essence", "omen", "currency"]},
    {"name": "Belt barato", "expected_cost_div": 0.03, "roi_pct": 8980, "mechanics": ["currency"]},
]


def test_parse_tolerant():
    resp = parse_guides_json(RAW)
    assert [g.name for g in resp.guides] == ["+3 Spell Skills Wand", "Belt barato"]
    assert resp.guides[0].sources[0] == {"url": "https://youtu.be/x"}  # string -> dict


def test_to_rows_takes_numbers_from_ev_and_sorts_by_roi():
    # RAW guides carry no id -> matched back by normalised name
    rows = to_rows(parse_guides_json(RAW), METHODS)
    assert [r["name"] for r in rows] == ["Belt barato", "+3 Spell Skills Wand"]  # 8980 > 425
    assert rows[0]["roi_pct"] == 8980 and rows[0]["expected_cost_div"] == 0.03
    assert rows[1]["roi_pct"] == 425 and rows[1]["expected_cost_div"] == 11.42
    assert rows[0]["mechanics"] == ["currency"]  # falls back to EV when guide omits them


def test_to_rows_matches_by_id_even_when_name_drifts():
    # the model renamed/translated the guide but echoed the id -> numbers still attach
    raw = '{"guides":[{"id":"m1","name":"Cinto Barato (traduzido!)","steps":["x"]}]}'
    rows = to_rows(parse_guides_json(raw), METHODS)
    assert rows[0]["roi_pct"] == 8980 and rows[0]["expected_cost_div"] == 0.03


def test_to_rows_without_ev_leaves_numbers_none():
    # numbers are calculated, never invented — no method to match means no number
    rows = to_rows(parse_guides_json(RAW))
    assert all(r["roi_pct"] is None and r["expected_cost_div"] is None for r in rows)


def test_build_prompt_carries_patch_and_computed_numbers():
    methods = [{
        "name": "M", "item_base": "B", "mechanics": ["omen"], "output": "X", "priced": True,
        "roi_pct": 300, "expected_cost_div": 5.0, "success_prob": 0.2, "steps": ["s1"],
        "missing_prices": [],
    }]
    p = build_prompt(methods, [{"title": "T", "content": "c"}], "0.5.4", "Runes of Aldur")
    assert "0.5.4" in p and "Runes of Aldur" in p
    assert "ROI ~300%" in p and "cost ~5.0 div" in p


def test_build_prompt_flags_unpriced_methods():
    methods = [{
        "name": "M", "item_base": "B", "mechanics": ["rune"], "output": "X", "priced": False,
        "roi_pct": None, "expected_cost_div": None, "success_prob": 1.0, "steps": [],
        "missing_prices": ["Foo Rune"],
    }]
    p = build_prompt(methods, [], "0.5.4", "L")
    assert "not yet priceable" in p and "Foo Rune" in p


def test_parse_salvages_truncated_response():
    # first guide complete, second cut off mid-object (token overrun) — keep the complete one
    truncated = '{"guides":[{"id":"m0","name":"A","steps":["x"]},{"id":"m1","name":"B","overv'
    resp = parse_guides_json(truncated)
    assert [g.name for g in resp.guides] == ["A"]


def test_parse_rejects_garbage():
    with pytest.raises(ValueError):
        parse_guides_json("not json")


def test_build_prompt_numbers_knowledge_for_citation():
    knowledge = [
        {"source_url": "https://www.youtube.com/watch?v=A", "title": "Essence", "content": "c"},
        {"source_url": "https://www.youtube.com/watch?v=B", "title": "Omen", "content": "c"},
    ]
    p = build_prompt([], knowledge, "0.5.4", "L")
    assert "[1] Essence: c" in p
    assert "[2] Omen: c" in p


def test_to_rows_resolves_source_refs_to_real_urls():
    raw = '{"guides":[{"id":"m0","name":"+3 Spell Skills Wand","source_refs":[2]}]}'
    ref_map = [
        {"url": "https://www.youtube.com/watch?v=A", "title": "A"},
        {"url": "https://www.youtube.com/watch?v=B", "title": "B"},
    ]
    rows = to_rows(parse_guides_json(raw), METHODS, ref_map)
    assert rows[0]["sources"] == [{"url": "https://www.youtube.com/watch?v=B", "title": "B"}]
