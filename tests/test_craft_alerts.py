"""Offline tests for craft profit alerts (pure — no DB/network)."""

from datetime import datetime

from api.craft_alerts import craft_alert_lines, craft_alerts, split_two_days

EXP, DIV = "Exalted Orb", "Divine Orb"


def _p(name, chaos, when=None):
    return {"name": name, "item_type": "currency", "chaos_value": chaos, "captured_at": when}


def prices(exalt):
    # divine pinned at 200 chaos; the exalt price is the variable that moves ROI
    return [_p(EXP, exalt), _p(DIV, 200)]


# a craft that costs 10 exalts and sells for 5 div: profitable only when exalts are cheap
M = {"name": "M", "inputs": {EXP: 10}, "success_prob": 1.0, "output_value_div": 5,
     "mechanics": ["currency"]}


def test_crosses_into_profit_when_input_drops():
    alerts = craft_alerts([M], prices(50), prices(200))  # cheap today, dear yesterday
    assert len(alerts) == 1
    a = alerts[0]
    assert a.kind == "into_profit"
    assert a.from_roi < 0 < a.to_roi
    assert a.name == "M" and a.cost_div == 2.5


def test_crosses_out_of_profit_when_input_rises():
    alerts = craft_alerts([M], prices(200), prices(50))  # dear today, cheap yesterday
    assert [a.kind for a in alerts] == ["out_of_profit"]


def test_no_alert_when_profit_sign_unchanged():
    assert craft_alerts([M], prices(40), prices(50)) == []  # both profitable
    assert craft_alerts([M], prices(300), prices(250)) == []  # both at a loss


def test_skips_methods_unpriced_on_either_day():
    m = {"name": "X", "inputs": {"Mystery Orb": 1}, "success_prob": 1.0, "output_value_div": 5}
    assert craft_alerts([m], prices(50), prices(200)) == []


def test_into_profit_sorted_before_out_and_lines_render():
    losing = {"name": "L", "inputs": {EXP: 10}, "success_prob": 1.0, "output_value_div": 5}
    a = craft_alerts([M, losing], prices(50), prices(200))
    assert [x.kind for x in a] == ["into_profit", "into_profit"]
    lines = craft_alert_lines(a)
    assert "INTO profit" in lines[0] and "**M**" in lines[0]


def test_split_two_days_buckets_by_date():
    rows = [
        _p("a", 1, datetime(2026, 6, 19, 4)),
        _p("b", 2, datetime(2026, 6, 18, 4)),
        _p("c", 3, datetime(2026, 6, 19, 9)),
    ]
    latest, prev = split_two_days(rows)
    assert {r["name"] for r in latest} == {"a", "c"}
    assert {r["name"] for r in prev} == {"b"}
