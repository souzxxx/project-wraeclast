import pytest

import collector.guides as guides_mod
from collector.guides import build_prompt, generate, parse_guides_json, to_rows

RAW = """```json
{"guides":[
  {"name":"Ritual Omen","profit_per_hour":"32 div","risk":"medium","target_currency":"Divine Orb",
   "overview":"Run rituals.","steps":["Set tablets","Run maps","Defer altars"],
   "items":[{"name":"Ritual tablet","purpose":"spawn altars"}],
   "atlas":"Pegue os notáveis de Ritual e densidade de monstros.",
   "faq":[{"q":"Risky?","a":"Death penalty on reroll."}],
   "sources":["https://youtu.be/x"]},
  {"name":"Breach","profit_per_hour":-5,"risk":"med","steps":["open breaches"]}
]}
```"""


def test_parse_guides_tolerant():
    resp = parse_guides_json(RAW)
    assert [g.name for g in resp.guides] == ["Ritual Omen", "Breach"]
    assert resp.guides[0].profit_per_hour == 32.0  # "32 div" coerced
    assert resp.guides[0].sources[0] == {"url": "https://youtu.be/x"}  # string -> dict


def test_to_rows_sorts_and_clamps():
    rows = to_rows(parse_guides_json(RAW))
    assert rows[0]["name"] == "Ritual Omen"
    assert rows[1]["profit_per_hour"] == 0.0  # -5 clamped to 0
    assert rows[0]["items"][0] == {"name": "Ritual tablet", "purpose": "spawn altars"}
    assert rows[0]["steps"] == ["Set tablets", "Run maps", "Defer altars"]
    assert "Ritual" in rows[0]["atlas"]
    assert rows[1]["atlas"] == ""  # missing atlas defaults to empty


def test_parse_salvages_truncated_response():
    # second guide cut off mid-object — the complete first guide must still come through
    truncated = '{"guides":[{"name":"A","steps":["x"]},{"name":"B","prof'
    resp = parse_guides_json(truncated)
    assert [g.name for g in resp.guides] == ["A"]


def test_parse_rejects_garbage():
    with pytest.raises(ValueError):
        parse_guides_json("not json")


def test_build_prompt_numbers_knowledge_for_citation():
    knowledge = [
        {"source_url": "https://www.youtube.com/watch?v=A", "title": "Ritual", "content": "c"},
        {"source_url": "https://www.youtube.com/watch?v=B", "title": "Abyss", "content": "c"},
    ]
    p = build_prompt(knowledge, [])
    assert "[1] Ritual: c" in p
    assert "[2] Abyss: c" in p


def test_to_rows_resolves_source_refs_to_real_chunk_urls():
    raw = '{"guides":[{"name":"G","source_refs":[2]}]}'
    ref_map = [
        {"url": "https://www.youtube.com/watch?v=A", "title": "A"},
        {"url": "https://www.youtube.com/watch?v=B", "title": "B"},
    ]
    rows = to_rows(parse_guides_json(raw), ref_map)
    assert rows[0]["sources"] == [{"url": "https://www.youtube.com/watch?v=B", "title": "B"}]


def test_to_rows_falls_back_to_llm_sources_without_refs():
    # no source_refs and no ref_map -> existing behaviour: keep whatever the LLM put in sources
    rows = to_rows(parse_guides_json(RAW))
    assert rows[0]["sources"] == [{"url": "https://youtu.be/x"}]


def test_generate_attaches_real_source_urls(monkeypatch):
    # The model cites knowledge by number; generate must resolve it to the chunk's REAL url.
    knowledge = [{"source_url": "https://www.youtube.com/watch?v=ID", "title": "T", "content": "c"}]
    monkeypatch.setattr(
        guides_mod, "glm_chat", lambda *a, **k: '{"guides":[{"name":"G","source_refs":[1]}]}'
    )
    rows = generate(knowledge, [])
    assert rows[0]["sources"] == [{"url": "https://www.youtube.com/watch?v=ID", "title": "T"}]
