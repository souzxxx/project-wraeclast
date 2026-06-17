"""poe.ninja economy collector (skill §1).

Reality check (bootstrap 2026-06-17): poe.ninja's PoE2 site is an Astro SPA and the
classic `/api/data/*` paths 404 publicly. So base URL + endpoint paths are config-driven
(see .env.example) and there is an `explore` command that dumps raw JSON to confirm the
live shape before trusting the parser. The parser below handles the classic poe.ninja
response shapes (currencyoverview / itemoverview) defensively.

CLI:
    python -m collector.ninja_client explore   # GET + pretty-print raw JSON, no DB writes
    python -m collector.ninja_client run        # fetch, normalize, write price_snapshot
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from collector.config import Settings, get_settings
from collector.http import HttpClient
from db.models import ItemType, PriceSnapshot

CACHE_TTL = 6 * 3600  # economy is a daily-ish snapshot; don't hammer.


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_currency(payload: dict[str, Any], league: str) -> list[PriceSnapshot]:
    """Classic shape: {"lines": [{"currencyTypeName", "chaosEquivalent", ...}], ...}."""
    out: list[PriceSnapshot] = []
    for line in payload.get("lines", []) or []:
        name = line.get("currencyTypeName") or line.get("name")
        if not name:
            continue
        out.append(
            PriceSnapshot(
                league=league,
                item_type="currency",
                name=name,
                chaos_value=_num(line.get("chaosEquivalent") or line.get("chaosValue")),
                divine_value=_num(line.get("divineValue")),
                listing_count=_int(line.get("listingCount") or line.get("count")),
            )
        )
    return out


def normalize_items(
    payload: dict[str, Any], league: str, item_type: ItemType
) -> list[PriceSnapshot]:
    """Classic shape: {"lines": [{"name", "chaosValue", "divineValue", "listingCount"}]}."""
    out: list[PriceSnapshot] = []
    for line in payload.get("lines", []) or []:
        name = line.get("name")
        if not name:
            continue
        out.append(
            PriceSnapshot(
                league=league,
                item_type=item_type,
                name=name,
                chaos_value=_num(line.get("chaosValue")),
                divine_value=_num(line.get("divineValue")),
                listing_count=_int(line.get("listingCount") or line.get("count")),
            )
        )
    return out


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def fetch_economy(settings: Settings | None = None) -> list[PriceSnapshot]:
    """Fetch currency + a couple of item categories and normalize to PriceSnapshot rows."""
    settings = settings or get_settings()
    league = settings.poe2_league
    rows: list[PriceSnapshot] = []
    async with HttpClient(settings.reddit_user_agent, base_url=settings.ninja_base_url) as http:
        currency = await http.get_json(
            settings.ninja_economy_path,
            params={"league": league, "type": "Currency"},
            cache_ttl=CACHE_TTL,
        )
        rows += normalize_currency(currency, league)
        for cat, item_type in (("UniqueWeapon", "unique"), ("SkillGem", "gem")):
            try:
                data = await http.get_json(
                    settings.ninja_item_path,
                    params={"league": league, "type": cat},
                    cache_ttl=CACHE_TTL,
                )
            except Exception:  # noqa: BLE001 — one bad category shouldn't kill the run
                continue
            rows += normalize_items(data, league, item_type)  # type: ignore[arg-type]
    return rows


async def run() -> int:
    from db.repo import insert_price_snapshots

    rows = await fetch_economy()
    written = insert_price_snapshots(rows)
    print(f"price_snapshot: wrote {written} rows for league={get_settings().poe2_league}")
    return written


async def explore() -> None:
    """GET the configured economy endpoint and dump raw JSON — confirm shape before modeling."""
    settings = get_settings()
    async with HttpClient(settings.reddit_user_agent, base_url=settings.ninja_base_url) as http:
        data = await http.get_json(
            settings.ninja_economy_path,
            params={"league": settings.poe2_league, "type": "Currency"},
        )
    sample = data if not isinstance(data, dict) else {
        k: (v[:2] if isinstance(v, list) else v) for k, v in data.items()
    }
    print(json.dumps(sample, indent=2, ensure_ascii=False)[:4000])


def _main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "run"
    if cmd == "explore":
        asyncio.run(explore())
        return 0
    if cmd == "run":
        asyncio.run(run())
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
