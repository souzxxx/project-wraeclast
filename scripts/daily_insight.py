"""Daily "what changed today" insight (ROADMAP P1 — daily intelligence layer).

Compares the two most recent collection days and writes a concise, human-readable
Markdown note: which farms entered/left the top ranking, notable currency price moves,
and the community guides captured today. Sharp moves are flagged as anomalies.

The comparison logic is pure (no DB/network) so it is unit-tested offline; `run()` is the
thin DB-backed wrapper invoked by `collector.run_daily` after the Obsidian export.

CLI:  python -m scripts.daily_insight
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from collector.config import get_settings

# Thresholds. A move must clear BOTH the relative and absolute bars to count as "notable"
# (a 30% swing on a 0.1-chaos item is noise); the steeper bar additionally flags an anomaly.
PRICE_MOVE_MIN_PCT = 25.0
PRICE_MOVE_MIN_CHAOS = 2.0
PRICE_ANOMALY_PCT = 50.0
TOP_N = 5


# ── models ────────────────────────────────────────────────────────────────────────

class FarmMove(BaseModel):
    name: str
    from_rank: int
    to_rank: int


class PriceMove(BaseModel):
    name: str
    item_type: str
    from_chaos: float
    to_chaos: float
    pct: float


class NewSource(BaseModel):
    title: str
    url: str


class DailyInsight(BaseModel):
    league: str
    on_date: date
    has_baseline: bool = False
    current_top: list[str] = Field(default_factory=list)
    farms_entered_top: list[str] = Field(default_factory=list)
    farms_left_top: list[str] = Field(default_factory=list)
    farm_moves: list[FarmMove] = Field(default_factory=list)
    price_moves: list[PriceMove] = Field(default_factory=list)
    new_sources: list[NewSource] = Field(default_factory=list)
    anomalies: list[str] = Field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.farms_entered_top
            or self.farms_left_top
            or self.farm_moves
            or self.price_moves
            or self.new_sources
        )


# ── helpers (pure) ──────────────────────────────────────────────────────────────────

def _to_date(value: Any) -> date | None:
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


def _split_two_latest_days(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Bucket rows by their captured_at date; return (latest day, previous day)."""
    by_date: dict[date, list[dict[str, Any]]] = {}
    for r in rows:
        d = _to_date(r.get("captured_at"))
        if d is None:
            continue
        by_date.setdefault(d, []).append(r)
    days = sorted(by_date, reverse=True)
    latest = by_date[days[0]] if days else []
    previous = by_date[days[1]] if len(days) > 1 else []
    return latest, previous


def _dedupe_latest(
    rows: list[dict[str, Any]], key: tuple[str, ...]
) -> dict[tuple[Any, ...], dict[str, Any]]:
    """Keep one row per key: the newest captured_at (defensive vs intra-day reruns)."""
    out: dict[tuple[Any, ...], dict[str, Any]] = {}
    for r in rows:
        k = tuple(r.get(field) for field in key)
        prev = out.get(k)
        if prev is None or (_to_date(r.get("captured_at")) or date.min) >= (
            _to_date(prev.get("captured_at")) or date.min
        ):
            out[k] = r
    return out


def _ranked_names(farms: list[dict[str, Any]]) -> list[str]:
    ordered = sorted(
        farms, key=lambda f: (f.get("est_profit_per_hour") or 0.0), reverse=True
    )
    return [f["name"] for f in ordered if f.get("name")]


def farm_ranking_changes(
    latest_farms: list[dict[str, Any]], prev_farms: list[dict[str, Any]], top_n: int = TOP_N
) -> tuple[list[str], list[str], list[FarmMove], list[str]]:
    """Return (entered_top, left_top, moves_within_top, current_top_names)."""
    latest_top = _ranked_names(latest_farms)[:top_n]
    prev_top = _ranked_names(prev_farms)[:top_n]
    entered = [n for n in latest_top if n not in prev_top]
    left = [n for n in prev_top if n not in latest_top]
    moves: list[FarmMove] = []
    for n in latest_top:
        if n in prev_top:
            old_rank = prev_top.index(n) + 1
            new_rank = latest_top.index(n) + 1
            if old_rank != new_rank:
                moves.append(FarmMove(name=n, from_rank=old_rank, to_rank=new_rank))
    return entered, left, moves, latest_top


def notable_price_moves(
    latest_prices: list[dict[str, Any]], prev_prices: list[dict[str, Any]]
) -> list[PriceMove]:
    prev_by_key = _dedupe_latest(prev_prices, ("name", "item_type"))
    latest_by_key = _dedupe_latest(latest_prices, ("name", "item_type"))
    moves: list[PriceMove] = []
    for key, row in latest_by_key.items():
        now_val = row.get("chaos_value")
        old_row = prev_by_key.get(key)
        if old_row is None or now_val is None:
            continue
        old_val = old_row.get("chaos_value")
        if not old_val or old_val <= 0:
            continue
        pct = (now_val - old_val) / old_val * 100.0
        if abs(pct) >= PRICE_MOVE_MIN_PCT and abs(now_val - old_val) >= PRICE_MOVE_MIN_CHAOS:
            moves.append(
                PriceMove(
                    name=row.get("name") or "?",
                    item_type=row.get("item_type") or "currency",
                    from_chaos=round(float(old_val), 2),
                    to_chaos=round(float(now_val), 2),
                    pct=round(pct, 1),
                )
            )
    moves.sort(key=lambda m: abs(m.pct), reverse=True)
    return moves


def _new_sources(knowledge_rows: list[dict[str, Any]]) -> list[NewSource]:
    latest, _ = _split_two_latest_days(knowledge_rows)
    seen: set[str] = set()
    out: list[NewSource] = []
    for r in latest:
        url = r.get("source_url")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(NewSource(title=r.get("title") or url, url=url))
    return out


def compute_insight(
    league: str,
    farm_rows: list[dict[str, Any]],
    price_rows: list[dict[str, Any]],
    knowledge_rows: list[dict[str, Any]],
    today: date | None = None,
) -> DailyInsight:
    """Pure core: turn recent (multi-day) rows into a structured daily diff with anomalies."""
    today = today or date.today()
    latest_farms, prev_farms = _split_two_latest_days(farm_rows)
    latest_prices, prev_prices = _split_two_latest_days(price_rows)

    entered, left, moves, current_top = farm_ranking_changes(latest_farms, prev_farms)
    price_moves = notable_price_moves(latest_prices, prev_prices)
    new_sources = _new_sources(knowledge_rows)
    has_baseline = bool(prev_farms or prev_prices)

    anomalies: list[str] = []
    for name in entered:
        anomalies.append(f"Farm entered top {TOP_N}: {name}")
    for name in left:
        anomalies.append(f"Farm left top {TOP_N}: {name}")
    for m in price_moves:
        if abs(m.pct) >= PRICE_ANOMALY_PCT:
            direction = "jumped" if m.pct > 0 else "dropped"
            anomalies.append(
                f"{m.name} {direction} {m.pct:+.0f}% "
                f"({m.from_chaos} → {m.to_chaos} chaos)"
            )

    return DailyInsight(
        league=league,
        on_date=today,
        has_baseline=has_baseline,
        current_top=current_top,
        farms_entered_top=entered,
        farms_left_top=left,
        farm_moves=moves,
        price_moves=price_moves,
        new_sources=new_sources,
        anomalies=anomalies,
    )


def render_insight(insight: DailyInsight) -> str:
    """Render the insight as an Obsidian-friendly Markdown note."""
    d = insight.on_date.isoformat()
    lines = [
        "---",
        f"date: {d}",
        f"league: {insight.league}",
        "tags: [poe2, wraeclast, daily, insight]",
        "---",
        "",
        f"# What changed today — {insight.league} — {d}",
        "",
        "_Day-over-day diff vs the previous collection. Profit/hour figures are estimates._",
        "",
    ]

    if not insight.has_baseline:
        lines += [
            "_No previous day to compare against yet — this is the first baseline._",
            "",
        ]

    lines += ["## Anomalies", ""]
    if insight.anomalies:
        lines += [f"- ⚠️ {a}" for a in insight.anomalies]
    else:
        lines.append("_None flagged._")

    lines += ["", "## Farm ranking", ""]
    if insight.current_top:
        lines.append(f"Current top {len(insight.current_top)}: " + ", ".join(insight.current_top))
    if insight.farms_entered_top:
        lines.append("- ⬆️ Entered: " + ", ".join(insight.farms_entered_top))
    if insight.farms_left_top:
        lines.append("- ⬇️ Left: " + ", ".join(insight.farms_left_top))
    for m in insight.farm_moves:
        lines.append(f"- ↕️ **{m.name}**: #{m.from_rank} → #{m.to_rank}")
    if not (insight.farms_entered_top or insight.farms_left_top or insight.farm_moves):
        lines.append("_No ranking changes._")

    lines += ["", "## Notable price moves", ""]
    if insight.price_moves:
        for m in insight.price_moves:
            arrow = "📈" if m.pct > 0 else "📉"
            lines.append(
                f"- {arrow} **{m.name}** ({m.item_type}): "
                f"{m.from_chaos} → {m.to_chaos} chaos ({m.pct:+.1f}%)"
            )
    else:
        lines.append("_No moves past the threshold._")

    lines += ["", "## New community sources today", ""]
    if insight.new_sources:
        for s in insight.new_sources:
            lines.append(f"- [{s.title}]({s.url})")
    else:
        lines.append("_None captured today._")

    lines.append("")
    return "\n".join(lines)


def run() -> str:
    from db.repo import (
        farm_strategies_since,
        knowledge_chunks_since,
        price_snapshots_since,
    )

    settings = get_settings()
    league = settings.poe2_league
    insight = compute_insight(
        league=league,
        farm_rows=farm_strategies_since(league, days=3),
        price_rows=price_snapshots_since(league, days=3),
        knowledge_rows=knowledge_chunks_since(days=2),
    )
    out_dir = Path(settings.obsidian_vault_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date.today().isoformat()}-insight-{league}.md"
    out_path.write_text(render_insight(insight), encoding="utf-8")
    return str(out_path)


if __name__ == "__main__":
    print(f"wrote {run()}")
