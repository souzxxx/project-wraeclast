"""Offline tests for the craft EV core (pure math — no DB/network)."""

from decimal import Decimal

from api.craft_ev import method_ev, price_index, rank_methods

_PRICES = [
    {"name": "Exalted Orb", "chaos_value": 5.0, "divine_value": 0.025},
    {"name": "Divine Orb", "chaos_value": 200.0, "divine_value": 1.0},
    {"name": "Regal Orb", "chaos_value": 2.0, "divine_value": 0.01},
]


def _idx():
    return price_index(_PRICES)


def test_price_index_maps_name_to_chaos_float():
    idx = _idx()
    assert idx["Exalted Orb"] == 5.0 and idx["Divine Orb"] == 200.0
    assert all(isinstance(v, float) for v in idx.values())


def test_expected_cost_includes_retries():
    # 4 Exalts @5c = 20c base; success 0.5 -> 2 expected attempts -> 40c; /200c per div = 0.2 div
    m = {"inputs": {"Exalted Orb": 4}, "success_prob": 0.5, "output_value_div": 10}
    ev = method_ev(m, _idx(), 200.0)
    assert ev["expected_attempts"] == 2.0
    assert ev["base_cost_div"] == 0.1
    assert ev["expected_cost_div"] == 0.2
    assert ev["profit_div"] == 9.8
    assert ev["roi_pct"] == 4900
    assert ev["priced"] is True
    assert ev["missing_prices"] == []


def test_deterministic_method_has_one_attempt():
    m = {"inputs": {"Regal Orb": 1}, "success_prob": 1.0, "output_value_div": 5}
    ev = method_ev(m, _idx(), 200.0)
    assert ev["expected_attempts"] == 1.0
    assert ev["expected_cost_div"] == ev["base_cost_div"]


def test_missing_prices_are_flagged_and_not_counted():
    m = {"inputs": {"Exalted Orb": 2, "Omen of Whittling": 1}, "success_prob": 1.0}
    ev = method_ev(m, _idx(), 200.0)
    assert ev["missing_prices"] == ["Omen of Whittling"]
    assert ev["priced"] is False  # an input couldn't be valued
    assert ev["base_cost_div"] == round(10 / 200, 2)  # only the priced Exalts counted


def test_handles_decimal_inputs_like_postgres_numeric():
    # psycopg returns NUMERIC as Decimal — the core must not choke mixing Decimal and float.
    prices = [
        {"name": "Exalted Orb", "chaos_value": Decimal("5")},
        {"name": "Divine Orb", "chaos_value": Decimal("200")},
    ]
    m = {
        "inputs": {"Exalted Orb": 4},
        "success_prob": Decimal("0.5"),
        "output_value_div": Decimal("10"),
    }
    ev = method_ev(m, price_index(prices), 200.0)
    assert ev["expected_cost_div"] == 0.2 and ev["roi_pct"] == 4900


def test_rank_puts_priced_high_roi_first_unpriceable_last():
    methods = [
        {"name": "low", "inputs": {"Exalted Orb": 10}, "success_prob": 1.0, "output_value_div": 1},
        {"name": "high", "inputs": {"Exalted Orb": 1}, "success_prob": 1.0, "output_value_div": 50},
        {
            "name": "unpriced",
            "inputs": {"Mystery Orb": 1},
            "success_prob": 1.0,
            "output_value_div": 99,
        },
    ]
    ranked = rank_methods(methods, _PRICES)
    assert [m["name"] for m in ranked] == ["high", "low", "unpriced"]
    assert ranked[-1]["priced"] is False


def test_no_divine_price_degrades_gracefully():
    # without a Divine Orb price we can't convert to div; must not crash, div fields are None.
    prices = [{"name": "Exalted Orb", "chaos_value": 5.0}]
    m = {"inputs": {"Exalted Orb": 2}, "success_prob": 1.0, "output_value_div": 10}
    ev = method_ev(m, price_index(prices), None)
    assert ev["expected_cost_div"] is None and ev["roi_pct"] is None
