import pytest

from collector.curate import (
    estimate_profit_per_hour,
    parse_llm_json,
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
