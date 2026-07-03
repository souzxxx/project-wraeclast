"""Offline tests for the Obsidian daily-report exporter.

`render_report` is a pure Markdown builder (the owner-facing daily note); `run()` is the
thin DB-backed wrapper. Both are exercised without any network or Neon: the repo reads and
`rank_methods` are monkeypatched and the vault points at a tmp dir, mirroring the pattern the
rest of the suite uses for collector `run()` wrappers.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import scripts.export_obsidian as eo
from collector.config import Settings
from scripts.export_obsidian import render_report

FIXED_DAY = date(2026, 7, 3)


def test_render_report_full():
    farms = [
        {
            "name": "Abyss Farm",
            "est_profit_per_hour": 12.5,
            "risk": "medium",
            "investment_required": "low",
            "summary": "Run abyss depths for lich drops.",
        },
        # second farm exercises the .get() fallbacks (no risk/invest/summary).
        {"name": "Breach Farm", "est_profit_per_hour": 8.0},
    ]
    crafts = [
        {
            "name": "Quarterstaff Essence Slam",
            "mechanics": ["essence", "omen"],
            "priced": True,
            "roi_pct": 42.0,
            "expected_cost_div": 1.3,
            "success_prob": 0.6,
        },
        # unpriceable branch: no roi, lists the missing inputs.
        {
            "name": "Rune Gamble",
            "mechanics": [],
            "priced": False,
            "missing_prices": ["Mysterious Rune"],
        },
    ]
    my = {
        "character_name": "Exile",
        "char_class": "Monk",
        "level": 92,
        "gems": [{"name": "Ice Strike"}, "Tempest Bell", {"name": ""}],
    }
    out = render_report(
        league="Runes of Aldur",
        farms=farms,
        my_snapshot=my,
        price_count=451,
        craft_methods=crafts,
        today=FIXED_DAY,
    )
    # frontmatter carries the (config-driven) league + dated tag, never hardcoded.
    assert "date: 2026-07-03" in out
    assert "league: Runes of Aldur" in out
    assert "451 priced items tracked today" in out
    # farms: ranking + summary line + graceful n/a for the sparse second farm.
    assert "1. **Abyss Farm** — ~12.5 div/h (risk: medium, invest: low)" in out
    assert "   - Run abyss depths for lich drops." in out
    assert "2. **Breach Farm** — ~8.0 div/h (risk: n/a, invest: n/a)" in out
    # crafts: priced ROI line + unpriceable line naming the missing input.
    assert "1. **Quarterstaff Essence Slam** [essence, omen] — ROI ~42.0%" in out
    assert "2. **Rune Gamble** [craft] — cost not yet priceable (Mysterious Rune)" in out
    # my build: header + only the non-empty gem names survive the filter.
    assert "- **Exile** — Monk lvl 92" in out
    assert "- Gems: Ice Strike, Tempest Bell" in out


def test_render_report_empty_sections():
    out = render_report(
        league="Runes of Aldur",
        farms=[],
        my_snapshot=None,
        price_count=0,
        craft_methods=None,
        today=FIXED_DAY,
    )
    assert "_No farm strategies curated yet._" in out
    assert "_No craft methods yet._" in out
    assert "_No character snapshot yet._" in out


def test_render_report_snapshot_without_gems():
    # a snapshot present but gem-less must not emit a "Gems:" line.
    out = render_report(
        league="Runes of Aldur",
        farms=[],
        my_snapshot={"character_name": "Exile", "char_class": "Monk", "level": 5, "gems": []},
        price_count=1,
        craft_methods=None,
        today=FIXED_DAY,
    )
    assert "- **Exile** — Monk lvl 5" in out
    assert "Gems:" not in out


def test_render_report_defaults_to_today(monkeypatch):
    # today=None path resolves to date.today(); assert it lands in the frontmatter.
    monkeypatch.setattr(eo, "date", type("D", (), {"today": staticmethod(lambda: FIXED_DAY)}))
    out = render_report(
        league="Runes of Aldur", farms=[], my_snapshot=None, price_count=0
    )
    assert "date: 2026-07-03" in out


def test_run_writes_report(monkeypatch, tmp_path):
    vault = tmp_path / "vault" / "nested"  # exercises mkdir(parents=True)
    settings = Settings(poe2_league="Runes of Aldur", obsidian_vault_dir=str(vault))
    monkeypatch.setattr(eo, "get_settings", lambda: settings)

    seen: dict = {}

    def _prices(league, limit):
        seen["prices"] = (league, limit)
        return [{"name": "Divine Orb"}, {"name": "Chaos Orb"}]

    monkeypatch.setattr("db.repo.latest_prices", _prices)
    monkeypatch.setattr(
        "db.repo.latest_farm_strategies",
        lambda league, limit: [{"name": "Abyss Farm", "est_profit_per_hour": 9.0}],
    )
    monkeypatch.setattr(
        "db.repo.latest_my_snapshot",
        lambda: {"character_name": "Exile", "char_class": "Monk", "level": 92, "gems": []},
    )
    monkeypatch.setattr("db.repo.latest_craft_methods", lambda league: [{"id": 1}])
    # rank_methods is imported inside run(); patch it at its source module.
    ranked = [{"name": "M", "mechanics": [], "priced": False, "missing_prices": ["x"]}]
    monkeypatch.setattr("api.craft_ev.rank_methods", lambda methods, prices: ranked)

    out_path = Path(eo.run())

    assert out_path.exists()
    assert out_path.parent == vault
    assert out_path.name.endswith("-wraeclast-Runes of Aldur.md")
    body = out_path.read_text(encoding="utf-8")
    assert "league: Runes of Aldur" in body
    assert "2 priced items tracked today" in body  # price_count = len(prices)
    assert "**Abyss Farm**" in body
    assert "**Exile** — Monk lvl 92" in body
    # league threaded from config into the repo read; craft methods capped at 8 via slice.
    assert seen["prices"] == ("Runes of Aldur", 1000)
