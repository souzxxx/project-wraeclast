"""Offline coverage for scripts/export_obsidian.py.

`render_report` is a pure Markdown builder — exercised directly across the
farms/crafts/snapshot branches. `run()` defers its `db.repo` + `api.craft_ev`
imports to call time and reads the vault dir from settings, so it drives fully
offline with those attributes monkeypatched and a tmp vault. No DB, no network.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from scripts.export_obsidian import render_report, run

TODAY = date(2026, 7, 5)


def _farm(name, profit, **kw):
    return {
        "name": name,
        "est_profit_per_hour": profit,
        "risk": kw.get("risk"),
        "investment_required": kw.get("investment_required"),
        "summary": kw.get("summary"),
    }


# ── render_report — frontmatter + header ────────────────────────────────────────────

def test_render_report_frontmatter_and_header():
    out = render_report("Runes of Aldur", [], None, price_count=42, today=TODAY)
    assert out.startswith("---\n")
    assert "date: 2026-07-05" in out
    assert "league: Runes of Aldur" in out
    assert "tags: [poe2, wraeclast, daily]" in out
    assert "# Wraeclast — Runes of Aldur — 2026-07-05" in out
    assert "42 priced items tracked today" in out
    # empty-state placeholders when nothing was collected
    assert "_No farm strategies curated yet._" in out
    assert "_No craft methods yet._" in out
    assert "_No character snapshot yet._" in out


def test_render_report_defaults_today_when_omitted():
    out = render_report("L", [], None, price_count=0)
    assert f"date: {date.today().isoformat()}" in out


# ── render_report — farms ───────────────────────────────────────────────────────────

def test_render_report_lists_farms_numbered_with_meta_and_summary():
    farms = [
        _farm("Abyss", 3.5, risk="low", investment_required="1 div", summary="scarab loop"),
        _farm("Breach", 2.0),  # missing meta -> n/a fallbacks, no summary line
    ]
    out = render_report("L", farms, None, price_count=1, today=TODAY)
    assert "1. **Abyss** — ~3.5 div/h (risk: low, invest: 1 div)" in out
    assert "   - scarab loop" in out
    # defensive fallbacks for absent risk/investment
    assert "2. **Breach** — ~2.0 div/h (risk: n/a, invest: n/a)" in out
    # a farm with no summary emits no bullet
    assert out.count("   - ") == 1


# ── render_report — crafts ──────────────────────────────────────────────────────────

def test_render_report_priced_craft_shows_roi():
    crafts = [
        {
            "name": "Quarterstaff EV",
            "mechanics": ["essence", "omen"],
            "priced": True,
            "roi_pct": 120,
            "expected_cost_div": 0.8,
            "success_prob": 0.5,
        }
    ]
    out = render_report("L", [], None, price_count=1, craft_methods=crafts, today=TODAY)
    assert "1. **Quarterstaff EV** [essence, omen] — ROI ~120%, ~0.8 div cost (success 0.5)" in out


def test_render_report_unpriced_craft_lists_missing_and_defaults_mechanics():
    crafts = [
        # not priced -> missing-prices branch; empty mechanics -> "craft" default
        {"name": "Chaos spam", "mechanics": [], "priced": False, "missing_prices": ["Omen X"]},
        # roi_pct None also routes to the unpriced branch even if priced flag is truthy-ish
        {"name": "Rune craft", "priced": True, "roi_pct": None, "missing_prices": []},
    ]
    out = render_report("L", [], None, price_count=1, craft_methods=crafts, today=TODAY)
    assert "1. **Chaos spam** [craft] — cost not yet priceable (Omen X)" in out
    assert "2. **Rune craft** [craft] — cost not yet priceable (n/a)" in out


# ── render_report — my build ────────────────────────────────────────────────────────

def test_render_report_snapshot_with_gems_mixed_shapes():
    snap = {
        "character_name": "Exile",
        "char_class": "Monk",
        "level": 92,
        # gems come as dicts from ninja and bare strings from PoB — both tolerated
        "gems": [{"name": "Ice Strike"}, "Tempest Bell", {"name": None}, {"noname": 1}],
    }
    out = render_report("L", [], snap, price_count=1, today=TODAY)
    assert "- **Exile** — Monk lvl 92" in out
    # None/nameless gems are filtered out of the joined line
    assert "- Gems: Ice Strike, Tempest Bell" in out


def test_render_report_snapshot_missing_fields_use_placeholders():
    out = render_report("L", [], {"gems": []}, price_count=1, today=TODAY)
    assert "- **?** — ? lvl ?" in out
    # empty gems -> no Gems line
    assert "Gems:" not in out


# ── run() — wiring, offline ──────────────────────────────────────────────────────────

def test_run_writes_dated_report_and_is_idempotent(tmp_path, monkeypatch):
    league = "Runes of Aldur"
    monkeypatch.setattr(
        "scripts.export_obsidian.get_settings",
        lambda: SimpleNamespace(poe2_league=league, obsidian_vault_dir=str(tmp_path / "vault")),
    )
    monkeypatch.setattr("db.repo.latest_prices", lambda lg, limit=1000: [{"name": "Chaos"}] * 3)
    monkeypatch.setattr(
        "db.repo.latest_farm_strategies", lambda lg, limit=10: [_farm("Abyss", 3.5, risk="low")]
    )
    monkeypatch.setattr("db.repo.latest_my_snapshot", lambda: {"character_name": "Exile"})
    monkeypatch.setattr("db.repo.latest_craft_methods", lambda lg: [{"name": "m"}])
    # rank_methods is imported inside run(); patch it on its home module
    monkeypatch.setattr("api.craft_ev.rank_methods", lambda methods, prices: methods)

    out_path = run()

    expected = tmp_path / "vault" / f"{date.today().isoformat()}-wraeclast-{league}.md"
    assert out_path == str(expected)
    assert expected.exists()
    text = expected.read_text(encoding="utf-8")
    assert f"league: {league}" in text
    assert "**Abyss**" in text
    assert "3 priced items tracked today" in text

    # re-running the same day overwrites in place (idempotent per day)
    again = run()
    assert again == str(expected)
    assert len(list((tmp_path / "vault").glob("*.md"))) == 1
