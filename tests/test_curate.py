import json

import pytest

import collector.curate as curate_mod
from collector.curate import (
    build_user_prompt,
    curate,
    estimate_profit_per_hour,
    parse_llm_json,
    run,
    to_farm_strategies,
    to_markdown,
)


def test_profit_per_hour_basic():
    # 5 drops × 10 chaos − 2 entry = 48 profit/map; 12 min/map => 5 maps/h => 240/h
    assert estimate_profit_per_hour(5, 10, 12, 2) == 240.0


def test_profit_per_hour_guards_zero_clear_time():
    assert estimate_profit_per_hour(5, 10, 0, 0) == 0.0


def test_parse_llm_json_plain():
    raw = '{"strategies":[{"name":"Breach","expected_drops_per_map":3,' \
          '"unit_price_chaos":20,"clear_time_minutes":6,"risk":"med","summary":"x"}]}'
    resp = parse_llm_json(raw)
    assert resp.strategies[0].name == "Breach"


def test_parse_llm_json_tolerates_code_fence():
    raw = '```json\n{"strategies":[{"name":"Ritual","clear_time_minutes":10}]}\n```'
    resp = parse_llm_json(raw)
    assert resp.strategies[0].name == "Ritual"


def test_parse_llm_json_rejects_garbage():
    with pytest.raises(ValueError):
        parse_llm_json("totally not json")


def test_to_farm_strategies_ranks_by_profit():
    raw = (
        '{"strategies":['
        '{"name":"Low","expected_drops_per_map":1,"unit_price_chaos":1,"clear_time_minutes":10},'
        '{"name":"High","expected_drops_per_map":10,"unit_price_chaos":10,"clear_time_minutes":5}'
        "]}"
    )
    strategies = to_farm_strategies(parse_llm_json(raw), "test-league")
    assert [s.name for s in strategies] == ["High", "Low"]
    assert strategies[0].league == "test-league"


def test_prefers_calculated_formula_over_llm_freetext():
    # the model gives an inflated free-text 999 AND real components -> the CALCULATED number wins
    raw = ('{"strategies":[{"name":"X","est_profit_per_hour":999,'
           '"expected_drops_per_map":2,"unit_price_chaos":5,"clear_time_minutes":6}]}')
    [s] = to_farm_strategies(parse_llm_json(raw), "L")
    assert s.est_profit_per_hour == 100.0  # (2*5)*(60/6), not 999


def test_falls_back_to_llm_estimate_when_no_components():
    raw = '{"strategies":[{"name":"Y","est_profit_per_hour":42}]}'  # no formula components
    [s] = to_farm_strategies(parse_llm_json(raw), "L")
    assert s.est_profit_per_hour == 42.0


def test_to_markdown_contains_estimate_disclaimer():
    strategies = to_farm_strategies(parse_llm_json('{"strategies":[]}'), "test-league")
    md = to_markdown(strategies, "test-league")
    assert "estimate" in md.lower()


def test_build_user_prompt_numbers_knowledge_for_citation():
    knowledge = [
        {"source_url": "https://www.youtube.com/watch?v=A", "title": "Ritual", "content": "c"},
        {"source_url": "https://www.youtube.com/watch?v=B", "title": "Abyss", "content": "c"},
    ]
    p = build_user_prompt(knowledge, [])
    assert "[1] Ritual: c" in p
    assert "[2] Abyss: c" in p


def test_to_farm_strategies_resolves_source_refs_to_real_urls():
    raw = '{"strategies":[{"name":"S","source_refs":[1]}]}'
    ref_map = [{"url": "https://www.youtube.com/watch?v=A", "title": "A"}]
    [s] = to_farm_strategies(parse_llm_json(raw), "L", ref_map)
    assert s.sources == [{"url": "https://www.youtube.com/watch?v=A", "title": "A"}]


def test_to_farm_strategies_falls_back_to_llm_sources_without_refs():
    raw = '{"strategies":[{"name":"S","sources":["https://youtu.be/x"]}]}'
    [s] = to_farm_strategies(parse_llm_json(raw), "L")
    assert s.sources == [{"url": "https://youtu.be/x"}]


# ── field coercion (the lenient _LLMStrategy validators) ────────────────────────────

def test_coerce_float_pulls_number_from_string_and_tolerates_null():
    # est_profit_per_hour: a string like "~42 divine" -> 42.0; explicit null -> None (fallback 0).
    raw = '{"strategies":[{"name":"A","est_profit_per_hour":"~42 divine"},' \
          '{"name":"B","est_profit_per_hour":null}]}'
    resp = parse_llm_json(raw)
    by_name = {s.name: s for s in resp.strategies}
    assert by_name["A"].est_profit_per_hour == 42.0
    assert by_name["B"].est_profit_per_hour is None


@pytest.mark.parametrize(
    "given, expected",
    [("Low", "low"), ("HIGH", "high"), ("moderate", "med"), ("", None)],
)
def test_risk_is_normalized(given, expected):
    raw = '{"strategies":[{"name":"R","risk":' + json.dumps(given) + "}]}"
    [s] = parse_llm_json(raw).strategies
    assert s.risk == expected


def test_sources_validator_keeps_dicts_and_drops_non_list():
    # a mixed list -> dict kept as-is, str wrapped; a non-list -> empty.
    [s] = parse_llm_json(
        '{"strategies":[{"name":"S","sources":[{"url":"u","title":"t"},"bare"]}]}'
    ).strategies
    assert s.sources == [{"url": "u", "title": "t"}, {"url": "bare"}]
    [t] = parse_llm_json('{"strategies":[{"name":"T","sources":"nope"}]}').strategies
    assert t.sources == []


# ── prompt pricing (_price_value: divine first, chaos fallback) ─────────────────────

def test_build_user_prompt_prices_divine_first_then_chaos():
    prices = [
        {"name": "Divine Orb", "item_type": "currency", "divine_value": 1.0},
        {"name": "Chaos Orb", "item_type": "currency", "chaos_value": 0.03},  # divine absent
        {"name": "Unpriced", "item_type": "currency"},  # no value -> skipped
    ]
    p = build_user_prompt([], prices)
    assert "- Divine Orb (currency): 1.0 divine" in p
    assert "- Chaos Orb (currency): 0.03 divine" in p
    assert "Unpriced" not in p


# ── parse_llm_json edge branches ────────────────────────────────────────────────────

def test_parse_llm_json_isolates_json_after_stray_prose():
    resp = parse_llm_json('Here you go: {"strategies":[{"name":"Z"}]}')
    assert resp.strategies[0].name == "Z"


def test_parse_llm_json_accepts_bare_list_of_strategies():
    resp = parse_llm_json('[{"name":"BareList"}]')
    assert resp.strategies[0].name == "BareList"


def test_parse_llm_json_rejects_schema_violation():
    # valid JSON, wrong shape (strategies must be a list) -> ValueError, not a raw ValidationError.
    with pytest.raises(ValueError, match="schema"):
        parse_llm_json('{"strategies":"not-a-list"}')


# ── to_markdown body (numbered entries with meta + summary) ─────────────────────────

def test_to_markdown_numbers_strategies_with_meta_and_summary():
    raw = ('{"strategies":[{"name":"Breach","est_profit_per_hour":50,'
           '"risk":"low","investment_required":3,"summary":"boa rota"}]}')
    md = to_markdown(to_farm_strategies(parse_llm_json(raw), "L"), "L")
    assert "### 1. Breach" in md
    assert "~50.0 div/h" in md
    assert "risk: low" in md
    assert "investment: 3.0" in md
    assert "- boa rota" in md


# ── curate() + run() + _recent_knowledge() pipeline (GLM + DB mocked) ───────────────

def test_curate_computes_profit_and_grounds_sources(monkeypatch):
    # The model cites knowledge [1] and gives formula components -> curate must COMPUTE the
    # profit/hour (not trust free text) and resolve the citation to the chunk's real url.
    knowledge = [{"source_url": "https://youtu.be/ID", "title": "Guide", "content": "c"}]
    llm_json = ('{"strategies":[{"name":"Ritual","est_profit_per_hour":999,'
                '"expected_drops_per_map":2,"unit_price_chaos":5,"clear_time_minutes":6,'
                '"source_refs":[1]}]}')
    monkeypatch.setattr(curate_mod, "glm_chat", lambda *a, **k: llm_json)
    strategies, markdown = curate(knowledge, [], "test-league")
    assert len(strategies) == 1
    s = strategies[0]
    assert s.est_profit_per_hour == 100.0  # (2*5)*(60/6), not the inflated 999
    assert s.sources == [{"url": "https://youtu.be/ID", "title": "Guide"}]
    assert "### 1. Ritual" in markdown


def test_run_reads_db_curates_and_writes(monkeypatch, capsys):
    monkeypatch.setattr(
        "db.repo.latest_prices",
        lambda league: [{"name": "Divine Orb", "item_type": "currency", "divine_value": 1.0}],
    )
    monkeypatch.setattr(
        "db.connection.fetch_all",
        lambda *a, **k: [{"source_url": "https://youtu.be/K", "title": "K", "content": "c"}],
    )
    written: list = []
    monkeypatch.setattr(
        "db.repo.insert_farm_strategies", lambda rows: written.append(rows) or len(rows)
    )
    monkeypatch.setattr(
        curate_mod, "glm_chat", lambda *a, **k: '{"strategies":[{"name":"Abyss"}]}'
    )
    count = run()
    assert count == 1
    assert [s.name for s in written[0]] == ["Abyss"]
    assert "farm_strategy: wrote 1 strategies" in capsys.readouterr().out
