"""Generate a daily Markdown report for an Obsidian vault (CLAUDE.md pillar 4).

Reads the latest state from Neon and writes a dated, navigable note. Idempotent per day:
re-running overwrites today's file.

CLI:  python -m scripts.export_obsidian
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from collector.config import get_settings


def render_report(
    league: str,
    farms: list[dict[str, Any]],
    my_snapshot: dict[str, Any] | None,
    price_count: int,
    today: date | None = None,
) -> str:
    today = today or date.today()
    lines = [
        "---",
        f"date: {today.isoformat()}",
        f"league: {league}",
        "tags: [poe2, wraeclast, daily]",
        "---",
        "",
        f"# Wraeclast — {league} — {today.isoformat()}",
        "",
        f"_{price_count} priced items tracked today. All profit/hour figures are estimates._",
        "",
        "## Top farms by profit/hour",
        "",
    ]
    if farms:
        for i, f in enumerate(farms, 1):
            lines.append(
                f"{i}. **{f['name']}** — ~{f.get('est_profit_per_hour')} chaos/h "
                f"(risk: {f.get('risk') or 'n/a'}, invest: {f.get('investment_required') or 'n/a'})"
            )
            if f.get("summary"):
                lines.append(f"   - {f['summary']}")
    else:
        lines.append("_No farm strategies curated yet._")

    lines += ["", "## My build", ""]
    if my_snapshot:
        lines.append(
            f"- **{my_snapshot.get('character_name') or '?'}** — "
            f"{my_snapshot.get('char_class') or '?'} lvl {my_snapshot.get('level') or '?'}"
        )
        gems = my_snapshot.get("gems") or []
        if gems:
            names = [g.get("name") if isinstance(g, dict) else str(g) for g in gems]
            lines.append(f"- Gems: {', '.join(n for n in names if n)}")
    else:
        lines.append("_No character snapshot yet._")

    lines.append("")
    return "\n".join(lines)


def run() -> str:
    from db.repo import latest_farm_strategies, latest_my_snapshot, latest_prices

    settings = get_settings()
    league = settings.poe2_league
    report = render_report(
        league=league,
        farms=latest_farm_strategies(league, limit=10),
        my_snapshot=latest_my_snapshot(),
        price_count=len(latest_prices(league, limit=1000)),
    )
    vault = Path(settings.obsidian_vault_dir)
    vault.mkdir(parents=True, exist_ok=True)
    out_path = vault / f"{date.today().isoformat()}-wraeclast-{league}.md"
    out_path.write_text(report, encoding="utf-8")
    return str(out_path)


if __name__ == "__main__":
    print(f"wrote {run()}")
