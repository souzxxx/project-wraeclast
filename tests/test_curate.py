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


# ── lenient field coercion (_LLMStrategy validators) ─────────────────────────
def test_coerce_float_pulls_leading_number_and_nulls_junk():
    # "20 divine" -> 20.0 (regex path); "abc" -> None -> _req_float defaults to 0.0;
    # an explicit null est_profit_per_hour stays None (optional coercion).
    raw = ('{"strategies":[{"name":"X","est_profit_per_hour":null,'
           '"unit_price_chaos":"20 divine","entry_cost_chaos":"abc",'
           '"expected_drops_per_map":2,"clear_time_minutes":6}]}')
    [strat] = parse_llm_json(raw).strategies
    assert strat.unit_price_chaos == 20.0  # leading number pulled from the string
    assert strat.entry_cost_chaos == 0.0  # no number in "abc" -> None -> 0.0
    assert strat.est_profit_per_hour is None  # null preserved, not coerced to 0.0


@pytest.mark.parametrize(
    "raw_risk,expected",
    [("low", "low"), ("High", "high"), ("moderate", "med"), ("", None)],
)
def test_risk_normalization(raw_risk, expected):
    raw = '{"strategies":[{"name":"X","risk":"' + raw_risk + '"}]}'
    [strat] = parse_llm_json(raw).strategies
    assert strat.risk == expected


def test_sources_validator_tolerates_non_list_and_keeps_dicts():
    # a non-list `sources` collapses to []; a dict entry is kept as-is.
    raw = '{"strategies":[{"name":"X","sources":"nope"}]}'
    assert parse_llm_json(raw).strategies[0].sources == []
    raw = '{"strategies":[{"name":"X","sources":[{"url":"u","title":"t"}]}]}'
    assert parse_llm_json(raw).strategies[0].sources == [{"url": "u", "title": "t"}]


# ── parse_llm_json defensive paths ───────────────────────────────────────────
def test_parse_llm_json_strips_prose_before_the_object():
    raw = 'Sure! Here are the strategies: {"strategies":[{"name":"Breach"}]}'
    assert parse_llm_json(raw).strategies[0].name == "Breach"


def test_parse_llm_json_accepts_a_bare_list():
    raw = '[{"name":"Ritual","clear_time_minutes":10}]'
    assert parse_llm_json(raw).strategies[0].name == "Ritual"


def test_parse_llm_json_rejects_valid_json_that_breaks_schema():
    with pytest.raises(ValueError, match="schema validation"):
        parse_llm_json('{"strategies":"not a list"}')


# ── price fallback + markdown rendering ──────────────────────────────────────
def test_build_user_prompt_falls_back_to_chaos_price():
    prices = [{"name": "Chaos Orb", "item_type": "currency", "chaos_value": 1.0}]
    assert "- Chaos Orb (currency): 1.0 divine" in build_user_prompt([], prices)


def test_to_markdown_renders_ranked_entries_with_summary():
    raw = ('{"strategies":[{"name":"Abyss","est_profit_per_hour":42,"risk":"low",'
           '"investment_required":3,"summary":"farmar profundezas"}]}')
    md = to_markdown(to_farm_strategies(parse_llm_json(raw), "L"), "L")
    assert "### 1. Abyss" in md
    assert "~42.0 div/h" in md and "risk: low" in md and "investment: 3.0" in md
    assert "- farmar profundezas" in md


# ── curate() / run() wiring (GLM + DB monkeypatched) ─────────────────────────
def test_curate_wires_glm_and_computes_profit(monkeypatch):
    captured: dict = {}

    def fake_glm(messages, **kwargs):
        captured["messages"] = messages
        captured["model"] = kwargs.get("model")
        return '{"strategies":[{"name":"Breach","expected_drops_per_map":4,' \
               '"unit_price_chaos":5,"clear_time_minutes":6}]}'

    monkeypatch.setattr(curate_mod, "glm_chat", fake_glm)
    knowledge = [{"source_url": "https://youtu.be/A", "title": "Breach", "content": "c"}]
    strategies, markdown = curate(knowledge, [], "test-league")
    assert [s.name for s in strategies] == ["Breach"]
    assert strategies[0].est_profit_per_hour == 200.0  # (4*5)*(60/6), computed not free-text
    assert "Top farm strategies — test-league" in markdown
    assert captured["model"] == "glm-5.2"  # settings.glm_curation_model default


def test_run_reads_knowledge_and_persists_strategies(monkeypatch):
    written: list = []
    monkeypatch.setattr(curate_mod, "glm_chat", lambda *a, **k: '{"strategies":[{"name":"S"}]}')
    monkeypatch.setattr("db.repo.latest_prices", lambda league: [])
    monkeypatch.setattr("db.repo.insert_farm_strategies", lambda s: written.append(s) or len(s))
    monkeypatch.setattr("db.connection.fetch_all", lambda *a, **k: [
        {"source_url": "https://youtu.be/A", "title": "S", "content": "c"}
    ])
    assert run() == 1
    assert [s.name for s in written[0]] == ["S"]
