import pytest

from collector.guides import parse_guides_json, to_rows

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
