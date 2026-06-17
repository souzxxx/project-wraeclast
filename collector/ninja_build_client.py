"""Owner account data via poe.ninja Builds — PRIMARY source, no OAuth (skill §2b).

The ninja exposes the owner's character (gear/passives/skills, PoB code). Critical gotcha:
the character only appears via API once it reaches the league ladder's minimum level. If it
isn't there, we fall back to a manually supplied PoB code (reusing pob_parser) — the same
MySnapshot shape either way, so downstream (build diff) is source-agnostic.

CLI:
    python -m collector.ninja_build_client explore   # dump raw JSON for the configured char
    python -m collector.ninja_build_client run        # fetch + write my_snapshot
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from collector.config import Settings, get_settings
from collector.http import HttpClient
from collector.pob_parser import PoBParseError, parse_pob_code
from db.models import MySnapshot


class CharacterNotOnLadder(RuntimeError):
    """Raised when the tracked character can't be found via the ninja API (likely below the
    ladder minimum level). Caller should fall back to a PoB code."""


def _builds_endpoint(settings: Settings) -> str:
    # poe.ninja builds API is character-keyed; exact path confirmed via `explore`.
    base = settings.ninja_builds_base
    return f"{base}/character/{settings.ninja_account}/{settings.ninja_character}"


def normalize_build(payload: dict[str, Any], settings: Settings) -> MySnapshot:
    """Defensive map of a ninja build payload -> MySnapshot. Fields may be missing."""
    char = payload.get("character", payload)
    gear = char.get("items") or char.get("equipment") or {}
    gems = char.get("skills") or char.get("gems") or []
    passives = char.get("passives") or char.get("passiveTree") or {}
    return MySnapshot(
        character_name=char.get("name") or settings.ninja_character or None,
        char_class=char.get("class") or char.get("className"),
        level=_int(char.get("level")),
        gear=gear if isinstance(gear, dict) else {"items": gear},
        gems=gems if isinstance(gems, list) else [gems],
        passive_tree=passives if isinstance(passives, dict) else {"nodes": passives},
    )


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def fetch_my_build(settings: Settings | None = None) -> MySnapshot:
    settings = settings or get_settings()
    if not settings.ninja_character:
        raise CharacterNotOnLadder("NINJA_CHARACTER not configured")
    async with HttpClient(settings.reddit_user_agent) as http:
        try:
            data = await http.get_json(_builds_endpoint(settings), cache_ttl=3600)
        except Exception as exc:  # noqa: BLE001
            raise CharacterNotOnLadder(str(exc)) from exc
    if not data:
        raise CharacterNotOnLadder("empty response from ninja builds")
    return normalize_build(data, settings)


def from_pob_code(code: str) -> MySnapshot:
    """Phase-1 fallback: parse a manually supplied PoB code (or ninja 'Copy PoB code')."""
    return parse_pob_code(code)


async def run(pob_code: str | None = None) -> bool:
    from db.repo import insert_my_snapshot

    settings = get_settings()
    try:
        snap = await fetch_my_build(settings)
        source = "ninja"
    except CharacterNotOnLadder as exc:
        if not pob_code:
            print(
                f"character not on ladder ({exc}); supply a PoB code to record a snapshot. "
                "See skill §2b fallback.",
                file=sys.stderr,
            )
            return False
        snap = from_pob_code(pob_code)
        source = "pob_code"
    insert_my_snapshot(snap)
    print(f"my_snapshot: wrote 1 row (source={source}, level={snap.level})")
    return True


async def explore() -> None:
    settings = get_settings()
    async with HttpClient(settings.reddit_user_agent) as http:
        data = await http.get_json(_builds_endpoint(settings))
    print(json.dumps(data, indent=2, ensure_ascii=False)[:4000])


def _main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "run"
    if cmd == "explore":
        asyncio.run(explore())
        return 0
    if cmd == "run":
        code = None
        if len(argv) > 2 and argv[2] == "--pob" and len(argv) > 3:
            code = argv[3]
        try:
            ok = asyncio.run(run(code))
        except PoBParseError as exc:
            print(f"PoB parse failed: {exc}", file=sys.stderr)
            return 1
        return 0 if ok else 1
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
