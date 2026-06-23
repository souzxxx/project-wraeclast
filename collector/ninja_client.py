"""poe.ninja economy collector (skill §1).

Confirmed live (2026-06-17) against the real PoE2 API: the classic `/api/data/*` paths
404; PoE2 economy is the currency-exchange overview:

    GET /poe2/api/economy/exchange/{version}/overview?league=<DISPLAY NAME>&type=Currency

Notes baked in from exploration:
- The `league` param is the DISPLAY NAME with spaces ("Runes of Aldur"), NOT the URL slug.
- Response: {core:{primary,secondary,...}, lines:[...], items:[...]} where lines[i] and
  items[i] are parallel (same `id`). `primaryValue` is the price in the `core.primary`
  currency (divine for PoE2). Only type=Currency carries data today; uniques/gems live
  elsewhere (TODO).

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
from db.models import PriceSnapshot

CACHE_TTL = 6 * 3600  # economy is a daily-ish snapshot; don't hammer.


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_exchange(
    payload: dict[str, Any], league: str, item_type: str = "currency"
) -> list[PriceSnapshot]:
    """Parse a PoE2 exchange overview (any category) into PriceSnapshot rows tagged `item_type`.

    lines[i] holds the price (`primaryValue`, denominated in core.primary); items[i] holds
    the name. They are parallel by index and share an `id`. Defensive against length drift.
    """
    core = payload.get("core") or {}
    primary = (core.get("primary") or "").lower()
    lines = payload.get("lines") or []
    items = payload.get("items") or []
    by_id = {it.get("id"): it for it in items if isinstance(it, dict)}

    out: list[PriceSnapshot] = []
    seen: set[str] = set()
    for idx, line in enumerate(lines):
        if not isinstance(line, dict):
            continue
        item = by_id.get(line.get("id")) or (items[idx] if idx < len(items) else {})
        name = (item or {}).get("name")
        if not name or name in seen:  # one row per name per run (no intra-run duplicates)
            continue
        seen.add(name)
        value = _num(line.get("primaryValue"))
        # core.primary is the base unit; for PoE2 it's typically "divine".
        divine_value = value if primary == "divine" else None
        chaos_value = value if primary == "chaos" else None
        if divine_value is None and chaos_value is None:
            divine_value = value  # unknown base: still record under divine as the PoE2 base
        out.append(
            PriceSnapshot(
                league=league,
                item_type=item_type,
                name=name,
                chaos_value=chaos_value,
                divine_value=divine_value,
                listing_count=None,
            )
        )
    return out


async def _get_category(
    http: HttpClient, settings: Settings, ninja_type: str, cache_ttl: float
) -> dict[str, Any]:
    return await http.get_json(
        settings.ninja_economy_path,
        params={"league": settings.poe2_league, "type": ninja_type},
        cache_ttl=cache_ttl,
    )


async def fetch_economy(settings: Settings | None = None) -> list[PriceSnapshot]:
    """Fetch every configured craft-surface category (currency, essences, omens via Ritual,
    catalysts via Breach, liquid emotions via Delirium, runes, soul cores, abyss, expedition) and
    tag each with its item_type. One bad category is logged and skipped, not fatal."""
    settings = settings or get_settings()
    rows: list[PriceSnapshot] = []
    async with HttpClient(settings.user_agent, base_url=settings.ninja_base_url) as http:
        for ninja_type, item_type in settings.ninja_economy_category_list:
            try:
                payload = await _get_category(http, settings, ninja_type, CACHE_TTL)
            except Exception:  # noqa: BLE001 — one bad/renamed category shouldn't sink the rest
                continue
            rows += normalize_exchange(payload, settings.poe2_league, item_type)
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
    async with HttpClient(settings.user_agent, base_url=settings.ninja_base_url) as http:
        data = await _get_category(http, settings, settings.ninja_economy_type, 0)
    if isinstance(data, dict):
        sample = {k: (v[:2] if isinstance(v, list) else v) for k, v in data.items()}
    else:
        sample = data
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
