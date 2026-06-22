"""Build per-currency price-history sparklines for the 'Hoje' tab (ROADMAP P2).

Pure transformation (no DB/network) so it is unit-tested offline: takes raw price_snapshot
rows over a recent window and produces, per currency, a day-bucketed chaos-value series plus
a first->last change percentage. The thin DB-backed route (`api/routes/price.py`) feeds it
`price_history_since`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class Sparkline(BaseModel):
    name: str
    item_type: str
    points: list[float]  # day-bucketed chaos values, oldest -> newest
    latest: float
    change_pct: float | None  # first -> last point, None if fewer than 2 points


def _to_datetime(value: Any) -> datetime | None:
    """Coerce a captured_at value (datetime / date / ISO string) to a datetime, defensively."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def build_sparklines(
    rows: list[dict[str, Any]],
    item_type: str = "currency",
    max_series: int = 12,
    max_points: int = 14,
    min_points: int = 2,
) -> list[Sparkline]:
    """Per-currency day-bucketed chaos-value series, sorted by latest value (desc).

    One point per calendar day (the latest snapshot that day wins, defensive vs intra-day
    reruns). Series shorter than `min_points` are dropped — a sparkline needs a line. Only the
    most recent `max_points` days are kept, and only the top `max_series` currencies by latest
    value are returned. Rows with a missing name/value or an unparseable timestamp are skipped.
    """
    # name -> day -> (captured_at, chaos_value); the newest timestamp per day wins.
    by_name: dict[str, dict[date, tuple[datetime, float]]] = {}
    for r in rows:
        if item_type and r.get("item_type") not in (None, item_type):
            continue
        name = r.get("name")
        # PoE2's ninja feed is divine-denominated (chaos_value is NULL); fall back to divine_value
        # so the series isn't permanently empty. Mirrors api.craft_ev.price_index.
        raw = r.get("chaos_value")
        if raw is None:
            raw = r.get("divine_value")
        if not name or raw is None:
            continue
        ts = _to_datetime(r.get("captured_at"))
        if ts is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        days = by_name.setdefault(name, {})
        prev = days.get(ts.date())
        if prev is None or ts >= prev[0]:
            days[ts.date()] = (ts, value)

    series: list[Sparkline] = []
    for name, days in by_name.items():
        ordered_days = sorted(days)[-max_points:]
        points = [days[d][1] for d in ordered_days]
        if len(points) < min_points:
            continue
        first, latest = points[0], points[-1]
        change = round((latest - first) / first * 100.0, 1) if first else None
        series.append(
            Sparkline(
                name=name,
                item_type=item_type or "currency",
                points=points,
                latest=round(latest, 2),
                change_pct=change,
            )
        )
    series.sort(key=lambda s: s.latest, reverse=True)
    return series[:max_series]
