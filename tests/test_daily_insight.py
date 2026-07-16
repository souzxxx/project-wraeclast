from datetime import date, datetime
from decimal import Decimal

from scripts.daily_insight import (
    PRICE_MOVE_MIN_BASELINE,
    canonical_farm_key,
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


def test_canonical_farm_key_collapses_mechanic_variants():
    assert canonical_farm_key("Abyss Lich Farming") == "abyss"
    assert canonical_farm_key("Abyss Farm") == "abyss"
    assert canonical_farm_key("Ritual Farm (Omen + Defer)") == "ritual"
    assert canonical_farm_key("Arbiter of Ash Boss Farm") == "arbiter"  # arbiter before boss
    assert canonical_farm_key("Wisp Strongboxes") == "wisp"
    assert canonical_farm_key("Mystery Strat") == "mystery strat"  # fallback, filler stripped


def test_farm_ranking_collapses_renames_no_phantom_churn():
    # Same two farms, renamed by the GLM between runs — must NOT show as left+entered.
    latest = [_farm("Abyss Farm", 30, T1), _farm("Ritual Farm (Omen + Defer)", 25, T1)]
    prev = [_farm("Abyss Lich Farming", 28, T0), _farm("Ritual Omen Farm", 26, T0)]
    entered, left, moves, top = farm_ranking_changes(latest, prev, top_n=5)
    assert entered == [] and left == []
    assert top == ["Abyss Farm", "Ritual Farm (Omen + Defer)"]  # latest display names


def test_farm_ranking_dedupes_same_day_reruns_by_key():
    # Two curate runs the same day produced renamed duplicates of one mechanic.
    latest = [_farm("Abyss Farm", 30, T1), _farm("Abyss Lich Farm", 12, T1)]
    _, _, _, top = farm_ranking_changes(latest, [], top_n=5)
    assert top == ["Abyss Farm"]  # one entry, highest-profit name kept


# ── price moves ───────────────────────────────────────────────────────────────────

def test_price_moves_requires_both_pct_and_value_thresholds():
    # divine-scaled (PoE2): the 0.02-div absolute floor filters a big-% move on a tiny item
    latest = [
        _price("Divine", 2.0, T1),     # +33% and +0.5 div -> notable
        _price("Tiny", 0.015, T1),     # +50% but only +0.005 div -> filtered by the floor
        _price("Flat", 1.0, T1),       # unchanged
    ]
    prev = [_price("Divine", 1.5, T0), _price("Tiny", 0.010, T0), _price("Flat", 1.0, T0)]
    moves = notable_price_moves(latest, prev)
    assert [m.name for m in moves] == ["Divine"]
    assert moves[0].pct == 33.3


def test_price_moves_detect_divine_denominated_feed():
    # PoE2 rows carry value in divine_value (chaos_value NULL) — moves must still be detected.
    def _d(name, divine, when):
        return {"name": name, "item_type": "currency", "chaos_value": None,
                "divine_value": divine, "captured_at": when}

    moves = notable_price_moves([_d("Big", 1.5, T1)], [_d("Big", 1.0, T0)])
    assert [m.name for m in moves] == ["Big"]  # +50%, +0.5 div clears the floor
    assert moves[0].pct == 50.0


def test_price_moves_handle_decimal_values_from_db():
    # Regression: psycopg returns NUMERIC columns as Decimal, and Decimal doesn't mix with the
    # float `* 100.0` in the pct math — this silently failed every daily run in production while
    # the float-fed tests above stayed green. Feed Decimals (both the chaos and divine columns)
    # exactly as the DB does and assert the move is computed, not a TypeError.
    def _dec(name, chaos, divine, when):
        return {"name": name, "item_type": "currency",
                "chaos_value": Decimal(str(chaos)) if chaos is not None else None,
                "divine_value": Decimal(str(divine)) if divine is not None else None,
                "captured_at": when}

    latest = [_dec("Chaos", 2.0, None, T1), _dec("Div", None, 1.5, T1)]
    prev = [_dec("Chaos", 1.5, None, T0), _dec("Div", None, 1.0, T0)]
    moves = notable_price_moves(latest, prev)
    by_name = {m.name: m for m in moves}
    assert set(by_name) == {"Chaos", "Div"}
    assert by_name["Chaos"].pct == 33.3
    assert by_name["Div"].pct == 50.0
    # values are plain floats on the model, not Decimal
    assert isinstance(by_name["Div"].to_chaos, float)


def test_compute_insight_end_to_end_with_decimal_prices():
    # Full daily-insight path (as run() feeds it) with Decimal-valued price rows — must not raise.
    farms = [_farm("A", 10, T1), _farm("A", 8, T0)]
    prices = [
        {"name": "Mirror", "item_type": "currency", "chaos_value": None,
         "divine_value": Decimal("3.0"), "captured_at": T1},
        {"name": "Mirror", "item_type": "currency", "chaos_value": None,
         "divine_value": Decimal("1.0"), "captured_at": T0},  # +200% -> anomaly
    ]
    ins = compute_insight("Runes of Aldur", farms, prices, [], today=date(2026, 6, 19))
    assert any("Mirror" in a and "jumped" in a for a in ins.anomalies)
    render_insight(ins)  # renders without raising


def test_price_moves_ignore_missing_baseline_and_zero_old():
    latest = [_price("New", 50, T1), _price("ZeroOld", 50, T1)]
    prev = [_price("ZeroOld", 0, T0)]  # no "New" yesterday; ZeroOld had 0 -> skip div-by-zero
    assert notable_price_moves(latest, prev) == []


def test_price_moves_skip_near_zero_baseline_noise():
    # Regression: a micro-price baseline (illiquid item, ~0.002 div) makes the percentage
    # meaningless — 0.002 -> 0.4 div reads as "+17000%" and floods the report. It clears both the
    # relative (>=25%) and absolute (>=0.02 div) bars, so only the baseline floor stops it.
    latest = [_price("Illiquid", 0.4, T1), _price("Real", 0.41, T1)]
    prev = [_price("Illiquid", 0.002, T0), _price("Real", 0.15, T0)]  # 0.002 < floor, 0.15 >= floor
    moves = notable_price_moves(latest, prev)
    assert [m.name for m in moves] == ["Real"]  # only the move off a real baseline survives
    # The kept move is a sane double-digit-hundreds %, not a five-digit explosion.
    assert moves[0].pct < 1000


def test_price_moves_keep_move_exactly_at_baseline_floor():
    # The floor is inclusive: a baseline of exactly PRICE_MOVE_MIN_BASELINE still counts.
    latest = [_price("Edge", PRICE_MOVE_MIN_BASELINE + 0.5, T1)]
    prev = [_price("Edge", PRICE_MOVE_MIN_BASELINE, T0)]
    assert [m.name for m in notable_price_moves(latest, prev)] == ["Edge"]


def test_price_moves_baseline_floor_does_not_block_crash_to_zero():
    # A currency crashing FROM a real price TO near-zero must still be flagged — the floor gates the
    # divisor (yesterday's price), not today's, so a -90% collapse off a healthy baseline survives.
    latest = [_price("Crashed", 0.01, T1)]
    prev = [_price("Crashed", 0.5, T0)]
    moves = notable_price_moves(latest, prev)
    assert [m.name for m in moves] == ["Crashed"]
    assert moves[0].pct < 0


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


def test_compute_insight_includes_craft_alerts_and_renders():
    method = {"name": "Cheap Craft", "inputs": {"Exalted Orb": 10}, "success_prob": 1.0,
              "output_value_div": 5}
    prices = [
        _price("Exalted Orb", 50, T1), _price("Divine Orb", 200, T1),  # cheap today
        _price("Exalted Orb", 200, T0), _price("Divine Orb", 200, T0),  # dear yesterday
    ]
    ins = compute_insight("L", [], prices, [], craft_method_rows=[method], today=date(2026, 6, 19))
    assert [a.kind for a in ins.craft_alerts] == ["into_profit"]
    assert any("crossed into profit" in a for a in ins.anomalies)
    md = render_insight(ins)
    assert "## Craft alerts" in md and "Cheap Craft" in md


def test_render_links_new_sources_and_lists_anomalies():
    farms = [_farm("A", 10, T1), _farm("B", 8, T1), _farm("A", 8, T0)]
    prices = [_price("Mirror", 300, T1), _price("Mirror", 100, T0)]
    knowledge = [{"source_url": "https://youtu.be/x", "title": "Vid", "captured_at": T1}]
    md = render_insight(compute_insight("L", farms, prices, knowledge, today=date(2026, 6, 19)))
    assert "[Vid](https://youtu.be/x)" in md
    assert "⚠️" in md
