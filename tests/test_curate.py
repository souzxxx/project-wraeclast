import pytest

from collector import curate as curate_mod
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


# --- defensive field coercion (resilience against LLM output drift) --------------------


def test_coerces_number_strings_in_formula_components():
    # the model often emits "20 divine" / "~6" instead of bare numbers; the validators must
    # pull the leading number so the golden-rule calculation still fires.
    raw = ('{"strategies":[{"name":"S","expected_drops_per_map":"2 stacks",'
           '"unit_price_chaos":"20 divine","clear_time_minutes":"~6 min"}]}')
    [s] = to_farm_strategies(parse_llm_json(raw), "L")
    assert s.est_profit_per_hour == 400.0  # (2*20)*(60/6), coerced from strings


def test_unparseable_component_string_coerces_to_zero():
    # a non-numeric string must degrade to 0.0, not blow up validation.
    raw = '{"strategies":[{"name":"S","clear_time_minutes":"soon","est_profit_per_hour":7}]}'
    [s] = to_farm_strategies(parse_llm_json(raw), "L")
    assert s.est_profit_per_hour == 7.0  # no usable components -> LLM free-text fallback


def test_null_optional_estimate_stays_none():
    raw = '{"strategies":[{"name":"S","est_profit_per_hour":null,"investment_required":null}]}'
    [s] = to_farm_strategies(parse_llm_json(raw), "L")
    assert s.est_profit_per_hour == 0.0  # max(None-or-0, 0.0)
    assert s.investment_required is None


@pytest.mark.parametrize(
    "raw_risk, expected",
    [("low", "low"), ("Lenta", "low"), ("high", "high"), ("Hardcore", "high"),
     ("moderate", "med"), ("", None), (None, None)],
)
def test_risk_normalization(raw_risk, expected):
    import json

    raw = json.dumps({"strategies": [{"name": "S", "risk": raw_risk}]})
    [s] = to_farm_strategies(parse_llm_json(raw), "L")
    assert s.risk == expected


def test_sources_validator_accepts_dicts_and_ignores_non_list():
    # a dict source passes through untouched...
    raw = '{"strategies":[{"name":"S","sources":[{"url":"u","title":"t"}]}]}'
    [s] = to_farm_strategies(parse_llm_json(raw), "L")
    assert s.sources == [{"url": "u", "title": "t"}]
    # ...and a non-list `sources` degrades to an empty list rather than erroring.
    raw2 = '{"strategies":[{"name":"S","sources":"not-a-list"}]}'
    [s2] = to_farm_strategies(parse_llm_json(raw2), "L")
    assert s2.sources == []


# --- parse_llm_json robustness ---------------------------------------------------------


def test_parse_llm_json_isolates_object_after_leading_prose():
    # the model prefixes a sentence before the JSON; isolation from the first `{` recovers it.
    raw = 'Sure! Here is the JSON: {"strategies":[{"name":"Breach"}]}'
    resp = parse_llm_json(raw)
    assert resp.strategies[0].name == "Breach"


def test_parse_llm_json_accepts_bare_list_of_strategies():
    resp = parse_llm_json('[{"name":"Ritual"},{"name":"Abyss"}]')
    assert [s.name for s in resp.strategies] == ["Ritual", "Abyss"]


def test_parse_llm_json_rejects_valid_json_with_wrong_schema():
    # valid JSON, but `strategies` is not a list -> schema validation must raise ValueError.
    with pytest.raises(ValueError, match="schema validation"):
        parse_llm_json('{"strategies":"nope"}')


# --- pricing + markdown rendering ------------------------------------------------------


def test_build_user_prompt_falls_back_to_chaos_when_no_divine():
    prices = [
        {"name": "Divine Orb", "item_type": "currency", "divine_value": 1.0},
        {"name": "Chaos Orb", "item_type": "currency", "chaos_value": 0.02},  # PoE1-style
        {"name": "Nothing", "item_type": "currency"},  # no price -> dropped
    ]
    p = build_user_prompt([], prices)
    assert "Divine Orb (currency): 1.0 divine" in p
    assert "Chaos Orb (currency): 0.02 divine" in p
    assert "Nothing" not in p


def test_to_markdown_renders_ranked_strategies_with_and_without_summary():
    raw = ('{"strategies":['
           '{"name":"Breach","est_profit_per_hour":50,"risk":"high",'
           '"investment_required":10,"summary":"farmar breaches"},'
           '{"name":"Bare","est_profit_per_hour":5}]}')
    strategies = to_farm_strategies(parse_llm_json(raw), "L")
    md = to_markdown(strategies, "L")
    assert "### 1. Breach" in md and "### 2. Bare" in md  # numbered in rank order
    assert "~50.0 div/h" in md and "risk: high" in md and "investment: 10.0" in md
    assert "farmar breaches" in md
    assert "risk: n/a" in md and "investment: n/a" in md  # Bare has neither


# --- curate() + run() wiring (LLM + DB monkeypatched, fully offline) -------------------


def test_curate_calls_glm_and_builds_ranked_strategies(monkeypatch):
    captured: dict = {}

    def fake_glm(messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return '{"strategies":[{"name":"Abyss","est_profit_per_hour":30}]}'

    monkeypatch.setattr(curate_mod, "glm_chat", fake_glm)
    knowledge = [{"source_url": "https://youtu.be/A", "title": "T", "content": "c"}]
    strategies, markdown = curate(knowledge, [], "test-league")
    assert [s.name for s in strategies] == ["Abyss"]
    assert strategies[0].league == "test-league"
    assert "Abyss" in markdown
    # system + user turns are passed, temperature pinned low for determinism.
    assert [m["role"] for m in captured["messages"]] == ["system", "user"]
    assert captured["kwargs"]["temperature"] == 0.3


def test_run_wires_prices_knowledge_and_persists(monkeypatch):
    written: list = []
    monkeypatch.setattr(
        "db.repo.latest_prices",
        lambda league, limit=1000: [
            {"name": "Divine Orb", "item_type": "currency", "divine_value": 1.0}
        ],
    )
    monkeypatch.setattr(
        curate_mod, "_recent_knowledge",
        lambda: [{"source_url": "https://youtu.be/A", "title": "T", "content": "c"}],
    )
    monkeypatch.setattr(curate_mod, "glm_chat",
                        lambda *a, **k: '{"strategies":[{"name":"Breach"}]}')
    monkeypatch.setattr(
        "db.repo.insert_farm_strategies", lambda rows: written.append(rows) or len(rows)
    )
    assert run() == 1
    assert [s.name for s in written[0]] == ["Breach"]


def test_recent_knowledge_queries_knowledge_chunk(monkeypatch):
    calls: dict = {}

    def fake_fetch_all(sql, *args):
        calls["sql"] = sql
        return [{"source_url": "u", "title": "t", "content": "c"}]

    monkeypatch.setattr("db.connection.fetch_all", fake_fetch_all)
    rows = curate_mod._recent_knowledge()
    assert rows == [{"source_url": "u", "title": "t", "content": "c"}]
    assert "FROM knowledge_chunk" in calls["sql"]
