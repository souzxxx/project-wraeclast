import pytest

import collector.curate as curate_mod
from collector.curate import (
    _coerce_float,
    _LLMStrategy,
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


# ── pure helper edge branches ──


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        (12, 12.0),
        (3.5, 3.5),
        ("12 divine", 12.0),
        ("~5", 5.0),
        ("-2.5 chaos", -2.5),
        ("no number here", None),
    ],
)
def test_coerce_float(value, expected):
    assert _coerce_float(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("", None),
        ("low", "low"),
        ("Lowish", "low"),
        ("HIGH", "high"),
        ("moderate", "med"),
        ("mid", "med"),
    ],
)
def test_normalize_risk(value, expected):
    assert _normalize_risk(value) == expected


def test_llm_strategy_sources_validator_coerces_and_drops_junk():
    # non-list -> []; a mixed list keeps dicts and wraps bare strings as {"url": ...},
    # while non-str/non-dict items (e.g. ints) are dropped.
    s = _LLMStrategy.model_validate(
        {"name": "S", "sources": [{"url": "https://a"}, "https://b", 7]}
    )
    assert s.sources == [{"url": "https://a"}, {"url": "https://b"}]
    s2 = _LLMStrategy.model_validate({"name": "S", "sources": "not-a-list"})
    assert s2.sources == []


def test_price_value_prefers_divine_then_falls_back_to_chaos():
    assert _price_value({"divine_value": 2.0, "chaos_value": 300}) == 2.0
    assert _price_value({"divine_value": None, "chaos_value": 300}) == 300
    assert _price_value({"chaos_value": 42}) == 42


def test_build_user_prompt_prices_use_chaos_fallback():
    prices = [{"name": "Divine Orb", "item_type": "currency", "chaos_value": 250}]
    p = build_user_prompt([], prices)
    assert "Divine Orb (currency): 250 divine" in p


# ── parse_llm_json remaining branches ──


def test_parse_llm_json_strips_stray_prose_before_object():
    raw = 'Here is the JSON you asked for:\n{"strategies":[{"name":"Z"}]}'
    resp = parse_llm_json(raw)
    assert resp.strategies[0].name == "Z"


def test_parse_llm_json_accepts_bare_list():
    resp = parse_llm_json('[{"name":"Bare"}]')
    assert resp.strategies[0].name == "Bare"


def test_parse_llm_json_rejects_valid_json_failing_schema():
    # valid JSON, but a strategy missing the required `name` fails schema validation.
    with pytest.raises(ValueError):
        parse_llm_json('{"strategies":[{"summary":"no name"}]}')


# ── to_markdown loop body ──


def test_to_markdown_numbers_strategies_and_includes_summary():
    raw = ('{"strategies":[{"name":"Abyss","est_profit_per_hour":10,'
           '"risk":"low","investment_required":3,"summary":"faça abyss"}]}')
    md = to_markdown(to_farm_strategies(parse_llm_json(raw), "L"), "L")
    assert "### 1. Abyss" in md
    assert "~10.0 div/h" in md
    assert "risk: low" in md
    assert "investment: 3.0" in md
    assert "- faça abyss" in md


# ── curate() / run() / _recent_knowledge() with I/O mocked ──


class _FakeSettings:
    glm_curation_model = "glm-test"
    poe2_league = "Test League"


def test_curate_wires_prompt_through_glm_and_ranks(monkeypatch):
    captured = {}

    def fake_glm_chat(messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return ('{"strategies":['
                '{"name":"Low","est_profit_per_hour":5},'
                '{"name":"High","est_profit_per_hour":50}]}')

    monkeypatch.setattr(curate_mod, "glm_chat", fake_glm_chat)
    monkeypatch.setattr(curate_mod, "get_settings", lambda: _FakeSettings())

    knowledge = [{"source_url": "https://youtu.be/A", "title": "T", "content": "c"}]
    prices = [{"name": "Divine Orb", "item_type": "currency", "divine_value": 1.0}]
    strategies, markdown = curate(knowledge, prices, "Test League")

    assert [s.name for s in strategies] == ["High", "Low"]  # ranked by profit desc
    assert captured["kwargs"]["model"] == "glm-test"
    assert captured["kwargs"]["temperature"] == 0.3
    assert captured["messages"][0]["role"] == "system"
    assert "Top farm strategies" in markdown


def test_run_reads_prices_and_knowledge_then_inserts(monkeypatch, capsys):
    inserted = {}

    monkeypatch.setattr(curate_mod, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(
        curate_mod, "_recent_knowledge",
        lambda: [{"source_url": "https://youtu.be/A", "title": "T", "content": "c"}],
    )
    monkeypatch.setattr(
        curate_mod, "curate",
        lambda knowledge, prices, league: (
            to_farm_strategies(parse_llm_json('{"strategies":[{"name":"X"}]}'), league),
            "## md",
        ),
    )
    import db.repo as repo

    monkeypatch.setattr(repo, "latest_prices", lambda league: [{"name": "p"}])
    monkeypatch.setattr(
        repo, "insert_farm_strategies",
        lambda strategies: inserted.setdefault("rows", strategies),
    )

    count = run()

    assert count == 1
    assert [s.name for s in inserted["rows"]] == ["X"]
    out = capsys.readouterr().out
    assert "farm_strategy: wrote 1 strategies for league=Test League" in out


def test_recent_knowledge_queries_latest_chunks(monkeypatch):
    import db.connection as connection

    rows = [{"source_url": "u", "title": "t", "content": "c"}]
    seen = {}

    def fake_fetch_all(query, *args):
        seen["query"] = query
        return rows

    monkeypatch.setattr(connection, "fetch_all", fake_fetch_all)
    assert _recent_knowledge() == rows
    assert "knowledge_chunk" in seen["query"]
    assert "ORDER BY captured_at DESC" in seen["query"]
