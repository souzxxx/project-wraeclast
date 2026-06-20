from datetime import datetime

from api.price_history import build_sparklines

D1 = datetime(2026, 6, 17, 6, 0)
D2 = datetime(2026, 6, 18, 6, 0)
D3 = datetime(2026, 6, 19, 6, 0)


def _row(name, chaos, when, item_type="currency"):
    return {"name": name, "item_type": item_type, "chaos_value": chaos, "captured_at": when}


def test_builds_chronological_day_series():
    rows = [_row("Divine", 200, D3), _row("Divine", 180, D1), _row("Divine", 190, D2)]
    [s] = build_sparklines(rows)
    assert s.name == "Divine"
    assert s.points == [180, 190, 200]  # oldest -> newest, regardless of input order
    assert s.latest == 200
    assert s.change_pct == 11.1  # (200-180)/180


def test_one_point_per_day_latest_snapshot_wins():
    # Two snapshots the same day (an intra-day rerun); the later timestamp's value is kept.
    rows = [
        _row("Exalt", 5, datetime(2026, 6, 18, 6, 0)),
        _row("Exalt", 7, datetime(2026, 6, 18, 18, 0)),
        _row("Exalt", 6, D3),
    ]
    [s] = build_sparklines(rows)
    assert s.points == [7, 6]  # day 18 collapsed to its latest (7), then day 19


def test_drops_series_shorter_than_min_points():
    rows = [_row("OneDay", 100, D3)]  # only a single day -> no line to draw
    assert build_sparklines(rows) == []


def test_filters_non_currency_rows():
    rows = [
        _row("Divine", 200, D2),
        _row("Divine", 210, D3),
        _row("Some Unique", 999, D2, item_type="unique"),
        _row("Some Unique", 999, D3, item_type="unique"),
    ]
    names = [s.name for s in build_sparklines(rows)]
    assert names == ["Divine"]


def test_sorted_by_latest_value_and_capped_by_max_series():
    rows = []
    for i, name in enumerate(["A", "B", "C"]):
        rows += [_row(name, (i + 1) * 10, D2), _row(name, (i + 1) * 10, D3)]
    series = build_sparklines(rows, max_series=2)
    assert [s.name for s in series] == ["C", "B"]  # highest latest value first, top 2 only


def test_keeps_only_most_recent_max_points_days():
    rows = [_row("Chaos", 1, datetime(2026, 6, d, 6, 0)) for d in range(10, 20)]
    [s] = build_sparklines(rows, max_points=3, min_points=2)
    assert len(s.points) == 3  # last 3 calendar days only


def test_skips_missing_and_unparseable_fields():
    rows = [
        _row("Divine", 200, D2),
        _row("Divine", 210, D3),
        _row(None, 5, D2),  # no name
        _row("Divine", None, D3),  # no value
        _row("Bad", 5, "not-a-date"),  # unparseable timestamp
        _row("Bad", 6, D3),
    ]
    series = {s.name: s for s in build_sparklines(rows)}
    assert set(series) == {"Divine"}  # "Bad" has one good + one dropped row -> single point
    assert series["Divine"].points == [200, 210]


def test_handles_iso_string_dates():
    rows = [
        _row("Divine", 100, "2026-06-18T06:00:00"),
        _row("Divine", 120, "2026-06-19T06:00:00"),
    ]
    [s] = build_sparklines(rows)
    assert s.points == [100, 120]
    assert s.change_pct == 20.0


def test_change_pct_none_when_first_value_zero():
    rows = [_row("Free", 0, D2), _row("Free", 5, D3)]
    [s] = build_sparklines(rows)
    assert s.change_pct is None  # avoid div-by-zero
