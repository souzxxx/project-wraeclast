from datetime import date, datetime

from scripts.daily_insight import (
    compute_insight,
    farm_ranking_changes,
    notable_price_moves,
    render_insight,
)

T0 = datetime(2026, 6, 18, 4, 0)  # previous day
T1 = datetime(2026, 6, 19, 4, 0)  # today


def _farm(name, profit, when):
    return {"name": name, "est_profit_per_hour": profit, "risk": "low", "captured_at": when}


def _price(name, chaos, when, item_type="currency"):
    return {"name": name, "item_type": item_type, "chaos_value": chaos, "captured_at": when}


# ── farm ranking ────────────────────────────────────────────────────────────────────

def test_farm_ranking_detects_enter_leave_and_moves():
    latest = [_farm("A", 10, T1), _farm("B", 8, T1), _farm("C", 5, T1)]
    prev = [_farm("B", 12, T0), _farm("A", 9, T0), _farm("D", 4, T0)]
    entered, left, moves, top = farm_ranking_changes(latest, prev, top_n=3)
    assert entered == ["C"]
    assert left == ["D"]
    assert top == ["A", "B", "C"]
    # A went #2 -> #1, B went #1 -> #2
    moved = {m.name: (m.from_rank, m.to_rank) for m in moves}
    assert moved == {"A": (2, 1), "B": (1, 2)}


def test_farm_ranking_sorts_by_profit_not_input_order():
    latest = [_farm("Low", 1, T1), _farm("High", 100, T1)]
    _, _, _, top = farm_ranking_changes(latest, [], top_n=5)
    assert top == ["High", "Low"]


# ── price moves ───────────────────────────────────────────────────────────────────

def test_price_moves_requires_both_pct_and_chaos_thresholds():
    latest = [
        _price("Divine", 200, T1),      # +33% and +50 chaos -> notable
        _price("Tiny", 0.15, T1),       # +50% but only +0.05 chaos -> filtered
        _price("Flat", 100, T1),        # unchanged
    ]
    prev = [_price("Divine", 150, T0), _price("Tiny", 0.10, T0), _price("Flat", 100, T0)]
    moves = notable_price_moves(latest, prev)
    names = [m.name for m in moves]
    assert names == ["Divine"]
    assert moves[0].pct == 33.3


def test_price_moves_ignore_missing_baseline_and_zero_old():
    latest = [_price("New", 50, T1), _price("ZeroOld", 50, T1)]
    prev = [_price("ZeroOld", 0, T0)]  # no "New" yesterday; ZeroOld had 0 -> skip div-by-zero
    assert notable_price_moves(latest, prev) == []


def test_price_moves_sorted_by_magnitude():
    latest = [_price("Up", 70, T1), _price("Down", 5, T1)]
    prev = [_price("Up", 50, T0), _price("Down", 50, T0)]
    moves = notable_price_moves(latest, prev)
    assert [m.name for m in moves] == ["Down", "Up"]  # -90% beats +40%


# ── compute_insight (integration of the pieces) ──────────────────────────────────────

def test_compute_insight_flags_anomalies_and_baseline():
    farms = [_farm("A", 10, T1), _farm("B", 8, T1), _farm("A", 8, T0)]
    prices = [_price("Mirror", 300, T1), _price("Mirror", 100, T0)]  # +200% anomaly
    knowledge = [
        {"source_url": "https://youtu.be/today", "title": "Fresh", "captured_at": T1},
        {"source_url": "https://youtu.be/old", "title": "Old", "captured_at": T0},
    ]
    ins = compute_insight("Runes of Aldur", farms, prices, knowledge, today=date(2026, 6, 19))
    assert ins.has_baseline is True
    assert "B" in ins.farms_entered_top
    assert any("Mirror" in a and "jumped" in a for a in ins.anomalies)
    # only today's source is "new"
    assert [s.url for s in ins.new_sources] == ["https://youtu.be/today"]
    assert ins.has_changes is True


def test_compute_insight_no_baseline_when_single_day():
    farms = [_farm("A", 10, T1)]
    ins = compute_insight("L", farms, [], [], today=date(2026, 6, 19))
    assert ins.has_baseline is False
    assert ins.current_top == ["A"]


def test_compute_insight_handles_iso_string_dates():
    farms = [_farm("A", 10, "2026-06-19T04:00:00"), _farm("A", 8, "2026-06-18T04:00:00")]
    ins = compute_insight("L", farms, [], [], today=date(2026, 6, 19))
    assert ins.has_baseline is True


# ── rendering ───────────────────────────────────────────────────────────────────────

def test_render_includes_frontmatter_and_estimate_disclaimer():
    ins = compute_insight("Runes of Aldur", [], [], [], today=date(2026, 6, 19))
    md = render_insight(ins)
    assert md.startswith("---")
    assert "league: Runes of Aldur" in md
    assert "estimate" in md.lower()
    assert "first baseline" in md.lower()  # no prev day


def test_render_links_new_sources_and_lists_anomalies():
    farms = [_farm("A", 10, T1), _farm("B", 8, T1), _farm("A", 8, T0)]
    prices = [_price("Mirror", 300, T1), _price("Mirror", 100, T0)]
    knowledge = [{"source_url": "https://youtu.be/x", "title": "Vid", "captured_at": T1}]
    md = render_insight(compute_insight("L", farms, prices, knowledge, today=date(2026, 6, 19)))
    assert "[Vid](https://youtu.be/x)" in md
    assert "⚠️" in md
