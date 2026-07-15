import pytest

import collector.curate as curate_mod
from collector.curate import (
    _coerce_float,
    _LLMStrategy,
    _normalize_risk,
    _price_value,
    build_user_prompt,
    curate,
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


# --- pure helper edge branches ---------------------------------------------------------------


def test_coerce_float_handles_none_number_string_and_garbage():
    assert _coerce_float(None) is None
    assert _coerce_float(7) == 7.0
    assert _coerce_float("~12.5 divine") == 12.5  # pulls the leading number out of free text
    assert _coerce_float("-3") == -3.0
    assert _coerce_float("no digits here") is None


def test_normalize_risk_maps_prefixes_and_defaults_to_med():
    assert _normalize_risk(None) is None
    assert _normalize_risk("") is None
    assert _normalize_risk("Low") == "low"
    assert _normalize_risk("HIGH") == "high"
    assert _normalize_risk("moderate") == "med"  # anything else collapses to med


def test_llm_strategy_drops_non_list_sources():
    # a scalar `sources` (not a list) is coerced to an empty list, not an error
    s = _LLMStrategy.model_validate({"name": "X", "sources": "not-a-list"})
    assert s.sources == []


def test_llm_strategy_keeps_dict_sources_and_wraps_bare_urls():
    # dict entries pass through as-is; bare strings are wrapped in {"url": ...}
    s = _LLMStrategy.model_validate(
        {"name": "X", "sources": [{"url": "https://a", "title": "A"}, "https://b", 42]}
    )
    assert s.sources == [{"url": "https://a", "title": "A"}, {"url": "https://b"}]  # 42 dropped


def test_price_value_prefers_divine_then_falls_back_to_chaos():
    assert _price_value({"divine_value": 2.0, "chaos_value": 300}) == 2.0
    assert _price_value({"divine_value": None, "chaos_value": 150}) == 150  # PoE1-style fallback


def test_build_user_prompt_prices_use_divine_with_chaos_fallback():
    prices = [
        {"name": "Divine Orb", "item_type": "currency", "divine_value": 1.0, "chaos_value": None},
        {"name": "Chaos Orb", "item_type": "currency", "divine_value": None, "chaos_value": 0.5},
        {"name": "Unpriced", "item_type": "currency", "divine_value": None, "chaos_value": None},
    ]
    p = build_user_prompt([], prices)
    assert "Divine Orb (currency): 1.0 divine" in p
    assert "Chaos Orb (currency): 0.5 divine" in p
    assert "Unpriced" not in p  # rows with no usable price are dropped


# --- parse_llm_json defensive branches -------------------------------------------------------


def test_parse_llm_json_isolates_object_after_stray_prose():
    raw = 'Sure! Here is the JSON:\n{"strategies":[{"name":"Delirium"}]}'
    resp = parse_llm_json(raw)
    assert resp.strategies[0].name == "Delirium"


def test_parse_llm_json_accepts_bare_list_of_strategies():
    resp = parse_llm_json('[{"name":"Expedition"}]')
    assert resp.strategies[0].name == "Expedition"


def test_parse_llm_json_rejects_valid_json_failing_schema():
    # decodes fine, but a strategy missing its required `name` fails schema validation
    with pytest.raises(ValueError, match="schema validation"):
        parse_llm_json('{"strategies":[{"summary":"no name"}]}')


# --- to_markdown with real strategies --------------------------------------------------------


def test_to_markdown_numbers_strategies_with_meta_and_summary():
    raw = (
        '{"strategies":[{"name":"Breach","est_profit_per_hour":5,'
        '"risk":"high","investment_required":20,"summary":"corre breach"}]}'
    )
    strategies = to_farm_strategies(parse_llm_json(raw), "L")
    md = to_markdown(strategies, "L")
    assert "### 1. Breach" in md
    assert "risk: high" in md
    assert "investment: 20" in md
    assert "- corre breach" in md


# --- curate / run / _recent_knowledge network+dispatch surface -------------------------------


def test_curate_calls_glm_and_returns_ranked_strategies_and_markdown(monkeypatch):
    captured: dict[str, object] = {}

    def fake_glm_chat(messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return '{"strategies":[{"name":"Ritual","est_profit_per_hour":7}]}'

    monkeypatch.setattr(curate_mod, "glm_chat", fake_glm_chat)
    knowledge = [{"source_url": "https://youtu.be/a", "title": "Ritual guide", "content": "c"}]
    strategies, markdown = curate(knowledge, [], "test-league")

    assert [s.name for s in strategies] == ["Ritual"]
    assert strategies[0].league == "test-league"
    assert "Top farm strategies — test-league" in markdown
    # system + user turns were sent, and the curation temperature is fixed low
    assert [m["role"] for m in captured["messages"]] == ["system", "user"]
    assert captured["kwargs"]["temperature"] == 0.3


def test_run_wires_prices_knowledge_and_persistence(monkeypatch):
    import db.repo as repo

    written: dict[str, object] = {}
    monkeypatch.setattr(repo, "latest_prices", lambda league: [{"name": "p"}])
    monkeypatch.setattr(
        repo, "insert_farm_strategies", lambda strategies: written.setdefault("s", strategies)
    )
    monkeypatch.setattr(curate_mod, "_recent_knowledge", lambda: [{"title": "k"}])
    monkeypatch.setattr(
        curate_mod,
        "curate",
        lambda knowledge, prices, league: (["strat"], "# md"),
    )

    n = curate_mod.run()
    assert n == 1
    assert written["s"] == ["strat"]


def test_recent_knowledge_reads_latest_chunks(monkeypatch):
    import db.connection as connection

    seen: dict[str, str] = {}

    def fake_fetch_all(sql):
        seen["sql"] = sql
        return [{"source_url": "u", "title": "t", "content": "c"}]

    monkeypatch.setattr(connection, "fetch_all", fake_fetch_all)
    rows = curate_mod._recent_knowledge()
    assert rows == [{"source_url": "u", "title": "t", "content": "c"}]
    assert "FROM knowledge_chunk" in seen["sql"]
    assert "ORDER BY captured_at DESC" in seen["sql"]
