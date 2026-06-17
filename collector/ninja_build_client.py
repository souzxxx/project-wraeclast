"""Owner account data via poe.ninja public profile — PRIMARY source, no OAuth (skill §2b).

Confirmed live (2026-06-17):

    GET /poe2/api/profile/characters/<account>/<version>   ->  JSON list of characters

Each character: {accountName, name, level, updated, isCurrent, league, leagueUrl,
className, skills:[{name, icon, damage}]}. We pick the current character (or the one named
in NINJA_CHARACTER) and map it to MySnapshot. This public endpoint exposes skills but not
full gear/passive tree — that's the ninja limitation; PoB-code fallback fills the rest.

CLI:
    python -m collector.ninja_build_client explore   # dump the raw character list
    python -m collector.ninja_build_client run        # pick current char + write my_snapshot
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
    """Raised when no character can be read from the public profile (private, below ladder
    minimum level, or empty). Caller should fall back to a PoB code."""


def _profile_endpoint(settings: Settings, version: int = 0) -> str:
    return f"{settings.ninja_profile_path}/{settings.ninja_account}/{version}"


def pick_character(chars: list[dict[str, Any]], wanted: str = "") -> dict[str, Any]:
    """Choose the character to track: explicit name > isCurrent > first."""
    if wanted:
        for c in chars:
            if c.get("name") == wanted:
                return c
    for c in chars:
        if c.get("isCurrent"):
            return c
    return chars[0]


def normalize_profile_character(char: dict[str, Any]) -> MySnapshot:
    """Map one ninja profile character to MySnapshot. Skills -> gems; gear/passives unavailable."""
    skills = char.get("skills") or []
    gems = [
        {"name": s.get("name"), "icon": s.get("icon"), "damage": s.get("damage")}
        for s in skills
        if isinstance(s, dict) and s.get("name")
    ]
    return MySnapshot(
        character_name=char.get("name"),
        char_class=char.get("className"),
        level=_int(char.get("level")),
        gear={},  # not exposed by the public profile endpoint
        gems=gems,
        passive_tree={"source": "ninja_profile", "league": char.get("league")},
    )


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def fetch_my_build(settings: Settings | None = None) -> MySnapshot:
    settings = settings or get_settings()
    if not settings.ninja_account:
        raise CharacterNotOnLadder("NINJA_ACCOUNT not configured")
    async with HttpClient(settings.user_agent, base_url=settings.ninja_base_url) as http:
        try:
            data = await http.get_json(_profile_endpoint(settings), cache_ttl=3600)
        except Exception as exc:  # noqa: BLE001
            raise CharacterNotOnLadder(str(exc)) from exc
    if not isinstance(data, list) or not data:
        raise CharacterNotOnLadder("no characters in public profile")
    return normalize_profile_character(pick_character(data, settings.ninja_character))


def from_pob_code(code: str) -> MySnapshot:
    """Phase-1 fallback: parse a manually supplied PoB code (or ninja 'Copy PoB code')."""
    return parse_pob_code(code)


async def run(pob_code: str | None = None) -> bool:
    from db.repo import insert_my_snapshot

    settings = get_settings()
    try:
        snap = await fetch_my_build(settings)
        source = "ninja_profile"
    except CharacterNotOnLadder as exc:
        if not pob_code:
            print(
                f"could not read character ({exc}); supply a PoB code to record a snapshot.",
                file=sys.stderr,
            )
            return False
        snap = from_pob_code(pob_code)
        source = "pob_code"
    insert_my_snapshot(snap)
    print(
        f"my_snapshot: wrote 1 row (source={source}, "
        f"char={snap.character_name}, class={snap.char_class}, level={snap.level}, "
        f"gems={len(snap.gems)})"
    )
    return True


async def explore() -> None:
    settings = get_settings()
    async with HttpClient(settings.user_agent, base_url=settings.ninja_base_url) as http:
        data = await http.get_json(_profile_endpoint(settings))
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
