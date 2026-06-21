"""Craft 6 — craft profit alerts.

Day-over-day diff of craft EV: flag a method that CROSSED into profit (its inputs got cheaper, so
ROI went positive) or dropped out of profit. Output value is curated/static, so the driver is the
live input prices — exactly the "input dropped → now worth crafting" signal the ROADMAP wants.

Pure (no I/O): given the craft methods + two price sets (today, prior), it computes the crossing.
Surfaced on the daily report (`scripts.daily_insight`) and the site (`GET /craft/alerts`).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from api.craft_ev import method_ev, price_index


class CraftAlert(BaseModel):
    name: str
    kind: Literal["into_profit", "out_of_profit"]
    from_roi: int | None = None
    to_roi: int | None = None
    cost_div: float | None = None  # today's expected cost (div)
    mechanics: list[str] = Field(default_factory=list)


def as_date(value: Any) -> date | None:
    """Coerce a captured_at (datetime / date / ISO string) to a date. Shared by daily_insight."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None
    return None


def split_two_days(
    price_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Bucket price rows by captured_at date; return (latest day, previous day)."""
    by_date: dict[date, list[dict[str, Any]]] = {}
    for r in price_rows:
        d = as_date(r.get("captured_at"))
        if d is not None:
            by_date.setdefault(d, []).append(r)
    days = sorted(by_date, reverse=True)
    latest = by_date[days[0]] if days else []
    previous = by_date[days[1]] if len(days) > 1 else []
    return latest, previous


def craft_alerts(
    methods: list[dict[str, Any]],
    latest_prices: list[dict[str, Any]],
    prev_prices: list[dict[str, Any]],
) -> list[CraftAlert]:
    """Flag methods whose ROI crossed the profit line (0%) between the two price days. Only
    methods priced on BOTH days are comparable; the rest are skipped."""
    li = price_index(latest_prices)
    ld = li.get("Divine Orb")
    pi = price_index(prev_prices)
    pd = pi.get("Divine Orb")

    alerts: list[CraftAlert] = []
    for m in methods:
        today = method_ev(m, li, ld)
        prev = method_ev(m, pi, pd)
        if not (today["priced"] and prev["priced"]):
            continue
        # crossing is decided on the EXACT (unrounded) ROI so a barely-profitable craft whose
        # display ROI rounds to 0 can't fabricate or hide a profit-line crossing.
        rt, rp = today["roi_pct_exact"], prev["roi_pct_exact"]
        if rt is None or rp is None:
            continue
        if rp <= 0 < rt:
            kind: Literal["into_profit", "out_of_profit"] = "into_profit"
        elif rt <= 0 < rp:
            kind = "out_of_profit"
        else:
            continue
        alerts.append(
            CraftAlert(
                name=m.get("name") or "?",
                kind=kind,
                from_roi=prev["roi_pct"],  # rounded, for display
                to_roi=today["roi_pct"],
                cost_div=today["expected_cost_div"],
                mechanics=m.get("mechanics") or [],
            )
        )
    # into-profit first, then by best new ROI
    alerts.sort(key=lambda a: (a.kind != "into_profit", -(a.to_roi or 0)))
    return alerts


def craft_alert_lines(alerts: list[CraftAlert]) -> list[str]:
    """Markdown bullet lines for the daily report (English, matching daily_insight)."""
    out: list[str] = []
    for a in alerts:
        if a.kind == "into_profit":
            out.append(
                f"- 🟢 **{a.name}** crossed INTO profit: ROI {a.from_roi}% → {a.to_roi}% "
                f"(~{a.cost_div} div cost now)"
            )
        else:
            out.append(
                f"- 🔴 **{a.name}** dropped OUT of profit: ROI {a.from_roi}% → {a.to_roi}%"
            )
    return out
