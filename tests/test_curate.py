import pytest

import collector.curate as curate_mod
from collector.curate import (
    _coerce_float,
    _normalize_risk,
    _price_value,
    _recent_knowledge,
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


# --- _coerce_float --------------------------------------------------------

def test_coerce_float_none_returns_none():
    assert _coerce_float(None) is None


def test_coerce_float_pulls_leading_number_from_string():
    assert _coerce_float("~12.5 divine") == 12.5
    assert _coerce_float("-3 chaos") == -3.0


def test_coerce_float_no_number_returns_none():
    assert _coerce_float("divine") is None


# --- _normalize_risk ------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Low", "low"),
        ("high", "high"),
        ("moderate", "med"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_risk(raw, expected):
    assert _normalize_risk(raw) == expected


# --- validator branches (via _LLMStrategy through parse_llm_json) ---------

def test_sources_validator_drops_non_list():
    # A non-list `sources` value is coerced to an empty list, not carried through.
    [s] = parse_llm_json('{"strategies":[{"name":"S","sources":"not-a-list"}]}').strategies
    assert s.sources == []


def test_sources_validator_keeps_dict_entries():
    raw = '{"strategies":[{"name":"S","sources":[{"url":"https://youtu.be/x","title":"t"}]}]}'
    [s] = parse_llm_json(raw).strategies
    assert s.sources == [{"url": "https://youtu.be/x", "title": "t"}]


def test_source_refs_validator_drops_non_list():
    [s] = parse_llm_json('{"strategies":[{"name":"S","source_refs":"nope"}]}').strategies
    assert s.source_refs == []


# --- _price_value ---------------------------------------------------------

def test_price_value_prefers_divine():
    assert _price_value({"divine_value": 2.0, "chaos_value": 300.0}) == 2.0


def test_price_value_falls_back_to_chaos():
    assert _price_value({"divine_value": None, "chaos_value": 300.0}) == 300.0


def test_build_user_prompt_uses_chaos_fallback_price(monkeypatch):
    prices = [{"name": "Chaos Orb", "item_type": "currency", "chaos_value": 5.0}]
    p = build_user_prompt([], prices)
    assert "Chaos Orb (currency): 5.0 divine" in p


# --- parse_llm_json edge cases -------------------------------------------

def test_parse_llm_json_strips_leading_prose():
    raw = 'Sure! Here is the JSON: {"strategies":[{"name":"Breach"}]}'
    resp = parse_llm_json(raw)
    assert resp.strategies[0].name == "Breach"


def test_parse_llm_json_accepts_bare_list():
    resp = parse_llm_json('[{"name":"Ritual"}]')
    assert resp.strategies[0].name == "Ritual"


def test_parse_llm_json_rejects_schema_violation():
    # Valid JSON, but a strategy is missing its required `name` -> schema validation error.
    with pytest.raises(ValueError):
        parse_llm_json('{"strategies":[{"risk":"low"}]}')


# --- to_markdown loop body ------------------------------------------------

def test_to_markdown_renders_numbered_entries_with_summary():
    raw = ('{"strategies":[{"name":"Abyss","est_profit_per_hour":3,'
           '"risk":"high","investment_required":1,"summary":"farmar abismo"}]}')
    strategies = to_farm_strategies(parse_llm_json(raw), "L")
    md = to_markdown(strategies, "L")
    assert "### 1. Abyss" in md
    assert "risk: high" in md
    assert "investment: 1" in md
    assert "farmar abismo" in md


# --- curate() / run() / _recent_knowledge() wiring ------------------------

def test_curate_wires_llm_and_returns_ranked_strategies(monkeypatch):
    monkeypatch.setattr(
        curate_mod,
        "glm_chat",
        lambda *a, **k: '{"strategies":[{"name":"Fast","expected_drops_per_map":10,'
        '"unit_price_chaos":10,"clear_time_minutes":5}]}',
    )
    strategies, markdown = curate([], [], "test-league")
    assert [s.name for s in strategies] == ["Fast"]
    assert strategies[0].league == "test-league"
    assert "test-league" in markdown


def test_run_persists_strategies_and_returns_count(monkeypatch):
    import db.repo as repo

    written: list = []
    monkeypatch.setattr(repo, "latest_prices", lambda league: [])
    monkeypatch.setattr(repo, "insert_farm_strategies", lambda rows: written.extend(rows))
    monkeypatch.setattr(curate_mod, "_recent_knowledge", lambda: [])
    monkeypatch.setattr(
        curate_mod,
        "curate",
        lambda knowledge, prices, league: (["strat-a", "strat-b"], "# md"),
    )

    count = run()

    assert count == 2
    assert written == ["strat-a", "strat-b"]


def test_recent_knowledge_queries_latest_chunks(monkeypatch):
    import db.connection as connection

    captured: dict = {}

    def fake_fetch_all(query, params=None):
        captured["query"] = query
        return [{"source_url": "u", "title": "t", "content": "c"}]

    monkeypatch.setattr(connection, "fetch_all", fake_fetch_all)
    rows = _recent_knowledge()
    assert rows == [{"source_url": "u", "title": "t", "content": "c"}]
    assert "FROM knowledge_chunk" in captured["query"]
    assert "ORDER BY captured_at DESC" in captured["query"]
